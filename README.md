# IconGuard

macOS Menu Bar App zum Speichern und Wiederherstellen von Desktop-Icon-Positionen.

## Features

- **Profile speichern** – Desktop-Icon-Positionen als benannte Profile sichern
- **Profile wiederherstellen** – Gespeicherte Positionen jederzeit wiederherstellen
- **Auto-Restore** – Automatische Wiederherstellung in konfigurierbaren Intervallen (1–60 Min)
- **Autostart** – Optionaler Start beim Login via macOS LaunchAgent
- **Menüleisten-App** – Läuft unauffällig in der Menüleiste (kein Dock-Icon)
- **CLI-Modus** – Kommandozeilen-Interface für Scripting

## Installation

### DMG (empfohlen)
1. `build_dmg.sh` ausführen (erfordert Python 3 + venv)
2. Die erstellte `IconGuard-1.0.0.dmg` öffnen
3. App nach `/Programme` ziehen
4. Aus Launchpad starten

### Entwicklung
```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install rumps pyobjc-framework-Cocoa

# GUI starten
python3 desktop_icon_manager_app.py

# CLI nutzen
python3 desktop_icon_manager.py save "Mein Profil"
python3 desktop_icon_manager.py restore "Mein Profil"
python3 desktop_icon_manager.py list
```

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `desktop_icon_manager_app.py` | Haupt-App (Menüleiste) |
| `desktop_icon_manager.py` | CLI-Version |
| `setup_app.py` | py2app Build-Konfiguration |
| `build_dmg.sh` | Build-Script für .app + DMG |
| `create_icon.py` | Icon-Generator (icns + png) |
| `setup.py` | venv + Dependency Installer |
| `start.sh` | Schnellstart-Script |

## Technologie

- Python 3 + [rumps](https://github.com/jaredks/rumps) (Menu Bar Framework)
- AppleScript (`desktop position`) für Finder-Integration
- py2app für macOS .app Bundle
- macOS LaunchAgent für Autostart

## Lizenz

MIT License – Copyright (c) 2026 Norbert Jander

Erstellt nach einer Idee von Norbert Jander mit Hilfe eines KI-Agents.
