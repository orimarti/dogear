import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv")
def test_wheel_contains_assets(tmp_path):
    subprocess.run(["uv", "build", "--wheel", "-o", str(tmp_path), str(ROOT)], check=True, capture_output=True)
    [wheel] = tmp_path.glob("dogear-*.whl")
    names = set(zipfile.ZipFile(wheel).namelist())
    for asset in ("claude_skill.md", "codex_skill.md", "codex_openai.yaml"):
        assert f"dogear/assets/{asset}" in names


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


@pytest.mark.skipif(not (ROOT / ".git").exists(), reason="needs a git checkout")
def test_no_personal_data():
    """Nothing in the repo mentions the machine's real home directory or the git user's email."""
    try:  # HOME is redirected by the autouse fixture, so ask the OS for the real one
        import pwd

        real_home = pwd.getpwuid(os.getuid()).pw_dir
    except (ImportError, KeyError):  # Windows: only the email check applies
        real_home = ""
    needles = [n for n in (real_home, _git("config", "user.email")) if n and len(n) > 3]
    offenders = []
    for name in _git("ls-files").splitlines():
        path = ROOT / name
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        offenders += [f"{name}: {n}" for n in needles if n in text]
    assert offenders == []


@pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv")
def test_sdist_contains_only_project_files(tmp_path):
    """Local ignores (.git/info/exclude, global gitignore) must not leak into the sdist."""
    import tarfile

    subprocess.run(["uv", "build", "--sdist", "-o", str(tmp_path), str(ROOT)], check=True, capture_output=True)
    [sdist] = tmp_path.glob("dogear-*.tar.gz")
    tops = {n.split("/", 2)[1] for n in tarfile.open(sdist).getnames() if n.count("/") >= 1}
    assert tops <= {"src", "tests", "pyproject.toml", "README.md", "LICENSE", "PKG-INFO", ".gitignore"}
