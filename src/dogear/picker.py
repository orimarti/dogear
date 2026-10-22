"""Choose one row: fzf when available, a numbered list otherwise."""

from __future__ import annotations

from dogear.errors import DogearError

ATTEMPTS = 3


def _clean(text: str) -> str:
    return " ".join(text.replace("\t", " ").split())


def pick(rows: list[str], *, ctx, use_fzf: str, prompt: str, previews: list[str] | None = None) -> int | None:
    if not rows:
        return None
    if not ctx.stdin_isatty:
        raise DogearError("no TTY for the picker")
    fzf = ctx.which("fzf") if use_fzf != "never" else None
    if use_fzf == "always" and not fzf:
        raise DogearError("use_fzf = \"always\" but fzf is not on PATH")
    if fzf:
        return _pick_fzf(fzf, rows, ctx, prompt, previews)
    return _pick_numbered(rows, ctx, prompt)


def _pick_fzf(fzf: str, rows: list[str], ctx, prompt: str, previews: list[str] | None) -> int | None:
    lines = []
    for i, row in enumerate(rows):
        fields = [str(i), _clean(row)]
        if previews:
            fields.append(_clean(previews[i]))
        lines.append("\t".join(fields))
    args = [fzf, "--delimiter=\t", "--with-nth=2", "--reverse", "--height=40%", f"--prompt={prompt}> "]
    if previews:
        args += ["--preview=echo {3}", "--preview-window=down:3:wrap"]
    code, out = ctx.run_fzf(args, "\n".join(lines) + "\n")
    if code != 0 or not out.strip():
        return None
    first = out.split("\t", 1)[0].strip()
    return int(first) if first.isdigit() and int(first) < len(rows) else None


def _pick_numbered(rows: list[str], ctx, prompt: str) -> int | None:
    width = len(str(len(rows)))
    for i, row in enumerate(rows, 1):
        print(f"{i:>{width}}  {row}", file=ctx.stderr)
    for _ in range(ATTEMPTS):
        print(f"{prompt} [1-{len(rows)}, Enter to cancel]: ", end="", file=ctx.stderr, flush=True)
        line = ctx.stdin.readline()
        if not line or not line.strip():
            return None
        choice = line.strip()
        if choice.isdigit() and 1 <= int(choice) <= len(rows):
            return int(choice) - 1
        print(f"not a number between 1 and {len(rows)}", file=ctx.stderr)
    return None
