#!/usr/bin/env bash
# Fail if tracked or staged files look like they contain API keys or .env files.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

# Block env files from being added (example template is OK)
while IFS= read -r f; do
  case "$f" in
    .env.example) continue ;;
    .env|.env.*|*/.env|*/.env.*)
      echo "ERROR: env file must not be committed: $f" >&2
      fail=1
      ;;
  esac
done < <(git ls-files -c --others --exclude-standard 2>/dev/null || git ls-files)

# Scan staged + tracked text for common secret shapes
PATTERN='(AIza[0-9A-Za-z_-]{20,}|gsk_[0-9A-Za-z]+|nvapi-[0-9A-Za-z_-]+|sk-or-v1-[0-9a-f]+|csk-[0-9a-z]+)'

scan_files() {
  git diff --cached --name-only --diff-filter=ACM 2>/dev/null
  git ls-files 2>/dev/null
}

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  [[ "$file" == .env.example ]] && continue
  [[ -f "$file" ]] || continue
  if file -b --mime-type "$file" 2>/dev/null | grep -qE '^(text/|application/json|application/x-shellscript)'; then
    if grep -qE "$PATTERN" "$file" 2>/dev/null; then
      echo "ERROR: possible API key in: $file" >&2
      fail=1
    fi
  fi
done < <(scan_files | sort -u)

if [[ "$fail" -ne 0 ]]; then
  echo "Fix the issues above before committing. See .gitignore and .env.example." >&2
  exit 1
fi

echo "OK: no env files or obvious API keys in tracked paths."
