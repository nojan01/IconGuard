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
import stat
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


def get_desktop_path() -> Path:
    """Gibt den Pfad zum Desktop-Ordner zurück."""
    return Path.home() / "Desktop"


def get_hidden_items() -> list[str]:
    """Gibt eine Liste aller versteckten Dateien auf dem Desktop zurück."""
    desktop = get_desktop_path()
    hidden = []
    for item in desktop.iterdir():
        if item.name.startswith("."):
            continue  # System-Dateien ignorieren
        try:
            st = item.stat()
            if st.st_flags & stat.UF_HIDDEN:
                hidden.append(item.name)
        except OSError:
            pass
    return sorted(hidden)


def get_all_desktop_items() -> list[str]:
    """Gibt eine Liste aller Dateien auf dem Desktop zurück (sichtbar + versteckt)."""
    desktop = get_desktop_path()
    items = []
    for item in desktop.iterdir():
        if item.name.startswith("."):
            continue
        items.append(item.name)
    return sorted(items)


def hide_item(name: str) -> bool:
    """Versteckt ein Desktop-Icon. Gibt True bei Erfolg zurück."""
    path = get_desktop_path() / name
    if not path.exists():
        return False
    try:
        st = path.stat()
        os.chflags(path, st.st_flags | stat.UF_HIDDEN)
        return True
    except OSError:
        return False


def unhide_item(name: str) -> bool:
    """Macht ein verstecktes Desktop-Icon wieder sichtbar. Gibt True bei Erfolg zurück."""
    path = get_desktop_path() / name
    if not path.exists():
        return False
    try:
        st = path.stat()
        os.chflags(path, st.st_flags & ~stat.UF_HIDDEN)
        return True
    except OSError:
        return False


def get_profile_path(name: str) -> Path:
    """Gibt den Pfad zur Profil-Datei zurück."""
    # Sicherheit: Nur einfache Profilnamen erlauben
    safe_name = "".join(c for c in name if c.isalnum() or c in "-_ ")
    if not safe_name:
        raise ValueError("Ungültiger Profilname.")
    return PROFILES_DIR / f"{safe_name}.json"


def cmd_save(profile_name: str = "default"):
    """Speichert die aktuellen Icon-Positionen inkl. Sichtbarkeit."""
    PROFILES_DIR.mkdir(exist_ok=True)
    print(f"📸 Lese Desktop-Icon-Positionen...")
    positions = get_icon_positions()
    hidden = get_hidden_items()

    if not positions and not hidden:
        print("Keine Icons auf dem Desktop gefunden.")
        return

    profile_path = get_profile_path(profile_name)
    data = {
        "profile": profile_name,
        "saved_at": datetime.now().isoformat(),
        "icon_count": len(positions) + len(hidden),
        "positions": positions,
        "hidden": hidden,
    }
    profile_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"✅ {len(positions)} sichtbare + {len(hidden)} versteckte Icons gespeichert in Profil '{profile_name}'")
    if hidden:
        print(f"   Versteckt: {', '.join(hidden)}")
    print(f"   Datei: {profile_path}")


def cmd_restore(profile_name: str = "default"):
    """Stellt Icon-Positionen und Sichtbarkeit aus einem Profil wieder her."""
    profile_path = get_profile_path(profile_name)

    if not profile_path.exists():
        print(f"❌ Profil '{profile_name}' nicht gefunden.")
        print(f"   Verfügbare Profile:")
        cmd_list()
        return

    data = json.loads(profile_path.read_text())
    positions = data["positions"]
    hidden_list = data.get("hidden", [])
    saved_at = data.get("saved_at", "unbekannt")

    print(f"🔄 Stelle {len(positions)} Icon-Positionen wieder her...")
    print(f"   Profil: '{profile_name}' (gespeichert: {saved_at})")

    # Sichtbarkeit wiederherstellen: Alle Desktop-Items durchgehen
    all_items = get_all_desktop_items()
    hidden_restored = 0
    unhidden_restored = 0
    for item_name in all_items:
        if item_name in hidden_list:
            if hide_item(item_name):
                hidden_restored += 1
        else:
            if unhide_item(item_name):
                unhidden_restored += 1

    if hidden_restored or unhidden_restored:
        print(f"   👁 Sichtbarkeit: {hidden_restored} versteckt, {unhidden_restored} eingeblendet")

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
    """Zeigt die Icon-Positionen und Sichtbarkeit eines Profils an."""
    profile_path = get_profile_path(profile_name)

    if not profile_path.exists():
        print(f"❌ Profil '{profile_name}' nicht gefunden.")
        return

    data = json.loads(profile_path.read_text())
    positions = data["positions"]
    hidden_list = data.get("hidden", [])

    print(f"📍 Profil '{profile_name}' – {len(positions)} sichtbare Icons:\n")
    for name, pos in sorted(positions.items()):
        print(f"  {name:40s}  ({pos['x']:>5}, {pos['y']:>5})")

    if hidden_list:
        print(f"\n🙈 Versteckte Icons ({len(hidden_list)}):\n")
        for name in hidden_list:
            print(f"  {name}")


