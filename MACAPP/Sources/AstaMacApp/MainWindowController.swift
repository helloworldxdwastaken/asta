import AppKit
import SwiftUI

/// Owns the single persistent main window — the ChatGPT / Claude mac app pattern.
/// Cmd+Option+Space or tray-click shows/hides it. Closing hides (not destroys) it so
/// conversation history survives.
@MainActor
final class MainWindowController: NSObject, NSWindowDelegate {
    static let shared = MainWindowController()
    var appState: AppState?

    private var window: NSWindow?
    private override init() { super.init() }

    // MARK: - Public API

    func show() {
        if let w = window {
            NSApplication.shared.setActivationPolicy(.regular)
            NSApplication.shared.activate(ignoringOtherApps: true)
            w.makeKeyAndOrderFront(nil)
            return
        }
        guard let appState else { return }
        buildWindow(appState: appState)
    }

    func hide() {
        window?.orderOut(nil)
        // Drop back to accessory so the Dock icon disappears while hidden
        NSApplication.shared.setActivationPolicy(.accessory)
    }

    func toggle() {
        if let w = window, w.isVisible { hide() } else { show() }
    }

    // MARK: - Build

    private func buildWindow(appState: AppState) {
        let content = NSHostingView(rootView: ContentView(appState: appState))
        let w = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 960, height: 680),
            styleMask:   [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing:     .buffered,
            defer:       false
        )
        w.title                       = "Asta"
        w.titlebarAppearsTransparent  = true
        w.titleVisibility             = .hidden
        w.isMovableByWindowBackground = true
        w.contentView                 = content
        w.minSize                     = NSSize(width: 740, height: 520)
        w.setFrameAutosaveName("AstaMainWindow")
        w.collectionBehavior          = [.managed, .fullScreenPrimary]
        w.delegate                    = self
        window = w

        if w.frame.origin == .zero { w.center() }
        NSApplication.shared.setActivationPolicy(.regular)
        NSApplication.shared.activate(ignoringOtherApps: true)
        w.makeKeyAndOrderFront(nil)
    }

    // MARK: - NSWindowDelegate

    /// Intercept the close button — hide instead of destroy
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        hide()
        return false
    }

    func windowWillClose(_ notification: Notification) {
        NSApplication.shared.setActivationPolicy(.accessory)
    }
}
