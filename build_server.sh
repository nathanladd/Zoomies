#!/usr/bin/env bash
# Package the Rudi server for deployment to Ubuntu.
# Produces dist/rudi-server-<version>.tar.gz
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VERSION=$(python3 -c "exec(open('version.py').read()); print(__version__)")
OUTDIR="dist/rudi-server-${VERSION}"

rm -rf "$OUTDIR"
mkdir -p "$OUTDIR"

# Copy server files
cp -r server/ "$OUTDIR/server/"
cp -r static/ "$OUTDIR/static/"
cp -r deploy/ "$OUTDIR/deploy/"
cp run_server.py "$OUTDIR/"
cp run_server.sh "$OUTDIR/"
cp version.py "$OUTDIR/"
cp requirements-server.txt "$OUTDIR/"

# Make shell scripts executable
chmod +x "$OUTDIR/run_server.sh"

# Create tarball
cd dist
tar -czf "rudi-server-${VERSION}.tar.gz" "rudi-server-${VERSION}/"
rm -rf "rudi-server-${VERSION}/"

echo "Built: dist/rudi-server-${VERSION}.tar.gz"
