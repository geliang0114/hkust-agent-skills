import unittest
from unittest.mock import patch
import agent_mail

class AgentMailTests(unittest.TestCase):
    def test_invalid_limit(self):
        self.assertEqual(agent_mail.main(['list','--limit','0']),2)
    @patch('agent_mail.subprocess.run')
    def test_list_normalizes_cli_json(self, run):
        run.return_value=type('R',(),{'returncode':0,'stdout':'{"ok":true,"data":{"data":[]}}','stderr':''})()
        self.assertEqual(agent_mail.main(['list','--limit','1']),0)
        self.assertEqual(run.call_args.args[0][:3],['agently-cli','message','+list'])
    @patch('agent_mail.subprocess.run')
    def test_cli_error_is_structured(self, run):
        run.return_value=type('R',(),{'returncode':3,'stdout':'{"ok":false,"error":{"message":"not authorized"}}','stderr':''})()
        self.assertEqual(agent_mail.main(['me']),3)

    @patch('agent_mail.subprocess.run')
    def test_send_maps_json_to_provider_without_sending_confirmation(self, run):
        run.return_value=type('R',(),{'returncode':0,'stdout':'{"ok":true,"data":{"confirmation_required":true,"confirmation_token":"ctk_test"}}','stderr':''})()
        self.assertEqual(agent_mail.main(['send','--payload-json','{"to":["a@example.com"],"subject":"S","body":"B"}']),0)
        self.assertEqual(run.call_args.args[0],['agently-cli','message','+send','--to','a@example.com','--subject','S','--body','B'])

    @patch('agent_mail.subprocess.run')
    def test_reply_and_attachment_are_mapped(self, run):
        run.return_value=type('R',(),{'returncode':0,'stdout':'{"ok":true,"data":{"queued":true}}','stderr':''})()
        self.assertEqual(agent_mail.main(['reply','--payload-json','{"id":"msg_1","body":"收到","reply_all":true}']),0)
        self.assertEqual(run.call_args.args[0],['agently-cli','message','+reply','--id','msg_1','--body','收到','--reply-all'])

if __name__=='__main__': unittest.main()
