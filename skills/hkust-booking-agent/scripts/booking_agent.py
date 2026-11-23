#!/usr/bin/env python3
"""Reusable Booking connector for the HKUST(GZ) room-booking service.

The connector deliberately keeps authentication outside the model-facing API.
Pass a short-lived Bearer token through BOOKING_API_TOKEN or the constructor.
The site uses SSO, so this module does not collect or store a password.

Examples:
    BOOKING_API_TOKEN='...' python scripts/booking_agent.py me
    BOOKING_API_TOKEN='...' python scripts/booking_agent.py search \
        --date 2026-11-24 --start 14:00 --end 16:00 --capacity-min 6
    BOOKING_API_TOKEN='...' python scripts/booking_agent.py book \
        --room-key R... --date 2026-11-24 --start 14:00 --end 16:00 \
        --title '创业分享会' --confirm

The final command has an explicit --confirm guard because it creates an
external booking. Without it, the command only prints the normalized draft.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import uuid
from urllib.parse import quote
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests


DEFAULT_BASE_URL = "https://booking.hkust-gz.edu.cn"


class BookingAPIError(RuntimeError):
    """An HTTP or application-level error returned by the booking service."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须是 YYYY-MM-DD") from exc


def _time(value: str) -> dt.time:
    try:
        return dt.time.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("时间必须是 HH:MM") from exc


def format_timeslot(date: dt.date, start: dt.time, end: dt.time) -> str:
    """Convert an ISO date/time range to the site's compact representation."""

    start_dt = dt.datetime.combine(date, start)
    end_dt = dt.datetime.combine(date, end)
    if end_dt <= start_dt:
        raise ValueError("结束时间必须晚于开始时间")
    return f"{date:%Y%m%d}{start:%H%M}-{date:%Y%m%d}{end:%H%M}"


@dataclass(frozen=True)
class BookingDraft:
    """A local, side-effect-free booking request."""

    room_key: str
    subject: str
    timeslots: List[str]
    detail: str = ""
    participants: List[str] = field(default_factory=list)
    is_periodic: int = 0
    draft_id: str = field(default_factory=lambda: f"draft_{uuid.uuid4().hex}")

    def to_api_payload(self) -> Dict[str, Any]:
        return {
            "room_key": self.room_key,
            "subject": self.subject,
            "timeslots": self.timeslots,
            "detail": self.detail,
            "participants": self.participants,
            "is_periodic": self.is_periodic,
        }


