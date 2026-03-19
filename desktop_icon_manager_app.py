#!/usr/bin/env python3
"""
IconGuard – macOS Menüleisten-App
Speichert und stellt Desktop-Icon-Positionen automatisch wieder her.

Copyright (c) 2026 Norbert Jander
Erstellt nach einer Idee von Norbert Jander mit Hilfe eines KI-Agents.
Lizenz: MIT (siehe LICENSE)
"""

import subprocess
import json
import threading
import os
import sys
from datetime import datetime
from pathlib import Path

import rumps
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

# Dock-Icon unterdrücken
NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)

# ─── Konfiguration ─────────────────────────────────────────────────
APP_NAME = "IconGuard"
APP_ICON = None  # Wird unten gesetzt falls vorhanden

PROFILES_DIR = Path.home() / ".iconguard"
CONFIG_PATH = PROFILES_DIR / "_config.json"

DEFAULT_CONFIG = {
    "auto_restore_enabled": False,
    "auto_restore_profile": "default",
    "auto_restore_interval_minutes": 30,
}

INTERVAL_OPTIONS = [5, 10, 15, 30, 60, 120, 240]


# ─── AppleScript / Finder Funktionen ──────────────────────────────

def run_applescript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def get_icon_positions() -> dict:
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
                pass
    return positions


def set_icon_positions(positions: dict) -> tuple:
    success = 0
    failed = 0
    for name, pos in positions.items():
        x, y = pos["x"], pos["y"]
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
                failed += 1
            else:
                success += 1
        except RuntimeError:
            failed += 1
    return success, failed


# ─── Profil-Verwaltung ────────────────────────────────────────────

def get_profile_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_ ")
    if not safe:
        raise ValueError("Ungültiger Profilname.")
    return PROFILES_DIR / f"{safe}.json"


