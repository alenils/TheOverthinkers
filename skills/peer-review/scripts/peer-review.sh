#!/usr/bin/env bash
# peer-review.sh — Run a peer-review prompt via the best available CLI.
# Dumb pipe: sends a prompt to an external LLM and returns its stdout.
#
# CLI chain:
#   1. command-code (primary)
#   2. agy (fallback)
#   3. mimo (fallback)
#   4. Exit 3 → signals the agent to run the peer as a native subagent
#
# Usage:
#   scripts/peer-review.sh "<prompt>"
#   echo "<prompt>" | scripts/peer-review.sh
#
# Exit codes: 0 success | 1 no prompt | 3 no usable CLI

set -uo pipefail

# Harvest PATH additions from shell profiles (nvm/fnm/volta/homebrew)
set +e
for profile in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.zprofile ~/.profile; do
  [[ -f "$profile" ]] || continue
  harvested=$(bash -c 'set +u; source "$1" >/dev/null 2>&1; printf %s "$PATH"' bash "$profile" 2>/dev/null)
  case "$harvested" in
    ""|"$PATH"|*$'\n'*) : ;;
    *)
      additive=1
      oldIFS=$IFS; IFS=:
      for entry in $PATH; do
        [ -n "$entry" ] || continue
        case ":$harvested:" in *":$entry:"*) : ;; *) additive=0 ;; esac
      done
      IFS=$oldIFS
      [ "$additive" = 1 ] && PATH="$harvested"
      ;;
  esac
done
set -e

# Support passing skill dir as optional first argument
if [[ -n "${1:-}" && -d "$1" ]]; then
  shift
fi

# cd to workspace root
WORKDIR="${PEER_REVIEW_WORKDIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$WORKDIR" || { echo "Error: Failed to cd to '$WORKDIR'" >&2; exit 1; }

PROMPT="${1:-}"
if [[ -z "$PROMPT" ]]; then PROMPT=$(cat); fi
if [[ -z "$PROMPT" ]]; then
  echo "Usage: peer-review.sh \"<prompt>\" or pipe a prompt via stdin" >&2
  exit 1
fi

TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT
printf '%s\n' "$PROMPT" > "$TMPFILE"

run_timeout() {
    if command -v timeout >/dev/null 2>&1; then
        timeout "$@"
    elif command -v gtimeout >/dev/null 2>&1; then
        gtimeout "$@"
    else
        perl -e 'alarm shift; exec @ARGV or exit 127' -- "$@"
    fi
}

try_cli() {
    local cli="$1"; shift
    local prompt_file="$1"; shift

    case "$cli" in
        command-code)
            run_timeout 180 command-code -p "$(cat "$prompt_file")" --tools-all --skip-onboarding -t </dev/null 2>/dev/null
            ;;
        agy)
            run_timeout 180 agy -p "$(cat "$prompt_file")" --dangerously-skip-permissions --print-timeout 180s </dev/null 2>/dev/null
            ;;
        mimo)
            run_timeout 180 mimo run "$(cat "$prompt_file")" </dev/null 2>/dev/null
            ;;
        *)
            return 1
            ;;
    esac
}

set +e
for CLI in command-code agy mimo; do
    if ! command -v "$CLI" &>/dev/null; then
        continue
    fi

    OUTPUT=$(try_cli "$CLI" "$TMPFILE" 2>&1)
    EC=$?

    if [ $EC -eq 0 ] && [ -n "$OUTPUT" ]; then
        printf '%s\n' "$OUTPUT"
        exit 0
    fi
    echo "Warning: $CLI failed (exit $EC), trying next" >&2
done
set -e

INSTALLED=0
for CLI in command-code agy mimo; do
    command -v "$CLI" &>/dev/null && INSTALLED=$((INSTALLED + 1))
done

if [ "$INSTALLED" -eq 0 ]; then
    echo "No peer CLI installed (checked: command-code, agy, mimo). Fall back to native subagent." >&2
else
    echo "All $INSTALLED installed peer CLI(s) failed. Fall back to native subagent." >&2
fi
exit 3
