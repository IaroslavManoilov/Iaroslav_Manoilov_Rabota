#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
[[ -x "$CHROME" ]] || { echo 'Установите Google Chrome в /Applications.'; exit 1; }
mkdir -p "$ROOT/.local/chrome-profile"
# Dedicated local profile. Do not open a remote-debugging port on the LAN.
nohup "$CHROME" --remote-debugging-address=127.0.0.1 --remote-debugging-port=9228 \
  --user-data-dir="$ROOT/.local/chrome-profile" \
  'https://admin.vitra.md' 'https://chatgpt.com' \
  > "$ROOT/.local/chrome-launch.log" 2>&1 < /dev/null &
echo 'Открыт отдельный Chrome. Войдите вручную в CMS и новый ChatGPT.'
