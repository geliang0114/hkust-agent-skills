# HKUST(GZ) Agent Skills

Reusable agent skills for HKUST(GZ) campus services and Outlook email. Each skill contains its connector and operating instructions.

- [Meeting room booking](skills/hkust-booking-agent/SKILL.md) requires a separately supplied short-lived `BOOKING_API_TOKEN`.
- [MyPortal calendar](skills/hkust-portal-calendar/SKILL.md) uses campus SSO credentials and a local session cookie.
- [Campus context](skills/hkust-campus-context/SKILL.md) reads public activities plus read-only MyPortal announcements, tasks, library loans, unread-mail count, and service links.

Python 3.9 or newer and `requests` are required. The services' private website interfaces can change. Do not commit credentials, tokens, cookies, or real personal data.

The calendar login and an empty-result query were tested with a real account. Event normalization has only been tested with synthetic data. Booking behavior depends on the current site and available authentication.

## Outlook via Microsoft Graph

[Outlook Graph](skills/outlook-graph/SKILL.md) is our own adapter for listing, searching and reading email, creating or editing drafts, and sending a reviewed draft after explicit confirmation. It requires a delegated Microsoft Graph OAuth access token; email credentials and tokens must never be committed. The Graph integration has mock tests but has not been validated against a real mailbox.
