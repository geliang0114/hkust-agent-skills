import importlib.util
import os
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("booking_tool_call.py")
SPEC = importlib.util.spec_from_file_location("booking_tool_call_test", SCRIPT)
tool_call = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tool_call
SPEC.loader.exec_module(tool_call)


class BookingToolCallTests(unittest.TestCase):
    def test_draft_returns_standard_response_without_network(self):
        result = tool_call.invoke(
            {
                "tool": "create_booking_draft",
                "arguments": {
                    "room_key": "room-1",
                    "subject": "Team meeting",
                    "timeslots": ["202611241400-202611241430"],
                },
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["tool"], "create_booking_draft")
        self.assertFalse(result["data"]["submitted"])
        self.assertEqual(result["data"]["draft"]["room_key"], "room-1")

    def test_missing_confirmation_does_not_submit(self):
        os.environ.pop("BOOKING_API_TOKEN", None)
        with self.assertRaises(tool_call.BookingAPIError):
            tool_call.invoke(
                {
                    "tool": "submit_booking",
                    "arguments": {
                        "draft": {
                            "room_key": "room-1",
                            "subject": "Team meeting",
                            "timeslots": ["202611241400-202611241430"],
                        }
                    },
                }
            )

    def test_date_and_time_formats_are_site_compatible(self):
        slot = tool_call.connector.format_timeslot(
            tool_call._date("2026-11-24"), tool_call._time("14:00"), tool_call._time("14:30")
        )
        self.assertEqual(slot, "202611241400-202611241430")

    def test_find_slots_filters_and_prioritizes_rooms_without_network(self):
        class FakeClient:
            def search_rooms(self, **kwargs):
                return {
                    "data": {
                        "rooms": [
                            {
                                "room_key": "other-1",
                                "room_code": "E2-101",
                                "room_path_cn": "科研楼E2/1层",
                                "capacity": 8,
                                "facilities": [],
                            },
                            {
                                "room_key": "preferred-1",
                                "room_code": "E1-201",
                                "room_path_cn": "科研楼E1/2层",
                                "capacity": 8,
                                "facilities": [
                                    {"facility_type_name_cn": "投影仪"}
                                ],
                            },
                            {
                                "room_key": "small-1",
                                "room_code": "E1-202",
                                "room_path_cn": "科研楼E1/2层",
                                "capacity": 2,
                                "facilities": [
                                    {"facility_type_name_cn": "投影仪"}
                                ],
                            },
                        ]
                    }
                }

            def room_detail(self, room_key, timeslot):
                if room_key == "preferred-1" and timeslot.endswith("1430"):
                    return {
                        "data": {
                            "timeslots": [
                                {
                                    "timeslot": "202611241400-202611241430",
                                    "state": "booked",
                                }
                            ]
                        }
                    }
                return {"data": {"timeslots": []}}

        original = tool_call.BookingClient
        tool_call.BookingClient = FakeClient
        try:
            result = tool_call.invoke(
                {
                    "tool": "find_slots",
                    "arguments": {
                        "date": "2026-11-24",
                        "window_start": "14:00",
                        "window_end": "15:00",
                        "duration_minutes": 30,
                        "step_minutes": 30,
                        "building_preferences": ["E1"],
                        "capacity_min": 4,
                        "required_facilities": ["投影"],
                        "limit": 2,
                    },
                }
            )
        finally:
            tool_call.BookingClient = original
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["data"]["slots"]), 1)
        self.assertEqual(result["data"]["slots"][0]["room"]["room_key"], "preferred-1")
        self.assertEqual(result["data"]["slots"][0]["start_time"], "2026-11-24 14:30")


if __name__ == "__main__":
    unittest.main()
