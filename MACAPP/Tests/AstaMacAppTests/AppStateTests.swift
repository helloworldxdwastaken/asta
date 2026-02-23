import XCTest
import AstaAPIClient
@testable import AstaMacApp

@MainActor
final class AppStateTests: XCTestCase {

    func testStatusLineWhenDisconnected() {
        let state = AppState()
        state.health = nil
        state.loading = false
        XCTAssertEqual(state.statusLine, "Cannot reach Asta")
    }

    func testStatusLineWhenLoading() {
        let state = AppState()
        state.health = nil
        state.loading = true
        XCTAssertEqual(state.statusLine, "Checking…")
    }

    func testStatusLineWhenConnected() throws {
        let state = AppState()
        let json = #"{"status": "ok", "app": "Asta", "version": "1.0"}"#.data(using: .utf8)!
        state.health = try JSONDecoder().decode(AstaHealth.self, from: json)
        state.loading = false
        XCTAssertEqual(state.statusLine, "Asta running")
        XCTAssertTrue(state.connected)
    }
}
