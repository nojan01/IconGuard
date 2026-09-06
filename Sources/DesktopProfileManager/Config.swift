import Foundation

/// Globale Konstanten – kompatibel zur Python-App (gleicher ~/.iconguard-Ordner).
enum Paths {
    static let appName = "Desktop Profile Manager"
    static let appVersion = "1.5.9"

    static let profilesDir: URL = FileManager.default
        .homeDirectoryForCurrentUser.appendingPathComponent(".iconguard", isDirectory: true)

    static let configPath: URL = profilesDir.appendingPathComponent("_config.json")

    static var desktop: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Desktop", isDirectory: true)
    }
}

let intervalOptions = [5, 10, 15, 30, 60, 120, 240]

/// Lädt/speichert die App-Konfiguration als veränderbares Dictionary.
final class Config {
    static let defaults: [String: Any] = [
        "auto_restore_enabled": false,
        "auto_restore_profile": "default",
        "auto_restore_interval_minutes": 30,
        "auto_restore_icons_only": false,
        "restore_on_login": true,
        "restore_on_wake": true,
        "restore_wallpaper": true,
        "restore_apps": true,
        "hide_other_apps": false,
        "quit_other_apps": false,
        "app_exclusions": [String](),
        "language": "system",
        "app_launch_delay": 1.5,
        "hotkeys_enabled": false,
        "hotkey_modifier": "cmd_ctrl",
        "auto_switch_enabled": false,
        "auto_switch_rules": [[String: Any]](),
        "widget_visible": false,
        "widget_pos": NSNull(),
        "widget_compact": false,
    ]

    private(set) var values: [String: Any]

    init() {
        var merged = Config.defaults
        if let data = try? Data(contentsOf: Paths.configPath),
           let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            for (k, v) in obj { merged[k] = v }
        }
        self.values = merged
    }

    func get<T>(_ key: String, _ fallback: T) -> T {
        if let v = values[key] as? T { return v }
        return fallback
    }

    func set(_ key: String, _ value: Any) {
        values[key] = value
    }

    func save() {
        try? FileManager.default.createDirectory(at: Paths.profilesDir, withIntermediateDirectories: true)
        if let data = try? JSONSerialization.data(withJSONObject: values, options: [.prettyPrinted, .sortedKeys]) {
            try? data.write(to: Paths.configPath, options: .atomic)
        }
    }
}
