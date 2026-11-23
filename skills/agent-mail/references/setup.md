# Bridge Agent Mail 配置

1. 注册自己的 Agent Mail 地址。
2. 在运行 Bridge 的宿主安装 Node.js 与 `@tencent-qqmail/agently-cli`。
3. 运行 `agently-cli auth login`，按官方流程在浏览器完成授权；token 由 CLI 保存，不写入仓库或环境日志。
4. 用 `agently-cli +me` 验证邮箱地址和授权范围。
5. 从校园邮箱手动转发一封测试邮件到 Agent Mail，再运行 Bridge 的 `list`、`read` 验证投递。学校允许时再配置自动转发，并再次做真实投递测试。
6. 在 Agent Mail 管理页设置发信昵称和身份简介。昵称可以写 Bridge；“接入工具”字段反映授权客户端，不等于 Bridge 的部署身份。

Bridge 不访问原始 Outlook。它只读取转发到 Agent Mail 的邮件；转发规则受学校租户策略约束，不能绕过。服务器、容器和移动端需要分别验证 OAuth 凭据存储和长时间运行能力。
