---
name: hkust-campus-context
description: Read HKUST(GZ) campus activities, announcements, tasks, library loans, unread-mail count, and portal service links when an agent needs campus context.
---

# HKUST(GZ) 校园上下文

这是只读校园上下文连接器，供 Personal Agent 按需加载。它组合两类数据：

- 学校公开活动网站：无需账号，可查询活动列表和详情。
- MyPortal：通过校园 SSO 会话读取公告、新闻、待办/已办、邮件未读数量、图书借阅和校园服务目录。

活动列表和详情：

```bash
python3 scripts/hkust_campus_context.py activities --page 1 --page-size 20 --keyword AI
python3 scripts/hkust_campus_context.py activity 10006
```

MyPortal 查询：

```bash
export HKUST_USERNAME='你的校园用户名'
export HKUST_PASSWORD='由宿主安全注入，不要写入 prompt 或日志'
python3 scripts/hkust_campus_context.py announcements --kind notice
python3 scripts/hkust_campus_context.py tasks
python3 scripts/hkust_campus_context.py unread-mail
python3 scripts/hkust_campus_context.py loans
python3 scripts/hkust_campus_context.py apps --favorites
```

首次登录或会话失效时加 `--relogin`。如果学校触发 2FA，脚本会在交互式终端等待用户输入 6 位验证码；验证码只在内存中使用。

所有命令只读，不报名活动、不提交审批、不修改订阅、不发送邮件、不创建或修改日程。活动 `--keyword` 只筛选当前返回页，不能当作全站搜索。活动详情中的地点可能同时包含线下地点和线上会议链接，提交给导航前要先向用户确认目标。

接口字段、输出 schema 和已验证边界见 [references/api.md](references/api.md)。
