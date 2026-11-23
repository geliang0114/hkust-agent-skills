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

if __name__=='__main__': unittest.main()
