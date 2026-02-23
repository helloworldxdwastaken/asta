import XCTest
@testable import AstaMacApp

@MainActor
final class PanelManagerTests: XCTestCase {

    func testPanelManagerSingletonExists() {
        let manager = PanelManager.shared
        XCTAssertNotNil(manager)
        XCTAssertTrue(PanelManager.shared === manager)
    }

    func testShowAstaPanelDoesNotCrashWhenAppStateNil() {
        PanelManager.shared.appState = nil
        PanelManager.shared.showAstaPanel()
        // Just assert we didn’t crash; panel may or may not show without app state for About/Chat
    }

    func testShowAboutDoesNotCrashWhenAppStateSet() {
        let appState = AppState()
        PanelManager.shared.appState = appState
        PanelManager.shared.showAbout()
        // If we get here without crashing, the panel was created
    }
}
