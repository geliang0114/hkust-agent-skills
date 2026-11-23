# HKUST Portal Calendar API

## Authentication

- Portal: `https://myportal.hkust-gz.edu.cn/`
- SSO host: `https://sso.hkust-gz.edu.cn/`
- Environment variables: `HKUST_USERNAME`, `HKUST_PASSWORD`
- Cookie path: `HKUST_PORTAL_SESSION` or `~/.sensebridge/hkust_portal_cookies.json`
- The cookie file contains only session cookies and is written with mode `0600`.

## Read-only endpoints

- `GET /calendar/mgr/api/category/list.rst` discovers category IDs.
- `GET /calendar/mgr/api/hkust/calendarList.rst` reads events.
- Both endpoints return JSONP and require the authenticated portal session.

The calendar request uses UTC ISO 8601 timestamps derived from `Asia/Shanghai` dates. Category IDs observed in the portal frontend include `-2` for course events, `-3` for meetings, and `-4` for other location-based events. The connector preserves the raw event and category ID.

## Output

```json
{
  "ok": true,
  "tool": "hkust_portal.list_events",
  "data": {
    "events": [
      {
        "source": "my_course",
        "title": "课程名称",
        "start": "2026-11-24 09:00:00",
        "end": "2026-11-24 10:30:00",
        "location": "E1-101",
        "category_id": -2,
        "raw": {}
      }
    ]
  }
}
```
