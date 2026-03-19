"""
py2app Setup – erzeugt IconGuard.app
Aufruf: python3 setup_app.py py2app

Copyright (c) 2026 Norbert Jander
Lizenz: MIT
"""

from setuptools import setup
import os

APP_NAME = "IconGuard"
APP_VERSION = "1.0.0"
APP_SCRIPT = "iconguard_app.py"
ICON_FILE = "icon.icns"

setup(
    name=APP_NAME,
    version=APP_VERSION,
    app=[APP_SCRIPT],
    data_files=[],
    options={
        "py2app": {
            "iconfile": ICON_FILE,
            "plist": {
                "CFBundleName": APP_NAME,
                "CFBundleDisplayName": APP_NAME,
                "CFBundleIdentifier": "com.iconguard.app",
                "CFBundleVersion": APP_VERSION,
                "CFBundleShortVersionString": APP_VERSION,
                "LSMinimumSystemVersion": "12.0",
                "LSUIElement": True,  # Kein Dock-Icon
                "NSHumanReadableCopyright": "Copyright © 2026 Norbert Jander. MIT License.",
                "CFBundleDocumentTypes": [],
                "NSAppleEventsUsageDescription":
                    "IconGuard benötigt Zugriff auf den Finder, "
                    "um Desktop-Icon-Positionen zu lesen und zu setzen.",
            },
            "packages": ["rumps", "AppKit", "objc"],
            "includes": [
                "rumps",
                "AppKit",
                "Foundation",
            ],
            "frameworks": [],
            "strip": True,
            "optimize": 2,
            "semi_standalone": False,
            "site_packages": True,
            "arch": "universal2",
        }
    },
    setup_requires=["py2app"],
)
