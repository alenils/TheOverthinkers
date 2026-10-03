#!/usr/bin/env bash
# leak-scan.sh — identity / PII / health gate for The Overthinkers repo.
# Secrets are delegated to gitleaks; this script owns identity, path and health patterns.
#
# Usage:
#   leak-scan.sh [options] <dir|->      scan a directory, or stdin (`git log -p | leak-scan.sh -`)
#
# Options:
#   -p, --patterns FILE   shape patterns (default: <script_dir>/leak-patterns.tsv)
#       --patterns-extra FILE
#                         value patterns (out-of-tree identifiers)
#       --no-gitleaks     skip the gitleaks pass
#       --quiet           summary only
#
# Exit: 0 clean | 1 hits found | 2 usage or setup error

set -uo pipefail

# ---- PCRE engine ------------------------------------------------------------
if printf 'pcre-probe' | grep -qP 'pcre-probe' 2>/dev/null; then
  PCRE_ENGINE="grep"
elif command -v perl >/dev/null 2>&1; then
  PCRE_ENGINE="perl"
else
  echo "error: no PCRE-capable engine — this gate needs GNU grep (-P) or perl." >&2
  exit 2
fi

pcre_compiles() {
  case "$PCRE_ENGINE" in
    grep) grep -qP -e "$1" /dev/null 2>/dev/null; [ "$?" -le 1 ];;
    perl) perl -e 'exit(eval { qr/$ARGV[0]/ } ? 0 : 2)' "$1" 2>/dev/null;;
  esac
}

pcre_lines() {
  case "$PCRE_ENGINE" in
    grep) grep -nP -e "$1" "${@:2}";;
    perl) perl -ne 'BEGIN { $re = eval { qr/$ARGV[0]/ } or exit 2; shift } s/\n\z//; print "$.:$_\n" if /$re/' "$1" "${@:2}";;
  esac
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATTERNS="$SCRIPT_DIR/leak-patterns.tsv"
PATTERNS_EXTRA="${LEAK_PATTERNS_EXTRA:-}"
TARGET=""
USE_GITLEAKS=1
QUIET=0
EXCLUDED=0

while [ $# -gt 0 ]; do
  case "$1" in
    -p|--patterns) PATTERNS="${2:-}"; shift 2;;
    --patterns-extra) PATTERNS_EXTRA="${2:-}"; shift 2;;
    --no-gitleaks) USE_GITLEAKS=0; shift;;
    --quiet)       QUIET=1; shift;;
    -h|--help)     sed -n '2,15p' "$0"; exit 0;;
    -)             TARGET="$1"; shift;;
    -*)            echo "unknown option: $1" >&2; exit 2;;
    *)             TARGET="$1"; shift;;
  esac
done

[ -n "$TARGET" ] || { echo "usage: leak-scan.sh [options] <dir|->" >&2; exit 2; }
[ -f "$PATTERNS" ] || { echo "pattern file not found: $PATTERNS" >&2; exit 2; }

validate_pattern_file() {
  local _file="$1" _pn _pe _px _bad=""
  while IFS=$'\t' read -r _pn _pe _px; do
    _pn="${_pn#"${_pn%%[![:space:]]*}"}"
    case "$_pn" in ''|\#*) continue;; esac
    if [ -z "${_pe:-}" ]; then _bad="${_bad:+$_bad; }entry '$_pn' has no regex"; continue; fi
    if [ -n "${_px:-}" ]; then _bad="${_bad:+$_bad; }entry '$_pn' has too many fields"; continue; fi
    if ! pcre_compiles "$_pe"; then _bad="${_bad:+$_bad; }entry '$_pn' has an invalid regex"; continue; fi
  done < "$_file"
  [ -z "$_bad" ] && return 0
  echo "error: $_file: $_bad" >&2
  return 2
}

validate_pattern_file "$PATTERNS" || exit 2

PATTERN_FILES=("$PATTERNS")
VALUE_STATE="NOT-CONFIGURED (0 value patterns applied)"
if [ -n "$PATTERNS_EXTRA" ]; then
  [ -f "$PATTERNS_EXTRA" ] || { echo "error: pattern file not found: $PATTERNS_EXTRA" >&2; exit 2; }
  validate_pattern_file "$PATTERNS_EXTRA" || exit 2
  PATTERN_FILES+=("$PATTERNS_EXTRA")
  VC=$(grep -v '^[[:space:]]*#' "$PATTERNS_EXTRA" | grep -cv '^[[:space:]]*$' || true)
  VALUE_STATE="configured (${VC} pattern(s) applied)"
fi

OWNER_ALLOW='(^|/)(README|ONBOARDING|CONTRIBUTING|PLAN)\.md$|(^|/)LICENSE$|(^|/)\.github/|^COMMIT_MSG$'
GLOBAL_ALLOW='noreply@|users\.noreply\.github\.com|git@github\.com|example\.com|@example\.org'

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
HITS="$WORK/hits.tsv"; : > "$HITS"

