import pytest

from dogear.config import load_config, split_command
from dogear.errors import DogearError


def test_missing_file_gives_defaults(homes):
    cfg = load_config()
    assert cfg.commands == {"claude": "claude", "codex": "codex"}
    assert cfg.use_fzf == "auto"


def test_custom_command(homes):
    homes.dogear.mkdir()
    (homes.dogear / "config.toml").write_text(
        '[claude]\ncommand = "claude --dangerously-skip-permissions"\n[picker]\nuse_fzf = "never"\n'
    )
    cfg = load_config()
    assert split_command(cfg.commands["claude"]) == ["claude", "--dangerously-skip-permissions"]
    assert cfg.commands["codex"] == "codex"
    assert cfg.use_fzf == "never"


def test_bad_use_fzf(homes):
    homes.dogear.mkdir()
    (homes.dogear / "config.toml").write_text('[picker]\nuse_fzf = "sometimes"\n')
    with pytest.raises(DogearError, match="use_fzf"):
        load_config()


def test_broken_toml_names_file(homes):
    homes.dogear.mkdir()
    (homes.dogear / "config.toml").write_text("[claude\n")
    with pytest.raises(DogearError, match="config.toml"):
        load_config()


def test_empty_command_rejected(homes):
    homes.dogear.mkdir()
    (homes.dogear / "config.toml").write_text('[codex]\ncommand = "  "\n')
    with pytest.raises(DogearError, match="codex"):
        load_config()
