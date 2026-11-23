#!/usr/bin/env python3
"""JSON tool-call adapter for the HKUST(GZ) booking connector.

Read one request object from stdin and emit one response object on stdout.
The bearer token is read from BOOKING_API_TOKEN and is never part of the
request schema.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import sys
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List


def _load_connector():
    path = Path(__file__).resolve().with_name("booking_agent.py")
    spec = importlib.util.spec_from_file_location("sensebridge_booking_agent", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"找不到预约连接器: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


connector = _load_connector()
BookingAPIError = connector.BookingAPIError
BookingClient = connector.BookingClient
BookingDraft = connector.BookingDraft


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def _time(value: str) -> dt.time:
    return dt.time.fromisoformat(value)


def _room(room: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "room_key": room.get("room_key"),
        "room_code": room.get("room_code"),
        "name": room.get("room_name_cn") or room.get("room_name_en") or "",
        "path_cn": room.get("room_path_cn"),
        "path_en": room.get("room_path_en"),
        "capacity": room.get("capacity"),
        "room_type": room.get("room_type_cn") or room.get("room_type_en"),
        "facilities": [
            item.get("facility_type_name_cn") or item.get("facility_type_name_en")
            for item in room.get("facilities") or []
        ],
        "book_start_time": room.get("book_start_time"),
        "book_end_time": room.get("book_end_time"),
        "has_workflow": bool(room.get("has_workflow")),
        "timeslots": [
            {
                "timeslot": item.get("timeslot"),
                "state": item.get("state"),
                "timeslot_key": item.get("timeslot_key"),
            }
            for item in room.get("timeslots") or []
        ],
    }


def _booking(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "booking_key": item.get("booking_key"),
        "subject": item.get("subject"),
        "detail": item.get("detail"),
        "room_key": item.get("room_key"),
        "room_code": item.get("room_code"),
        "path_cn": item.get("room_path_cn"),
        "path_en": item.get("room_path_en"),
        "workflow_status": item.get("workflow_status"),
        "timeslots": [
            {
                "timeslot": slot.get("timeslot"),
                "state": slot.get("state"),
                "timeslot_key": slot.get("timeslot_key"),
            }
            for slot in item.get("timeslots") or []
        ],
    }


def _blocked_ranges(items: List[Dict[str, Any]]) -> List[tuple]:
    blocked = []
    for item in items:
        if item.get("state") in {"deleted", "invalid"}:
            continue
        value = item.get("timeslot", "")
        try:
            start_raw, end_raw = value.split("-")
            start = dt.datetime.strptime(start_raw, "%Y%m%d%H%M")
            end = dt.datetime.strptime(end_raw, "%Y%m%d%H%M")
        except (ValueError, TypeError):
            continue
        blocked.append((start, end))
    return blocked


def _response(tool: str, data: Any) -> Dict[str, Any]:
    return {"ok": True, "tool": tool, "data": data}


def invoke(request: Dict[str, Any]) -> Dict[str, Any]:
    tool = request.get("tool")
    args = request.get("arguments") or {}
    if not isinstance(tool, str) or not isinstance(args, dict):
        raise ValueError("请求必须包含字符串 tool 和对象 arguments")
    client = BookingClient()

    if tool == "get_user_info":
        return _response(tool, client.user_info().get("data"))
    if tool == "list_filters":
        data = client.filter_data().get("data") or {}
        return _response(
            tool,
            {
                "buildings": data.get("buildings", []),
                "capacities": data.get("capacities", []),
                "facilities": data.get("facilities", []),
                "room_types": data.get("room_types", []),
            },
        )
    if tool == "search_rooms":
        date = _date(args["date"]) if args.get("date") else None
        start = _time(args["start_time"]) if args.get("start_time") else None
        end = _time(args["end_time"]) if args.get("end_time") else None
        capacity = []
        if args.get("capacity_min") is not None or args.get("capacity_max") is not None:
            capacity = [
                {
                    "lower_bound": int(args.get("capacity_min") or 0),
                    "upper_bound": int(args.get("capacity_max") or 0),
                }
            ]
        data = client.search_rooms(
            date=date,
            start=start,
            end=end,
            building=args.get("building", ""),
            capacity=capacity,
            facility=args.get("facility", []),
            search_key=args.get("keyword", ""),
            room_type=args.get("room_type") or ["meetingRoom"],
            page=int(args.get("page", 1)),
            page_size=int(args.get("page_size", 20)),
        ).get("data") or {}
        return _response(
            tool,
            {
                "count": data.get("count", 0),
                "rooms": [_room(item) for item in data.get("rooms", [])],
            },
        )
    if tool == "find_slots":
        date = _date(args["date"])
        window_start = _time(args.get("window_start", "13:00"))
        window_end = _time(args.get("window_end", "18:00"))
        duration = int(args.get("duration_minutes", 30))
        step = int(args.get("step_minutes", 30))
        if duration <= 0 or step <= 0:
            raise ValueError("duration_minutes 和 step_minutes 必须大于 0")
        limit = int(args.get("limit", 10))
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        window_begin = dt.datetime.combine(date, window_start)
        window_finish = dt.datetime.combine(date, window_end)
        if window_finish <= window_begin:
            raise ValueError("window_end 必须晚于 window_start")
        result = client.search_rooms(
            date=date,
            start=window_start,
            end=window_end,
            room_type=args.get("room_type") or ["meetingRoom"],
            page=1,
            page_size=min(int(args.get("page_size", 100)), 100),
        )
        raw_rooms = (result.get("data") or {}).get("rooms") or []
        min_capacity = int(args.get("capacity_min", 0))
        max_capacity = int(args.get("capacity_max", 0))
        building_preferences = [
            str(value).casefold() for value in args.get("building_preferences", [])
        ]
        room_preferences = [
            str(value).casefold() for value in args.get("room_preferences", [])
        ]
        required_facilities = [
            str(value).casefold() for value in args.get("required_facilities", [])
        ]

        def preference_rank(room: Dict[str, Any]) -> tuple:
            path = (room.get("room_path_cn") or "").casefold()
            room_code = (room.get("room_code") or "").casefold()
            room_number = (room.get("room_no") or "").casefold()
            building_rank = next(
                (index for index, value in enumerate(building_preferences) if value in path),
                len(building_preferences),
            )
            room_rank = next(
                (
                    index
                    for index, value in enumerate(room_preferences)
                    if value in room_code or value in room_number or value in path
                ),
                len(room_preferences),
            )
            return (room_rank, building_rank)

        candidates = []
        for room in raw_rooms:
            capacity = int(room.get("capacity") or 0)
            if capacity < min_capacity or (max_capacity and capacity > max_capacity):
                continue
            path = (room.get("room_path_cn") or "").casefold()
            if building_preferences and not any(value in path for value in building_preferences):
                continue
            facility_names = [
                str(item.get("facility_type_name_cn") or item.get("facility_type_name_en") or "").casefold()
                for item in room.get("facilities") or []
            ]
            if any(
                not any(required in available for available in facility_names)
                for required in required_facilities
            ):
                continue
            candidates.append(room)
        candidates.sort(key=preference_rank)

        slots = []
        scan = window_begin
        while scan + timedelta(minutes=duration) <= window_finish:
            slot_start = scan
            slot_end = scan + timedelta(minutes=duration)
            timeslot = (
                f"{slot_start:%Y%m%d%H%M}-{slot_end:%Y%m%d%H%M}"
            )
            for room in candidates:
                detail = client.room_detail(room["room_key"], timeslot)
                busy = _blocked_ranges((detail.get("data") or {}).get("timeslots") or [])
                if any(slot_start < end and slot_end > start for start, end in busy):
                    continue
                slots.append(
                    {
                        "room": _room(room),
                        "start_time": f"{slot_start:%Y-%m-%d %H:%M}",
                        "end_time": f"{slot_end:%Y-%m-%d %H:%M}",
                        "timeslot": timeslot,
                    }
                )
                if len(slots) >= limit:
                    break
            if len(slots) >= limit:
                break
            scan += timedelta(minutes=step)
        return _response(tool, {"date": date.isoformat(), "slots": slots})
    if tool == "get_availability":
        result = client.room_detail(args["room_key"], args["timeslot"])
        data = result.get("data") or {}
        return _response(
            tool,
            {
                "room_key": args["room_key"],
                "timeslots": [
                    {
                        "timeslot": item.get("timeslot"),
                        "state": item.get("state"),
                        "timeslot_key": item.get("timeslot_key"),
                        "subject": item.get("subject"),
                    }
                    for item in data.get("timeslots") or []
                ],
            },
        )
    if tool == "create_booking_draft":
        draft = BookingDraft(
            room_key=args["room_key"],
            subject=args["subject"],
            timeslots=list(args["timeslots"]),
            detail=args.get("detail", ""),
            participants=list(args.get("participants", [])),
            is_periodic=int(args.get("is_periodic", 0)),
        )
        return _response(tool, {"draft": asdict(draft), "submitted": False})
    if tool == "submit_booking":
        draft_data = args.get("draft") or {}
        draft = BookingDraft(
            room_key=draft_data["room_key"],
            subject=draft_data["subject"],
            timeslots=list(draft_data["timeslots"]),
            detail=draft_data.get("detail", ""),
            participants=list(draft_data.get("participants", [])),
            is_periodic=int(draft_data.get("is_periodic", 0)),
            draft_id=draft_data.get("draft_id", ""),
        )
        result = client.submit_booking(draft, confirmed=bool(args.get("confirmed")))
        response_data = result.get("data") or {}
        verification: Dict[str, Any] = {"status": "not_found"}
        if response_data.get("result") == 1:
            try:
                bookings = client.list_bookings(
                    search_type="current", page=1, page_size=50
                ).get("data", {}).get("bookings") or []
                match = next(
                    (
                        item
                        for item in bookings
                        if item.get("room_key") == draft.room_key
                        and item.get("subject") == draft.subject
                        and any(
                            slot.get("timeslot") in draft.timeslots
                            for slot in item.get("timeslots") or []
                        )
                    ),
                    None,
                )
                if match:
                    verification = {
                        "status": "verified",
                        "booking": _booking(match),
                    }
            except BookingAPIError as exc:
                verification = {"status": "verification_unavailable", "message": str(exc)}
        return _response(
            tool,
            {
                "submitted": response_data.get("result") == 1,
                "result": response_data,
                "verification": verification,
            },
        )
    if tool == "list_bookings":
        result = client.list_bookings(
            search_type=args.get("search_type", "current"),
            page=int(args.get("page", 1)),
            page_size=int(args.get("page_size", 20)),
        )
        data = result.get("data") or {}
        return _response(
            tool,
            {
                "count": data.get("count", 0),
                "bookings": [_booking(item) for item in data.get("bookings") or []],
            },
        )
    if tool == "cancel_booking":
        result = client.cancel_booking(
            args["booking_key"], confirmed=bool(args.get("confirmed"))
        )
        return _response(tool, {"cancelled": result.get("data")})
    raise ValueError(f"未知工具: {tool}")


def main() -> int:
    try:
        request = json.load(sys.stdin)
        result = invoke(request)
    except (BookingAPIError, KeyError, TypeError, ValueError) as exc:
        result = {
            "ok": False,
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
        }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
