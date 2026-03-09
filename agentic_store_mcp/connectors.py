"""
connectors.py — registry of all known external service connectors.

A Connector defines:
  - What service it connects to (GitHub, OpenAI, etc.)
  - What credentials it needs (fields)
  - How secrets are stored (via secrets.set_token("{slug}_{field_name}", value))
  - How to test the connection

Tool schemas declare connector dependencies via:
  "connectors": ["github"]

Adding a new connector: add one Connector(...) entry to REGISTRY below.
No other files need changing until you build tools that use it.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConnectorField:
    name: str           # storage key suffix: set_token(f"{slug}_{name}", value)
    label: str          # human label for webapp form
    description: str    # shown below the input
    secret: bool        # True → password input + keyring storage
    required: bool      # False → optional (e.g. GitHub token for public repos)
    placeholder: str    # example value shown in the form
    env_var: str        # conventional env var name (checked by secrets.get_token)


@dataclass
class Connector:
    slug: str               # e.g. "github" — must match schema.json "connectors" entries
    name: str               # display name: "GitHub"
    description: str        # one-sentence purpose
    docs_url: str           # link to credential setup docs
    fields: list[ConnectorField] = field(default_factory=list)
    test_supported: bool = True


# ─── Registry ─────────────────────────────────────────────────────────────────

REGISTRY: dict[str, Connector] = {
    "github": Connector(
        slug="github",
        name="GitHub",
        description="Access GitHub repos, issues, PRs, Dependabot alerts, and code scanning findings.",
        docs_url="https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens",
        fields=[
            ConnectorField(
                name="token",
                label="Personal Access Token",
                description="Classic PAT or fine-grained token with 'repo' scope. Public repos work without a token.",
                secret=True,
                required=False,
                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx",
                env_var="GITHUB_TOKEN",
            ),
        ],
    ),

    "openai": Connector(
        slug="openai",
        name="OpenAI",
        description="Use OpenAI APIs (GPT models, embeddings, etc.) from agent tools.",
        docs_url="https://platform.openai.com/api-keys",
        fields=[
            ConnectorField(
                name="api_key",
                label="API Key",
                description="Secret key from the OpenAI platform dashboard.",
                secret=True,
                required=True,
                placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx",
                env_var="OPENAI_API_KEY",
            ),
        ],
    ),

    "anthropic": Connector(
        slug="anthropic",
        name="Anthropic",
        description="Use Claude models via the Anthropic API.",
        docs_url="https://console.anthropic.com/account/keys",
        fields=[
            ConnectorField(
                name="api_key",
                label="API Key",
                description="Secret key from the Anthropic console.",
                secret=True,
                required=True,
                placeholder="sk-ant-xxxxxxxxxxxxxxxxxxxx",
                env_var="ANTHROPIC_API_KEY",
            ),
        ],
    ),

    "linear": Connector(
        slug="linear",
        name="Linear",
        description="Read and write Linear issues, projects, and cycles.",
        docs_url="https://linear.app/settings/api",
        fields=[
            ConnectorField(
                name="api_key",
                label="API Key",
                description="Personal API key from Linear Settings → API.",
                secret=True,
                required=True,
                placeholder="lin_api_xxxxxxxxxxxxxxxxxxxx",
                env_var="LINEAR_API_KEY",
            ),
        ],
    ),
}


def get(slug: str) -> Connector | None:
    """Return a connector by slug, or None if not found."""
    return REGISTRY.get(slug)


def all_connectors() -> list[Connector]:
    """Return all registered connectors."""
    return list(REGISTRY.values())
