# Bridge runtime foundation

`store.Store(path)` provides persistent event deduplication, basic task records, and pending reminder storage. `event(source, source_id, kind, payload, occurred_at=None)` returns an event ID and whether it was created; `task(title, source_event_id=None)` creates a task; `reminder(task_id, due_at, message)` records a time-zone-aware reminder; `due(at=None)` retrieves pending reminders. Call `close()` when finished.

This is a storage library, not a running agent: it has no scheduler, delivery mechanism, synchronization worker, language model, review agent, execution gateway, or memory consolidation. Event payloads may contain personal information; operators must secure the database and limit stored content. The command adapter cannot enforce isolation if a caller has direct provider credentials.
