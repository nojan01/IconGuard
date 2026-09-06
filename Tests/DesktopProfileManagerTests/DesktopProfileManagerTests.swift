import XCTest
@testable import DesktopProfileManager

final class DesktopProfileManagerTests: XCTestCase {
    func testProfileNamesAreValidatedWithoutSilentCollisions() {
        XCTAssertEqual(Profiles.validatedName("Work 2026"), "Work 2026")
        XCTAssertNil(Profiles.validatedName("Work/Home"))
        XCTAssertNil(Profiles.profilePath("Work/Home"))
    }

    func testImportedProfileNameIsNormalized() {
        XCTAssertEqual(Profiles.importName(" Work/Home "), "WorkHome")
        XCTAssertNil(Profiles.importName("///"))
    }

    func testMITLicenseTextIsAvailableInBothLanguages() {
        XCTAssertTrue(AppLicense.mitText(for: .de).contains("MIT-Lizenz"))
        XCTAssertTrue(AppLicense.mitText(for: .de).contains("Verbindlich ist die englische"))
        XCTAssertTrue(AppLicense.mitText(for: .en).contains("MIT License"))
        XCTAssertTrue(AppLicense.mitText(for: .en).contains("THE SOFTWARE IS PROVIDED"))
    }

    func testShellReadsLargeStandardOutputBeforeWaitingForExit() {
        let result = Shell.run("/bin/sh", ["-c", "head -c 131072 /dev/zero | tr '\\0' x"], timeout: 5)
        XCTAssertEqual(result.code, 0)
        XCTAssertEqual(result.output.count, 131_072)
    }

    func testShellTimeoutNeverWaitsForeverForInheritedPipes() {
        let started = Date()
        let result = Shell.run(
            "/bin/sh",
            ["-c", "(sleep 8) & trap '' TERM; while :; do sleep 1; done"],
            timeout: 0.1)
        XCTAssertEqual(result.code, -1)
        XCTAssertLessThan(Date().timeIntervalSince(started), 5)
    }

    func testShellProcessCanBeCancelledBeforeItsTimeout() {
        let started = Date()
        var checks = 0
        let result = Shell.run("/bin/sleep", ["30"], timeout: 30) {
            checks += 1
            return checks >= 2
        }
        XCTAssertEqual(result.code, -1)
        XCTAssertLessThan(Date().timeIntervalSince(started), 5)
    }

    func testDesktopIconRestoreTimeoutScalesButStaysBounded() {
        XCTAssertEqual(DesktopIcons.positionRestoreTimeout(itemCount: 2), 10)
        XCTAssertEqual(DesktopIcons.positionRestoreTimeout(itemCount: 200), 25)
        XCTAssertEqual(DesktopIcons.positionRestoreTimeout(itemCount: 1000), 30)
    }

    func testDesktopIconRestoreRetriesFinderTwice() {
        XCTAssertEqual(DesktopIcons.positionRestoreRetryCount, 2)
        XCTAssertEqual(DesktopIcons.positionRestoreRetryDelay, 0.6)
    }

    func testFinderVisibilityArgumentsDisableShowingHiddenFiles() {
        XCTAssertEqual(DesktopIcons.finderVisibilityArguments(showHiddenFiles: false), [
            "write", "com.apple.finder", "AppleShowAllFiles", "-bool", "false",
        ])
    }

