import json
import unittest

from hkust_campus_context import CampusContextClient, clean_html


class FakeResponse:
    def __init__(self, payload, callback="x"):
        self.text = payload if isinstance(payload, str) else json.dumps(payload)
        self.url = "https://events.hkust-gz.edu.cn/"
        self.status_code = 200
    def raise_for_status(self): pass
    def json(self): return json.loads(self.text)


class FakeHTTP:
    def __init__(self, responses): self.responses = list(responses); self.calls = []; self.headers = {}
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs)); return self.responses.pop(0)


class CampusContextTests(unittest.TestCase):
    def test_clean_html(self):
        self.assertEqual(clean_html("<p>Hello&nbsp;<strong>campus</strong></p>"), "Hello campus")

    def test_list_activities_normalizes_html_and_pagination(self):
        http = FakeHTTP([FakeResponse({"code": 200, "data": {"events": [{"id": 10006, "title": "<b>AI Seminar</b>", "startAt": "2026-11-25", "venue": {"location": "Lecture Hall B"}}], "pagination": {"current": 0, "total": 1}}})])
        result = CampusContextClient(http=http).list_activities(page=1, page_size=2)
        self.assertEqual(result["events"][0]["title"], "AI Seminar")
        params = http.calls[0][1]["params"]
        self.assertIn('"current":1', params["pagination"])

    def test_activity_detail_normalizes_registration(self):
        http = FakeHTTP([FakeResponse({"code": 200, "data": {"event": {"event": {"id": 10006, "eventStatus": "released"}, "content": {"title": {"title": "<p>AI</p>"}, "eventDate": {"startAtDate": "2026-11-25", "startAtTime": "11:00"}, "venue": {"location": "E1"}, "registration": {"registrationRequired": False}}}}})])
        result = CampusContextClient(http=http).get_activity(10006)
        self.assertEqual(result["title"], "AI")
        self.assertFalse(result["registration"]["required"])


if __name__ == "__main__": unittest.main()
