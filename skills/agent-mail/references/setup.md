# 安装、授权和转发

1. 到 [Agent Mail](https://agent.qq.com/) 注册并创建自己的邮箱。
2. 安装 Node.js / npm，然后运行 `npm install -g @tencent-qqmail/agently-cli`。
3. 安装官方 Skill：`npx skills add https://agent.qq.com --skill agently-mail -g -y`。当前 `skills` 版本要求 `--skill` 后有名称；若版本不同，先查看 `npx skills add --help`。
4. 运行 `agently-cli auth login`；在浏览器打开 CLI 输出的原始授权链接，完成登录和授权。不要将 token、密码或链接写入仓库。CLI 文档说明令牌保存在本机系统密钥链。失败或超时不要自动重试。
5. 执行 `agently-cli +me`，确认返回的邮箱地址是自己创建的邮箱。检查授权范围是否符合个人需求。
6. 从校园邮箱**手动转发一封测试邮件**到该 Agent Mail 地址，再使用 `list` 和 `read` 检查是否收到、原始发件人、时间、正文和附件是否符合预期。
7. 如果学校策略允许，用户可在 Outlook 设置转发规则，将选定类型邮件自动转发至自己的 Agent Mail；规则建立后必须再做实际投递测试。外部自动转发可能被学校禁止或隔离，失败时先检查租户策略，不绕过学校限制。

服务器部署时，需要在实际运行 CLI 的主机按官方支持方式登录并保护系统密钥链；移动端和无头服务器的凭证存储、长时间运行和 `message +watch` 的稳定性需要分别验证。CLI 的 `--help` 可查看当前选项；以官方文档为准。
