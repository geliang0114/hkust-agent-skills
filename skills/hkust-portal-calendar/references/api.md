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

## 2FA 接口（登录流程内部使用）

当 SSO 将浏览器重定向到 `https://2fa.hkust-gz.edu.cn/#/2fa/home?processId=<id>` 时，连接器在同一个 HTTP 会话中调用：

- `GET /api/2fa-portal/contact/get?processId=<id>`：读取可用验证方式及脱敏联系方式。
- `POST /api/2fa-portal/verification-code/send`：发送验证码，JSON 包含 `processId`、`verificationType` 和对应的 `personalEmail` 或 `phoneNumber`。
- `POST /api/2fa-portal/verification-code/verify`：校验 JSON 中的 `processId` 和 `verificationCode`。
- 校验成功后跟随响应中的 `jumpTo` 地址回到 MyPortal。

这些接口带有当前流程生成的 `User-Session-ID` 请求头。连接器不会记录验证码或完整联系方式；学校接口字段若有调整，应先更新模拟测试再修改解析逻辑。
