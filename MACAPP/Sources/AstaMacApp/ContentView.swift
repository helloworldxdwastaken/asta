import SwiftUI
import AppKit

// MARK: - Root layout (sidebar + chat, Claude.ai style)

struct ContentView: View {
    @ObservedObject var appState: AppState
    @State private var showSettings = false
    @State private var showAgents = false
    @State private var selectedConvID: String? = nil
    @State private var columnVisibility: NavigationSplitViewVisibility = .all

    /// Select a conversation from the sidebar: clear first, then set — so ChatView
    /// sees nil (clears messages) before seeing the new ID (loads history).
    private func selectConversation(_ id: String) {
        guard id != selectedConvID else { return }
        selectedConvID = nil
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            selectedConvID = id
        }
    }

    var body: some View {
        NavigationSplitView(columnVisibility: $columnVisibility) {
            SidebarView(
                appState:           appState,
                selectedConvID:     $selectedConvID,
                showSettings:       $showSettings,
                showAgents:         $showAgents,
                onSelectConversation: selectConversation
            )
            .navigationSplitViewColumnWidth(min: 200, ideal: 240, max: 290)
        } detail: {
            ChatView(
                appState:       appState,
                conversationID: $selectedConvID
            )
        }
        .navigationSplitViewStyle(.balanced)
        .sheet(isPresented: $showSettings) {
            SettingsView(appState: appState)
        }
        .sheet(isPresented: $showAgents) {
            AgentsSettingsTab(appState: appState)
                .frame(width: 760, height: 560)
        }
        .task { await appState.load() }
    }
}
