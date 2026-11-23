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

## 交互式 2FA

如果账号密码正确但学校要求二次验证，连接器会调用 2FA 接口发送一次性验证码，并在终端显示：

```text
请输入发送到 xxx 的 6 位验证码：
```

用户把收到的 6 位数字输入终端后，脚本会提交验证码、跟随学校返回的 `jumpTo` 地址并保存门户会话。验证码只在内存中使用，不会写入 cookie 文件、日志、命令行参数或 Skill 配置。运行环境必须保留交互式 stdin；在手机 App 或远程 agent 中，应通过安全的用户输入回调把验证码传给脚本，而不是把验证码放进 prompt 或环境变量。

非交互式调用会在无法读取验证码时失败，并返回结构化错误。验证码过期或格式错误时，可重新执行 `list --relogin`。
