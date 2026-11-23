# Microsoft Graph Outlook API

适配器使用 Graph v1.0：

- `GET /me/mailFolders/{folder}/messages`：列表
- `GET /me/messages?$search=...`：搜索
- `GET /me/messages/{id}`：读取正文
- `POST /me/messages`：创建草稿
- `PATCH /me/messages/{id}`：修改草稿
- `POST /me/messages/{id}/send`：发送

建议为个人 agent 使用 delegated permissions：`User.Read`, `Mail.Read`, `Mail.ReadWrite`, `Mail.Send`, `offline_access`。学校租户可能要求管理员批准；获得批准后仍需用户完成 OAuth 登录。Graph Explorer 可用于手工验证同一 Graph 请求，但不会为本地脚本提供可长期复用的 token。

当前适配器不实现 OAuth 登录页面和 refresh token 交换；宿主 agent 应通过安全 OAuth 客户端获得 access token，再注入 `GRAPH_ACCESS_TOKEN` 或安全 token 文件。token 文件权限应为 0600，且加入忽略规则。

外部副作用分级：读取、搜索和草稿修改由 agent 按用户请求执行；发送邮件必须有 `--confirm`，并且确认内容应覆盖最终收件人、抄送、主题和正文。删除邮件、移动邮件、改规则和自动回复不在当前适配器范围内。