if [ "$TARGET" = "-" ]; then
  STDIN_MODE=1
  SCAN_ROOT="$WORK"; cat > "$WORK/stream.txt"
  mkdir -p "$WORK/diff"
  awk -v dir="$WORK/diff" -v map="$WORK/map.tsv" '
    /^commit / { n++; out = dir "/commit" n ".txt"; printf "%s\t%s\n", out, "COMMIT_MSG" >> map; next }
    /^(Author|Date|Commit|Merge):/ { next }
    /^diff --git / {
      n++
      p = $NF; sub(/^b\//, "", p)
      printf "%s\t%s\n", dir "/d" n ".txt", p >> map
      out = dir "/d" n ".txt"; next
    }
    { if (out != "") print >> out }
  ' "$WORK/stream.txt"
  mapfile -t FILES < <(find "$WORK/diff" -type f | sort)
else
  [ -d "$TARGET" ] || { echo "not a directory: $TARGET" >&2; exit 2; }
  STDIN_MODE=0
  SCAN_ROOT="$TARGET"
  _T="$TARGET"
  while [ "${_T%/}" != "$_T" ]; do _T="${_T%/}"; done
  [ -n "$_T" ] || _T="/"
  find "$_T" -type f -not -path '*/.git/*' -not -path '*/__pycache__/*' -not -name '*.pyc' > "$WORK/all.txt"
  EXCLUDED=$(grep -cxF -e "$_T/scripts/leak-patterns.tsv" -e "$_T/scripts/leak-scan.sh" "$WORK/all.txt" || true)
  EXCLUDED=${EXCLUDED:-0}
  grep -vxF -e "$_T/scripts/leak-patterns.tsv" -e "$_T/scripts/leak-scan.sh" "$WORK/all.txt" > "$WORK/f1.txt" || true
  if [ -f "$TARGET/.leakignore" ]; then
    grep -vF -f "$TARGET/.leakignore" "$WORK/f1.txt" > "$WORK/f2.txt" || true
  else
    cp "$WORK/f1.txt" "$WORK/f2.txt"
  fi
  mapfile -t FILES < <(sort "$WORK/f2.txt")
  if [ "${#FILES[@]}" -eq 0 ]; then
    echo "error: no files enumerated under $_T" >&2
    exit 2
  fi
fi

declare -A FILEPATH
if [ -f "$WORK/map.tsv" ]; then
  while IFS=$'\t' read -r tf orig; do FILEPATH["$tf"]="$orig"; done < "$WORK/map.tsv"
fi

for _pf in "${PATTERN_FILES[@]}"; do
while IFS=$'\t' read -r name ere; do
  case "$name" in ''|\#*) continue;; esac
  [ -n "${ere:-}" ] || continue
  for f in "${FILES[@]:-}"; do
    [ -f "$f" ] || continue
    dpath="${FILEPATH[$f]:-$f}"
    grep -Iq . "$f" 2>/dev/null || continue
    while IFS= read -r hit; do
      [ -n "$hit" ] || continue
      line="${hit%%:*}"; content="${hit#*:}"
      if [ "$name" = "contact-email" ]; then
        printf '%s' "$content" | grep -qE "$GLOBAL_ALLOW" && continue
      fi
      if [ "$name" = "owner-handle" ]; then
        printf '%s' "$dpath" | grep -qE "$OWNER_ALLOW" && continue
      fi
      printf '%s\t%s\t%s\t%s\n' "$name" "$dpath" "$line" "$content" >> "$HITS"
    done < <(pcre_lines "$ere" "$f" 2>/dev/null)
  done
done < "$_pf"
done

# ---- secrets pass ----------------------------------------------------------
GITLEAKS_RC=0
GITLEAKS_STATE="skipped (stdin mode)"
if [ "$USE_GITLEAKS" -eq 1 ] && [ "$STDIN_MODE" -eq 0 ]; then
  if command -v gitleaks >/dev/null 2>&1; then
    gitleaks detect --source "$SCAN_ROOT" --no-git --no-banner --redact --exit-code 1 >"$WORK/gitleaks.txt" 2>&1
    GITLEAKS_RC=$?
    if [ "$GITLEAKS_RC" -ne 0 ]; then
      GITLEAKS_STATE="FAILED (rc=$GITLEAKS_RC)"
      if [ -s "$WORK/gitleaks.txt" ]; then
        grep -E 'Finding:|Secret:|File:' "$WORK/gitleaks.txt" >> "$HITS" 2>/dev/null || true
      fi
    else
      GITLEAKS_STATE="clean"
    fi
  else
    echo "warn: gitleaks not found, continuing with --no-gitleaks for shape scan." >&2
    GITLEAKS_STATE="skipped (gitleaks not installed)"
  fi
elif [ "$USE_GITLEAKS" -eq 0 ]; then
  GITLEAKS_STATE="disabled (--no-gitleaks)"
fi

NHITS=$(wc -l < "$HITS" | tr -d ' ')
if [ "$QUIET" -eq 0 ] && [ "$NHITS" -gt 0 ]; then
  echo "LEAK HITS ($NHITS) — by pattern:"
  awk -F'\t' '{c[$1]++} END{for (k in c) printf "  %-18s %s\n", k, c[k]}' "$HITS" | sort -k2 -rn
  echo "  --- locations (first 80 of $NHITS) ---"
  awk -F'\t' '{printf "  [%s] %s:%s\n", $1, $2, $3}' "$HITS" | sort -u | head -80
fi

EXCL_NOTE=""
[ "$STDIN_MODE" -eq 0 ] && EXCL_NOTE="gate file(s) excluded: $EXCLUDED; "

if [ "$NHITS" -gt 0 ] || [ "$GITLEAKS_RC" -ne 0 ]; then
  echo "FAIL: $NHITS identity/path/health hit(s); value layer: $VALUE_STATE; ${EXCL_NOTE}secrets pass: $GITLEAKS_STATE"
  exit 1
fi
echo "PASS: no identity/path/health hits; value layer: $VALUE_STATE; ${EXCL_NOTE}secrets pass: $GITLEAKS_STATE"
exit 0
