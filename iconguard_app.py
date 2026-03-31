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
import stat
import threading
import os
import time
import sys
from datetime import datetime
from pathlib import Path

import objc
import rumps
from AppKit import (
    NSApplication, NSApplicationActivationPolicyAccessory,
    NSWorkspace, NSWorkspaceDidWakeNotification,
    NSWindow, NSView, NSButton, NSScrollView, NSTextField,
    NSBackingStoreBuffered, NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable, NSWindowStyleMaskResizable,
    NSButtonTypeSwitch, NSBezelStyleRounded,
    NSFont, NSColor, NSApp,
    NSApplicationActivationPolicyRegular,
)

# Konstanten die in manchen PyObjC-Versionen fehlen
NSControlStateValueOn = 1
NSControlStateValueOff = 0
from Foundation import NSObject, NSMakeRect, NSBundle as FoundationNSBundle

# CGSessionCopyCurrentDictionary laden (ohne pyobjc-framework-Quartz)
_cg_functions = {}
objc.loadBundleFunctions(
    FoundationNSBundle.bundleWithPath_('/System/Library/Frameworks/ApplicationServices.framework'),
    _cg_functions,
    [('CGSessionCopyCurrentDictionary', b'@',)]
)
_CGSessionCopyCurrentDictionary = _cg_functions['CGSessionCopyCurrentDictionary']

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
    "restore_on_login": True,
    "restore_on_wake": True,
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


# ─── Desktop-Sichtbarkeit ────────────────────────────────────────────

def get_desktop_path() -> Path:
    return Path.home() / "Desktop"


def get_all_desktop_items() -> list[dict]:
    """Gibt alle Desktop-Items zurück mit Name und Hidden-Status."""
    desktop = get_desktop_path()
    items = []
    for item in desktop.iterdir():
        if item.name.startswith("."):
            continue
        try:
            st = item.stat()
            is_hidden = bool(st.st_flags & stat.UF_HIDDEN)
            items.append({"name": item.name, "hidden": is_hidden})
        except OSError:
            pass
    return sorted(items, key=lambda x: x["name"])


def get_hidden_items() -> list[str]:
    """Gibt eine Liste aller versteckten Dateien auf dem Desktop zurück."""
    return [i["name"] for i in get_all_desktop_items() if i["hidden"]]


def hide_item(name: str) -> bool:
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
    path = get_desktop_path() / name
    if not path.exists():
        return False
    try:
        st = path.stat()
        os.chflags(path, st.st_flags & ~stat.UF_HIDDEN)
        return True
    except OSError:
        return False


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
            hidden = data.get("hidden", [])
            profiles.append({
                "name": data.get("profile", p.stem),
                "count": data.get("icon_count", 0),
                "hidden_count": len(hidden),
                "saved_at": data.get("saved_at", ""),
                "path": p,
            })
        except (json.JSONDecodeError, ValueError):
            pass
    return profiles


