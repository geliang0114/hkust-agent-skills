import unittest
from bridge_runtime.store import Store

class StoreTests(unittest.TestCase):
    def test_deduplication_and_due_reminder(self):
        store = Store(':memory:')
        one = store.event('mail', 'm1', 'mail.received', {'subject':'event'})
        two = store.event('mail', 'm1', 'mail.received', {'subject':'event'})
        self.assertTrue(one['created'])
        self.assertFalse(two['created'])
        self.assertEqual(one['event_id'], two['event_id'])
        task = store.task('Activity', one['event_id'])
        store.reminder(task['task_id'], '2026-11-24T10:00:00+08:00', 'Depart')
        self.assertEqual(len(store.due('2026-11-24T03:00:00+00:00')), 1)
        with self.assertRaises(ValueError): store.reminder(task['task_id'], '2026-11-24T10:00:00', 'bad')
        store.close()