    func testFinderRefreshScriptEscapesDesktopPath() {
        let script = DesktopIcons.finderRefreshScript(
            desktopPath: #"/Users/Test/Desktop "quoted""#)

        XCTAssertTrue(script.contains(
            #"set desktopFolder to (POSIX file "/Users/Test/Desktop \"quoted\"") as alias"#))
        XCTAssertTrue(script.contains("update desktopFolder"))
    }

    func testBrowserTabsAcceptOnlyUniqueWebAndLocalFileURLs() {
        let urls = BrowserTabs.validURLs([
            "https://example.com",
            "https://example.com",
            "http://localhost:8080/path",
            "file:///Users/nojan/Documents/GitHub/streaming-selector/index.html",
            "file:///Users/nojan/Documents/GitHub/streaming-selector/index.html",
            "file://remote-host/Shared/index.html",
            "file:relative/index.html",
            "not a url",
        ])
        XCTAssertEqual(urls, [
            "https://example.com",
            "http://localhost:8080/path",
            "file:///Users/nojan/Documents/GitHub/streaming-selector/index.html",
        ])
    }

    func testBrowserQuitUsesBoundedTimeout() {
        XCTAssertEqual(BrowserTabs.quitTimeout, 15)
        XCTAssertEqual(BrowserTabs.windowRestoreDelay, 2)
    }

    func testBrowserTabsParseSkipsUnsupportedValues() {
        let parsed = BrowserTabs.parse([
            "com.apple.Safari": ["https://example.com", "file:///Users/nojan/index.html", "invalid"],
            "com.google.Chrome": "not an array",
        ])
        XCTAssertEqual(parsed, ["com.apple.Safari": ["https://example.com", "file:///Users/nojan/index.html"]])
    }

    func testBrowserTabsKeepPreviousTabsWhenCaptureTemporarilyReturnsNothing() {
        let retained = BrowserTabs.tabsForSave(
            captured: [:],
            existing: ["com.apple.Safari": ["https://example.com"]],
            captureRequested: true)
        XCTAssertTrue(retained.preserved)
        XCTAssertEqual(retained.tabs, ["com.apple.Safari": ["https://example.com"]])

        let replacement = BrowserTabs.tabsForSave(
            captured: ["com.apple.Safari": ["https://new.example"]],
            existing: ["com.apple.Safari": ["https://example.com"]],
            captureRequested: true)
        XCTAssertFalse(replacement.preserved)
        XCTAssertEqual(replacement.tabs, ["com.apple.Safari": ["https://new.example"]])
    }

    func testBrowserLaunchPassesAllTabsInOneOpenCall() {
        XCTAssertEqual(BrowserTabs.launchArguments(
            bundleID: "com.apple.Safari",
            urls: ["https://example.com", "file:///Users/nojan/index.html"]), [
                "-b",
                "com.apple.Safari",
                "https://example.com",
                "file:///Users/nojan/index.html",
            ])
    }

    func testBrowserQuitDoesNotWaitForAppleScriptResponse() {
        let script = BrowserTabs.quitScript(browserName: "Safari")
        XCTAssertTrue(script.contains("ignoring application responses"))
        XCTAssertTrue(script.contains("tell application \"Safari\" to quit"))
    }

    func testBrowserWindowPositionsAreParsedAndValidated() {
        let parsed = BrowserTabs.parseWindowPositions([
            "com.apple.Safari": [
                ["x": 120, "y": 80, "w": 1400, "h": 900],
                ["x": 0, "y": 0, "w": 0, "h": 900],
            ],
            "com.google.Chrome": "invalid",
        ])
        XCTAssertEqual(parsed, [
            "com.apple.Safari": [["x": 120, "y": 80, "w": 1400, "h": 900]],
        ])
    }

    func testBrowserWindowPositionsArePreservedWhenCaptureIsTemporarilyEmpty() {
        let previous: [String: Any] = [
            "com.apple.Safari": [["x": 120, "y": 80, "w": 1400, "h": 900]],
        ]
        XCTAssertEqual(BrowserTabs.windowPositionsForSave(
            captured: [:], existing: previous, captureRequested: true), [
                "com.apple.Safari": [["x": 120, "y": 80, "w": 1400, "h": 900]],
            ])
    }

    func testRestoreActivityRejectsAnotherSwitchUntilFinished() {
        let gate = RestoreActivityGate()
        XCTAssertTrue(gate.begin())
        XCTAssertTrue(gate.isActive)
        XCTAssertFalse(gate.begin())
        gate.finish()
        XCTAssertFalse(gate.isActive)
        XCTAssertTrue(gate.begin())
    }

    func testCancelledAppLaunchReturnsWithoutOpeningAnything() {
        let app = Apps.AppInfo(name: "Must Not Launch", bundleID: nil,
                               path: "/Applications/Must Not Launch.app")
        XCTAssertEqual(Apps.launch([app], shouldCancel: { true }), 0)
    }

    func testFinderDesktopServiceShowsIconsWithoutActivatingFinder() {
        let script = Apps.finderDesktopOnlyScript()
        XCTAssertTrue(script.contains("set visible of finderWindow to false"))
        XCTAssertTrue(script.contains("set visible of process \"Finder\" to true"))
        XCTAssertFalse(script.lowercased().contains("activate"))
    }

    func testBrowserWithSavedTabsIsExcludedFromGeneralAppLaunch() {
        let safari = Apps.AppInfo(name: "Safari", bundleID: "com.apple.Safari",
                                  path: "/Applications/Safari.app")
        let thunderbird = Apps.AppInfo(name: "Thunderbird", bundleID: "org.mozilla.thunderbird",
                                       path: "/Applications/Thunderbird.app")
        let result = Profiles.appsForGeneralLaunch(
            [safari, thunderbird],
            browserTabs: ["com.apple.Safari": ["https://example.com"]])
        XCTAssertEqual(result.map(\.name), ["Thunderbird"])
    }

    func testUpdateReleaseUsesDMGAssetAndIgnoresOtherAssets() throws {
        let data = try XCTUnwrap("""
        {
          "tag_name": "v1.4.0",
          "assets": [
            {"name": "checksums.txt", "browser_download_url": "https://example.com/checksums.txt"},
            {"name": "DesktopProfileManager-1.4.0.dmg", "browser_download_url": "https://example.com/app.dmg"}
          ]
        }
        """.data(using: .utf8))

        let release = try XCTUnwrap(UpdateManager.release(from: data))
        XCTAssertEqual(release.version, "1.4.0")
        XCTAssertEqual(release.assetName, "DesktopProfileManager-1.4.0.dmg")
        XCTAssertEqual(release.downloadURL, URL(string: "https://example.com/app.dmg"))
    }

    func testUpdateReleaseWithoutDMGCanStillReportVersion() throws {
        let data = try XCTUnwrap("""
        {"tag_name": "v1.4.0", "assets": []}
        """.data(using: .utf8))

        let release = try XCTUnwrap(UpdateManager.release(from: data))
        XCTAssertEqual(release.version, "1.4.0")
        XCTAssertNil(release.downloadURL)
        XCTAssertNil(release.assetName)
    }
}