class BookingClient:
    """Small, stable wrapper around the site's internal REST API."""

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 20.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.token = token or os.environ.get("BOOKING_API_TOKEN")

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.token:
            raise BookingAPIError(
                "缺少登录态。请设置 BOOKING_API_TOKEN，或由宿主 Agent 注入短期 Bearer token。"
            )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/reserve",
            "User-Agent": "SenseBridge-BookingAgent/0.1",
        }
        try:
            response = self.session.post(
                f"{self.base_url}{path}",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            status_code = response.status_code
            body = response.json()
        except (requests.RequestException, ValueError):
            # Some macOS Python builds negotiate TLS differently from the
            # browser and curl. Keep the same connector usable in that case.
            try:
                curl = subprocess.run(
                    [
                        "curl", "--silent", "--show-error", "--max-time",
                        str(int(self.timeout)), "--http1.1", "-X", "POST",
                        f"{self.base_url}{path}",
                        "-H", "Accept: application/json",
                        "-H", "Content-Type: application/json",
                        "-H", f"Authorization: Bearer {self.token}",
                        "-H", f"Origin: {self.base_url}",
                        "-H", f"Referer: {self.base_url}/reserve",
                        "--data-binary", json.dumps(payload),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if not curl.stdout:
                    raise BookingAPIError(
                        f"请求预约服务失败: {curl.stderr.strip() or 'curl 无响应'}"
                    )
                status_code = 200
                body = json.loads(curl.stdout)
            except (OSError, ValueError) as exc:
                raise BookingAPIError(f"请求预约服务失败: {exc}") from exc

        if status_code == 401 or body.get("code") == 401:
            raise BookingAPIError("登录态已失效，请重新完成 SSO 登录", status_code=401)
        if status_code >= 400:
            message = body.get("codeText") or body.get("message") or "请求失败"
            raise BookingAPIError(str(message), status_code=status_code)
        if body.get("code") not in (None, 200):
            message = body.get("codeText") or body.get("message") or "预约服务返回错误"
            raise BookingAPIError(str(message), status_code=status_code)
        return body

    def filter_data(self, room_type_parent_key: str = "meetingRoom") -> Dict[str, Any]:
        """Return building, capacity, facility, and room-type mappings."""

        if not self.token:
            raise BookingAPIError(
                "缺少登录态。请设置 BOOKING_API_TOKEN，或由宿主 Agent 注入短期 Bearer token。"
            )
        path = "/api/booking-space/get_filter_data?room_type_parent_key=" + quote(
            room_type_parent_key
        )
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/home",
            "User-Agent": "SenseBridge-BookingAgent/0.1",
        }
        try:
            response = self.session.get(
                f"{self.base_url}{path}", headers=headers, timeout=self.timeout
            )
            status_code = response.status_code
            body = response.json()
        except (requests.RequestException, ValueError):
            try:
                curl = subprocess.run(
                    [
                        "curl", "--silent", "--show-error", "--max-time",
                        str(int(self.timeout)), "--http1.1", f"{self.base_url}{path}",
                        "-H", "Accept: application/json",
                        "-H", f"Authorization: Bearer {self.token}",
                        "-H", f"Origin: {self.base_url}",
                        "-H", f"Referer: {self.base_url}/home",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if not curl.stdout:
                    raise BookingAPIError(
                        f"请求预约筛选数据失败: {curl.stderr.strip() or 'curl 无响应'}"
                    )
                status_code = 200
                body = json.loads(curl.stdout)
            except (OSError, ValueError) as exc:
                raise BookingAPIError(f"请求预约筛选数据失败: {exc}") from exc
        if status_code == 401 or body.get("code") == 401:
            raise BookingAPIError("登录态已失效，请重新完成 SSO 登录", status_code=401)
        if body.get("code") not in (None, 200):
            message = body.get("codeText") or body.get("message") or "请求失败"
            raise BookingAPIError(str(message), status_code=status_code)
        return body

    def user_info(self) -> Dict[str, Any]:
        return self._post("/api/booking-auth/user/info", {})

    def search_rooms(
        self,
        *,
        date: Optional[dt.date] = None,
        start: Optional[dt.time] = None,
        end: Optional[dt.time] = None,
        building: str = "",
        facility: Optional[Sequence[str]] = None,
        capacity: Optional[Sequence[Dict[str, int]]] = None,
        search_key: str = "",
        room_type: Optional[Sequence[str]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        timeslot: List[str] = []
        if date is not None and start is not None and end is not None:
            timeslot = [format_timeslot(date, start, end)]
        payload = {
            "building": building,
            "facility": list(facility or []),
            "capacity": list(capacity or []),
            "search_key": search_key,
            "room_type": list(room_type or ["meetingRoom"]),
            "timeslot": timeslot,
            "booking_timeslot": [],
            "is_periodic": 0,
            "page": page,
            "page_size": page_size,
        }
        return self._post("/api/booking/booking/get_room_list", payload)

    def room_detail(self, room_key: str, timeslot: str) -> Dict[str, Any]:
        return self._post(
            "/api/booking/booking/get_book_detail",
            {"room_key": room_key, "timeslot": timeslot},
        )

    def available_booking(
        self, room_key: str, timeslot_type: str = "degrade"
    ) -> Dict[str, Any]:
        return self._post(
            "/api/booking/booking/get_available_booking",
            {"room_key": room_key, "timeslot_type": timeslot_type},
        )

    def list_bookings(
        self,
        *,
        search_type: str = "current",
        page: int = 1,
        page_size: int = 20,
        by_system: str = "",
        subject: str = "",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "search_type": search_type,
            "page": page,
            "page_size": page_size,
        }
        if by_system:
            payload["by_system"] = by_system
        if subject:
            payload["subject"] = subject
        return self._post("/api/booking/booking/get_account_booking", payload)

    def submit_booking(self, draft: BookingDraft, *, confirmed: bool = False) -> Dict[str, Any]:
        if not confirmed:
            raise BookingAPIError("提交预约需要 confirmed=True，避免 Agent 误操作")
        return self._post(
            "/api/booking/booking/do_booking", draft.to_api_payload()
        )

    def modify_booking(
        self,
        booking_key: str,
        *,
        subject: str,
        detail: str = "",
        participants: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        return self._post(
            "/api/booking/booking/modify_account_booking",
            {
                "booking_key": booking_key,
                "subject": subject,
                "detail": detail,
                "participants": list(participants or []),
                "delete": 0,
            },
        )

    def cancel_booking(self, booking_key: str, *, confirmed: bool = False) -> Dict[str, Any]:
        if not confirmed:
            raise BookingAPIError("取消预约需要 confirmed=True，避免 Agent 误操作")
        return self._post(
            "/api/booking/booking/modify_account_booking",
            {
                "booking_key": booking_key,
                "subject": "",
                "detail": "",
                "participants": [],
                "delete": 1,
            },
        )

    def append_timeslots(
        self, booking_key: str, timeslots: Iterable[str], *, confirmed: bool = False
    ) -> Dict[str, Any]:
        if not confirmed:
            raise BookingAPIError("增加预约时段需要 confirmed=True")
        return self._post(
            "/api/booking/booking/append_timeslots",
            {"booking_key": booking_key, "timeslots": list(timeslots)},
        )

    def modify_timeslot(
        self,
        timeslot_key: str,
        timeslot: str,
        *,
        delete: int = 0,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        if not confirmed:
            raise BookingAPIError("修改预约时段需要 confirmed=True")
        return self._post(
            "/api/booking/booking/modify_timeslot",
            {"timeslot_key": timeslot_key, "timeslot": timeslot, "delete": delete},
        )


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _client_from_args(args: argparse.Namespace) -> BookingClient:
    return BookingClient(token=args.token, base_url=args.base_url)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HKUST(GZ) Booking Agent Connector")
    parser.add_argument("--token", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("me", help="验证登录态并返回当前用户信息")

    search = sub.add_parser("search", help="搜索会议室")
    search.add_argument("--date", type=_date)
    search.add_argument("--start", type=_time)
    search.add_argument("--end", type=_time)
    search.add_argument("--building", default="")
    search.add_argument("--capacity-min", type=int, default=None)
    search.add_argument("--keyword", default="")
    search.add_argument("--page-size", type=int, default=20)

    availability = sub.add_parser("availability", help="查询房间详细时间段")
    availability.add_argument("--room-key", required=True)
    availability.add_argument("--timeslot", required=True)

    listing = sub.add_parser("list", help="查询我的预约")
    listing.add_argument("--search-type", default="current")
    listing.add_argument("--page-size", type=int, default=20)

    book = sub.add_parser("book", help="生成预约草稿，带 --confirm 才提交")
    book.add_argument("--room-key", required=True)
    book.add_argument("--date", type=_date, required=True)
    book.add_argument("--start", type=_time, required=True)
    book.add_argument("--end", type=_time, required=True)
    book.add_argument("--title", required=True)
    book.add_argument("--detail", default="")
    book.add_argument("--participant", action="append", default=[])
    book.add_argument("--confirm", action="store_true")

    cancel = sub.add_parser("cancel", help="取消预约，带 --confirm 才执行")
    cancel.add_argument("--booking-key", required=True)
    cancel.add_argument("--confirm", action="store_true")

    cancel_slot = sub.add_parser(
        "cancel-timeslot", help="取消单个预约时段，带 --confirm 才执行"
    )
    cancel_slot.add_argument("--timeslot-key", required=True)
    cancel_slot.add_argument("--timeslot", required=True)
    cancel_slot.add_argument("--confirm", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    client = _client_from_args(args)
    try:
        if args.command == "me":
            _print_json(client.user_info())
        elif args.command == "search":
            capacity = ([{"lower_bound": args.capacity_min, "upper_bound": 0}]
                         if args.capacity_min else [])
            _print_json(
                client.search_rooms(
                    date=args.date,
                    start=args.start,
                    end=args.end,
                    building=args.building,
                    capacity=capacity,
                    search_key=args.keyword,
                    page_size=args.page_size,
                )
            )
        elif args.command == "availability":
            _print_json(client.room_detail(args.room_key, args.timeslot))
        elif args.command == "list":
            _print_json(
                client.list_bookings(
                    search_type=args.search_type, page_size=args.page_size
                )
            )
        elif args.command == "book":
            slot = format_timeslot(args.date, args.start, args.end)
            draft = BookingDraft(
                room_key=args.room_key,
                subject=args.title,
                timeslots=[slot],
                detail=args.detail,
                participants=args.participant,
            )
            if not args.confirm:
                _print_json({"draft": asdict(draft), "submitted": False})
            else:
                _print_json(
                    {"draft": asdict(draft), "submitted": True,
                     "result": client.submit_booking(draft, confirmed=True)}
                )
        elif args.command == "cancel":
            _print_json(client.cancel_booking(args.booking_key, confirmed=args.confirm))
        elif args.command == "cancel-timeslot":
            _print_json(
                client.modify_timeslot(
                    args.timeslot_key,
                    args.timeslot,
                    delete=1,
                    confirmed=args.confirm,
                )
            )
        return 0
    except (BookingAPIError, ValueError, requests.RequestException) as exc:
        print(f"booking-agent: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
