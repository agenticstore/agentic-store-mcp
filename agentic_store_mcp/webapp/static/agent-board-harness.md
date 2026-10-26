# Relay Harness

Use this workflow whenever you receive a Relay handoff.

## Start

1. Read the assigned ticket and the latest handoff, comments, acceptance criteria, blockers, Git evidence, and validations.
2. Post a short `task_board` comment before changing files: what you understood, the working branch, and the first verification step.
3. Work only in the supplied workspace. Do not change the board path or ticket ID.

## Branch and commit rules

Follow the branch rules supplied with the handoff. If none were supplied, create a `feature/<ticket-id>-<short-slug>` branch before edits. Keep commits focused. Before every commit, run the applicable lint or static checks; run relevant tests before marking work complete. Never commit secrets, local recordings, local memory, credentials, or generated private data. Before committing and again before closing a ticket as done, draft a concise potential PR description covering the outcome, key changes, validation, and remaining risks; add it to the ticket as a `task_board` comment so a reviewer can use it directly.

## Evidence and callbacks

Use `task_board` with the supplied board path and ticket ID. Every modifying call needs `confirm_write=true`.

- `comment`: progress, decisions, useful command results, and blockers.
- `record_validation`: lint, tests, build, type checks, or review result. Mark failures as `failed`.
- `attach_git_evidence`: attach branch, commit, diff stat, and files after meaningful work.
- `handoff_ticket`: use if another agent should continue; name the next agent and give a concise next step.
- `complete_ticket`: only after acceptance criteria have validation evidence. If requirements are unclear or blocked, do not mark complete; add a comment and move it to `blocked` when appropriate.

Keep comments concise and factual. Include paths, commit identifiers, command outcomes, risks, and missing evidence rather than pasting large logs. Finish with a final comment that states the outcome, tests run, and remaining risks.