def cmd_delete(profile_name: str):
    """Löscht ein gespeichertes Profil."""
    profile_path = get_profile_path(profile_name)

    if not profile_path.exists():
        print(f"❌ Profil '{profile_name}' nicht gefunden.")
        return

    profile_path.unlink()
    print(f"🗑  Profil '{profile_name}' gelöscht.")


def cmd_hide(name: str):
    """Versteckt ein Desktop-Icon."""
    if hide_item(name):
        print(f"🙈 '{name}' wurde versteckt.")
    else:
        print(f"❌ '{name}' nicht auf dem Desktop gefunden oder Zugriff verweigert.")


def cmd_unhide(name: str):
    """Macht ein verstecktes Desktop-Icon wieder sichtbar."""
    if unhide_item(name):
        print(f"👁 '{name}' ist wieder sichtbar.")
    else:
        print(f"❌ '{name}' nicht auf dem Desktop gefunden oder Zugriff verweigert.")


def cmd_hidden():
    """Zeigt alle versteckten Desktop-Icons an."""
    hidden = get_hidden_items()
    if not hidden:
        print("Keine versteckten Icons auf dem Desktop.")
        return
    print(f"🙈 Versteckte Icons ({len(hidden)}):\n")
    for name in hidden:
        print(f"  {name}")


def print_usage():
    print("""
Desktop Icon Manager für macOS
==============================

Verwendung:
  python3 desktop_icon_manager.py save [Profilname]     Positionen + Sichtbarkeit speichern
  python3 desktop_icon_manager.py restore [Profilname]  Positionen + Sichtbarkeit wiederherstellen
  python3 desktop_icon_manager.py list                  Alle Profile anzeigen
  python3 desktop_icon_manager.py show [Profilname]     Positionen eines Profils anzeigen
  python3 desktop_icon_manager.py delete <Profilname>   Profil löschen
  python3 desktop_icon_manager.py hide <Dateiname>      Desktop-Icon verstecken
  python3 desktop_icon_manager.py unhide <Dateiname>    Verstecktes Icon einblenden
  python3 desktop_icon_manager.py hidden                Alle versteckten Icons anzeigen

Profilname ist optional und standardmäßig "default".

Beispiele:
  python3 desktop_icon_manager.py save                  # Speichert als "default"
  python3 desktop_icon_manager.py save arbeit           # Speichert als "arbeit"
  python3 desktop_icon_manager.py restore arbeit        # Stellt "arbeit" Layout her
  python3 desktop_icon_manager.py hide "Geheim.pdf"     # Versteckt eine Datei
  python3 desktop_icon_manager.py unhide "Geheim.pdf"   # Blendet sie wieder ein
  python3 desktop_icon_manager.py hidden                # Zeigt versteckte Icons
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
        "hide": lambda: cmd_hide(profile) if profile != "default" else print("❌ Bitte Dateiname angeben: hide <Dateiname>"),
        "unhide": lambda: cmd_unhide(profile) if profile != "default" else print("❌ Bitte Dateiname angeben: unhide <Dateiname>"),
        "hidden": cmd_hidden,
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
