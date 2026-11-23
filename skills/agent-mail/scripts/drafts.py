"""Versioned local Bridge drafts; no outbound network calls."""
import json
import os
import sqlite3
import uuid
from pathlib import Path
from contextlib import closing


def connect():
    path = Path(os.environ.get('BRIDGE_MAIL_DB', str(Path.home() / '.bridge' / 'mail.sqlite3'))).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    db = sqlite3.connect(str(path))
    db.execute('CREATE TABLE IF NOT EXISTS drafts (id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(id, version))')
    return db


def create(payload):
    validate(payload)
    draft_id = str(uuid.uuid4())
    with closing(connect()) as db, db:
        db.execute('INSERT INTO drafts VALUES (?,?,?)', (draft_id, 1, json.dumps(payload, ensure_ascii=False)))
    return {'id': draft_id, 'version': 1, 'payload': payload, 'storage': 'bridge_local'}


def get(draft_id):
    with closing(connect()) as db:
        row = db.execute('SELECT version,payload FROM drafts WHERE id=? ORDER BY version DESC LIMIT 1', (draft_id,)).fetchone()
    if row is None:
        raise ValueError('draft not found')
    return {'id': draft_id, 'version': row[0], 'payload': json.loads(row[1]), 'storage': 'bridge_local'}


def update(draft_id, version, changes):
    if not isinstance(changes, dict):
        raise ValueError('changes must be an object')
    with closing(connect()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT version,payload FROM drafts WHERE id=? ORDER BY version DESC LIMIT 1', (draft_id,)).fetchone()
        if row is None:
            raise ValueError('draft not found')
        if row[0] != version:
            raise ValueError('draft version conflict')
        payload = json.loads(row[1])
        payload.update(changes)
        validate(payload)
        db.execute('INSERT INTO drafts VALUES (?,?,?)', (draft_id, version + 1, json.dumps(payload, ensure_ascii=False)))
    return {'id': draft_id, 'version': version + 1, 'payload': payload, 'storage': 'bridge_local'}


def validate(payload):
    if not isinstance(payload, dict) or set(payload) - {'to', 'cc', 'bcc', 'subject', 'body', 'signature', 'attachment'}:
        raise ValueError('invalid draft fields')
    for field in ('to', 'cc', 'bcc', 'attachment'):
        if field in payload and (not isinstance(payload[field], list) or not all(isinstance(x, str) and x.strip() for x in payload[field])):
            raise ValueError(field + ' must be a list of addresses')
    for field in ('subject', 'body', 'signature'):
        if field in payload and not isinstance(payload[field], str):
            raise ValueError(field + ' must be a string')
