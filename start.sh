#!/bin/bash
# Desktop Icon Manager starten
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/.venv/bin/python3" "$DIR/desktop_icon_manager_app.py"
