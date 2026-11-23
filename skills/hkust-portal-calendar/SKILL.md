---
name: hkust-portal-calendar
description: Read HKUST(GZ) MyPortal calendar, Outlook, and course events through the campus SSO session when an agent needs the user's campus schedule.
---

# HKUST(GZ) 门户日程

这是只读连接器。它通过学校 SSO 登录 `myportal.hkust-gz.edu.cn`，把门户“我的日程”中的课程、Outlook 和其他事件转换成标准 JSON。首次运行从 `HKUST_USERNAME` 和 `HKUST_PASSWORD` 读取登录凭据；成功后只复用本地 0600 权限的 cookie 文件，不保存密码。

```bash
export HKUST_USERNAME='你的校园用户名'
export HKUST_PASSWORD='由宿主安全注入，不要写入 prompt 或日志'
python3 skills/hkust-portal-calendar/scripts/hkust_portal_calendar.py list --start 2026-11-24 --end 2026-11-30
```

只调用 `list` 查询；不要通过该 Skill 创建、修改或删除门户日程。会话失效时，在安全环境中重新提供环境变量并使用 `--relogin`，保留原文件以便恢复。

接口与字段说明见 [references/api.md](references/api.md)。