def list_profiles() -> list:
    if not PROFILES_DIR.exists():
        return []
    profiles = []
    for p in sorted(PROFILES_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            data = json.loads(p.read_text())
            profiles.append({
                "name": data.get("profile", p.stem),
                "count": data.get("icon_count", 0),
                "saved_at": data.get("saved_at", ""),
                "path": p,
            })
        except (json.JSONDecodeError, ValueError):
            pass
    return profiles


def save_profile(name: str) -> tuple:
    PROFILES_DIR.mkdir(exist_ok=True)
    positions = get_icon_positions()
    if not positions:
        return 0, "Keine Icons gefunden"
    path = get_profile_path(name)
    data = {
        "profile": name,
        "saved_at": datetime.now().isoformat(),
        "icon_count": len(positions),
        "positions": positions,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return len(positions), path


def restore_profile(name: str) -> tuple:
    path = get_profile_path(name)
    if not path.exists():
        return 0, 0, f"Profil '{name}' nicht gefunden"
    data = json.loads(path.read_text())
    success, failed = set_icon_positions(data["positions"])
    return success, failed, None


# ─── Konfiguration ────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text())
            config = {**DEFAULT_CONFIG, **saved}
            return config
        except (json.JSONDecodeError, ValueError):
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    PROFILES_DIR.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


# ─── LaunchAgent ──────────────────────────────────────────────────

LAUNCH_AGENT_LABEL = "com.iconguard.app"
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def get_app_script_path() -> str:
    """Gibt den Pfad zum Startskript zurück."""
    return str(Path(__file__).resolve())


def get_python_path() -> str:
    """Gibt den Pfad zum Python-Executable in der venv zurück."""
    venv_python = Path(__file__).resolve().parent / ".venv" / "bin" / "python3"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def is_autostart_enabled() -> bool:
    return LAUNCH_AGENT_PATH.exists()


def enable_autostart():
    python_path = get_python_path()
    script_path = get_app_script_path()

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{PROFILES_DIR}/app.log</string>
    <key>StandardErrorPath</key>
    <string>{PROFILES_DIR}/app.log</string>
</dict>
</plist>
"""
    LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENT_PATH.write_text(plist_content)
    subprocess.run(["launchctl", "load", str(LAUNCH_AGENT_PATH)],
                   capture_output=True)


def disable_autostart():
    if LAUNCH_AGENT_PATH.exists():
        subprocess.run(["launchctl", "unload", str(LAUNCH_AGENT_PATH)],
                       capture_output=True)
        LAUNCH_AGENT_PATH.unlink()


# ─── Menüleisten-App ──────────────────────────────────────────────

class DesktopIconManagerApp(rumps.App):
    def __init__(self):
        super().__init__(
            APP_NAME,
            icon=APP_ICON,
            title=None,
            quit_button=None,
        )
        self.config = load_config()
        self.auto_timer = None
        self._build_menu()
        if self.config["auto_restore_enabled"]:
            self._start_auto_restore()

    # ── Menü aufbauen ─────────────────────────────────────────────

    def _build_menu(self):
        self.menu.clear()

        # Speichern
        save_menu = rumps.MenuItem("💾 Positionen speichern …")
        save_new = rumps.MenuItem("Neues Profil …", callback=self.on_save_new)
        save_menu.add(save_new)
        save_menu.add(rumps.separator)
        for p in list_profiles():
            item = rumps.MenuItem(
                f"Überschreiben: {p['name']} ({p['count']} Icons)",
                callback=self.on_save_existing
            )
            item._profile_name = p["name"]
            save_menu.add(item)
        self.menu.add(save_menu)

        # Wiederherstellen
        restore_menu = rumps.MenuItem("🔄 Positionen wiederherstellen")
        profiles = list_profiles()
        if profiles:
            for p in profiles:
                dt_str = ""
                if p["saved_at"]:
                    try:
                        dt = datetime.fromisoformat(p["saved_at"])
                        dt_str = f" – {dt.strftime('%d.%m. %H:%M')}"
                    except ValueError:
                        pass
                item = rumps.MenuItem(
                    f"{p['name']} ({p['count']} Icons{dt_str})",
                    callback=self.on_restore
                )
                item._profile_name = p["name"]
                restore_menu.add(item)
        else:
            restore_menu.add(rumps.MenuItem("(keine Profile vorhanden)"))
        self.menu.add(restore_menu)

        self.menu.add(rumps.separator)

        # Auto-Restore
        auto_item = rumps.MenuItem(
            "⏱ Auto-Wiederherstellen",
            callback=self.on_toggle_auto_restore
        )
        auto_item.state = self.config["auto_restore_enabled"]
        self.menu.add(auto_item)

        # Intervall
        interval_menu = rumps.MenuItem("⏰ Intervall")
        current = self.config["auto_restore_interval_minutes"]
        for mins in INTERVAL_OPTIONS:
            if mins < 60:
                label = f"{mins} Minuten"
            else:
                label = f"{mins // 60} Stunde{'n' if mins > 60 else ''}"
            item = rumps.MenuItem(label, callback=self.on_set_interval)
            item._interval_minutes = mins
            item.state = (mins == current)
            interval_menu.add(item)
        self.menu.add(interval_menu)

        # Auto-Restore Profil
        profile_menu = rumps.MenuItem("📋 Auto-Restore Profil")
        current_profile = self.config["auto_restore_profile"]
        for p in list_profiles():
            item = rumps.MenuItem(p["name"], callback=self.on_set_auto_profile)
            item._profile_name = p["name"]
            item.state = (p["name"] == current_profile)
            profile_menu.add(item)
        if not profiles:
            profile_menu.add(rumps.MenuItem("(erst ein Profil speichern)"))
        self.menu.add(profile_menu)

        self.menu.add(rumps.separator)

        # Profil löschen
        delete_menu = rumps.MenuItem("🗑 Profil löschen")
        for p in list_profiles():
            item = rumps.MenuItem(p["name"], callback=self.on_delete_profile)
            item._profile_name = p["name"]
            delete_menu.add(item)
        if not profiles:
            delete_menu.add(rumps.MenuItem("(keine Profile)"))
        self.menu.add(delete_menu)

        self.menu.add(rumps.separator)

        # Autostart
        autostart_item = rumps.MenuItem(
            "🚀 Beim Anmelden starten",
            callback=self.on_toggle_autostart
        )
        autostart_item.state = is_autostart_enabled()
        self.menu.add(autostart_item)

        self.menu.add(rumps.separator)

        # Status
        if self.config["auto_restore_enabled"]:
            interval = self.config["auto_restore_interval_minutes"]
            profile = self.config["auto_restore_profile"]
            if interval < 60:
                iv_text = f"alle {interval} Min."
            else:
                iv_text = f"alle {interval // 60} Std."
            status_text = f"Auto: '{profile}' {iv_text}"
        else:
            status_text = "Auto-Restore: Aus"
        status = rumps.MenuItem(f"ℹ️ {status_text}")
        status.set_callback(None)
        self.menu.add(status)

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Über IconGuard", callback=self.on_about))
        self.menu.add(rumps.MenuItem("Beenden", callback=self.on_quit))

    # ── Callbacks ─────────────────────────────────────────────────

    def on_save_new(self, _):
        window = rumps.Window(
            message="Name für das neue Layout-Profil:",
            title="Profil speichern",
            default_text="default",
            ok="Speichern",
            cancel="Abbrechen",
            dimensions=(300, 24)
        )
        response = window.run()
        if response.clicked and response.text.strip():
            name = response.text.strip()
            self._do_save(name)

    def on_save_existing(self, sender):
        name = sender._profile_name
        self._do_save(name)

    def _do_save(self, name):
        def task():
            try:
                count, path = save_profile(name)
                if isinstance(path, Path):
                    rumps.notification(
                        APP_NAME,
                        f"Profil '{name}' gespeichert",
                        f"{count} Icon-Positionen gesichert."
                    )
                else:
                    rumps.notification(APP_NAME, "Fehler", str(path))
            except Exception as e:
                rumps.notification(APP_NAME, "Fehler beim Speichern", str(e))
            self._build_menu()
        threading.Thread(target=task, daemon=True).start()

    def on_restore(self, sender):
        name = sender._profile_name
        self._do_restore(name, notify=True)

    def _do_restore(self, name, notify=True):
        def task():
            try:
                success, failed, error = restore_profile(name)
                if error:
                    if notify:
                        rumps.notification(APP_NAME, "Fehler", error)
                    return
                msg = f"{success} Icons wiederhergestellt"
                if failed:
                    msg += f", {failed} fehlgeschlagen"
                if notify:
                    rumps.notification(APP_NAME, f"Profil '{name}'", msg)
            except Exception as e:
                if notify:
                    rumps.notification(APP_NAME, "Fehler", str(e))
        threading.Thread(target=task, daemon=True).start()

    def on_toggle_auto_restore(self, sender):
        self.config["auto_restore_enabled"] = not self.config["auto_restore_enabled"]
        save_config(self.config)
        if self.config["auto_restore_enabled"]:
            self._start_auto_restore()
            rumps.notification(APP_NAME, "Auto-Restore aktiviert",
                               f"Profil '{self.config['auto_restore_profile']}' "
                               f"wird alle {self.config['auto_restore_interval_minutes']} Min. wiederhergestellt.")
        else:
            self._stop_auto_restore()
            rumps.notification(APP_NAME, "Auto-Restore deaktiviert", "")
        self._build_menu()

    def on_set_interval(self, sender):
        self.config["auto_restore_interval_minutes"] = sender._interval_minutes
        save_config(self.config)
        if self.config["auto_restore_enabled"]:
            self._stop_auto_restore()
            self._start_auto_restore()
        self._build_menu()

    def on_set_auto_profile(self, sender):
        self.config["auto_restore_profile"] = sender._profile_name
        save_config(self.config)
        self._build_menu()

    def on_delete_profile(self, sender):
        name = sender._profile_name
        try:
            path = get_profile_path(name)
            if path.exists():
                path.unlink()
                rumps.notification(APP_NAME, f"Profil '{name}' gelöscht", "")
        except Exception as e:
            rumps.notification(APP_NAME, "Fehler", str(e))
        self._build_menu()

    def on_toggle_autostart(self, sender):
        if is_autostart_enabled():
            disable_autostart()
            rumps.notification(APP_NAME, "Autostart deaktiviert",
                               "App wird nicht mehr beim Anmelden gestartet.")
        else:
            enable_autostart()
            rumps.notification(APP_NAME, "Autostart aktiviert",
                               "App startet beim nächsten Anmelden automatisch.")
        self._build_menu()

    def on_about(self, _):
        rumps.alert(
            title="Über IconGuard",
            message=(
                "IconGuard v1.0.0\n\n"
                "Speichert und stellt Desktop-Icon-Positionen\n"
                "automatisch wieder her.\n\n"
                "Copyright © 2026 Norbert Jander\n"
                "Erstellt nach einer Idee von Norbert Jander\n"
                "mit Hilfe eines KI-Agents.\n\n"
                "Lizenz: MIT"
            ),
            ok="OK"
        )

    def on_quit(self, _):
        self._stop_auto_restore()
        rumps.quit_application()

    # ── Auto-Restore Timer ────────────────────────────────────────

    def _start_auto_restore(self):
        self._stop_auto_restore()
        interval_sec = self.config["auto_restore_interval_minutes"] * 60
        self.auto_timer = rumps.Timer(self._auto_restore_tick, interval_sec)
        self.auto_timer.start()

    def _stop_auto_restore(self):
        if self.auto_timer is not None:
            self.auto_timer.stop()
            self.auto_timer = None

    def _auto_restore_tick(self, _):
        profile = self.config["auto_restore_profile"]
        self._do_restore(profile, notify=False)


# ─── Haupteinstieg ────────────────────────────────────────────────

def find_icon() -> str | None:
    """Sucht das Icon – funktioniert sowohl als Skript als auch im .app Bundle."""
    candidates = [
        Path(__file__).resolve().parent / "icon.png",                    # Skript-Modus
        Path(__file__).resolve().parent / ".." / "Resources" / "icon.png",  # .app Bundle
    ]
    for p in candidates:
        p = p.resolve()
        if p.exists():
            return str(p)
    return None


if __name__ == "__main__":
    PROFILES_DIR.mkdir(exist_ok=True)
    APP_ICON = find_icon()
    app = DesktopIconManagerApp()
    app.run()
