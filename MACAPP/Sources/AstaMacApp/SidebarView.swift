import SwiftUI
import AppKit
import AstaAPIClient

// MARK: - Sidebar (conversation list + nav + settings gear)

struct SidebarView: View {
    @ObservedObject var appState: AppState
    @Binding var selectedConvID: String?
    @Binding var showSettings: Bool
    @Binding var showAgents: Bool
    var onSelectConversation: (String) -> Void

    @State private var conversations: [AstaConversationItem] = []
    @State private var folders: [AstaFolder] = []
    @State private var loading = false
    @State private var collapsedFolders: Set<String> = []
    @State private var droppingOnFolder: String? = nil          // folder being hovered over
    @State private var showNewFolderPrompt = false
    @State private var newFolderName = ""
    @State private var renamingFolderID: String? = nil
    @State private var renamingFolderName = ""

    // Sidebar palette
    private var sidebarBg:     Color { Color(nsColor: .windowBackgroundColor) }
    private var textPrimary:   Color { Color(nsColor: .labelColor) }
    private var textSecondary: Color { Color(nsColor: .secondaryLabelColor) }
    private var accentColor:   Color { Color.accentColor }

    var body: some View {
        VStack(spacing: 0) {
            // ── New chat button ──────────────────────────────────────────
            newChatButton
                .padding(.horizontal, 12)
                .padding(.top, 8)
                .padding(.bottom, 6)

            // ── Agents button ───────────────────────────────────────────
            agentsButton
                .padding(.horizontal, 12)
                .padding(.bottom, 8)

            Divider().opacity(0.4)

            // ── Conversation list ────────────────────────────────────────
            ScrollView {
                LazyVStack(spacing: 2) {
                    if loading && conversations.isEmpty && folders.isEmpty {
                        ProgressView().padding(.top, 20)
                    } else {
                        // Folders
                        ForEach(folders) { folder in
                            folderSection(folder)
                        }

                        // Unfiled conversations
                        let unfiled = conversations.filter { $0.folder_id == nil }
                        if !unfiled.isEmpty {
                            if !folders.isEmpty {
                                sectionHeader("Chats")
                            }
                            ForEach(unfiled) { conv in
                                convRow(conv, folderID: nil)
                            }
                        }

                        if conversations.isEmpty && folders.isEmpty {
                            Text("No conversations yet")
                                .font(.system(size: 11))
                                .foregroundStyle(textSecondary)
                                .frame(maxWidth: .infinity, alignment: .center)
                                .padding(.top, 24)
                        }
                    }
                }
                .padding(.horizontal, 8)
                .padding(.top, 8)
                .padding(.bottom, 4)
            }

            Divider().opacity(0.4)

            // ── Bottom bar ───────────────────────────────────────────────
            bottomBar
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
        }
        .background(sidebarBg)
        .frame(maxHeight: .infinity)
        .task { await reload() }
        .onChange(of: appState.connected) { connected in
            if connected { Task { await reload() } }
        }
        .onChange(of: selectedConvID) { id in
            if id != nil { Task { await reload() } }
        }
        .onChange(of: appState.sidebarRefreshTrigger) { _ in
            Task { await reload() }
        }
        // New folder prompt
        .sheet(isPresented: $showNewFolderPrompt) {
            newFolderSheet
        }
        // Rename folder prompt
        .sheet(item: renamingFolderBinding) { f in
            renameFolderSheet(folder: f)
        }
    }

    // MARK: - Folder section

