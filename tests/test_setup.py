import json
from importlib.resources import files

from dogear.cli import Context, main


def run(argv, **kw):
    ctx = Context.for_test(**kw)
    return main(argv, ctx), ctx


def asset(name):
    return (files("dogear") / "assets" / name).read_bytes()


def tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def test_setup_claude_writes_skill(homes):
    code, ctx = run(["setup", "claude"])
    assert code == 0, ctx.stderr.getvalue()
    target = homes.claude / "skills" / "dogear" / "SKILL.md"
    assert target.read_bytes() == asset("claude_skill.md")
    out = ctx.stdout.getvalue()
    assert str(target) in out and "/dogear" in out
    assert tree(homes.claude) == ["skills", "skills/dogear", "skills/dogear/SKILL.md"]


def test_setup_claude_refuses_overwrite(homes):
    run(["setup", "claude"])
    target = homes.claude / "skills" / "dogear" / "SKILL.md"
    target.write_text("mine", encoding="utf-8")
    code, ctx = run(["setup", "claude"])
    assert code == 1 and "--force" in ctx.stderr.getvalue()
    assert target.read_text(encoding="utf-8") == "mine"
    assert run(["setup", "claude", "--force"])[0] == 0
    assert target.read_bytes() == asset("claude_skill.md")


def test_setup_claude_warns_about_plugin(homes):
    plugins = homes.claude / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {"dogear@dogear": [{}]}}), encoding="utf-8")
    code, ctx = run(["setup", "claude"])
    assert code == 0 and "plugin" in ctx.stderr.getvalue()
    assert (plugins / "installed_plugins.json").read_text(encoding="utf-8").startswith('{"version": 2')


def test_setup_claude_no_warning_without_plugin(homes):
    code, ctx = run(["setup", "claude"])
    assert "plugin" not in ctx.stderr.getvalue()


def test_setup_codex(homes):
    code, ctx = run(["setup", "codex"])
    assert code == 0, ctx.stderr.getvalue()
    skill = homes.codex / "skills" / "dogear"
    assert (skill / "SKILL.md").read_bytes() == asset("codex_skill.md")
    assert (skill / "agents" / "openai.yaml").read_bytes() == asset("codex_openai.yaml")
    assert "$dogear" in ctx.stdout.getvalue()
    assert tree(homes.codex) == ["skills", "skills/dogear", "skills/dogear/SKILL.md", "skills/dogear/agents", "skills/dogear/agents/openai.yaml"]


def test_setup_codex_refuses_overwrite(homes):
    run(["setup", "codex"])
    code, ctx = run(["setup", "codex"])
    assert code == 1 and "--force" in ctx.stderr.getvalue()


def test_setup_touches_nothing_else(homes):
    run(["setup", "claude"])
    assert tree(homes.codex) == [] and tree(homes.dogear) == []
