import json
from importlib.resources import files
from pathlib import Path

import dogear

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "dogear"


def asset(name):
    return (files("dogear") / "assets" / name).read_text(encoding="utf-8")


def test_plugin_skill_is_the_setup_skill():
    assert (PLUGIN / "skills" / "dogear" / "SKILL.md").read_text(encoding="utf-8") == asset("claude_skill.md")


def test_plugin_version_matches_package():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "dogear"
    assert manifest["version"] == dogear.__version__


def test_marketplace_lists_plugin():
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    [entry] = market["plugins"]
    assert market["name"] == "dogear" and market["owner"]["name"]
    assert entry["name"] == manifest["name"]
    assert (ROOT / entry["source"]).resolve() == PLUGIN.resolve()


def test_skills_mention_install_hint_and_command():
    for name in ("claude_skill.md", "codex_skill.md"):
        text = asset(name)
        assert text.startswith("---\nname: dogear\n")
        assert "dogear add" in text
        assert "uv tool install dogear" in text


def test_claude_skill_is_user_invoked_only():
    text = asset("claude_skill.md")
    assert "disable-model-invocation: true" in text
    assert "$ARGUMENTS" in text


def test_codex_skill_not_implicit():
    assert "allow_implicit_invocation: false" in asset("codex_openai.yaml")