    @ViewBuilder
    private func folderSection(_ folder: AstaFolder) -> some View {
        let isCollapsed = collapsedFolders.contains(folder.id)
        let folderConvs = conversations.filter { $0.folder_id == folder.id }
        let isDropTarget = droppingOnFolder == folder.id

        VStack(spacing: 2) {
            // Folder header row
            HStack(spacing: 6) {
                Image(systemName: isCollapsed ? "chevron.right" : "chevron.down")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(textSecondary)
                    .frame(width: 12)

                Image(systemName: "folder.fill")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(Color(hex: folder.color) ?? accentColor)

                Text(folder.name)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(textSecondary)
                    .lineLimit(1)

                Spacer()

                Text("\(folderConvs.count)")
                    .font(.system(size: 10).monospacedDigit())
                    .foregroundStyle(textSecondary.opacity(0.6))
            }
            .padding(.horizontal, 8).padding(.vertical, 5)
            .background(isDropTarget ? accentColor.opacity(0.12) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
            .overlay(
                isDropTarget
                    ? RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .strokeBorder(accentColor.opacity(0.5), lineWidth: 1.5)
                    : nil
            )
            .contentShape(Rectangle())
            .onTapGesture {
                withAnimation(.easeOut(duration: 0.15)) {
                    if isCollapsed { collapsedFolders.remove(folder.id) }
                    else { collapsedFolders.insert(folder.id) }
                }
            }
            .contextMenu { folderContextMenu(folder) }
            // Drop target: drag a conversation onto a folder header
            .dropDestination(for: String.self) { items, _ in
                guard let convID = items.first else { return false }
                Task { await assignConversation(convID, to: folder.id) }
                droppingOnFolder = nil
                return true
            } isTargeted: { targeting in
                droppingOnFolder = targeting ? folder.id : nil
            }

            // Folder contents
            if !isCollapsed {
                if folderConvs.isEmpty {
                    Text("Drag chats here")
                        .font(.system(size: 11))
                        .foregroundStyle(textSecondary.opacity(0.5))
                        .padding(.leading, 28).padding(.vertical, 4)
                } else {
                    ForEach(folderConvs) { conv in
                        convRow(conv, folderID: folder.id)
                            .padding(.leading, 14)
                    }
                }
            }
        }
        .padding(.top, 2)
    }

    // MARK: - Conversation row

    private func convRow(_ conv: AstaConversationItem, folderID: String?) -> some View {
        let isSelected = selectedConvID == conv.id
        return Button {
            onSelectConversation(conv.id)
        } label: {
            VStack(alignment: .leading, spacing: 5) {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(conv.title)
                        .font(.system(size: 13))
                        .foregroundStyle(Color(nsColor: .labelColor))
                        .lineLimit(1)
                        .layoutPriority(1)
                    Spacer(minLength: 4)
                    Text("\(tokenSummary(conv.approx_tokens)) · \(relativeTime(conv.last_active))")
                        .font(.system(size: 10).monospacedDigit())
                        .foregroundStyle(Color(nsColor: .secondaryLabelColor))
                        .lineLimit(1)
                        .fixedSize(horizontal: true, vertical: false)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 10).padding(.vertical, 7)
        }
        .buttonStyle(.plain)
        .background(isSelected ? accentColor.opacity(0.12) : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        // Use onDrag instead of .draggable() to avoid interfering with button tap events on macOS
        .onDrag { NSItemProvider(object: conv.id as NSString) }
        .contextMenu {
            // Move to folder submenu
            if !folders.isEmpty {
                Menu("Move to folder") {
                    if folderID != nil {
                        Button("Remove from folder") {
                            Task { await assignConversation(conv.id, to: nil) }
                        }
                        Divider()
                    }
                    ForEach(folders.filter { $0.id != folderID }) { f in
                        Button(f.name) {
                            Task { await assignConversation(conv.id, to: f.id) }
                        }
                    }
                }
            }
            Divider()
            Button(role: .destructive) {
                // Optimistic removal — instant UI response
                conversations.removeAll { $0.id == conv.id }
                if selectedConvID == conv.id { selectedConvID = nil }
                Task {
                    try? await appState.client.deleteConversation(id: conv.id)
                    await reload()
                }
            } label: {
                Label("Delete", systemImage: "trash")
            }
        }
    }

    // MARK: - Folder context menu

    @ViewBuilder
    private func folderContextMenu(_ folder: AstaFolder) -> some View {
        Button("Rename folder") {
            renamingFolderID = folder.id
            renamingFolderName = folder.name
        }
        Divider()
        Button(role: .destructive) {
            Task {
                try? await appState.client.deleteFolder(id: folder.id)
                await reload()
            }
        } label: {
            Label("Delete folder", systemImage: "trash")
        }
    }

    // MARK: - Section header

    private func sectionHeader(_ title: String) -> some View {
        Text(title.uppercased())
            .font(.system(size: 10, weight: .semibold))
            .foregroundStyle(textSecondary.opacity(0.6))
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 10)
            .padding(.top, 10)
            .padding(.bottom, 2)
    }

    // MARK: - Load

    func reload() async {
        guard appState.connected else { return }
        loading = true
        async let convFetch = try? appState.client.conversations()
        async let foldFetch = try? appState.client.listFolders()
        if let list = await convFetch { conversations = list.conversations }
        if let fList = await foldFetch { folders = fList }
        loading = false
    }

    // MARK: - Folder actions

    private func assignConversation(_ convID: String, to folderID: String?) async {
        try? await appState.client.setConversationFolder(conversationID: convID, folderID: folderID)
        await reload()
    }

    // MARK: - New chat button

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
                StatusPill(text: shortProvider, tint: accentColor)
            }
            .foregroundStyle(textPrimary)
            .padding(.horizontal, 12).padding(.vertical, 9)
            .background(Color(nsColor: .controlBackgroundColor))
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

    // MARK: - Bottom bar

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
            // New folder button
            Button {
                newFolderName = ""
                showNewFolderPrompt = true
            } label: {
                Image(systemName: "folder.badge.plus")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(textSecondary)
                    .frame(width: 30, height: 30)
            }
            .buttonStyle(.plain)
            .help("New folder")

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

