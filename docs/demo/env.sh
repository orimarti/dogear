# Sourced (hidden) at the start of demo.tape: a throwaway HOME with synthetic
# sessions, stand-in agents on PATH, and the repo's dogear.
repo=$(pwd)
DEMO_HOME=${DEMO_HOME:-$(mkdir -p /tmp/dogear-demo && cd /tmp/dogear-demo && pwd -P)/home}  # short and resolved, so ~ abbreviates
"$repo/.venv/bin/python" "$repo/docs/demo/setup.py" "$DEMO_HOME" || return
unset CLAUDE_CONFIG_DIR CODEX_HOME DOGEAR_HOME XDG_CONFIG_HOME PROMPT_COMMAND
export HOME=$DEMO_HOME
export PATH="$HOME/.demo/bin:$repo/.venv/bin:$PATH"
export BASH_SILENCE_DEPRECATION_WARNING=1
export PS1='\[\e[38;5;117m\]\w\[\e[0m\] $ '
cd ~ && clear
