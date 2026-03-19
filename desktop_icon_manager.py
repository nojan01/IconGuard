#!/usr/bin/env python3
"""
IconGuard CLI for macOS
Speichert und stellt Desktop-Icon-Positionen wieder her.

Copyright (c) 2026 Norbert Jander
Erstellt nach einer Idee von Norbert Jander mit Hilfe eines KI-Agents.
Lizenz: MIT (siehe LICENSE)
    python3 desktop_icon_manager.py save [Profilname]
    python3 desktop_icon_manager.py restore [Profilname]
    python3 desktop_icon_manager.py list
    python3 desktop_icon_manager.py show [Profilname]
    python3 desktop_icon_manager.py delete [Profilname]
"""

import subprocess
import json
import sys
import os
from datetime import datetime
from pathlib import Path

PROFILES_DIR = Path.home() / ".iconguard"


def run_applescript(script: str) -> str:
    """Führt ein AppleScript aus und gibt das Ergebnis zurück."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript Fehler: {result.stderr.strip()}")
    return result.stdout.strip()


def get_icon_positions() -> dict:
    """Liest alle Desktop-Icon-Positionen über Finder AppleScript."""
    script = '''
    tell application "Finder"
        set output to ""
        set allItems to every item of desktop
        repeat with anItem in allItems
            set itemName to name of anItem as text
            set itemPos to desktop position of anItem
            set x to item 1 of itemPos
            set y to item 2 of itemPos
            set output to output & itemName & "||" & x & "||" & y & linefeed
        end repeat
        return output
    end tell
    '''
    raw = run_applescript(script)
    positions = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("||")
        if len(parts) == 3:
            name = parts[0]
            try:
                x = int(float(parts[1]))
                y = int(float(parts[2]))
                positions[name] = {"x": x, "y": y}
            except ValueError:
                print(f"  Warnung: Position für '{name}' konnte nicht gelesen werden.")
    return positions


def set_icon_positions(positions: dict) -> tuple[int, int]:
    """Setzt Desktop-Icon-Positionen über Finder AppleScript.
    Gibt (erfolgreich, fehlgeschlagen) zurück."""
    success = 0
    failed = 0
    for name, pos in positions.items():
        x, y = pos["x"], pos["y"]
        # Dateinamen mit Sonderzeichen escapen
        escaped_name = name.replace('\\', '\\\\').replace('"', '\\"')
        script = f'''
        tell application "Finder"
            try
                set desktop position of item "{escaped_name}" of desktop to {{{x}, {y}}}
                return "ok"
            on error errMsg
                return "error: " & errMsg
            end try
        end tell
        '''
        try:
            result = run_applescript(script)
            if result.startswith("error"):
                print(f"  ⚠ '{name}': {result}")
                failed += 1
            else:
                success += 1
        except RuntimeError as e:
            print(f"  ⚠ '{name}': {e}")
            failed += 1
    return success, failed


def get_profile_path(name: str) -> Path:
    """Gibt den Pfad zur Profil-Datei zurück."""
    # Sicherheit: Nur einfache Profilnamen erlauben
    safe_name = "".join(c for c in name if c.isalnum() or c in "-_ ")
    if not safe_name:
        raise ValueError("Ungültiger Profilname.")
    return PROFILES_DIR / f"{safe_name}.json"


def cmd_save(profile_name: str = "default"):
    """Speichert die aktuellen Icon-Positionen."""
    PROFILES_DIR.mkdir(exist_ok=True)
    print(f"📸 Lese Desktop-Icon-Positionen...")
    positions = get_icon_positions()

    if not positions:
        print("Keine Icons auf dem Desktop gefunden.")
        return

    profile_path = get_profile_path(profile_name)
    data = {
        "profile": profile_name,
        "saved_at": datetime.now().isoformat(),
        "icon_count": len(positions),
        "positions": positions
    }
    profile_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"✅ {len(positions)} Icon-Positionen gespeichert in Profil '{profile_name}'")
    print(f"   Datei: {profile_path}")


def cmd_restore(profile_name: str = "default"):
    """Stellt Icon-Positionen aus einem Profil wieder her."""
    profile_path = get_profile_path(profile_name)

    if not profile_path.exists():
        print(f"❌ Profil '{profile_name}' nicht gefunden.")
        print(f"   Verfügbare Profile:")
        cmd_list()
        return

    data = json.loads(profile_path.read_text())
    positions = data["positions"]
    saved_at = data.get("saved_at", "unbekannt")

    print(f"🔄 Stelle {len(positions)} Icon-Positionen wieder her...")
    print(f"   Profil: '{profile_name}' (gespeichert: {saved_at})")

    success, failed = set_icon_positions(positions)

    print(f"\n✅ Fertig: {success} erfolgreich", end="")
    if failed:
        print(f", {failed} fehlgeschlagen (Icons möglicherweise nicht mehr vorhanden)")
    else:
        print()


def cmd_list():
    """Listet alle gespeicherten Profile auf."""
    if not PROFILES_DIR.exists():
        print("Keine Profile vorhanden.")
        return

    profiles = sorted(PROFILES_DIR.glob("*.json"))
    if not profiles:
        print("Keine Profile vorhanden.")
        return

    print(f"📋 Gespeicherte Profile ({len(profiles)}):\n")
    for p in profiles:
        try:
            data = json.loads(p.read_text())
            name = data.get("profile", p.stem)
            count = data.get("icon_count", "?")
            saved = data.get("saved_at", "?")
            if saved != "?":
                dt = datetime.fromisoformat(saved)
                saved = dt.strftime("%d.%m.%Y %H:%M")
            print(f"  • {name:20s}  {count:>3} Icons  ({saved})")
        except (json.JSONDecodeError, ValueError):
            print(f"  • {p.stem:20s}  (Datei beschädigt)")


def cmd_show(profile_name: str = "default"):
    """Zeigt die Icon-Positionen eines Profils an."""
    profile_path = get_profile_path(profile_name)

    if not profile_path.exists():
        print(f"❌ Profil '{profile_name}' nicht gefunden.")
        return

    data = json.loads(profile_path.read_text())
    positions = data["positions"]

    print(f"📍 Profil '{profile_name}' – {len(positions)} Icons:\n")
    for name, pos in sorted(positions.items()):
        print(f"  {name:40s}  ({pos['x']:>5}, {pos['y']:>5})")


def cmd_delete(profile_name: str):
    """Löscht ein gespeichertes Profil."""
    profile_path = get_profile_path(profile_name)

    if not profile_path.exists():
        print(f"❌ Profil '{profile_name}' nicht gefunden.")
        return

    profile_path.unlink()
    print(f"🗑  Profil '{profile_name}' gelöscht.")


def print_usage():
    print("""
