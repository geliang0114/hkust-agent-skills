# HKUST(GZ) Agent Skills

Reusable agent skills for HKUST(GZ) campus services and Agent Mail. Each skill contains its connector and operating instructions.

- [Meeting room booking](skills/hkust-booking-agent/SKILL.md) requires a separately supplied short-lived `BOOKING_API_TOKEN`.
- [MyPortal calendar](skills/hkust-portal-calendar/SKILL.md) uses campus SSO credentials and a local session cookie.
- [Campus context](skills/hkust-campus-context/SKILL.md) reads public activities plus read-only MyPortal announcements, tasks, library loans, unread-mail count, and service links.

Python 3.9 or newer and `requests` are required. The services' private website interfaces can change. Do not commit credentials, tokens, cookies, or real personal data.

The calendar login and an empty-result query were tested with a real account. Event normalization has only been tested with synthetic data. Booking behavior depends on the current site and available authentication.

## Agent Mail

[Agent Mail](skills/agent-mail/SKILL.md) uses Tencent Agent Mail CLI to read an authorized user's dedicated inbox. Campus users can manually forward messages or configure a permitted Outlook rule to forward selected email. Follow the [setup guide](skills/agent-mail/references/setup.md) to create and authorize your own mailbox. This integration does not access the original Outlook mailbox and forwarding availability depends on the school's policy. Sending is provided separately by the official CLI and requires its authorization and confirmation workflow.
