import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from hkust_portal_calendar import PortalCalendarClient, parse_jsonp, normalize_events, TZ


class FakeResponse:
    def __init__(self, text="", url="https://myportal.hkust-gz.edu.cn/", status_code=200, headers=None):
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.cookies = FakeCookies()

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)


class FakeCookies(dict):
    def set(self, name, value, domain=None, path="/"):
        self[name] = value

    def __iter__(self):
        return iter([type("Cookie", (), {"name": k, "value": v, "domain": "", "path": "/"})() for k, v in self.items()])


class PortalCalendarTests(unittest.TestCase):
    def test_parse_jsonp(self):
        self.assertEqual(parse_jsonp("cb([1, {\"a\": 2}])", "cb"), [1, {"a": 2}])

    def test_normalize_events(self):
        events = normalize_events(
            [
                {
                    "events": [
                        {
                            "beginTime": "2026-11-24 09:00:00",
                            "endTime": "2026-11-24 10:30:00",
                            "schedule": {
                                "title": "课程 A",
                                "location": "E1-101",
                                "content": "教学班名称: B1;教师: 张老师",
                                "cateGory": {"id": -2, "calendarCateName": "My Course"},
                            },
                        }
                    ]
                }
            ]
        )
        self.assertEqual(events[0]["source"], "my_course")
        self.assertEqual(events[0]["title"], "课程 A")
        self.assertEqual(events[0]["location"], "E1-101")
        self.assertEqual(events[0]["course_class"], "B1")

    def test_login_posts_hidden_fields_and_reaches_portal(self):
        login_html = (
            '<form action="" method="post">'
            '<input name="ReturnUrl" value="return">'
            '<input name="__RequestVerificationToken" value="csrf">'
            '<input name="RememberLogin" value="false">'
            '</form>'
        )
        session = FakeSession(
            [
                FakeResponse(login_html, "https://sso.hkust-gz.edu.cn/Account/Login"),
                FakeResponse("ok", "https://myportal.hkust-gz.edu.cn/commonback"),
            ]
        )
        client = PortalCalendarClient(session=session)
        client.login("orenglouyang", "secret")
        method, _, kwargs = session.calls[1]
        self.assertEqual(method, "POST")
        self.assertEqual(kwargs["data"]["Username"], "orenglouyang")
        self.assertEqual(kwargs["data"]["Password"], "secret")
        self.assertEqual(kwargs["data"]["__RequestVerificationToken"], "csrf")

    def test_two_factor_prompts_and_follows_jump(self):
        session = FakeSession(
            [
                FakeResponse('{"data":{"verificationType":"personalEmail","personalEmail":"l***@hkust-gz.edu.cn"}}', "https://2fa.hkust-gz.edu.cn/"),
                FakeResponse('{"code":0,"message":"sent"}', "https://2fa.hkust-gz.edu.cn/"),
                FakeResponse('{"code":0,"data":{"jumpTo":"/complete?processId=abc"}}', "https://2fa.hkust-gz.edu.cn/"),
                FakeResponse("ok", "https://myportal.hkust-gz.edu.cn/commonback"),
            ]
        )
        client = PortalCalendarClient(session=session)
        final_url = client.complete_two_factor(
            "https://2fa.hkust-gz.edu.cn/#/2fa/home?processId=abc",
            input_code=lambda prompt: "123456",
        )
        self.assertIn("myportal.hkust-gz.edu.cn", final_url)
        self.assertEqual(session.calls[1][2]["json"]["verificationType"], "Email")
        self.assertEqual(session.calls[2][2]["json"]["verificationCode"], "123456")
        self.assertEqual(session.calls[1][2]["headers"], session.calls[2][2]["headers"])

    def test_two_factor_rejects_invalid_code_without_verifying(self):
        session = FakeSession(
            [
                FakeResponse('{"data":{"verificationType":"phoneNumber","phoneNumber":"***1234"}}'),
                FakeResponse('{"code":0}'),
            ]
        )
        client = PortalCalendarClient(session=session)
        with self.assertRaisesRegex(Exception, "6 位数字"):
            client.complete_two_factor(
                "https://2fa.hkust-gz.edu.cn/#/2fa/home?processId=abc",
                input_code=lambda prompt: "12",
            )
        self.assertEqual(len(session.calls), 2)

    def test_list_events_queries_categories_and_calendar(self):
        category = 'categories({"result":{"data":[{"teamCategoryVOS":[{"id":-2,"calendarCateName":"My Course"}]}]}})'
        calendar = 'calendar([{"events":[{"beginTime":"2026-11-24 09:00:00","endTime":"2026-11-24 10:00:00","schedule":{"title":"A","cateGory":{"id":-2}}}]}])'
        session = FakeSession(
            [
                FakeResponse(category),
                FakeResponse(calendar),
            ]
        )
        client = PortalCalendarClient(session=session)
        events = client.list_events(dt.date(2026, 11, 24), dt.date(2026, 11, 24))
        self.assertEqual(events[0]["title"], "A")
        self.assertEqual(session.calls[0][1], "https://myportal.hkust-gz.edu.cn/calendar/mgr/api/category/list.rst")
        self.assertEqual(session.calls[1][1], "https://myportal.hkust-gz.edu.cn/calendar/mgr/api/hkust/calendarList.rst")
        self.assertEqual(session.calls[1][2]["params"]["categoryIds"], "-2")

    def test_cookie_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.json"
            client = PortalCalendarClient(session=FakeSession([]), session_path=path)
            client.session.cookies.update({".AspNetCore.Cookies": "abc"})
            client.save_session()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            other = PortalCalendarClient(session=FakeSession([]), session_path=path)
            self.assertEqual(other.load_session(), True)
            self.assertEqual(other.session.cookies.get(".AspNetCore.Cookies"), "abc")

    def test_fixed_timezone_fallback_has_china_offset(self):
        self.assertEqual(
            dt.datetime(2026, 11, 24, tzinfo=dt.timezone.utc).astimezone(TZ).utcoffset(),
            dt.timedelta(hours=8),
        )


if __name__ == "__main__":
    unittest.main()
