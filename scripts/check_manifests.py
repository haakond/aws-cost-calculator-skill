"""Consistency checks between the Agent Skill and the plugin manifests.

Covers the Agent Plugins manifests used by Kiro and Cursor (plugin.json, mcp.json) and the Claude Code plugin files (.claude-plugin/*, .mcp.json).

Run from anywhere: python3 scripts/check_manifests.py
Exits non-zero with a message per mismatch.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "aws-cost-calculator"
REQUIRED_SERVERS = {"aws-pricing-calculator-mcp-server", "aws-knowledge-mcp-server"}
# Agent Plugins names the remote transport "streamable-http"; Claude Code's .mcp.json calls the same transport "http".
AGENT_PLUGINS_TO_CLAUDE_TYPE = {"streamable-http": "http"}


def as_claude_servers(servers: dict) -> dict:
    return {name: {**config, "type": AGENT_PLUGINS_TO_CLAUDE_TYPE.get(config.get("type"), config.get("type"))} for name, config in servers.items()}


def frontmatter_field(text: str, key: str) -> str | None:
    match = re.search(rf'^\s*{re.escape(key)}:\s*"?([^"\n]+?)"?\s*$', text, re.MULTILINE)
    return match.group(1) if match else None


def main() -> int:
    errors = []

    plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
    skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    skill_name = frontmatter_field(skill_md, "name")
    skill_version = frontmatter_field(skill_md, "version")

    if skill_name != SKILL_DIR.name:
        errors.append(f"SKILL.md name '{skill_name}' does not match directory '{SKILL_DIR.name}'")
    if plugin.get("name") != skill_name:
        errors.append(f"plugin.json name '{plugin.get('name')}' does not match skill name '{skill_name}'")
    if plugin.get("version") != skill_version:
        errors.append(f"plugin.json version '{plugin.get('version')}' does not match SKILL.md metadata.version '{skill_version}'")
    if plugin.get("license") != frontmatter_field(skill_md, "license"):
        errors.append("plugin.json license does not match SKILL.md license")

    missing = REQUIRED_SERVERS - set(mcp.get("mcpServers", {}))
    if missing:
        errors.append(f"mcp.json is missing servers: {sorted(missing)}")

    claude_plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    claude_marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    claude_mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))

    for field in ("name", "version", "license"):
        if claude_plugin.get(field) != plugin.get(field):
            errors.append(f".claude-plugin/plugin.json {field} '{claude_plugin.get(field)}' does not match plugin.json '{plugin.get(field)}'")
    if claude_mcp.get("mcpServers") != as_claude_servers(mcp.get("mcpServers", {})):
        errors.append(".mcp.json (Claude Code) and mcp.json (Kiro, Cursor) define different mcpServers")
    entries = claude_marketplace.get("plugins", [])
    if [entry.get("name") for entry in entries] != [plugin.get("name")]:
        errors.append("marketplace.json must list exactly the plugin named in plugin.json")

    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print("Manifests consistent with SKILL.md")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
