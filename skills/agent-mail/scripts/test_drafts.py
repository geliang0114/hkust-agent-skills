import os, unittest, uuid
import drafts

class DraftTests(unittest.TestCase):
    def test_version_conflict_preserves_previous_version(self):
        os.environ['BRIDGE_MAIL_DB']='/tmp/bridge-draft-test-' + str(uuid.uuid4()) + '.sqlite3'
        item = drafts.create({'to':['test@example.com'],'subject':'A','body':'hello','signature':'Bridge'})
        newer = drafts.update(item['id'], 1, {'body':'changed'})
        self.assertEqual(newer['version'],2)
        with self.assertRaises(ValueError): drafts.update(item['id'],1,{'body':'stale'})
        self.assertEqual(drafts.get(item['id'])['payload']['body'],'changed')
