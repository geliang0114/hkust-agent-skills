# Agent Mail 接口参考

在本 Skill 目录执行脚本。每次输出单个 JSON envelope：`ok`、`tool`、`data` 或 `error`； provider 返回的 `confirmation_required`、`confirmation_token`、`queued` 保留在 `data` 内。HTTP/CLI 错误不代表发送成功；超时可能为结果未知。

```bash
python3 scripts/agent_mail.py account
python3 scripts/agent_mail.py list --limit 10
python3 scripts/agent_mail.py search --query 活动 --limit 10
python3 scripts/agent_mail.py read --id 'msg_...'
python3 scripts/agent_mail.py draft-create --payload-json '{"to":["a@example.com"],"subject":"主题","body":"正文","signature":"Bridge"}'
python3 scripts/agent_mail.py draft-get --id '草稿ID'
python3 scripts/agent_mail.py draft-update --id '草稿ID' --version 1 --changes-json '{"body":"更新后的正文"}'
python3 scripts/agent_mail.py send-prepare --draft-id '草稿ID'
```

`send-prepare` 把正文和可选署名组合成最终 `payload`，并返回草稿版本、SHA-256 和 `prepared_not_sent`；这只是准备数据，不进行审批或发送。以其 `payload` 作为以下 `send` 的输入；审批后若草稿变动，重新准备并重新确认。哈希仅供比对，不提供独立的安全隔离。

以下命令支持 `--payload-json`，也可从标准输入读取 JSON，建议对真实邮件使用标准输入，避免将正文直接写入 shell 命令历史。

| 命令 | JSON 字段 |
| --- | --- |
| `send` | 必需 `to`（地址数组）、`subject`、`body`；可选 `cc`、`bcc`、`attachment`（数组） |
| `reply` | 必需 `id`、`body`；可选 `cc`、`bcc`、`attachment`、`reply_all`（布尔） |
| `forward` | 必需 `id`、`to`；可选 `cc`、`bcc`、`body`、`attachment`、`include_attachments`（布尔） |
| `trash` | 必需 `id`；移到服务端回收站 |
| `attachment-download` | 必需 `msg`、`att`；可选 `output`（相对于当前工作目录） |

例如先以 JSON 标准输入调用 `python3 scripts/agent_mail.py send`。如 provider 返回 `confirmation_required`，展示完整收件人、抄送、主题、正文和附件给用户；用户同意后，把返回的 `confirmation_token` 加入**未改变的原 JSON** 再调用同一命令。回复、转发和移入回收站使用相同机制。不要在日志中保存或泄露确认令牌。具体附件路径遵循 CLI 要求，为当前工作目录下的相对路径。

授权与提供方限制以腾讯官方 CLI 当前行为为准；脚本没有实现服务端草稿、永久删除、Bridge 三档权限网关或在服务端保证幂等。真实部署时应限制谁能调用 CLI 和使用其凭据。
