import SwiftUI
import AppKit
import AstaAPIClient

// MARK: - Sidebar (conversation list + nav + settings gear)

struct SidebarView: View {
    @ObservedObject var appState: AppState
    @Binding var selectedConvID: String?
    @Binding var showSettings: Bool
    var onSelectConversation: (String) -> Void

    @State private var conversations: [AstaConversationItem] = []
    @State private var loading = false

    // Sidebar palette — uses NSColor so it adapts to light/dark
    private var sidebarBg:    Color { Color(nsColor: .windowBackgroundColor) }
    private var textPrimary:  Color { Color(nsColor: .labelColor) }
    private var textSecondary: Color { Color(nsColor: .secondaryLabelColor) }
    private var accentColor:  Color { Color.accentColor }
    private var divider:      Color { Color(nsColor: .separatorColor) }

    var body: some View {
        VStack(spacing: 0) {
            // ── New chat button ───────────────────────────────────────────
            newChatButton
                .padding(.horizontal, 12)
                .padding(.top, 52)
                .padding(.bottom, 8)

            Divider().opacity(0.4)

            // ── Conversation list ─────────────────────────────────────────
            ScrollView {
                LazyVStack(spacing: 2) {
                    if loading && conversations.isEmpty {
                        ProgressView().padding(.top, 20)
                    } else if conversations.isEmpty {
                        Text("No conversations yet")
                            .font(.system(size: 11))
                            .foregroundStyle(textSecondary)
                            .frame(maxWidth: .infinity, alignment: .center)
                            .padding(.top, 24)
                    } else {
                        ForEach(conversations) { conv in
                            conversationRow(conv)
                        }
                    }
                }
                .padding(.horizontal, 8)
                .padding(.top, 8)
            }

            Spacer()
            Divider().opacity(0.4)

            // ── Bottom bar: status dot + settings gear ────────────────────
            bottomBar
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
        }
        .background(sidebarBg)
        .frame(maxHeight: .infinity)
        .task { await loadConversations() }
        .onChange(of: appState.connected) { connected in
            if connected { Task { await loadConversations() } }
        }
        .onChange(of: selectedConvID) { id in
            // Refresh list whenever a new conversation is assigned (first message done)
            if id != nil { Task { await loadConversations() } }
        }
    }

    // MARK: Load

    func loadConversations() async {
        guard appState.connected else { return }
        loading = true
        if let list = try? await appState.client.conversations() {
            conversations = list.conversations
        }
        loading = false
    }

    // MARK: New chat

    private var newChatButton: some View {
        Button {
            selectedConvID = nil
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "square.and.pencil")
                    .font(.system(size: 14, weight: .medium))
                Text("New chat")
                    .font(.system(size: 13, weight: .medium))
                Spacer()
                Text(shortProvider)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(accentColor)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(accentColor.opacity(0.1))
                    .clipShape(Capsule())
            }
            .foregroundStyle(textPrimary)
            .padding(.horizontal, 12).padding(.vertical, 9)
            .background(Color.primary.opacity(0.06))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
        .buttonStyle(.plain)
    }

    private var shortProvider: String {
        switch appState.selectedProvider {
        case "claude":     return "Claude"
        case "openrouter": return "OR"
        case "openai":     return "GPT"
        case "google":     return "Gemini"
        case "groq":       return "Groq"
        case "ollama":     return "Local"
        default:           return appState.selectedProvider.isEmpty ? "AI" : appState.selectedProvider
        }
    }

    // MARK: Conversation row

    private func conversationRow(_ conv: AstaConversationItem) -> some View {
        let isSelected = selectedConvID == conv.id
        return HStack(spacing: 0) {
            Button {
                onSelectConversation(conv.id)
            } label: {
                VStack(alignment: .leading, spacing: 2) {
                    Text(conv.title)
                        .font(.system(size: 13))
                        .foregroundStyle(textPrimary)
                        .lineLimit(1)
                    Text(relativeTime(conv.last_active))
                        .font(.system(size: 10))
                        .foregroundStyle(textSecondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 10).padding(.vertical, 7)
            }
            .buttonStyle(.plain)

            // Delete button — only on hover via right-click context menu
        }
        .background(
            isSelected
                ? accentColor.opacity(0.12)
                : Color.clear
        )
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .contextMenu {
            Button(role: .destructive) {
                Task {
                    try? await appState.client.deleteConversation(id: conv.id)
                    if selectedConvID == conv.id { selectedConvID = nil }
                    await loadConversations()
                }
            } label: {
                Label("Delete conversation", systemImage: "trash")
            }
        }
    }

    // MARK: Relative time helper

    private func relativeTime(_ iso: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = formatter.date(from: iso)
        if date == nil {
            formatter.formatOptions = [.withInternetDateTime]
            date = formatter.date(from: iso)
        }
        if date == nil {
            // Try SQLite datetime format: "2024-01-15 14:30:00"
            let df = DateFormatter()
            df.dateFormat = "yyyy-MM-dd HH:mm:ss"
            df.timeZone = TimeZone(identifier: "UTC")
            date = df.date(from: iso)
        }
        guard let d = date else { return "" }
        let diff = Date().timeIntervalSince(d)
        if diff < 60 { return "just now" }
        if diff < 3600 { return "\(Int(diff/60))m ago" }
        if diff < 86400 { return "\(Int(diff/3600))h ago" }
        if diff < 86400 * 7 { return "\(Int(diff/86400))d ago" }
        let df = DateFormatter()
        df.dateStyle = .short; df.timeStyle = .none
        return df.string(from: d)
    }

    // MARK: Bottom bar

    private var bottomBar: some View {
        HStack(spacing: 10) {
            HStack(spacing: 5) {
                Circle()
                    .fill(appState.connected ? Color.green : Color.red)
                    .frame(width: 6, height: 6)
                    .shadow(color: (appState.connected ? Color.green : Color.red).opacity(0.5), radius: 3)
                Text(appState.connected ? "Online" : "Offline")
                    .font(.system(size: 11))
                    .foregroundStyle(textSecondary)
            }
            Spacer()
            Button {
                showSettings = true
            } label: {
                Image(systemName: "gearshape")
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(textSecondary)
                    .frame(width: 30, height: 30)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            .buttonStyle(.plain)
            .help("Settings")
        }
    }
}
