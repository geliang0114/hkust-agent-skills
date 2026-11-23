# HKUST(GZ) Booking API

站点前端调用的是内部 REST API，基础地址为 `https://booking.hkust-gz.edu.cn`。请求需要 `Content-Type: application/json` 和 `Authorization: Bearer <短期 token>`。token 由 SSO 登录态提供，底层脚本从 `BOOKING_API_TOKEN` 读取。

连接器使用的接口：

| 能力 | 方法和路径 |
| --- | --- |
| 筛选映射 | `GET /api/booking-space/get_filter_data?room_type_parent_key=meetingRoom` |
| 搜索房间 | `POST /api/booking/booking/get_room_list` |
| 查询时段 | `POST /api/booking/booking/get_book_detail` |
| 当前用户 | `POST /api/booking-auth/user/info` |
| 我的预约 | `POST /api/booking/booking/get_account_booking` |
| 提交预约 | `POST /api/booking/booking/do_booking` |
| 修改预约 | `POST /api/booking/booking/modify_account_booking` |
| 修改时段 | `POST /api/booking/booking/modify_timeslot` |

提交预约的底层字段是：

```json
{
  "room_key": "R...",
  "subject": "会议标题",
  "timeslots": ["YYYYMMDDHHmm-YYYYMMDDHHmm"],
  "detail": "",
  "participants": [],
  "is_periodic": 0
}
```

网站时间段必须使用本地时间压缩格式，例如 `202611241400-202611241430`。房间搜索的容量筛选是对象数组，例如 `[{"lower_bound":0,"upper_bound":10}]`。

当前站点的“我的预约”部分搜索状态可能受后端排序错误影响。连接器仍支持 `current`、`all`、`expired`、`canceled` 和 `workflow`。如果某个状态返回后端错误，可以用其他状态查询，或先用房间详情核对目标时段，再使用返回的 `booking_key` 取消或修改。
