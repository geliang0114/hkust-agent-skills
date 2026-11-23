# Outlook MCP integration

This directory vendors [ryaker/outlook-mcp](https://github.com/ryaker/outlook-mcp) at commit `95d6ff2d248903c086f17782c2de28e16016e6aa`. Source is preserved in `outlook-mcp/`; upstream `package.json` states MIT, and upstream does not provide a separate LICENSE file. This is a vendored snapshot, not a GitHub fork or a configured MCP service.

The upstream project implements Microsoft Graph email list, search and full-body read tools (`list-emails`, `search-emails`, `read-email`) and calendar operations. It also exposes tools that send, delete and modify emails and calendar events, OneDrive, and Power Automate; applications embedding it must apply their own authorization and tool access policies.

## Setup

Requires Node.js and npm. In `integrations/outlook-mcp`, run `npm ci`, then configure a Microsoft Entra application and authorize the required delegated Graph scopes. Follow the upstream [README](outlook-mcp/README.md) for the auth server, client ID, secret and tenant configuration. Provision secrets through the host environment; do not commit `.env`, cookies or tokens. A school account may require administrator consent under its tenant policy. No valid authorization or successful live email query is established merely by copying this project.

To register the upstream server in an MCP host, adapt the following with an absolute path and inject credentials through the host's secure environment mechanism:

```json
{"mcpServers":{"m365-assistant":{"command":"node","args":["/absolute/path/to/hkust-agent-skills/integrations/outlook-mcp/index.js"],"env":{"USE_TEST_MODE":"false"}}}}
```

The upstream auth server and token refresh have additional `MS_*` environment configuration; see its documentation. Verify host compatibility and complete OAuth before treating the connector as operational. The repo's HKUST portal calendar and campus context skills remain separate; an agent can combine them after both MCP and MyPortal are authorized.
