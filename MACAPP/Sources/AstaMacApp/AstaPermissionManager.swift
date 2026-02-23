// OpenClaw-style permission handling for Asta (Accessibility for global hotkey / Option+Space).
import AppKit
import ApplicationServices
import Foundation
import SwiftUI

enum AstaPermissionManager {
    /// Returns whether the app has Accessibility permission (required for global hotkey).
    static var isAccessibilityAuthorized: Bool {
        AXIsProcessTrusted()
    }

    /// Requests Accessibility permission (shows system prompt). Call when you need to prompt the user.
    static func requestAccessibility(interactive: Bool) async -> Bool {
        let trusted = AXIsProcessTrusted()
        if interactive, !trusted {
            await MainActor.run {
                let opts: NSDictionary = ["AXTrustedCheckOptionPrompt": true]
                _ = AXIsProcessTrustedWithOptions(opts)
            }
        }
        return AXIsProcessTrusted()
    }

    /// Opens System Settings → Privacy & Security → Accessibility so the user can enable Asta.
    static func openAccessibilitySettings() {
        let candidates = [
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            "x-apple.systempreferences:com.apple.preference.security",
        ]
        for candidate in candidates {
            if let url = URL(string: candidate), NSWorkspace.shared.open(url) {
                return
            }
        }
    }
}