Desktop Icon Manager für macOS
==============================

Verwendung:
  python3 desktop_icon_manager.py save [Profilname]     Positionen speichern
  python3 desktop_icon_manager.py restore [Profilname]  Positionen wiederherstellen
  python3 desktop_icon_manager.py list                  Alle Profile anzeigen
  python3 desktop_icon_manager.py show [Profilname]     Positionen eines Profils anzeigen
  python3 desktop_icon_manager.py delete <Profilname>   Profil löschen

Profilname ist optional und standardmäßig "default".

Beispiele:
  python3 desktop_icon_manager.py save                  # Speichert als "default"
  python3 desktop_icon_manager.py save arbeit           # Speichert als "arbeit"
  python3 desktop_icon_manager.py restore arbeit        # Stellt "arbeit" Layout her
  python3 desktop_icon_manager.py list                  # Zeigt alle Profile
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    command = sys.argv[1].lower()
    profile = sys.argv[2] if len(sys.argv) > 2 else "default"

    commands = {
        "save": lambda: cmd_save(profile),
        "restore": lambda: cmd_restore(profile),
        "list": cmd_list,
        "show": lambda: cmd_show(profile),
        "delete": lambda: cmd_delete(profile),
        "help": print_usage,
        "-h": print_usage,
        "--help": print_usage,
    }

    if command in commands:
        commands[command]()
    else:
        print(f"❌ Unbekannter Befehl: '{command}'")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
