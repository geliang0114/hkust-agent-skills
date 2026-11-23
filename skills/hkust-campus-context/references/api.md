# 校园上下文接口说明

所有命令输出统一为：

```json
{"ok": true, "tool": "hkust_campus.*", "data": {}, "source": "...", "fetched_at": "..."}
```

失败输出为 `ok=false` 和结构化 `error.type`、`error.message`。HTTP 200 不代表业务成功，连接器会检查活动 API 的 `code` 和门户 JSONP 的 `result`。

## 公开活动

- `GET https://events.hkust-gz.edu.cn/api/event-public/public/event/page`
  - `locale=en`
  - `campusCode=gz`
  - `pagination={"current":1,"pageSize":20}`；脚本的 `--page 1` 对应 API 的 `current=1`。
- `GET /public/event/get?id=<id>&locale=en`
- 活动列表返回标题、日期、地点、活动形式、受众、状态和详情链接。
- 活动详情另外返回起止时间、摘要、演讲者和报名要求；本 Skill 不提交报名。
- 当前学校接口中 `locale=en` 可用；`en-US` 曾返回记录不存在。活动数据可能含 HTML，脚本会清理文本。

## MyPortal

门户查询使用同一个 SSO 会话和已有的 `HKUST_PORTAL_SESSION` 配置；未设置时沿用默认 cookie 文件。登录后会调用 `loginInfo.jsp` 校验会话账号与 `HKUST_USERNAME` 一致。

- 公告/新闻：`/sopplus/_web/customized/getHkustArticleList.jsp`，`--kind notice|news|activity`
- 待办/已办：`/sopplus/_web/customized/todo/todotask.jsp`、`donetask.jsp`
- 邮件未读数：`/sopplus/_web/customized/email/getUnReadCount.jsp`
- 图书借阅：`/sopplus/_web/customized/book/queryBookList.jsp`
- 服务目录/收藏：`loadAllServiceApps.jsp`、`getMyFavoriteApps.jsp`

这些是学校前端使用的内部 JSONP 接口，接口和字段可能变化。门户返回的服务入口不等于下游系统已授权；Canvas、SIS、Booking 等系统仍应使用各自的连接器或授权流程。邮件未读数不代表可以读取邮件正文。