def save_profile(name: str) -> tuple:
    PROFILES_DIR.mkdir(exist_ok=True)
    positions = get_icon_positions()
    hidden = get_hidden_items()
    if not positions and not hidden:
        return 0, "Keine Icons gefunden"
    path = get_profile_path(name)
    data = {
        "profile": name,
        "saved_at": datetime.now().isoformat(),
        "icon_count": len(positions) + len(hidden),
        "positions": positions,
        "hidden": hidden,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return len(positions) + len(hidden), path


def restore_profile(name: str) -> tuple:
    path = get_profile_path(name)
    if not path.exists():
        return 0, 0, f"Profil '{name}' nicht gefunden"
    data = json.loads(path.read_text())
    hidden_list = data.get("hidden", [])

    # Sichtbarkeit wiederherstellen
    all_items = get_all_desktop_items()
    for item in all_items:
        if item["name"] in hidden_list:
            hide_item(item["name"])
        else:
            unhide_item(item["name"])

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


def get_app_bundle_path() -> str | None:
    """Gibt den Pfad zum .app-Bundle zurück, falls wir darin laufen."""
    exe = Path(sys.executable).resolve()
    # py2app-Bundle: .../IconGuard.app/Contents/MacOS/IconGuard
    for parent in exe.parents:
        if parent.suffix == ".app" and (parent / "Contents" / "MacOS").is_dir():
            return str(parent)
    return None


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
    app_bundle = get_app_bundle_path()

    if app_bundle:
        # Als .app-Bundle: mit 'open' starten
        program_args = f"""    <array>
        <string>/usr/bin/open</string>
        <string>-a</string>
        <string>{app_bundle}</string>
    </array>"""
    else:
        # Entwicklungsmodus: Python + Skript direkt
        python_path = get_python_path()
        script_path = get_app_script_path()
        program_args = f"""    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
    </array>"""

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
{program_args}
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

class SleepWakeObserver(NSObject):
    """Beobachtet Sleep/Wake-Events vom System."""
    def initWithApp_(self, app):
        self = objc.super(SleepWakeObserver, self).init()
        if self is None:
            return None
        self._app = app
        return self

    def handleWakeNotification_(self, notification):
        """Wird aufgerufen wenn der Mac aus dem Ruhemodus aufwacht."""
        if self._app.config.get("restore_on_wake", True):
            self._app._restore_after_wake()





class VisibilityWindowDelegate(NSObject):
    """Delegate für das Sichtbarkeits-Fenster."""

    def initWithCheckboxes_window_app_(self, checkboxes, window, app):
        self = objc.super(VisibilityWindowDelegate, self).init()
        if self is None:
            return None
        self._checkboxes = checkboxes
        self._window = window
        self._app = app
        return self

    def onSelectAll_(self, sender):
        """Setzt alle Checkboxen auf 'sichtbar'."""
        for name, cb in self._checkboxes:
            cb.setState_(NSControlStateValueOn)

    def onApply_(self, sender):
        """Wendet die Änderungen an und schließt das Fenster."""
        changes = []
        for name, cb in self._checkboxes:
            should_be_visible = (cb.state() == NSControlStateValueOn)
            changes.append((name, should_be_visible))

        self._window.close()

        # Zurück zur Accessory-App (kein Dock-Icon)
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        def task():
            hidden_count = 0
            shown_count = 0
            for name, should_be_visible in changes:
                if should_be_visible:
                    if unhide_item(name):
                        shown_count += 1
                else:
                    if hide_item(name):
                        hidden_count += 1
            parts = []
            if hidden_count:
                parts.append(f"{hidden_count} versteckt")
            if shown_count:
                parts.append(f"{shown_count} eingeblendet")
            if parts:
                rumps.notification(APP_NAME, "Sichtbarkeit geändert", ", ".join(parts))
            self._app._build_menu()

        threading.Thread(target=task, daemon=True).start()

    def windowWillClose_(self, notification):
        """Wird aufgerufen wenn das Fenster geschlossen wird."""
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        self._app._visibility_window = None


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
        self._wake_observer = None
        self._visibility_window = None
        self._visibility_delegate = None
        self._last_check_time = time.time()
        self._screen_was_locked = False
        self._build_menu()
        if self.config["auto_restore_enabled"]:
            self._start_auto_restore()
        if self.config.get("restore_on_login", True):
            self._restore_on_login()
        self._register_wake_observer()
        self._start_wake_detector()

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
                hidden_info = f", {p['hidden_count']} versteckt" if p.get("hidden_count") else ""
                item = rumps.MenuItem(
                    f"{p['name']} ({p['count']} Icons{hidden_info}{dt_str})",
                    callback=self.on_restore
                )
                item._profile_name = p["name"]
                restore_menu.add(item)
        else:
            restore_menu.add(rumps.MenuItem("(keine Profile vorhanden)"))
        self.menu.add(restore_menu)

        self.menu.add(rumps.separator)

        # Icons ein-/ausblenden (öffnet Fenster)
        visibility_item = rumps.MenuItem(
            "👁 Icons ein-/ausblenden …", callback=self.on_open_visibility_window
        )
        self.menu.add(visibility_item)

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

        # Beim Login wiederherstellen
        login_restore_item = rumps.MenuItem(
            "🔁 Beim Login Icons wiederherstellen",
            callback=self.on_toggle_restore_on_login
        )
        login_restore_item.state = self.config.get("restore_on_login", True)
        self.menu.add(login_restore_item)

        # Nach Ruhemodus wiederherstellen
        wake_restore_item = rumps.MenuItem(
            "😴 Nach Ruhemodus wiederherstellen",
            callback=self.on_toggle_restore_on_wake
        )
        wake_restore_item.state = self.config.get("restore_on_wake", True)
        self.menu.add(wake_restore_item)

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
                    hidden = get_hidden_items()
                    msg = f"{count} Icons gesichert"
                    if hidden:
                        msg += f" ({len(hidden)} versteckt)"
                    rumps.notification(
                        APP_NAME,
                        f"Profil '{name}' gespeichert",
                        msg
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

    def on_open_visibility_window(self, _):
        """Öffnet ein Fenster mit Checkboxen für alle Desktop-Icons."""
        try:
            desktop_items = get_all_desktop_items()
        except Exception:
            rumps.notification(APP_NAME, "Fehler", "Desktop-Items konnten nicht gelesen werden.")
            return

        if not desktop_items:
            rumps.notification(APP_NAME, "Keine Items", "Keine Icons auf dem Desktop gefunden.")
            return

        # App temporär sichtbar machen für das Fenster
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)

        row_height = 26
        padding = 16
        content_height = len(desktop_items) * row_height
        window_height = min(content_height + 120, 600)

        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 200, 420, window_height),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable,
            NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("Icons ein-/ausblenden")
        window.setMinSize_((350, 250))

        content_view = window.contentView()
        view_width = 420

        # Scrollbare Liste mit Checkboxen
        scroll_view = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, 50, view_width, window_height - 80)
        )
        scroll_view.setHasVerticalScroller_(True)
        scroll_view.setAutoresizingMask_(0b010010)  # Breite + Höhe flexibel

        doc_view = NSView.alloc().initWithFrame_(
            NSMakeRect(0, 0, view_width - 20, max(content_height, window_height - 80))
        )

        checkboxes = []
        for i, di in enumerate(desktop_items):
            y = content_height - (i + 1) * row_height
            cb = NSButton.alloc().initWithFrame_(
                NSMakeRect(padding, y, view_width - 2 * padding, row_height)
            )
            cb.setButtonType_(NSButtonTypeSwitch)
            cb.setTitle_(di["name"])
            cb.setFont_(NSFont.systemFontOfSize_(13))
            cb.setState_(NSControlStateValueOff if di["hidden"] else NSControlStateValueOn)
            cb.setTag_(i)
            doc_view.addSubview_(cb)
            checkboxes.append((di["name"], cb))

        scroll_view.setDocumentView_(doc_view)
        content_view.addSubview_(scroll_view)

        # Buttons unten
        btn_all = NSButton.alloc().initWithFrame_(
            NSMakeRect(padding, 12, 120, 28)
        )
        btn_all.setTitle_("Alle einblenden")
        btn_all.setBezelStyle_(NSBezelStyleRounded)

        btn_apply = NSButton.alloc().initWithFrame_(
            NSMakeRect(view_width - padding - 120, 12, 120, 28)
        )
        btn_apply.setTitle_("Anwenden")
        btn_apply.setBezelStyle_(NSBezelStyleRounded)
        btn_apply.setKeyEquivalent_("\r")  # Enter

        # Delegate für Button-Aktionen
        delegate = VisibilityWindowDelegate.alloc().initWithCheckboxes_window_app_(
            checkboxes, window, self
        )
        btn_all.setTarget_(delegate)
        btn_all.setAction_(objc.selector(delegate.onSelectAll_, signature=b"v@:@"))
        btn_apply.setTarget_(delegate)
        btn_apply.setAction_(objc.selector(delegate.onApply_, signature=b"v@:@"))

        content_view.addSubview_(btn_all)
        content_view.addSubview_(btn_apply)

        # Fenster und Delegate auf self speichern damit GC sie nicht freigibt
        self._visibility_window = window
        self._visibility_delegate = delegate
        window.setDelegate_(delegate)
        window.setReleasedWhenClosed_(False)

        window.center()
        window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

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

    def on_toggle_restore_on_login(self, sender):
        self.config["restore_on_login"] = not self.config.get("restore_on_login", True)
        save_config(self.config)
        state = self.config["restore_on_login"]
        rumps.notification(
            APP_NAME,
            "Login-Restore aktiviert" if state else "Login-Restore deaktiviert",
            "Icons werden beim nächsten Login automatisch wiederhergestellt."
            if state else "Icons werden beim Login nicht mehr automatisch wiederhergestellt."
        )
        self._build_menu()

    def on_toggle_restore_on_wake(self, sender):
        self.config["restore_on_wake"] = not self.config.get("restore_on_wake", True)
        save_config(self.config)
        state = self.config["restore_on_wake"]
        rumps.notification(
            APP_NAME,
            "Ruhemodus-Restore aktiviert" if state else "Ruhemodus-Restore deaktiviert",
            "Icons werden nach dem Aufwachen automatisch wiederhergestellt."
            if state else "Icons werden nach dem Aufwachen nicht mehr wiederhergestellt."
        )
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
                "IconGuard v1.1.0\n\n"
                "Speichert und stellt Desktop-Icon-Positionen\n"
                "automatisch wieder her.\n"
                "Icons können einzeln versteckt werden.\n\n"
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

    def _restore_on_login(self):
        """Stellt Icons beim App-Start wieder her (mit Verzögerung für Finder)."""
        profile = self.config["auto_restore_profile"]
        path = get_profile_path(profile)
        if not path.exists():
            return

        import time

        def task():
            # Warten bis der Finder bereit ist
            time.sleep(8)

            # Finder aktivieren
            try:
                run_applescript('tell application "Finder" to activate')
            except RuntimeError:
                pass
            time.sleep(2)

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    success, failed, error = restore_profile(profile)
                    if not error and success > 0:
                        msg = f"{success} Icons wiederhergestellt"
                        if failed:
                            msg += f", {failed} fehlgeschlagen"
                        rumps.notification(APP_NAME, f"Login-Restore: '{profile}'", msg)
                        return
                    elif attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    else:
                        rumps.notification(APP_NAME, f"Login-Restore: '{profile}'",
                                         error or "Keine Icons wiederhergestellt")
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    rumps.notification(APP_NAME, "Login-Restore Fehler", str(e))

        threading.Thread(target=task, daemon=True).start()

    # ── Sleep/Wake Beobachtung ────────────────────────────────────

    def _register_wake_observer(self):
        """Registriert einen Observer für Wake-from-Sleep Events."""
        self._wake_observer = SleepWakeObserver.alloc().initWithApp_(self)
        NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
            self._wake_observer,
            'handleWakeNotification:',
            NSWorkspaceDidWakeNotification,
            None
        )

    def _start_wake_detector(self):
        """Startet einen Timer der Wake-from-Sleep erkennt über Zeitsprünge."""
        self._wake_timer = rumps.Timer(self._check_wake, 10)
        self._wake_timer.start()

    def _check_wake(self, _):
        """Prüft auf Wake-from-Sleep (Zeitsprung) und Screen-Unlock (CGSession)."""
        now = time.time()
        elapsed = now - self._last_check_time
        self._last_check_time = now

        # 1. Zeitsprung-Erkennung: Timer ist 10s, >30s = Sleep/Wake
        if elapsed > 30:
            if self.config.get("restore_on_wake", True):
                self._restore_after_wake()
            return

        # 2. Screen-Lock/Unlock-Erkennung via CGSession-Polling
        try:
            session = _CGSessionCopyCurrentDictionary()
            is_locked = bool(session.get('CGSSessionScreenIsLocked', False)) if session else False
        except Exception:
            is_locked = False

        if self._screen_was_locked and not is_locked:
            # Bildschirm wurde gerade entsperrt
            if self.config.get("restore_on_wake", True):
                self._restore_after_wake()

        self._screen_was_locked = is_locked

    def _restore_after_wake(self):
        """Stellt Icons nach dem Aufwachen aus dem Ruhemodus wieder her."""
        profile = self.config["auto_restore_profile"]
        path = get_profile_path(profile)
        if not path.exists():
            return

        import time

        def task():
            # Warten bis Finder nach dem Aufwachen bereit ist
            time.sleep(3)

            # Finder aktivieren damit Desktop-Items geladen werden
            try:
                run_applescript('tell application "Finder" to activate')
            except RuntimeError:
                pass
            time.sleep(2)

            # Mehrere Versuche mit steigender Wartezeit
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    success, failed, error = restore_profile(profile)
                    if not error and success > 0:
                        msg = f"{success} Icons wiederhergestellt"
                        if failed:
                            msg += f", {failed} fehlgeschlagen"
                        rumps.notification(APP_NAME, f"Wake-Restore: '{profile}'", msg)
                        return
                    elif error:
                        if attempt < max_retries - 1:
                            time.sleep(5)
                            continue
                        rumps.notification(APP_NAME, "Wake-Restore Fehler", error)
                        return
                    else:
                        # success == 0, vielleicht Finder noch nicht bereit
                        if attempt < max_retries - 1:
                            time.sleep(5)
                            continue
                        rumps.notification(APP_NAME, f"Wake-Restore: '{profile}'",
                                         "Keine Icons wiederhergestellt")
                        return
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    rumps.notification(APP_NAME, "Wake-Restore Fehler", str(e))

        threading.Thread(target=task, daemon=True).start()


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
