# IconGuard

macOS Menu Bar App zum Schützen und Verwalten deiner Desktop-Icon-Positionen und -Sichtbarkeit.

Wer kennt es nicht: Nach dem Aufwachen aus dem Ruhemodus oder einem Monitor-Wechsel hat macOS die Icons auf dem Desktop wild durcheinandergewürfelt. **IconGuard** merkt sich die Positionen und stellt sie automatisch wieder her – und erlaubt zusätzlich, einzelne Icons gezielt ein- oder auszublenden.

## Features

- **Profile speichern** – Desktop-Icon-Positionen als benannte Profile sichern
- **Profile wiederherstellen** – Gespeicherte Positionen jederzeit wiederherstellen
- **Icons ein-/ausblenden** – Einzelne Desktop-Icons per Checkbox-Fenster verstecken/anzeigen (wird im Profil gespeichert)
- **Auto-Restore** – Automatische Wiederherstellung in konfigurierbaren Intervallen (5–240 Min)
- **Wake-Restore** – Automatische Wiederherstellung nach dem Aufwachen aus dem Ruhemodus (mit Retry)
- **Login-Restore** – Wiederherstellung beim Anmelden
- **Autostart** – Optionaler Start beim Login via macOS LaunchAgent
- **Menüleisten-App** – Läuft unauffällig in der Menüleiste (kein Dock-Icon)
- **CLI-Modus** – Kommandozeilen-Interface für Scripting

## Installation

### DMG (empfohlen)
1. `build_dmg.sh` ausführen (erfordert Python 3 + venv)
2. Die erstellte `IconGuard-1.1.0.dmg` öffnen
3. App nach `/Programme` ziehen
4. Aus Launchpad oder Spotlight starten

### Entwicklung
```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install rumps pyobjc-framework-Cocoa

# GUI starten
python3 iconguard_app.py

# CLI nutzen
python3 iconguard_cli.py save "Mein Profil"
python3 iconguard_cli.py restore "Mein Profil"
python3 iconguard_cli.py list
python3 iconguard_cli.py hide "desktop.ini"
python3 iconguard_cli.py unhide "desktop.ini"
python3 iconguard_cli.py hidden
```

## Anleitung

1. **App starten** – IconGuard erscheint als Schild-Icon (🛡) in der Menüleiste
2. **Profil speichern** – Über „💾 Positionen speichern …" → „Neues Profil …" die aktuelle Anordnung sichern
3. **Profil wiederherstellen** – Über „🔄 Positionen wiederherstellen" ein gespeichertes Profil wählen
4. **Icons ausblenden** – Über „👁 Icons ein-/ausblenden …" öffnet sich ein Fenster mit Checkboxen für alle Desktop-Icons
5. **Automatik einrichten** – Unter „⚙️ Einstellungen" Auto-Restore, Intervall und Wake/Login-Restore konfigurieren
6. **Autostart** – „🚀 Autostart bei Login" aktivieren, damit IconGuard beim Anmelden automatisch startet

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `iconguard_app.py` | Haupt-App (Menüleiste) |
| `iconguard_cli.py` | CLI-Version |
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
