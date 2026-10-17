# Changelog

## 1.0.8 (2026-10-17)

### Added

- Relay, a local project delivery system for humans and AI agents, with multiple boards, Epics, isolated workspaces, ticket handoffs, validation evidence, Git evidence, and planning-session records.
- Relay AI Task Planner: a guided triage flow that launches Codex or Claude locally, gathers project context, proposes testable work, and waits for explicit user approval before creating an Epic and tickets in bulk.
- A reusable planning harness that prompts for unit tests, integration checks, documentation, and relevant security, accessibility, migration, rollout, and rollback work.
- MCP risk annotations for the tool catalog and improved `tool_search` discovery across the full tool set.

### Fixed

- Updated the webapp template response call for current Starlette compatibility.
- Bundled the MIT-licensed mitmproxy runtime from its audited upstream commit, avoiding an unpublished upstream dependency while keeping the Prompt Firewall on current security fixes.
