# HKUST(GZ) Agent Skills

Two reusable skills for the HKUST(GZ) campus: meeting room booking and read-only MyPortal calendar queries. Each skill contains its connector and operating instructions.

- [Meeting room booking](skills/hkust-booking-agent/SKILL.md) requires a separately supplied short-lived `BOOKING_API_TOKEN`.
- [MyPortal calendar](skills/hkust-portal-calendar/SKILL.md) uses campus SSO credentials and a local session cookie.

Python 3.9 or newer and `requests` are required. The services' private website interfaces can change. Do not commit credentials, tokens, cookies, or real personal data.

The calendar login and an empty-result query were tested with a real account. Event normalization has only been tested with synthetic data. Booking behavior depends on the current site and available authentication.
