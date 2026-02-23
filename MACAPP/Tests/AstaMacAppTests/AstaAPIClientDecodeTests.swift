import XCTest
import AstaAPIClient

/// Tests that API response DTOs decode correctly (like a Python test for serialization).
final class AstaAPIClientDecodeTests: XCTestCase {

    func testDecodeAstaHealth() throws {
        let json = """
        {"status": "ok", "app": "Asta", "version": "1.2.3"}
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        let health = try decoder.decode(AstaHealth.self, from: json)
        XCTAssertEqual(health.status, "ok")
        XCTAssertEqual(health.app, "Asta")
        XCTAssertEqual(health.version, "1.2.3")
    }

    func testDecodeAstaCheckUpdate() throws {
        let json = """
        {"update_available": true, "local": "abc1234", "remote": "def5678"}
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        let update = try decoder.decode(AstaCheckUpdate.self, from: json)
        XCTAssertEqual(update.update_available, true)
        XCTAssertEqual(update.local, "abc1234")
        XCTAssertEqual(update.remote, "def5678")
    }

    func testDecodeAstaServerStatus() throws {
        let json = """
        {"ok": true, "version": "1.0", "cpu_percent": 12.5, "ram": {"total_gb": 16, "used_gb": 8, "percent": 50}, "disk": {"total_gb": 256, "used_gb": 128, "percent": 50}, "uptime_str": "1d 2h 3m"}
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        let status = try decoder.decode(AstaServerStatus.self, from: json)
        XCTAssertEqual(status.ok, true)
        XCTAssertEqual(status.cpu_percent, 12.5)
        XCTAssertEqual(status.ram?.total_gb, 16)
        XCTAssertEqual(status.ram?.used_gb, 8)
        XCTAssertEqual(status.uptime_str, "1d 2h 3m")
    }
}
