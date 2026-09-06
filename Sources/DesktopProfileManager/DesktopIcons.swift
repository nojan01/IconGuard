import Foundation
import AppKit

/// Desktop-Icon-Positionen und Sichtbarkeit von Desktop-Dateien.
enum DesktopIcons {

    /// Liest alle Desktop-Icon-Positionen als [name: (x, y)].
    static func getPositions() -> [String: (x: Int, y: Int)] {
        let script = """
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
        """
        guard let raw = Shell.runAppleScript(script) else { return [:] }
        var positions: [String: (x: Int, y: Int)] = [:]
        for line in raw.split(separator: "\n") {
            let parts = line.components(separatedBy: "||")
            if parts.count == 3,
               let x = Double(parts[1]), let y = Double(parts[2]) {
                positions[parts[0]] = (Int(x), Int(y))
            }
        }
        return positions
    }

    /// Setzt Positionen per Referenz-Iteration (umgeht macOS-Namen-Lookup-Bug).
    @discardableResult
    static func setPositions(_ positions: [String: (x: Int, y: Int)],
                             shouldCancel: () -> Bool = { false }) -> (success: Int, failed: Int) {
        if positions.isEmpty { return (0, 0) }
        var entries: [String] = []
        for (name, pos) in positions {
            entries.append("{\"\(Shell.esc(name))\", \(pos.x), \(pos.y)}")
        }
        let targets = "{" + entries.joined(separator: ", ") + "}"
        let script = """
        set targets to \(targets)
        set successCount to 0
        set failedCount to 0
        tell application "Finder"
            set allItems to every item of desktop
            repeat with t in targets
                set tName to item 1 of t
                set tX to item 2 of t
                set tY to item 3 of t
                set foundIt to false
                repeat with anItem in allItems
                    try
                        if (name of anItem as text) is tName then
                            set desktop position of anItem to {tX, tY}
                            set successCount to successCount + 1
                            set foundIt to true
                            exit repeat
                        end if
                    end try
                end repeat
                if not foundIt then set failedCount to failedCount + 1
            end repeat
        end tell
        return (successCount as text) & "|" & (failedCount as text)
        """
        guard let result = Shell.runAppleScript(
            script,
            timeout: positionRestoreTimeout(itemCount: positions.count),
            shouldCancel: shouldCancel) else { return (0, positions.count) }
        let parts = result.components(separatedBy: "|")
        if parts.count == 2, let s = Int(parts[0]), let f = Int(parts[1]) {
            // Finder übernimmt die Koordinaten zwar per AppleScript, zeichnet den
            // Desktop auf aktuellen macOS-Versionen aber nicht immer sofort neu.
            // Ein gezieltes Update verhindert, dass die alten Positionen sichtbar
            // bleiben oder später wieder darübergelegt werden.
            if s > 0 { refreshFinderDesktop() }
            return (s, f)
        }
        return (0, positions.count)
    }

    static func positionRestoreTimeout(itemCount: Int) -> TimeInterval {
        min(30, max(10, 5 + (Double(itemCount) * 0.1)))
    }

    // MARK: - Sichtbarkeit (versteckte Desktop-Dateien)

    struct DesktopItem { let name: String; let hidden: Bool }

    static func getAllItems() -> [DesktopItem] {
        let fm = FileManager.default
        guard let entries = try? fm.contentsOfDirectory(at: Paths.desktop,
                                                        includingPropertiesForKeys: [.isHiddenKey],
                                                        options: []) else { return [] }
        var items: [DesktopItem] = []
        for url in entries {
            let name = url.lastPathComponent
            if name.hasPrefix(".") { continue }
            let hidden = (try? url.resourceValues(forKeys: [.isHiddenKey]))?.isHidden ?? false
            items.append(DesktopItem(name: name, hidden: hidden))
        }
        return items.sorted { $0.name < $1.name }
    }

    static func getHiddenItems() -> [String] {
        return getAllItems().filter { $0.hidden }.map { $0.name }
    }

    /// Wendet mehrere Sichtbarkeitsänderungen an und aktualisiert Finder danach
    /// genau einmal.
    @discardableResult
    static func applyVisibility(_ changes: [(name: String, hidden: Bool)])
        -> (success: Int, failed: Int) {
        var success = 0
        var failed = 0
        var hidItem = false

        for change in changes {
            if setHidden(change.name, change.hidden) {
                success += 1
                if change.hidden { hidItem = true }
            } else {
                failed += 1
            }
        }

        if hidItem {
            enforceFinderHidesHiddenFiles()
        } else if success > 0 {
            refreshFinderDesktop()
        }
        return (success, failed)
    }

    @discardableResult
    static func hideItem(_ name: String) -> Bool {
        return applyVisibility([(name, true)]).failed == 0
    }

    @discardableResult
    static func unhideItem(_ name: String) -> Bool {
        return applyVisibility([(name, false)]).failed == 0
    }

    private static func setHidden(_ name: String, _ hidden: Bool) -> Bool {
        let url = Paths.desktop.appendingPathComponent(name)
        guard FileManager.default.fileExists(atPath: url.path) else { return false }
        do {
            var values = URLResourceValues()
            values.isHidden = hidden
            var mutableURL = url
            try mutableURL.setResourceValues(values)
            return true
        } catch {
            return false
        }
    }

    /// macOS zeigt unsichtbare Dateien ausgegraut an, wenn Finders globale
    /// Anzeige versteckter Dateien aktiv ist. Beim Ausblenden muss diese Option
    /// daher explizit ausgeschaltet und Finder neu geladen werden.
    private static func enforceFinderHidesHiddenFiles() {
        let result = Shell.run("/usr/bin/defaults", finderVisibilityArguments(showHiddenFiles: false))
        if result.code == 0 {
            let restart = Shell.run("/usr/bin/killall", ["Finder"], timeout: 5)
            if restart.code == 0 { return }
        }
        refreshFinderDesktop()
    }

    static func finderVisibilityArguments(showHiddenFiles: Bool) -> [String] {
        return ["write", "com.apple.finder", "AppleShowAllFiles", "-bool",
                showHiddenFiles ? "true" : "false"]
    }

    /// Erzwingt, dass Finder die geänderten Dateiattribute neu einliest, ohne
    /// Finder neu zu starten. Wird insbesondere beim Einblenden verwendet.
    private static func refreshFinderDesktop() {
        NSWorkspace.shared.noteFileSystemChanged(Paths.desktop.path)
        if Shell.runAppleScript(finderRefreshScript(desktopPath: Paths.desktop.path)) == nil {
            _ = Shell.run("/usr/bin/killall", ["Finder"], timeout: 5)
        }
    }

    static func finderRefreshScript(desktopPath: String) -> String {
        return """
        set desktopFolder to (POSIX file "\(Shell.esc(desktopPath))") as alias
        tell application "Finder"
            update desktopFolder
        end tell
        """
    }
}
