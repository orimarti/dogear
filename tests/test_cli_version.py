import os
import subprocess
import sys

from dogear import __version__
from dogear.cli import Context, main


def test_version_flag():
    ctx = Context.for_test()
    assert main(["--version"], ctx) == 0
    assert ctx.stdout.getvalue() == f"dogear {__version__}\n"


def test_module_runs():
    r = subprocess.run([sys.executable, "-m", "dogear", "--version"], capture_output=True, text=True)
    assert r.returncode == 0
    assert r.stdout.strip() == f"dogear {__version__}"


def test_env_isolated(tmp_path):
    assert os.environ["CLAUDE_CONFIG_DIR"].startswith(str(tmp_path))
    assert os.environ["CODEX_HOME"].startswith(str(tmp_path))
    assert os.environ["DOGEAR_HOME"].startswith(str(tmp_path))
