#!/usr/bin/env python3
"""
Requirements installieren und App starten.
"""
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
VENV_DIR = APP_DIR / ".venv"
APP_SCRIPT = APP_DIR / "iconguard_app.py"


def setup():
    print("🔧 IconGuard – Setup\n")

    # 1. venv erstellen
    if not VENV_DIR.exists():
        print("📦 Erstelle virtuelle Umgebung...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)

    pip = str(VENV_DIR / "bin" / "pip")
    python = str(VENV_DIR / "bin" / "python3")

    # 2. rumps installieren
    print("📦 Installiere Abhängigkeiten (rumps)...")
    subprocess.run([pip, "install", "--quiet", "rumps"], check=True)

    print("\n✅ Setup abgeschlossen!\n")
    print("Starten mit:")
    print(f"  {python} {APP_SCRIPT}")
    print()
    print("Oder einfach:")
    print(f"  {APP_DIR}/start.sh")


if __name__ == "__main__":
    setup()
