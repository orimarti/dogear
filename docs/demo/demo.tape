# Re-record with: vhs docs/demo/demo.tape   (from the repo root, after `uv sync`)
# Uses synthetic sessions and stand-in agents only; see setup.py.
Output docs/demo.gif

Require fzf
Require node

Set Shell "bash"
Set FontSize 19
Set Width 1280
Set Height 600
Set Padding 24
Set Theme "Dracula"
Set WindowBar Colorful
Set TypingSpeed 45ms

Hide
Type "source docs/demo/env.sh" Enter
Sleep 2s
Show

# Inside an agent session: bookmark it
Type "cd ~/code/jobs-api && claude" Enter
Sleep 1.2s
Type "/dogear jobs-api -t work" Sleep 400ms Enter
Sleep 2.5s
Type "/exit" Enter
Sleep 600ms

# Later, from anywhere
Type "cd ~ && dogear ls" Enter
Sleep 3.5s

# Pick one and land back in it, in the right folder
Type "dogear" Enter
Sleep 1.5s
Type "jobs" Sleep 900ms Enter
Sleep 2.5s
Type "/exit" Enter
Sleep 600ms

# Codex sessions live in the same list
Type "dogear open docs-site" Enter
Sleep 3s
