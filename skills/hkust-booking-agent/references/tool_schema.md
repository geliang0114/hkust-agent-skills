# JSON tool_call schema

所有调用都使用同一个入口：

```json
{
  "tool": "工具名",
  "arguments": {}
}
```

成功返回：

```json
{
  "ok": true,
  "tool": "search_rooms",
  "data": {}
}
```

失败返回：

```json
{
  "ok": false,
  "error": {
    "type": "BookingAPIError",
    "message": "...
  }
}
```

## list_filters

输入 `{}`。返回 `buildings`、`capacities`、`facilities` 和 `room_types`。楼栋对象含 `building_key`、`building_name_cn`、`building_name_en` 和 `floors`。

## search_rooms

输入字段：

```json
{
  "date": "2026-11-24",
  "start_time": "14:00",
  "end_time": "14:30",
  "building": "BD...",
  "capacity_min": 4,
  "capacity_max": 0,
  "facility": [],
  "keyword": "",
  "room_type": ["meetingRoom"],
  "page": 1,
  "page_size": 20
}
```

`building` 使用 `list_filters` 返回的 key。`capacity_max: 0` 表示没有上限。返回的 `rooms` 至少包含 `room_key`、`room_code`、`path_cn`、`capacity`、`facilities`、`has_workflow` 和 `timeslots`。

## get_availability

```json
{
  "room_key": "R...",
  "timeslot": "202611241400-202611241430"
}
```

## find_slots

这个工具适合处理“明天下午找一间我偏好的会议室”这类自然语言任务。它会扫描时间窗口，并对候选房间逐个做可用性核对。

```json
{
  "date": "2026-11-24",
  "window_start": "13:00",
  "window_end": "18:00",
  "duration_minutes": 30,
  "step_minutes": 30,
  "building_preferences": ["科研楼E1", "E1"],
  "room_preferences": [],
  "capacity_min": 4,
  "capacity_max": 0,
  "required_facilities": [],
  "limit": 10
}
```

返回 `slots`，每项含标准化房间信息、`start_time`、`end_time` 和可直接提交的 `timeslot`。`building_preferences` 使用路径文本匹配，因此可以传 `E1` 或 `科研楼E1`。

## create_booking_draft

```json
{
  "room_key": "R...",
  "subject": "会议标题",
  "timeslots": ["202611241400-202611241430"],
  "detail": "会议说明",
  "participants": [],
  "is_periodic": 0
}
```

这个调用只生成本地草稿，不改变网站状态。

## submit_booking

输入 `create_booking_draft` 返回的 `draft`，并显式传 `confirmed`：

```json
{
  "draft": {
    "draft_id": "draft_...",
    "room_key": "R...",
    "subject": "会议标题",
    "timeslots": ["202611241400-202611241430"],
    "detail": "",
    "participants": [],
    "is_periodic": 0
  },
  "confirmed": true
}
```

## list_bookings

```json
{
  "search_type": "current",
  "page": 1,
  "page_size": 20
}
```

可用的 `search_type` 包括 `current`、`all`、`expired`、`canceled` 和 `workflow`。

## cancel_booking

```json
{
  "booking_key": "BI...",
  "confirmed": true
}
```

取消整条预约，不要用 `modify_timeslot` 删除最后一个时段。
