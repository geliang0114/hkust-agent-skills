import contextlib
import io
import json
import unittest
from unittest.mock import patch

import outlook_graph as graph


class GraphAdapterTests(unittest.TestCase):
    def test_write_modes(self):
        with patch.dict('os.environ', {'AGENT_PERMISSION_MODE':'approval'}):
            with self.assertRaises(graph.GraphError): graph.require_write_permission('mail.draft.write')
            graph.require_write_permission('mail.draft.write', confirm=True)
        with patch.dict('os.environ', {'AGENT_PERMISSION_MODE':'auto'}):
            with self.assertRaises(graph.GraphError): graph.require_write_permission('mail.draft.write', confirm=True)
        with patch.dict('os.environ', {'AGENT_PERMISSION_MODE':'bypass'}):
            graph.require_write_permission('mail.draft.write')

    def test_signature_is_optional_and_escaped(self):
        with patch.dict('os.environ', {'GRAPH_SIGNATURE': 'Bridge <AI>'}):
            self.assertIn('Bridge &lt;AI&gt;', graph.body_html('hello'))
            self.assertNotIn('Bridge', graph.body_html('hello', add_signature=False))

    def test_fingerprint_changes_with_recipients_or_body(self):
        a = {'id':'1','isDraft':True,'subject':'hello','body':{'content':'first'},'toRecipients':[]}
        b = {**a, 'body':{'content':'changed'}}
        self.assertNotEqual(graph.draft_fingerprint(a), graph.draft_fingerprint(b))

    def test_send_rejects_changed_draft(self):
        draft={'id':'1','isDraft':True,'subject':'changed','body':{'content':'x'}}
        with patch.object(graph, 'get_draft', return_value=draft), patch.object(graph, 'request') as req, contextlib.redirect_stdout(io.StringIO()):
            code=graph.main(['send','1','--confirm','--review-hash','old'])
        self.assertEqual(code, 1)
        req.assert_not_called()

    def test_send_requires_confirmation_before_network(self):
        with patch.object(graph, 'request') as req, contextlib.redirect_stdout(io.StringIO()):
            code=graph.main(['send','1','--review-hash','a'])
        self.assertEqual(code,1)
        req.assert_not_called()

    def test_send_reports_acceptance_not_delivery(self):
        draft={'id':'a/b','isDraft':True,'subject':'x','body':{'content':'x'}}
        out=io.StringIO()
        with patch.object(graph,'get_draft',return_value=draft), patch.object(graph,'request',return_value={}) as req, contextlib.redirect_stdout(out):
            code=graph.main(['send','a/b','--confirm','--review-hash',graph.draft_fingerprint(draft)])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(out.getvalue())['data']['status'],'accepted_by_graph')
        self.assertEqual(req.call_args.args[1],'/me/messages/a%2Fb/send')

if __name__ == '__main__': unittest.main()
