# HKUST(GZ) Agent Skills

Three reusable skills for the HKUST(GZ) campus: meeting room booking, read-only MyPortal calendar queries, and read-only campus context. Each skill contains its connector and operating instructions.

- [Meeting room booking](skills/hkust-booking-agent/SKILL.md) requires a separately supplied short-lived `BOOKING_API_TOKEN`.
- [MyPortal calendar](skills/hkust-portal-calendar/SKILL.md) uses campus SSO credentials and a local session cookie.
- [Campus context](skills/hkust-campus-context/SKILL.md) reads public activities plus read-only MyPortal announcements, tasks, library loans, unread-mail count, and service links.

Python 3.9 or newer and `requests` are required. The services' private website interfaces can change. Do not commit credentials, tokens, cookies, or real personal data.

The calendar login and an empty-result query were tested with a real account. Event normalization has only been tested with synthetic data. Booking behavior depends on the current site and available authentication.

## Microsoft Outlook / Microsoft 365 MCP

The upstream [ryaker/outlook-mcp](https://github.com/ryaker/outlook-mcp) source is vendored at [integrations/outlook-mcp](integrations/outlook-mcp/README.md), pinned to commit `95d6ff2d248903c086f17782c2de28e16016e6aa`. Its `package.json` declares MIT; the upstream snapshot does not contain a separate LICENSE file. See [integration notes](integrations/OUTLOOK.md) for setup and authorization boundaries.

The server offers email reading as well as write-capable tools. Vendoring it does not install or connect an MCP server, approve Microsoft Graph permissions, or authenticate an account.
