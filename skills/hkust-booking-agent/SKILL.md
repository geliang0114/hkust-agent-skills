---
name: hkust-booking-agent
description: Search, reserve, inspect, and cancel HKUST(GZ) meeting rooms through the reusable booking connector when a user asks an agent to arrange a campus room.
---

# HKUST(GZ) 会议室预约

这个 Skill 把校园预约网站封装成可复用的 JSON 工具调用。使用它时，subagent 负责理解用户的自然语言、读取个人偏好、选择候选房间和空闲时段，再调用连接器完成预约。

底层脚本和统一入口均位于本 Skill 的 `scripts/` 内。`booking_tool_call.py` 从标准输入读取一个 JSON 对象，并向标准输出返回一个 JSON 对象。运行前由宿主注入短期 `BOOKING_API_TOKEN`。不要把账号密码或 token 写入 prompt、Skill、日志或个人上下文。

## 标准工作流

1. 从个人上下文读取偏好。优先使用用户明确说过的楼栋、人数、设备、日期和时间。没有明确偏好时，可以使用已保存的 `preferred_buildings`、`min_capacity`、`required_facilities` 和 `preferred_time_windows`。
2. 对“找一间空闲会议室”这类请求优先调用 `find_slots`。它会按 `building_preferences`、`room_preferences`、容量、设备和时间窗口返回候选时段。需要展示楼栋选项或使用精确 key 时，先调用 `list_filters`。不要猜楼栋 key。
3. 对最终候选调用 `get_availability` 做一次细粒度核对。结果中的 `timeslots` 表示已占用、受限或已删除的时间段。
4. 调用 `create_booking_draft`，把房间、时段、标题、描述和参与人固化为草稿。
5. 在产生外部预约前，向用户展示最终摘要。用户明确要求“直接预约”或确认摘要后，调用 `submit_booking` 并传 `confirmed: true`。
6. 返回标准化结果，把 `booking_key`、房间路径、时段和审批状态写入个人上下文。需要取消时调用 `list_bookings` 找到目标记录，再调用 `cancel_booking` 并传 `confirmed: true`。

如果目标时间没有空闲房间，按用户偏好顺序扩展楼栋或时间段，并说明实际选择。不要静默改到另一天。预约失败时读取 `error.message`，避免重复提交。

## 调用方式

```bash
printf '%s' '{"tool":"list_filters","arguments":{}}' \
  | python3 skills/hkust-booking-agent/scripts/booking_tool_call.py
```

完整字段和返回结构见 [references/tool_schema.md](references/tool_schema.md)。接口路径、认证方式和网站字段见 [references/api.md](references/api.md)。
