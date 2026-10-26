# Changelog

## 1.0.11 (2026-10-26)

- Relay: attach screenshots and files up to 10 MB to tickets and progress updates, with agent-readable attachment metadata and bytes.
- Relay: improve the planner, board layout, and ticket drawer; add checkable acceptance criteria and readable Markdown activity.
- Relay: link recorded Git branches and commits, and clarify the isolated-workspace and coordinated PyPI release workflow.

## 1.0.10 (2026-10-25)

- Relay: add an Archived ticket state with restore-to-Ready support and history entries.
- Relay: hide archived work by default and add a Show archived board toggle.
- Relay: require a workspace when creating tickets so agent handoffs have a known checkout.
- Relay: add guided empty-workspace setup and inline form errors for ticket and handoff failures.
- Relay: improve the product title and empty-state messaging in the webapp.

## 1.0.9 (2026-10-17)

### Fixed

- Re-released Relay with the official `mitmproxy` PyPI runtime, keeping the package lean and installable from PyPI without a Git-only dependency.

## 1.0.8 (2026-10-17)

### Added

- Relay, a local project delivery system for humans and AI agents, with multiple boards, Epics, isolated workspaces, ticket handoffs, validation evidence, Git evidence, and planning-session records.
- Relay AI Task Planner: a guided triage flow that launches Codex or Claude locally, gathers project context, proposes testable work, and waits for explicit user approval before creating an Epic and tickets in bulk.
- A reusable planning harness that prompts for unit tests, integration checks, documentation, and relevant security, accessibility, migration, rollout, and rollback work.
- MCP risk annotations for the tool catalog and improved `tool_search` discovery across the full tool set.

### Fixed

- Updated the webapp template response call for current Starlette compatibility.
- Refreshed runtime dependency constraints and the exported production requirements file.
- Initial Relay release. This version was superseded by 1.0.9 after a packaging correction.