    // MARK: - Agents button

    private var agentsButton: some View {
        Button {
            showAgents = true
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "person.2")
                    .font(.system(size: 14, weight: .medium))
                Text("Agents")
                    .font(.system(size: 13, weight: .medium))
                Spacer()
                let enabledCount = appState.agentsList.filter { $0.enabled ?? true }.count
                Text("\(enabledCount)")
                    .font(.system(size: 10, weight: .semibold).monospacedDigit())
                    .foregroundStyle(textSecondary)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(Color(nsColor: .separatorColor).opacity(0.35))
                    .clipShape(Capsule())
            }
            .foregroundStyle(textPrimary)
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(Color(nsColor: .controlBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
        .buttonStyle(.plain)
        .help("Explore, search, add/remove, and create agents")
    }

    // MARK: - New folder sheet

    private var newFolderSheet: some View {
        VStack(spacing: 16) {
            Text("New Folder")
                .font(.headline)
            TextField("Folder name", text: $newFolderName)
                .textFieldStyle(.roundedBorder)
                .onSubmit { createFolder() }
            HStack {
                Button("Cancel") { showNewFolderPrompt = false }.buttonStyle(.bordered)
                Spacer()
                Button("Create") { createFolder() }
                    .buttonStyle(.borderedProminent)
                    .disabled(newFolderName.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(20)
        .frame(width: 280)
    }

    private func createFolder() {
        let name = newFolderName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        showNewFolderPrompt = false
        Task {
            try? await appState.client.createFolder(name: name)
            await reload()
        }
    }

    // MARK: - Rename folder sheet

    private var renamingFolderBinding: Binding<AstaFolder?> {
        Binding(
            get: { folders.first(where: { $0.id == renamingFolderID }) },
            set: { if $0 == nil { renamingFolderID = nil } }
        )
    }

    private func renameFolderSheet(folder: AstaFolder) -> some View {
        VStack(spacing: 16) {
            Text("Rename Folder")
                .font(.headline)
            TextField("Folder name", text: $renamingFolderName)
                .textFieldStyle(.roundedBorder)
                .onSubmit { submitRename(folder: folder) }
            HStack {
                Button("Cancel") { renamingFolderID = nil }.buttonStyle(.bordered)
                Spacer()
                Button("Rename") { submitRename(folder: folder) }
                    .buttonStyle(.borderedProminent)
                    .disabled(renamingFolderName.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(20)
        .frame(width: 280)
        .onAppear { renamingFolderName = folder.name }
    }

    private func submitRename(folder: AstaFolder) {
        let name = renamingFolderName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        renamingFolderID = nil
        Task {
            try? await appState.client.renameFolder(id: folder.id, name: name)
            await reload()
        }
    }

    // MARK: - Helpers

    private func relativeTime(_ iso: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = formatter.date(from: iso)
        if date == nil {
            formatter.formatOptions = [.withInternetDateTime]
            date = formatter.date(from: iso)
        }
        if date == nil {
            let df = DateFormatter()
            df.dateFormat = "yyyy-MM-dd HH:mm:ss"
            df.timeZone = TimeZone(identifier: "UTC")
            date = df.date(from: iso)
        }
        guard let d = date else { return "" }
        let diff = Date().timeIntervalSince(d)
        if diff < 60    { return "just now" }
        if diff < 3600  { return "\(Int(diff/60))m ago" }
        if diff < 86400 { return "\(Int(diff/3600))h ago" }
        if diff < 86400 * 7 { return "\(Int(diff/86400))d ago" }
        let df = DateFormatter()
        df.dateStyle = .short; df.timeStyle = .none
        return df.string(from: d)
    }

    private func tokenSummary(_ tokens: Int) -> String {
        guard tokens > 0 else { return "0" }
        if tokens < 1000 { return "\(tokens)" }
        let k = Double(tokens) / 1000.0
        if k < 10 { return String(format: "%.1fk", k) }
        return "\(Int(k.rounded()))k"
    }

    private var contextWindow: Int {
        switch appState.selectedProvider {
        case "claude":     return 200_000
        case "google":     return 1_000_000
        case "openai":     return 128_000
        case "groq":       return 131_072
        case "openrouter": return 128_000
        case "ollama":     return 8_192
        default:           return 128_000
        }
    }
}

// MARK: - Hex colour helper

private extension Color {
    init?(hex: String) {
        var h = hex.trimmingCharacters(in: .whitespaces)
        if h.hasPrefix("#") { h = String(h.dropFirst()) }
        guard h.count == 6, let val = UInt64(h, radix: 16) else { return nil }
        self.init(
            red:   Double((val >> 16) & 0xFF) / 255,
            green: Double((val >>  8) & 0xFF) / 255,
            blue:  Double( val        & 0xFF) / 255)
    }
}
