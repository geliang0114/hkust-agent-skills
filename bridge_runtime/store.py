"""Persistent primitives for Bridge. No model, worker, or notification transport."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path), timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, source TEXT NOT NULL, source_id TEXT NOT NULL, kind TEXT NOT NULL, occurred_at TEXT, received_at TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(source, source_id));
            CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, source_event_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reminders (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, due_at TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        self.db.commit()

    def event(self, source, source_id, kind, payload, occurred_at=None):
        eid = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?)', (eid, source, source_id, kind, occurred_at, now(), json.dumps(payload, ensure_ascii=False)))
        row = self.db.execute('SELECT id FROM events WHERE source=? AND source_id=?', (source, source_id)).fetchone()
        return {'event_id': row['id'], 'created': row['id'] == eid}

    def task(self, title, source_event_id=None):
        tid, timestamp = str(uuid.uuid4()), now()
        with self.db:
            self.db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?)', (tid, title, 'open', source_event_id, timestamp, timestamp))
        return {'task_id': tid, 'status': 'open'}

    def reminder(self, task_id, due_at, message):
        if not self.db.execute('SELECT 1 FROM tasks WHERE id=?', (task_id,)).fetchone():
            raise ValueError('unknown task')
        parsed = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('due_at requires an explicit timezone')
        rid = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO reminders VALUES (?,?,?,?,?,?)', (rid, task_id, parsed.astimezone(timezone.utc).isoformat(), 'pending', message, now()))
        return {'reminder_id': rid, 'status': 'pending'}

    def due(self, at=None):
        at = at or now()
        parsed = datetime.fromisoformat(at.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('at requires an explicit timezone')
        at = parsed.astimezone(timezone.utc).isoformat()
        return [dict(r) for r in self.db.execute("SELECT * FROM reminders WHERE status='pending' AND due_at <= ? ORDER BY due_at", (at,))]

    def close(self):
        self.db.close()
