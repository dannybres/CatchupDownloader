#!/bin/bash
# Setup script for Ubuntu — creates venv with simple-term-menu
# Run once after cloning or moving the directory: bash setup_ubuntu.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo "Creating virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

echo "Installing simple-term-menu..."
"$VENV_DIR/bin/pip" install simple-term-menu

echo ""
echo "✅ Done. Run the app with:"
echo "   $VENV_DIR/bin/python3 $SCRIPT_DIR/catchup.py"
