# Relay ticket files

The Relay webapp accepts screenshots and other files (up to 10 MB each) when creating a ticket or posting a progress update. Files are stored beside the board JSON under `<board-name>.media/<ticket-id>/<attachment-id>`. They are local data; back up this directory with the board JSON, and do not commit it.

The `task_board` `get` action returns each file's id, original name (`label`), MIME type, size, and absolute local `reference` path. Agents can open that path directly. For clients without local filesystem access, call `read_attachment` with `path`, `id`, and `attachment_id`; its `data_base64` field contains the file bytes. The agent handoff harness asks agents to inspect attachments before work.

To attach a file through an MCP client such as Codex, call `task_board` with `action="attach_file"`, the board `path`, ticket `id`, `file_name`, base64 encoded `data_base64`, and `confirm_write=true`. The webapp uses its binary upload endpoint automatically. No API key is required.
