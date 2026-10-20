# Relay screen recording runbook

Use this flow to show the complete Relay loop: create work, plan with AI, triage several tickets, and watch the work stay connected to the board.

## Start the published build

From the repository root:

```bash
./scripts/launch_relay_demo.sh
```

The script installs the selected PyPI version into `/private/tmp`, starts the UI on `http://127.0.0.1:8782/#relay`, opens that URL, and leaves the server running until you stop it with `Ctrl-C`. Set `AGENTICSTORE_VERSION` or `RELAY_PORT` when recording another release or using a different port.

## Recording sequence

1. Open Relay and show the board selector, the Admin and Agent perspectives, and the empty activity state.
2. Use **Add work** three times to create three small, independent tickets. Good demo work is:
   - Add a health endpoint and a focused API test.
   - Improve the settings screen empty state and add an accessibility check.
   - Add a release checklist document and validate the published package metadata.
   Keep them unassigned and in Todo so the triage view can pick them up.
3. Switch to **Agent** and show the Codex and Claude cards. Launch triage for both clients. Relay divides the unassigned tickets, records a session ID on each ticket, and opens local terminal sessions in parallel.
4. Return to the board and open a ticket. Show its timestamped triage comment, current owner, activity timeline, and the option to move, hand off, or record evidence.
5. Click **AI task planner**. Use a prompt such as:

   ```text
   Prepare the next release of the Relay demo experience. Make the board easy to understand for a first-time user, keep local data private, and leave a clear validation trail. Create exactly one Epic with exactly two child tickets: one for the product changes and one for validation and release readiness. Include the web changes, API or state changes, tests, documentation, accessibility checks, and release verification needed for a safe demo.
   ```

   Select **New feature**, enable Unit tests, Integration checks, Documentation, and Accessibility, choose Web plus MCP, and use Codex as the planning agent.
6. In the terminal session, let the planner inspect the board and propose one Epic with bounded child tickets. Approve the plan explicitly. Relay then creates the Epic and its tickets in bulk. Show the planning record and the new Epic view.
7. Launch triage again. The original three tickets and the two planner-created tickets can now be distributed across the available agent sessions. Show the board changing while the terminal sessions work in parallel.
8. Finish by opening one completed or in-review ticket and show its comments, validation evidence, Git evidence, and handoff session. This makes the audit trail visible rather than ending on a spinner.

The planner is intentionally gated: it proposes work first and only writes the Epic and tickets after an explicit approval in the terminal.
