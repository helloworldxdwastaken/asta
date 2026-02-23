import AppKit
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    static weak var sharedAppState: AppState?

    private var globalMonitor: Any?
    private var localMonitor: Any?
    private var accessibilityTimer: Timer?
    private var hadAccessibility = false
    private var statusItem: NSStatusItem?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApplication.shared.setActivationPolicy(.accessory)
        buildTrayMenu()
        registerHotkey()
        hadAccessibility = AXIsProcessTrusted()
        // Re-register global monitor if accessibility is granted after launch
        accessibilityTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.checkAccessibility() }
        }
        // Start Tailscale status polling
        Task {
            await TailscaleManager.shared.refreshTailscaleStatus()
            TailscaleManager.shared.startPolling()
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func applicationWillTerminate(_ notification: Notification) {
        accessibilityTimer?.invalidate()
        if let m = localMonitor  { NSEvent.removeMonitor(m) }
        if let m = globalMonitor { NSEvent.removeMonitor(m) }
    }

    // MARK: - Tray

    private func buildTrayMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let btn = statusItem?.button {
            btn.image = CritterIconRenderer.makeIcon()
            btn.action = #selector(trayClicked)
            btn.target = self
        }
    }

    @objc private func trayClicked() {
        // Build a tiny menu: Open + Quit
        let menu = NSMenu()
        menu.addItem(withTitle: "Open Asta", action: #selector(openAsta), keyEquivalent: "")
            .target = self
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        statusItem?.menu = menu
        statusItem?.button?.performClick(nil)
        statusItem?.menu = nil  // reset so next click works
    }

    @objc private func openAsta() {
        MainWindowController.shared.show()
    }

    // MARK: - Cmd+Option+Space hotkey

    private func registerHotkey() {
        localMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if self?.isCmdOptionSpace(event) == true {
                Task { @MainActor in MainWindowController.shared.toggle() }
                return nil
            }
            return event
        }
        if AXIsProcessTrusted() {
            globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
                if self?.isCmdOptionSpace(event) == true {
                    Task { @MainActor in MainWindowController.shared.toggle() }
                }
            }
        }
    }

    private func isCmdOptionSpace(_ event: NSEvent) -> Bool {
        let mods = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        return mods == [.command, .option] && event.keyCode == 49
    }

    private func checkAccessibility() {
        let now = AXIsProcessTrusted()
        guard now != hadAccessibility else { return }
        hadAccessibility = now
        if let m = globalMonitor { NSEvent.removeMonitor(m); globalMonitor = nil }
        if now {
            globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
                if self?.isCmdOptionSpace(event) == true {
                    Task { @MainActor in MainWindowController.shared.toggle() }
                }
            }
        }
    }
}
