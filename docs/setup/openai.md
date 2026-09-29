# GPT / OpenAI client integration

## MCP Hub client setup

Open **MCP Hub → Clients**, select **GPT / OpenAI Codex**, choose your tools, and click **Apply**. Install the Codex CLI first and make sure `codex` is available on PATH. Apply writes `~/.codex/config.toml` (or `$CODEX_HOME/config.toml`) using the Codex TOML editor, preserving other server entries and settings. Invalid existing TOML is left untouched. Restart your Codex session to load the server.

This is the Codex MCP client integration; the separate OpenAI SDK connection below routes API traffic through the firewall.

## OpenAI API firewall setup

In the dashboard Firewall tab, start the proxy, then choose **Connect** beside **GPT / OpenAI SDK**. On macOS this sets `OPENAI_BASE_URL` in shell profiles and launchctl. Restart your API application in a new terminal. The default endpoint is:

```sh
export OPENAI_BASE_URL="http://127.0.0.1:8766/openai/v1"
```

Use your own `OPENAI_API_KEY` as usual. The Python OpenAI SDK reads this base URL; applications with an explicit `base_url` must set it to the same endpoint. Both `client.responses.create(...)` and `client.chat.completions.create(...)` requests are supported. No OpenAI SDK dependency is needed by the firewall itself.

This connection covers OpenAI API applications. It does not configure ChatGPT web conversations. Codex MCP setup is available separately in MCP Hub → Clients. Client transport, authentication, and MCP configuration are separate concerns.

## Custom replacement text

Under Firewall → Settings → **Redaction Replacement**, enter a label such as `[PRIVATE]`, then save. All deterministic detections use that exact literal text. Leave the field blank to restore typed defaults such as `[REDACTED_EMAIL]`. The setting is limited to 200 characters and persists across restarts. Optional local LLM review may produce its own replacement wording.

## Coverage and limits

The HTTP and TLS proxies share field-level sanitization of Claude messages, GPT Chat Completions, Responses `input` and `instructions`, text blocks, and tool argument/result text. Request IDs, model names, and image/audio binary fields are preserved. Binary files, images, audio, remote URLs, and server-side conversation history are not inspected. The plain HTTP proxy does not handle WebSockets; the TLS proxy handles outgoing JSON text frames for supported model hosts. HTTP responses, including SSE, stream through without buffering the whole reply.

Block mode rejects detected sensitive text before forwarding. If enabled local review is unavailable, block mode also rejects the request; redact mode retains deterministic protection. New audit findings retain original matched values locally. The Audit Log hides originals by default; enable **Reveal original matched values** to inspect original → replacement pairs. Use **Blocked / errors** or **Sanitized** to filter entries. Older entries without saved originals show them as unavailable. Clear the audit log to remove saved matches. Optional prompt recording still captures request text locally, so treat recordings as sensitive data and clear them when no longer needed.

Official request examples: [OpenAI text generation](https://developers.openai.com/api/docs/guides/text).

## Codex with ChatGPT login

MCP registration alone does not route model traffic. In Firewall, install the system proxy certificate and start the TLS proxy, then click **Connect** beside **GPT / Codex (ChatGPT login)**. This sets `HTTPS_PROXY` for newly launched macOS apps and terminal sessions. Fully quit and reopen Codex. Environment-aware HTTPS clients will use the local proxy; confirm a fresh `chatgpt.com` recording after a test prompt. A configured environment variable is not proof that an application used it.

The TLS firewall inspects HTTP requests to `chatgpt.com/backend-api/codex/responses` (including compact requests) and outgoing JSON text WebSocket frames at that endpoint or supported API hosts. Incoming WebSocket responses pass through. Blocked WebSocket prompts close the connection. Other ChatGPT website endpoints, binary WebSocket messages, images/audio, and server-side history are outside this coverage. Applications which ignore proxy environment variables need their own proxy configuration.

## Network proxy recovery

When system interception is installed, AgenticStore saves each macOS network service's previous HTTP and HTTPS proxy settings before changing them. Normal server shutdown (including Ctrl+C), explicit Stop/Uninstall, and failed installation restore those settings before the local listener stops. An independent watchdog checks the server and listener; if either disappears unexpectedly, it restores the saved settings. A hard OS shutdown or a failure of `networksetup` itself cannot be guaranteed recoverable; restarting AgenticStore retries restoration. The plain API proxy never enables a macOS system proxy without a trusted TLS certificate. An occupied dashboard port causes a visible error instead of terminating another process.
