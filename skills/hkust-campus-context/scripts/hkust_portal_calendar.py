#!/usr/bin/env python3
"""Read-only HKUST(GZ) MyPortal calendar connector.

The first run authenticates through the campus SSO using HKUST_USERNAME and
HKUST_PASSWORD. Later runs reuse a mode-0600 cookie jar. Passwords are never
written to disk, accepted as command-line arguments, or logged.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
import re
import stat
import sys
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


PORTAL_URL = "https://myportal.hkust-gz.edu.cn/"
PORTAL_ORIGIN = "https://myportal.hkust-gz.edu.cn"
TWO_FA_ORIGIN = "https://2fa.hkust-gz.edu.cn"
TWO_FA_API = f"{TWO_FA_ORIGIN}/api/2fa-portal"
CATEGORY_URL = f"{PORTAL_ORIGIN}/calendar/mgr/api/category/list.rst"
CALENDAR_URL = f"{PORTAL_ORIGIN}/calendar/mgr/api/hkust/calendarList.rst"
try:
    TZ = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:  # Windows may not have the IANA tzdata package.
    TZ = dt.timezone(dt.timedelta(hours=8), "Asia/Shanghai")
DEFAULT_SESSION_PATH = Path(os.environ.get("HKUST_PORTAL_SESSION", "~/.sensebridge/hkust_portal_cookies.json")).expanduser()


class PortalCalendarError(RuntimeError):
    pass


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.form: Dict[str, str] = {}
        self.inputs: Dict[str, str] = {}
        self._in_form = False

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        values = dict(attrs)
        if tag == "form" and not self._in_form:
            self._in_form = True
            self.form = values
        elif tag == "input" and self._in_form and values.get("name"):
            self.inputs[str(values["name"])] = str(values.get("value", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._in_form = False


def parse_jsonp(text: str, callback: Optional[str] = None) -> Any:
    value = text.strip()
    if callback:
        prefix = callback + "("
        if value.startswith(prefix) and value.endswith(")"):
            value = value[len(prefix) : -1]
    else:
        match = re.match(r"^[A-Za-z_$][\w$]*\((.*)\)\s*;?\s*$", value, re.S)
        if match:
            value = match.group(1)
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise PortalCalendarError("门户接口返回的 JSONP 无法解析") from exc


def _category_source(category_id: Any, label: str = "") -> str:
    try:
        numeric = int(category_id)
    except (TypeError, ValueError):
        numeric = None
    if numeric == -2 or "course" in label.casefold() or "课程" in label:
        return "my_course"
    if numeric == -3:
        return "meeting"
    if numeric == -4:
        return "other"
    if "outlook" in label.casefold():
        return "outlook"
    return "portal"


def normalize_events(payload: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for group in payload:
        for item in group.get("events") or []:
            schedule = item.get("schedule") or {}
            category = schedule.get("cateGory") or schedule.get("category") or {}
            category_id = category.get("id")
            label = str(category.get("calendarCateName") or category.get("name") or "")
            event: Dict[str, Any] = {
                "source": _category_source(category_id, label),
                "title": schedule.get("title") or item.get("title") or "",
                "start": item.get("beginTime"),
                "end": item.get("endTime"),
                "location": schedule.get("location") or "",
                "category_id": category_id,
                "category_label": label,
                "raw": item,
            }
            content = str(schedule.get("content") or "")
            match = re.search(r"教学班名称\s*:\s*([^;；]+)", content)
            if match:
                event["course_class"] = match.group(1).strip()
            output.append(event)
    return output


class PortalCalendarClient:
    def __init__(self, session: Optional[requests.Session] = None, *, session_path: Path = DEFAULT_SESSION_PATH):
        self.session = session or requests.Session()
        self.session_path = Path(session_path).expanduser()
        self._two_fa_session_id: Optional[str] = None
        if hasattr(self.session, "headers"):
            self.session.headers.update({"User-Agent": "SenseBridge-HKUST-Portal/0.1"})

    def load_session(self) -> bool:
        if not self.session_path.is_file():
            return False
        try:
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
            for item in data:
                self.session.cookies.set(item["name"], item["value"], domain=item.get("domain"), path=item.get("path", "/"))
            return True
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise PortalCalendarError(f"读取门户会话失败: {exc}") from exc

    def save_session(self) -> None:
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
            for c in self.session.cookies
        ]
        self.session_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(self.session_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            # Windows ACLs govern access; chmod is best effort there.
            pass

    @staticmethod
    def _json_response(response: Any) -> Any:
        """Decode a JSON response while keeping the fake-session tests simple."""
        try:
            return response.json()
        except (AttributeError, ValueError, TypeError):
            try:
                return json.loads(response.text)
            except (AttributeError, TypeError, json.JSONDecodeError) as exc:
                raise PortalCalendarError("2FA 接口返回的 JSON 无法解析") from exc

    @staticmethod
    def _find_value(payload: Any, names: Iterable[str]) -> Optional[Any]:
        wanted = set(names)
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in wanted and value not in (None, "", []):
                    return value
            for value in payload.values():
                found = PortalCalendarClient._find_value(value, names)
                if found is not None:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = PortalCalendarClient._find_value(value, names)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _process_id_from_url(url: str) -> Optional[str]:
        parsed = urlparse(url)
        fragment = parsed.fragment
        if "?" not in fragment:
            return None
        query = fragment.split("?", 1)[1]
        return parse_qs(query).get("processId", [None])[0]

    def _two_fa_headers(self) -> Dict[str, str]:
        if not self._two_fa_session_id:
            self._two_fa_session_id = str(uuid.uuid4())
        return {"User-Session-ID": self._two_fa_session_id}

    def complete_two_factor(
        self,
        two_fa_url: str,
        *,
        input_code: Optional[Callable[[str], str]] = None,
    ) -> str:
        """Complete the campus 2FA flow using a code typed by the user.

        The code is held only in memory and is never written to the cookie jar,
        logs, or process arguments. ``input_code`` is injectable for tests.
        """
        process_id = self._process_id_from_url(two_fa_url)
        if not process_id:
            raise PortalCalendarError("2FA 跳转地址缺少 processId")
        headers = self._two_fa_headers()
        contact_response = self.session.get(
            f"{TWO_FA_API}/contact/get",
            params={"processId": process_id},
            headers=headers,
            timeout=30,
        )
        contact_response.raise_for_status()
        contact = self._json_response(contact_response)
        verification_type = self._find_value(contact, ("verificationType", "type"))
        if isinstance(verification_type, (dict, list)):
            verification_type = None
        phone = self._find_value(contact, ("phoneNumber",))
        email = self._find_value(contact, ("personalEmail",))
        # The campus frontend names these methods SMS and Email; the contact
        # endpoint returns the corresponding values as phoneNumber/email.
        if not verification_type:
            verification_type = "SMS" if phone else "Email"
        if str(verification_type).casefold() in {"sms", "phone", "phonenumber"}:
            verification_type = "SMS"
            recipient = phone
        elif str(verification_type).casefold() in {"email", "personalemail"}:
            verification_type = "Email"
            recipient = email
        else:
            recipient = self._find_value(contact, ("personalEmail", "phoneNumber", "contact"))
        if not recipient:
            recipient = "已绑定的联系方式"
        send_payload: Dict[str, str] = {
            "processId": str(process_id),
            "verificationType": str(verification_type),
        }
        if verification_type == "Email":
            send_payload["personalEmail"] = str(recipient)
        elif verification_type == "SMS":
            send_payload["phoneNumber"] = str(recipient)
        else:
            # Some deployments return a custom type and expect the corresponding
            # contact field in the request; preserve it when available.
            send_payload[str(verification_type)] = str(recipient)
        send_response = self.session.post(
            f"{TWO_FA_API}/verification-code/send",
            json=send_payload,
            headers=headers,
            timeout=30,
        )
        send_response.raise_for_status()
        send_result = self._json_response(send_response)
        error_message = self._find_value(send_result, ("message", "msg", "error"))
        success = self._find_value(send_result, ("success",))
        if success is False or (isinstance(send_result, dict) and send_result.get("code") not in (None, 0, "0", 200, "200")):
            raise PortalCalendarError(str(error_message or "2FA 验证码发送失败"))
        prompt = f"请输入发送到 {recipient} 的 6 位验证码："
        if input_code is None and not sys.stdin.isatty():
            raise PortalCalendarError("学校要求输入验证码，请在交互式终端重新登录")
        try:
            code = (input_code or getpass.getpass)(prompt).strip()
        except (EOFError, KeyboardInterrupt) as exc:
            raise PortalCalendarError("验证码输入已取消或不可用") from exc
        if not re.fullmatch(r"\d{6}", code):
            raise PortalCalendarError("验证码必须是 6 位数字")
        verify_response = self.session.post(
            f"{TWO_FA_API}/verification-code/verify",
            json={"processId": str(process_id), "verificationCode": code},
            headers=headers,
            timeout=30,
        )
        verify_response.raise_for_status()
        verify_result = self._json_response(verify_response)
        jump_to = self._find_value(verify_result, ("jumpTo", "jump_to"))
        if not jump_to:
            message = self._find_value(verify_result, ("message", "msg", "error"))
            raise PortalCalendarError(str(message or "2FA 验证码校验失败或已过期"))
        continuation = self.session.get(urljoin(TWO_FA_ORIGIN, str(jump_to)), timeout=30, allow_redirects=True)
        continuation.raise_for_status()
        if "myportal.hkust-gz.edu.cn" not in continuation.url:
            raise PortalCalendarError("2FA 已校验，但未能回到 MyPortal")
        return continuation.url

    def login(self, username: str, password: str) -> None:
        response = self.session.get(PORTAL_URL, timeout=30, allow_redirects=True)
        response.raise_for_status()
        if "myportal.hkust-gz.edu.cn" in response.url and "Login" not in response.url:
            self.save_session()
            return
        parser = _FormParser()
        parser.feed(response.text)
        if not parser.inputs.get("ReturnUrl") or "sso.hkust-gz.edu.cn" not in response.url:
            raise PortalCalendarError("未找到学校 SSO 登录表单")
        action = urljoin(response.url, parser.form.get("action") or response.url)
        payload = dict(parser.inputs)
        payload.update({"Username": username, "Password": password, "button": "login", "RememberLogin": "false"})
        result = self.session.post(action, data=payload, timeout=30, allow_redirects=True)
        result.raise_for_status()
        if "2fa.hkust-gz.edu.cn" in result.url:
            final_url = self.complete_two_factor(result.url)
            # Keep the validation below meaningful after the extra redirect.
            result_url = final_url
        else:
            result_url = result.url
        if "myportal.hkust-gz.edu.cn" not in result_url or "Login" in result_url:
            raise PortalCalendarError(
                f"学校 SSO 登录未成功，请检查账号、密码或额外验证（HTTP {result.status_code}）"
            )
        self.save_session()

    def _get_jsonp(self, url: str, params: Dict[str, Any], callback: str) -> Any:
        response = self.session.get(url, params={**params, "callback": callback}, timeout=30)
        response.raise_for_status()
        if "sso.hkust-gz.edu.cn" in response.url or "Account/Login" in response.text:
            raise PortalCalendarError("门户会话已失效，请重新登录")
        return parse_jsonp(response.text, callback)

    def list_events(self, start: dt.date, end: dt.date) -> List[Dict[str, Any]]:
        if end < start:
            raise ValueError("结束日期必须不早于开始日期")
        category_payload = self._get_jsonp(
            CATEGORY_URL,
            {"_p": "YXQ9MSZwPTEmbT1OJg__", "queryType": "2", "categoryIds": ""},
            "categories",
        )
        categories: List[str] = []
        try:
            for group in (category_payload.get("result", {}).get("data") or []):
                for category in group.get("teamCategoryVOS") or []:
                    if str(category.get("id")) != "0":
                        categories.append(str(category["id"]))
        except (AttributeError, KeyError, TypeError) as exc:
            raise PortalCalendarError("门户分类接口返回格式异常") from exc
        local_begin = dt.datetime.combine(start, dt.time.min, TZ)
        local_end = dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min, TZ) - dt.timedelta(milliseconds=1)
        payload = self._get_jsonp(
            CALENDAR_URL,
            {
                "_p": "YXM9MiZ0PTUmZD05NyZwPTEmZj0yMiZtPU4m",
                "queryType": 2,
                "categoryIds": ",".join(categories),
                "fromDate": local_begin.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "endDate": local_end.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "type": 0,
                "t": int(dt.datetime.now().timestamp() * 1000),
            },
            "calendar",
        )
        if not isinstance(payload, list):
            raise PortalCalendarError("门户日程接口返回格式异常")
        return normalize_events(payload)


def _client_from_env(*, relogin: bool = False) -> PortalCalendarClient:
    client = PortalCalendarClient()
    if relogin or not client.load_session():
        username = os.environ.get("HKUST_USERNAME")
        password = os.environ.get("HKUST_PASSWORD")
        if (not username or not password) and not sys.stdin.isatty():
            raise PortalCalendarError("缺少 HKUST_USERNAME 或 HKUST_PASSWORD，无法进行非交互式登录")
        if not username:
            username = input("HKUST username: ").strip()
        if not password:
            password = getpass.getpass("HKUST password: ")
        client.login(username, password)
    return client


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read HKUST(GZ) MyPortal calendar events")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="list calendar and course events")
    listing.add_argument("--start", required=True, type=dt.date.fromisoformat)
    listing.add_argument("--end", required=True, type=dt.date.fromisoformat)
    listing.add_argument("--relogin", action="store_true", help="使用环境变量重新登录，不读取旧会话")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            events = _client_from_env(relogin=args.relogin).list_events(args.start, args.end)
            print(json.dumps({"ok": True, "tool": "hkust_portal.list_events", "data": {"events": events}}, ensure_ascii=False))
            return 0
    except (PortalCalendarError, requests.RequestException, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": {"type": exc.__class__.__name__, "message": str(exc)}}, ensure_ascii=False))
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
