import Foundation
import AppKit
import Combine

// MARK: - Tailscale status

enum TailscaleStatus: Equatable {
    case notInstalled
    case notLoggedIn
    case disconnected
    case connecting
    case connected(ip: String)

    var isConnected: Bool { if case .connected = self { return true }; return false }

    var ip: String? {
        if case .connected(let ip) = self { return ip.isEmpty ? nil : ip }
        return nil
    }

    var label: String {
        switch self {
        case .notInstalled:      return "Tailscale not installed"
        case .notLoggedIn:       return "Not logged in"
        case .disconnected:      return "Disconnected"
        case .connecting:        return "Connecting…"
        case .connected(let ip): return ip.isEmpty ? "Connected" : "Connected · \(ip)"
        }
    }
}

// MARK: - Manager

@MainActor
final class TailscaleManager: ObservableObject {
    static let shared = TailscaleManager()

    @Published var tsStatus: TailscaleStatus = .notInstalled
    @Published var tsInstalled = false
    /// MagicDNS hostname, e.g. "mymac.tail12345.ts.net" (trailing dot stripped)
    @Published var tsDNSName: String? = nil
    /// True when `tailscale serve` is forwarding HTTPS → local backend
    @Published var tsServeEnabled: Bool = false

    private var pollTask: Task<Void, Never>?
    private let tsBinPaths = [
        "/usr/local/bin/tailscale",
        "/opt/homebrew/bin/tailscale",
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    ]

    private init() {}

    // MARK: - Tailscale CLI

    private func tsBinary() -> String? {
        tsBinPaths.first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    private func tsRun(_ args: [String]) async -> (output: String, code: Int32) {
        guard let bin = tsBinary() else { return ("", 1) }
        return await Task.detached(priority: .utility) {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: bin)
            p.arguments = args
            let pipe = Pipe()
            p.standardOutput = pipe; p.standardError = pipe
            do {
                try p.run(); p.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                return (String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "", p.terminationStatus)
            } catch { return ("", 1) }
        }.value
    }

    func refreshTailscaleStatus() async {
        guard let _ = tsBinary() else {
            tsInstalled = false; tsStatus = .notInstalled; tsDNSName = nil; return
        }
        tsInstalled = true
        let (out, code) = await tsRun(["status", "--json"])
        guard code == 0, !out.isEmpty,
              let data = out.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { tsStatus = .notLoggedIn; tsDNSName = nil; return }

        let self_ = json["Self"] as? [String: Any]

        // Extract MagicDNS hostname (strip trailing dot)
        if let dns = self_?["DNSName"] as? String, !dns.isEmpty {
            tsDNSName = dns.hasSuffix(".") ? String(dns.dropLast()) : dns
        } else {
            tsDNSName = nil
        }

        switch (json["BackendState"] as? String) ?? "" {
        case "NeedsLogin": tsStatus = .notLoggedIn
        case "Stopped":    tsStatus = .disconnected
        case "Running":
            let ip = (self_?["TailscaleIPs"] as? [String])?.first ?? ""
            tsStatus = .connected(ip: ip)
        default: tsStatus = .disconnected
        }

        await refreshServeStatus()
    }

    // MARK: - Tailscale Serve (HTTPS tunnel)

    /// Check whether `tailscale serve` is currently forwarding to our local backend.
    func refreshServeStatus() async {
        let (out, _) = await tsRun(["serve", "status"])
        tsServeEnabled = !out.contains("No serve config") && !out.trimmingCharacters(in: .whitespaces).isEmpty
    }

    /// Run `tailscale serve --bg http://localhost:<port>` to expose the backend over HTTPS.
    func setupServeHTTPS(port: Int) async {
        _ = await tsRun(["serve", "--bg", "http://localhost:\(port)"])
        await refreshServeStatus()
    }

    /// Disable the serve config.
    func teardownServeHTTPS() async {
        _ = await tsRun(["serve", "--https=443", "off"])
        await refreshServeStatus()
    }

    @discardableResult
    func connectTailscale() async -> Bool {
        guard tsInstalled else { return false }
        tsStatus = .connecting
        _ = await tsRun(["up"])
        await refreshTailscaleStatus()
        return tsStatus.isConnected
    }

    func loginTailscale() async {
        guard tsInstalled else { return }
        let (out, _) = await tsRun(["login"])
        for line in out.components(separatedBy: .newlines) {
            let t = line.trimmingCharacters(in: .whitespaces)
            if t.hasPrefix("https://"), let url = URL(string: t) {
                _ = NSWorkspace.shared.open(url); return
            }
        }
        if FileManager.default.fileExists(atPath: "/Applications/Tailscale.app") {
            _ = NSWorkspace.shared.open(URL(fileURLWithPath: "/Applications/Tailscale.app"))
        }
        await refreshTailscaleStatus()
    }

    func disconnectTailscale() async {
        guard tsInstalled else { return }
        _ = await tsRun(["down"])
        await refreshTailscaleStatus()
    }

    // MARK: - Polling

    func startPolling() {
        pollTask?.cancel()
        pollTask = Task {
            while !Task.isCancelled {
                await refreshTailscaleStatus()
                try? await Task.sleep(nanoseconds: 20_000_000_000)
            }
        }
    }

    func stopPolling() { pollTask?.cancel(); pollTask = nil }
}
