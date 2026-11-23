# Microsoft Graph Outlook API

适配器使用 Graph v1.0：

- `GET /me/mailFolders/{folder}/messages`：列表
- `GET /me/messages?$search=...`：搜索
- `GET /me/messages/{id}`：读取正文
- `POST /me/messages`：创建草稿
- `PATCH /me/messages/{id}`：修改草稿
- `POST /me/messages/{id}/send`：发送

建议为个人 agent 使用 delegated permissions：`User.Read`, `Mail.Read`, `Mail.ReadWrite`, `Mail.Send`, `offline_access`。学校租户可能要求管理员批准；获得批准后仍需用户完成 OAuth 登录。Graph Explorer 可用于手工验证同一 Graph 请求，但不会为本地脚本提供可长期复用的 token。

`graph_login.py` 使用设备码流程；需要组织允许的 Entra 公共客户端应用 ID、启用公共客户端流程、用户授权以及可能的管理员同意。登录成功后缓存 access/refresh token 并支持续期；本功能尚未在真实租户端到端验证。文件在类 Unix 上设置 0600；Windows 使用目录 ACL，部署者应限制当前用户访问。token 及续期备份均不可提交。

用户可选择 approval（每次写入审批）、auto（Review Agent 审批，尚未接线，fail closed）或 bypass（跳过审批）。权限模式与审批必须由可信宿主控制；CLI 参数本身不构成安全边界。删除邮件、移动邮件、改规则和自动回复不在当前适配器范围内。
