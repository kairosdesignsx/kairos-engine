#!/usr/bin/env bash
# One-time setup for a fresh session: Node and Python dependencies. Safe to re-run.
set -e
cd "$(dirname "$0")"
[ -d node_modules/playwright ] || PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-audit --no-fund --silent
python3 -c "import jsonschema, imagehash, PIL, numpy, sklearn" 2>/dev/null || pip install --break-system-packages -q jsonschema imagehash pillow numpy scikit-learn
command -v qpdf >/dev/null || (apt-get install -y -q qpdf poppler-utils >/dev/null 2>&1 || echo "WARN: qpdf missing")
echo "setup ok"
