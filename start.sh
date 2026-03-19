#!/bin/bash
# IconGuard starten
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/.venv/bin/python3" "$DIR/iconguard_app.py"
