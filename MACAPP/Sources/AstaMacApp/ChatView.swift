import SwiftUI
import AppKit
import UniformTypeIdentifiers
import AstaAPIClient

// MARK: - ChatView

struct ChatView: View {
    @ObservedObject var appState: AppState
    @Binding var conversationID: String?

    @State private var inputText      = ""
    @State private var messages: [ChatMessage] = []
    @State private var isLoading      = false
    @State private var attachments: [ChatAttachment] = []
    @State private var showThinking   = false
    @State private var isDraggingOver = false
    @State private var streamRevision = 0
    @State private var requestFocus   = false
    @State private var currentStreamTask: Task<Void, Never>?
    @State private var pollTask: Task<Void, Never>?
    @State private var selectedAgentID: String? = nil
    @State private var selectedAgentByConversation: [String: String] = [:]
    @State private var pendingAgentForNewConversation: String? = nil
    @State private var previousConversationID: String? = nil
    @State private var historyLoading = false
    @State private var historyError: String? = nil

    @AppStorage("AstaMacApp.webEnabled") private var webEnabled = false

    // Palette
    private var bg:            Color { Color(nsColor: .windowBackgroundColor) }
    private var inputBg:       Color { Color(nsColor: .controlBackgroundColor) }
    private var textPrimary:   Color { Color(nsColor: .labelColor) }
    private var textSecondary: Color { Color(nsColor: .secondaryLabelColor) }
    private var textTertiary:  Color { Color(nsColor: .tertiaryLabelColor) }

    private let thinkingOptions = ["off","minimal","low","medium","high","xhigh"]
    private let moodOptions     = ["normal","friendly","serious"]
    private var selectedAgent: AstaAgent? {
        guard let selectedAgentID else { return nil }
        return appState.agentsList.first(where: { $0.id == selectedAgentID && ($0.enabled ?? true) })
    }

    private func setSelectedAgent(_ agentID: String?) {
        selectedAgentID = agentID
        if let cid = conversationID, !cid.isEmpty {
            if let agentID {
                selectedAgentByConversation[cid] = agentID
            } else {
                selectedAgentByConversation.removeValue(forKey: cid)
            }
        } else {
            pendingAgentForNewConversation = agentID
        }
    }

    private func restoreAgentSelection(for conversationIDValue: String?) {
        if let cid = conversationIDValue, !cid.isEmpty {
            let restored = selectedAgentByConversation[cid] ?? pendingAgentForNewConversation
            selectedAgentID = restored
            if let restored {
                selectedAgentByConversation[cid] = restored
            }
            pendingAgentForNewConversation = nil
            return
        }
        selectedAgentID = pendingAgentForNewConversation
    }

    // MARK: - Body

    var body: some View {
        VStack(spacing: 0) {
            chatToolbar
            Divider().opacity(0.5)
            messageList
            inputArea
        }
        .background(bg)
        .overlay(dragOverlay)
        .onDrop(of: [.fileURL, .image], isTargeted: $isDraggingOver, perform: handleDrop)
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { requestFocus = true }
            previousConversationID = conversationID
            restoreAgentSelection(for: conversationID)
            Task { await appState.loadAgents() }
        }
        .onChange(of: conversationID) { id in
            if let prev = previousConversationID, !prev.isEmpty {
                if let selectedAgentID {
                    selectedAgentByConversation[prev] = selectedAgentID
                } else {
                    selectedAgentByConversation.removeValue(forKey: prev)
                }
            } else {
                pendingAgentForNewConversation = selectedAgentID
            }

            // Cancel any in-flight stream and poll immediately (OpenClaw pattern)
            currentStreamTask?.cancel()
            currentStreamTask = nil
            stopPolling()
            isLoading = false
            historyError = nil
            withAnimation(.easeOut(duration: 0.18)) {
                messages = []; attachments = []; inputText = ""
            }
            restoreAgentSelection(for: id)
            previousConversationID = id
            if let id = id, !id.isEmpty {
                Task { await loadHistory(conversationID: id) }
                startPolling(conversationID: id)
            }
        }
    }

    // MARK: - Toolbar

    private var chatToolbar: some View {
        HStack(spacing: 8) {
            Spacer()

            // Provider picker
            Menu {
                Picker("Provider", selection: Binding(
                    get: { appState.selectedProvider },
                    set: { new in Task { await appState.setDefaultAI(new) } }
                )) {
                    ForEach(providerNames, id: \.self) { p in
                        let model = appState.modelsResponse?.models?[p] ?? ""
                        Text(model.isEmpty ? astaProviderDisplayName(p) : "\(astaProviderDisplayName(p)) · \(model)").tag(p)
                    }
                }
                .pickerStyle(.inline)
            } label: {
                chipLabel(icon: "cpu", text: shortProvider)
            }
            .menuStyle(.borderlessButton).fixedSize()
            .help("Switch AI provider — currently using \(shortProvider)")

            // Thinking + Mood
            Menu {
                Section("Thinking level") {
                    Picker("Thinking", selection: Binding(
                        get: { appState.selectedThinking },
                        set: { new in Task { await appState.setThinking(new) } }
                    )) { ForEach(thinkingOptions, id: \.self) { Text($0).tag($0) } }
                    .pickerStyle(.inline)
                }
                Section("Mood") {
                    Picker("Mood", selection: Binding(
                        get: { appState.selectedMood },
                        set: { new in Task { await appState.setMood(new) } }
                    )) { ForEach(moodOptions, id: \.self) { m in Text(m.capitalized).tag(m) } }
                    .pickerStyle(.inline)
                }
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: "slider.horizontal.3").font(.system(size: 10, weight: .medium))
                    Image(systemName: "chevron.down").font(.system(size: 8, weight: .semibold))
                }
                .foregroundStyle(textSecondary)
                .frame(width: 44, height: 28)
                .background(Color.primary.opacity(0.045))
                .clipShape(RoundedRectangle(cornerRadius: 7))
            }
            .menuStyle(.borderlessButton)
            .help("Thinking & Mood — thinking: \(appState.selectedThinking), mood: \(appState.selectedMood)\n\nThinking: how much the model reasons before replying (off = fastest, xhigh = deepest).\nMood: normal, friendly, or serious.")

            // Show/hide thinking toggle
            if appState.selectedThinking != "off" && !appState.selectedThinking.isEmpty {
                Button {
                    withAnimation(.easeOut(duration: 0.15)) { showThinking.toggle() }
                } label: {
                    Image(systemName: showThinking ? "brain.filled.head.profile" : "brain.head.profile")
                        .font(.system(size: 13))
                        .foregroundStyle(showThinking ? Color.accentColor : textTertiary)
                        .frame(width: 30, height: 30)
                        .background(showThinking ? Color.accentColor.opacity(0.1) : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: 7))
                }
                .buttonStyle(.plain)
                .help(showThinking ? "Hide reasoning — collapse the model's thought process in responses" : "Show reasoning — expand the model's thought process inside each response")
            }

            // Learning mode toggle
            Button {
                withAnimation(.easeOut(duration: 0.15)) { appState.learningModeEnabled.toggle() }
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: appState.learningModeEnabled ? "book.fill" : "book")
                        .font(.system(size: 12, weight: .medium))
                    if appState.learningModeEnabled {
                        Text("Learn").font(.system(size: 10, weight: .medium))
                    }
                }
                .foregroundStyle(appState.learningModeEnabled ? Color.green : textSecondary)
                .padding(.horizontal, appState.learningModeEnabled ? 8 : 6)
                .padding(.vertical, 5)
                .background(appState.learningModeEnabled ? Color.green.opacity(0.15) : Color.primary.opacity(0.045))
                .clipShape(RoundedRectangle(cornerRadius: 7))
            }
            .buttonStyle(.plain)
            .help(appState.learningModeEnabled
                  ? "Learning mode ON — next message will be saved to knowledge base"
                  : "Enable learning mode — teach Asta by sending information")
        }
        .frame(height: 44)
        .padding(.horizontal, 16)
        .background(inputBg)
    }

    private func chipLabel(icon: String, text: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon).font(.system(size: 10, weight: .medium))
            Text(text).font(.system(size: 11, weight: .medium)).lineLimit(1)
            Image(systemName: "chevron.down").font(.system(size: 8, weight: .semibold))
        }
        .foregroundStyle(textSecondary)
        .padding(.horizontal, 9).padding(.vertical, 5)
        .background(Color.primary.opacity(0.045))
        .clipShape(RoundedRectangle(cornerRadius: 7))
    }

    private var providerNames: [String] {
        let flow = (appState.providerFlow?.providers ?? []).map { $0.provider }
        return flow.isEmpty ? ["claude","ollama","openrouter","openai","google","groq"] : flow
    }

    private var shortProvider: String {
        astaProviderDisplayName(appState.selectedProvider)
    }

    // MARK: - Message list

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView(.vertical, showsIndicators: true) {
                if historyLoading {
                    VStack(spacing: 10) {
                        ProgressView()
                        Text("Loading chat…")
                            .font(.system(size: 12))
                            .foregroundStyle(textSecondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(.top, 60)
                } else if let err = historyError {
                    VStack(spacing: 10) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 22))
                            .foregroundStyle(.orange)
                        Text(err)
                            .font(.system(size: 12))
                            .foregroundStyle(textSecondary)
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, 60)
                    .padding(.horizontal, 24)
                } else if messages.isEmpty {
                    emptyState
                } else {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(messages) { msg in
                            messageRow(msg)
                        }
                        Color.clear.frame(height: 20).id("bottom")
                    }
                    .padding(.top, 12)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .onChange(of: messages.count)  { _ in scrollToBottom(proxy) }
            .onChange(of: streamRevision)  { _ in scrollToBottom(proxy) }
        }
        .background(bg)
    }

    private func scrollToBottom(_ proxy: ScrollViewProxy) {
        withAnimation(.easeOut(duration: 0.1)) { proxy.scrollTo("bottom", anchor: .bottom) }
    }

    private var emptyState: some View {
        VStack(spacing: 14) {
            Image(nsImage: NSApp.applicationIconImage)
                .resizable()
                .scaledToFit()
                .frame(width: 56, height: 56)
                .clipShape(Circle())
                .shadow(color: Color.accentColor.opacity(0.3), radius: 10, y: 4)

            if !appState.connected {
                Text("Backend Offline")
                    .font(.system(size: 20, weight: .semibold)).foregroundStyle(.orange)
                Text("Start the Asta backend to begin chatting:")
                    .font(.system(size: 13)).foregroundStyle(textSecondary)
                Text("cd ~/asta && ./asta.sh start")
                    .font(.system(.caption, design: .monospaced))
                    .padding(10).background(Color.primary.opacity(0.07)).cornerRadius(8)
                    .textSelection(.enabled)
                Button("Retry connection") { Task { await appState.load() } }
                    .buttonStyle(.bordered).controlSize(.small).padding(.top, 4)
            } else {
                Text("How can I help?")
                    .font(.system(size: 20, weight: .semibold)).foregroundStyle(textPrimary)
                Text("Type a message, drop a file, or attach an image.")
                    .font(.system(size: 13)).foregroundStyle(textSecondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.vertical, 80)
    }

    // MARK: - Message row

    @ViewBuilder
    private func messageRow(_ msg: ChatMessage) -> some View {
        if msg.role == "user" {
            userRow(msg)
        } else if msg.content.hasPrefix("[Previously discussed]") {
            summaryDivider(msg)
        } else {
            assistantRow(msg)
        }
    }

    // MARK: Compaction summary divider

    private func summaryDivider(_ msg: ChatMessage) -> some View {
        let text = String(msg.content.dropFirst("[Previously discussed]".count)).trimmingCharacters(in: .whitespaces)
        return VStack(spacing: 6) {
            HStack(spacing: 8) {
                Rectangle().fill(Color.secondary.opacity(0.25)).frame(height: 1)
                Text("Context summarised")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(Color.secondary)
                    .fixedSize()
                Rectangle().fill(Color.secondary.opacity(0.25)).frame(height: 1)
            }
            if !text.isEmpty {
                Text(text)
                    .font(.caption)
                    .foregroundStyle(Color.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 20)
        .help("The conversation was getting long — older messages were summarised to save context space. The full content is still available in the database.")
        .id(msg.id)
    }

    // MARK: User message

    private func userRow(_ msg: ChatMessage) -> some View {
        VStack(alignment: .trailing, spacing: 6) {
            // Attachment chips
            if let atts = msg.attachments, !atts.isEmpty {
                HStack(spacing: 6) {
                    Spacer(minLength: 120)
                    ForEach(atts) { att in
                        HStack(spacing: 4) {
                            Image(systemName: att.icon).font(.system(size: 10))
                            Text(att.name).font(.system(size: 11)).lineLimit(1)
                        }
                        .foregroundStyle(.white.opacity(0.85))
                        .padding(.horizontal, 8).padding(.vertical, 4)
                        .background(Color.accentColor.opacity(0.7))
                        .clipShape(Capsule())
                    }
                }
            }
            // Message bubble
            HStack {
                Spacer(minLength: 80)
                Text(msg.content)
                    .textSelection(.enabled)
                    .font(.system(size: 14))
                    .foregroundStyle(.white)
                    .lineSpacing(2)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Color.accentColor)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                    .contextMenu { copyButton(msg.content) }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 6)
        .id(msg.id)
    }

    // MARK: Assistant message

    private func assistantRow(_ msg: ChatMessage) -> some View {
        HStack(alignment: .top, spacing: 10) {
            astaAvatar(phase: msg.phase).padding(.top, 2)

            VStack(alignment: .leading, spacing: 6) {
                // Thinking block
                let hasThinking = !(msg.thinkingContent ?? "").isEmpty
                if hasThinking || msg.phase == .thinking {
                    thinkingBlock(
                        text: msg.thinkingContent ?? "",
                        isStreaming: msg.phase == .thinking,
                        expanded: msg.phase == .thinking || showThinking
                    )
                }

                // Content
                if !msg.content.isEmpty {
                    answerContent(msg)
                } else if msg.phase == .responding {
                    HStack(spacing: 5) {
                        BounceDot(delay: 0); BounceDot(delay: 0.18); BounceDot(delay: 0.36)
                    }.padding(.top, 4)
                } else if msg.phase == .thinking && (msg.thinkingContent ?? "").isEmpty {
                    HStack(spacing: 6) {
                        ThinkingPulse()
                        Text("Thinking...").font(.system(size: 12)).foregroundStyle(textTertiary)
                    }
                }

                // Tool pills + provider
                messageMeta(msg)
            }

            Spacer(minLength: 40)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
        .id(msg.id)
    }

    // MARK: Thinking block — collapsible

    private func thinkingBlock(text: String, isStreaming: Bool, expanded: Bool) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header — always visible, acts as toggle
            Button {
                withAnimation(.easeOut(duration: 0.15)) { showThinking.toggle() }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: expanded ? "chevron.down" : "chevron.right")
                        .font(.system(size: 8, weight: .bold))
                        .foregroundStyle(Color.purple.opacity(0.6))
                        .frame(width: 10)
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(Color.purple.opacity(0.7))
                    Text(isStreaming ? "Thinking..." : "Thought")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(Color.purple.opacity(0.7))
                    if isStreaming { ThinkingPulse() }
                    Spacer()
                }
                .padding(.horizontal, 10).padding(.vertical, 7)
            }
            .buttonStyle(.plain)
            .help(expanded
                  ? "Model's internal reasoning — click to collapse"
                  : "The model reasoned before replying — click to expand")

            // Content — shown when expanded
            if expanded && !text.isEmpty {
                Text(text)
                    .font(.system(size: 12))
                    .foregroundStyle(textSecondary)
                    .lineSpacing(3)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 12).padding(.bottom, 10)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color.purple.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 8, style: .continuous).strokeBorder(Color.purple.opacity(0.12), lineWidth: 0.5))
    }

    // MARK: Answer content — markdown + inline images/GIFs

    private func answerContent(_ msg: ChatMessage) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            let segments = MessageSegment.parse(msg.content)
            ForEach(Array(segments.enumerated()), id: \.offset) { _, seg in
                switch seg {
                case .text(let t):
                    MarkdownView(content: t, textColor: textPrimary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contextMenu { copyButton(msg.content) }
                case .image(let url, _):
                    RemoteImageView(url: url)
                }
            }
        }
        // Streaming indicator — subtle left border
        .padding(.leading, msg.phase == .responding ? 6 : 0)
        .overlay(alignment: .leading) {
            if msg.phase == .responding {
                RoundedRectangle(cornerRadius: 1.5)
                    .fill(Color.accentColor.opacity(0.35))
                    .frame(width: 2)
                    .padding(.vertical, 2)
            }
        }
        .animation(.easeOut(duration: 0.15), value: msg.phase)
    }

    // MARK: Tool pills + provider

    @ViewBuilder
    private func messageMeta(_ msg: ChatMessage) -> some View {
        // Active tools: animated pills while a tool is executing
        if !msg.activeTools.isEmpty {
            activeToolPills(msg.activeTools)
        }
        // Completed tools: static pills after execution (infrastructure-tracked, no LLM text parsing)
        if !msg.completedTools.isEmpty {
            toolPills(msg.completedTools)
        }
        if let provider = msg.provider, !provider.isEmpty, msg.phase == .done {
            Text(astaProviderDisplayName(provider))
                .font(.system(size: 10))
                .foregroundStyle(textTertiary.opacity(0.5))
                .padding(.top, 1)
                .help("Response from \(astaProviderDisplayName(provider))")
        }
    }

    private func activeToolPills(_ tools: [String]) -> some View {
        FlowLayout(spacing: 4) {
            ForEach(tools, id: \.self) { tool in
                ActiveToolPill(label: tool, icon: toolIcon(for: tool))
            }
        }
    }

    private func toolPills(_ tools: [String]) -> some View {
        FlowLayout(spacing: 4) {
            ForEach(tools, id: \.self) { part in
                HStack(spacing: 3) {
                    Image(systemName: toolIcon(for: part)).font(.system(size: 8))
                    Text(part).font(.system(size: 10))
                }
                .foregroundStyle(textTertiary)
                .padding(.horizontal, 6).padding(.vertical, 3)
                .background(Color.primary.opacity(0.06))
                .clipShape(Capsule())
                .help("Tool: \(part)")
            }
        }
    }

    private func toolIcon(for name: String) -> String {
        let n = name.lowercased()
        if n.contains("search") || n.contains("web")    { return "magnifyingglass" }
        if n.contains("file")   || n.contains("read")   { return "doc.text" }
        if n.contains("memory") || n.contains("mem")    { return "brain" }
        if n.contains("code")   || n.contains("exec")   { return "terminal" }
        if n.contains("reminder") || n.contains("cal")  { return "bell" }
        if n.contains("spotify") || n.contains("music") { return "music.note" }
        if n.contains("image_gen") || n.contains("image gen") { return "photo.badge.plus" }
        return "wrench.and.screwdriver"
    }

    // MARK: Avatar

    private func astaAvatar(phase: ChatMessage.StreamPhase) -> some View {
        Image(nsImage: NSApp.applicationIconImage)
            .resizable()
            .scaledToFill()
            .frame(width: 26, height: 26)
            .clipShape(Circle())
            .shadow(color: Color.accentColor.opacity(0.25), radius: 3, y: 1)
            .scaleEffect(phase == .thinking ? 1.07 : 1.0)
            .animation(
                phase == .thinking
                    ? .easeInOut(duration: 0.85).repeatForever(autoreverses: true)
                    : .easeOut(duration: 0.2),
                value: phase == .thinking
            )
    }

    private func copyButton(_ text: String) -> some View {
        Button("Copy") {
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(text, forType: .string)
        }
    }

    // MARK: - Input area

    private var inputArea: some View {
        VStack(spacing: 0) {
            Divider().opacity(0.5)

            // Attachment strip
            if !attachments.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(attachments) { att in
                            attachmentChip(att)
                        }
                    }
                    .padding(.horizontal, 20).padding(.vertical, 8)
                }
                .background(Color.accentColor.opacity(0.04))
                Divider().opacity(0.3)
            }

            // Input field with buttons inside
            VStack(spacing: 0) {
                ChatTextField(text: $inputText, requestFocus: $requestFocus, onSend: send)
                    .frame(maxWidth: .infinity)
                    .frame(minHeight: 36, maxHeight: 120)

                // Bottom row: attach + web + spacer + stop/send
                HStack(spacing: 6) {
                    // Attach button (paperclip)
                    Button(action: pickFile) {
                        Image(systemName: "paperclip")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundStyle(attachments.isEmpty ? textSecondary : Color.accentColor)
                            .frame(width: 30, height: 28)
                    }
                    .buttonStyle(.plain)
                    .help("Attach files — images, PDFs, text, code")

                    // Web search toggle
                    Button {
                        webEnabled.toggle()
                    } label: {
                        HStack(spacing: 3) {
                            Image(systemName: "globe")
                                .font(.system(size: 12, weight: .medium))
                            if webEnabled {
                                Text("Web").font(.system(size: 10, weight: .medium))
                            }
                        }
                        .foregroundStyle(webEnabled ? Color.accentColor : textSecondary)
                        .padding(.horizontal, webEnabled ? 8 : 6).padding(.vertical, 4)
                        .background(webEnabled ? Color.accentColor.opacity(0.12) : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                    .buttonStyle(.plain)
                    .help(webEnabled ? "Web search enabled — Asta will search the web" : "Enable web search for this conversation")

                    // Agents picker
                    Menu {
                        if appState.agentsList.isEmpty {
                            Text("No agents yet")
                                .font(.caption)
                            Divider()
                            Text("Open Agents from the sidebar")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        } else {
                            Button {
                                setSelectedAgent(nil)
                            } label: {
                                HStack {
                                    Text("Asta (default)")
                                    if selectedAgentID == nil { Image(systemName: "checkmark") }
                                }
                            }
                            Divider()
                            ForEach(appState.agentsList.filter { $0.enabled ?? true }) { agent in
                                Button {
                                    setSelectedAgent(agent.id)
                                } label: {
                                    HStack {
                                        Text("\(agent.emoji.isEmpty ? "🤖" : agent.emoji) \(agent.name)")
                                        if selectedAgentID == agent.id { Image(systemName: "checkmark") }
                                    }
                                }
                            }
                        }
                    } label: {
                        HStack(spacing: 3) {
                            Image(systemName: "person.2")
                                .font(.system(size: 11, weight: .medium))
                            if let agent = selectedAgent {
                                Text(agent.emoji.isEmpty ? agent.name : "\(agent.emoji) \(agent.name)")
                                    .font(.system(size: 10, weight: .medium))
                                    .lineLimit(1)
                            }
                        }
                        .foregroundStyle(selectedAgent != nil ? Color.purple : textSecondary)
                        .padding(.horizontal, selectedAgent != nil ? 8 : 6).padding(.vertical, 4)
                        .background(selectedAgent != nil ? Color.purple.opacity(0.12) : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                    .menuStyle(.borderlessButton)
                    .fixedSize()
                    .help(selectedAgent != nil ? "Routing to \(selectedAgent?.name ?? "agent") — tap to change" : "Direct message to a specific agent")

                    Spacer()

                    // Stop or Send button
                    if isLoading {
                        Button(action: stopStreaming) {
                            Image(systemName: "stop.fill")
                                .font(.system(size: 10))
                                .foregroundStyle(.white)
                                .frame(width: 30, height: 30)
                                .background(Circle().fill(Color.secondary))
                        }
                        .buttonStyle(.plain)
                        .help("Stop generating")
                    } else {
                        Button(action: send) {
                            Image(systemName: "arrow.up")
                                .font(.system(size: 13, weight: .bold))
                                .foregroundStyle(.white)
                                .frame(width: 30, height: 30)
                                .background(Circle().fill(
                                    canSend
                                    ? LinearGradient(colors: [Color(red:0.30,green:0.48,blue:0.96), Color.accentColor], startPoint: .top, endPoint: .bottom)
                                    : LinearGradient(colors: [Color.primary.opacity(0.12), Color.primary.opacity(0.12)], startPoint: .top, endPoint: .bottom)
                                ))
                                .shadow(color: canSend ? Color.accentColor.opacity(0.3) : .clear, radius: 4, y: 2)
                        }
                        .buttonStyle(.plain)
                        .disabled(!canSend)
                        .animation(.easeOut(duration: 0.15), value: canSend)
                        .help("Send message (Enter)")
                    }
                }
                .padding(.horizontal, 8).padding(.bottom, 5).padding(.top, 2)
            }
            .padding(.horizontal, 12).padding(.top, 6)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(Color(nsColor: .textBackgroundColor))
                    .overlay(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5)
                    )
            )
            .padding(.horizontal, 16).padding(.vertical, 8)
        }
        .background(bg)
    }

    private func attachmentChip(_ att: ChatAttachment) -> some View {
        HStack(spacing: 5) {
            Image(systemName: att.icon)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(Color.accentColor)
            Text(att.name)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(textPrimary)
                .lineLimit(1)
            Button {
                withAnimation { attachments.removeAll { $0.id == att.id } }
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 12))
                    .foregroundStyle(textTertiary)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(Color.accentColor.opacity(0.08))
        .clipShape(Capsule())
        .help(att.name)
    }

    private var canSend: Bool {
        (!inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !attachments.isEmpty) && !isLoading
    }

    // MARK: - Drag overlay

    @ViewBuilder
    private var dragOverlay: some View {
        if isDraggingOver {
            ZStack {
                Rectangle()
                    .fill(Color.accentColor.opacity(0.08))
                    .ignoresSafeArea()
                VStack(spacing: 8) {
                    Image(systemName: "arrow.down.doc.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(Color.accentColor)
                    Text("Drop files here")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(Color.accentColor)
                }
            }
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(Color.accentColor.opacity(0.5), style: StrokeStyle(lineWidth: 2, dash: [8, 4]))
                    .padding(8)
            )
        }
    }

    // MARK: - Load history

    private func loadHistory(conversationID: String) async {
        guard !conversationID.isEmpty else { return }
        historyLoading = true
        historyError = nil
        do {
            let result = try await appState.client.chatMessages(conversationID: conversationID, limit: 100)
            let loaded = result.messages.compactMap { m -> ChatMessage? in
                guard let role = m.role, let content = m.content, !content.isEmpty else { return nil }
                return ChatMessage(role: role, content: content)
            }
            withAnimation(.easeOut(duration: 0.18)) {
                messages = loaded
            }
            startPolling(conversationID: conversationID)
        } catch {
            historyError = "Couldn't load chat history. Check your connection."
        }
        historyLoading = false
    }

    // MARK: - Stop streaming

    private func stopStreaming() {
        currentStreamTask?.cancel()
        currentStreamTask = nil
        for i in messages.indices where messages[i].isStreaming {
            messages[i].isStreaming = false
            messages[i].phase = .done
            if messages[i].content.isEmpty { messages[i].content = "(stopped)" }
        }
        isLoading = false
    }

    // MARK: - Background poll for subagent announces

    /// Polls the current conversation every 8 seconds for new messages while idle.
    /// This picks up subagent completion announces without requiring a persistent connection.
    private func startPolling(conversationID: String) {
        pollTask?.cancel()
        pollTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 8_000_000_000)
                guard !Task.isCancelled, !isLoading else { continue }
                guard let result = try? await appState.client.chatMessages(
                    conversationID: conversationID, limit: 100
                ) else { continue }
                let loaded = result.messages.compactMap { m -> ChatMessage? in
                    guard let role = m.role, let content = m.content, !content.isEmpty else { return nil }
                    return ChatMessage(role: role, content: content)
                }
                await MainActor.run {
                    if loaded.count > messages.count {
                        withAnimation(.easeOut(duration: 0.2)) { messages = loaded }
                    }
                }
            }
        }
    }

    private func stopPolling() {
        pollTask?.cancel()
        pollTask = nil
    }

    // MARK: - Send (streaming)

    private func send() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty || !attachments.isEmpty else { return }

        // Build the final message text
        var sendText = text
        if appState.learningModeEnabled && !text.isEmpty {
            sendText = "/learn " + text
            appState.learningModeEnabled = false
        }
        if let agent = selectedAgent, !sendText.isEmpty {
            sendText = "@\(agent.name): \(sendText)"
        }

        // Extract text content from non-image attachments and prepend
        var documentContext = ""
        for att in attachments {
            if let content = att.textContent {
                let truncated = String(content.prefix(20_000))
                documentContext += "<document name=\"\(att.name)\">\n\(truncated)\n</document>\n\n"
            }
        }
        if !documentContext.isEmpty {
            let question = sendText.isEmpty ? "Please analyze the attached document(s)." : sendText
            sendText = "\(documentContext)\(question)"
        }

        // Find image attachment (first one only — backend supports single image)
        let imageAtt = attachments.first(where: { $0.isImage })

        // Clear input
        let displayText = text.isEmpty ? (attachments.isEmpty ? "" : "[\(attachments.map(\.name).joined(separator: ", "))]") : text
        let msgAttachments = attachments.isEmpty ? nil : attachments
        inputText = ""
        attachments = []
        let currentConvID = conversationID
        let provider = appState.selectedProvider.isEmpty ? "default" : appState.selectedProvider
        let mood = appState.selectedMood == "normal" ? nil : appState.selectedMood

        messages.append(ChatMessage(role: "user", content: displayText, attachments: msgAttachments))
        isLoading = true

        let aMsg = ChatMessage(role: "assistant", content: "", isStreaming: true, phase: .thinking)
        let msgID = aMsg.id
        messages.append(aMsg)

        let streamTask = Task {
            do {
                let stream = appState.client.chatStream(
                    text: sendText.isEmpty ? "What's in this image?" : sendText,
                    conversationID: currentConvID,
                    provider: provider, mood: mood,
                    web: webEnabled,
                    imageData: imageAtt?.data, imageMime: imageAtt?.mime
                )

                for try await chunk in stream {
                    if Task.isCancelled { break }
                    await MainActor.run {
                        guard let idx = messages.firstIndex(where: { $0.id == msgID }) else { return }
                        switch chunk.type {
                        case "thinking":
                            var delta = chunk.text ?? ""
                            // Strip "Reasoning:\n" prefix that backend adds for formatting
                            if (messages[idx].thinkingContent ?? "").isEmpty && delta.hasPrefix("Reasoning:\n") {
                                delta = String(delta.dropFirst("Reasoning:\n".count))
                            }
                            messages[idx].thinkingContent = (messages[idx].thinkingContent ?? "") + delta
                            messages[idx].phase = .thinking
                            streamRevision += 1
                        case "text":
                            messages[idx].content += chunk.text ?? ""
                            messages[idx].phase = .responding
                            streamRevision += 1
                        case "status":
                            break
                        case "tool_start":
                            let toolLabel = chunk.toolLabel ?? chunk.toolName ?? "tool"
                            if !messages[idx].activeTools.contains(toolLabel) {
                                messages[idx].activeTools.append(toolLabel)
                            }
                            streamRevision += 1
                        case "tool_end":
                            let toolLabel = chunk.toolLabel ?? chunk.toolName ?? "tool"
                            messages[idx].activeTools.removeAll { $0 == toolLabel }
                            if !messages[idx].completedTools.contains(toolLabel) {
                                messages[idx].completedTools.append(toolLabel)
                            }
                            streamRevision += 1
                        case "done":
                            // Clear any remaining active tools (safety net)
                            messages[idx].activeTools = []
                            // Use streamed reply as fallback if token stream didn't populate content
                            if messages[idx].content.isEmpty, let r = chunk.reply, !r.isEmpty {
                                messages[idx].content = r.trimmingCharacters(in: .whitespacesAndNewlines)
                            }
                            messages[idx].isStreaming = false
                            messages[idx].phase = .done
                            messages[idx].provider = chunk.provider
                            let wasNewConversation = conversationID == nil
                            if let cid = chunk.conversation_id { conversationID = cid }
                            isLoading = false; streamRevision += 1
                            // For brand-new conversations, schedule a delayed sidebar refresh so the
                            // AI-generated title (produced async in backend) appears shortly after.
                            if wasNewConversation {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                                    appState.sidebarRefreshTrigger += 1
                                }
                            }
                        case "error":
                            messages[idx].content = chunk.text ?? "Server error"
                            messages[idx].isStreaming = false
                            messages[idx].phase = .done
                            isLoading = false
                        default: break
                        }
                    }
                }
                await MainActor.run {
                    if let idx = messages.firstIndex(where: { $0.id == msgID }) {
                        messages[idx].isStreaming = false
                        if messages[idx].phase != .done { messages[idx].phase = .done }
                    }
                    isLoading = false
                }
            } catch is CancellationError {
                // Handled by stopStreaming
            } catch {
                await MainActor.run {
                    if let idx = messages.firstIndex(where: { $0.id == msgID }) {
                        let e: String
                        if let u = error as? URLError {
                            switch u.code {
                            case .cannotConnectToHost, .cannotFindHost:
                                e = "Cannot connect to Asta backend. Make sure it's running:\n  cd ~/asta && ./asta.sh start"
                            case .timedOut:
                                e = "Request timed out. The backend may be overloaded or not running."
                            case .notConnectedToInternet:
                                e = "No internet connection."
                            case .networkConnectionLost:
                                e = "Connection lost. Check your network and backend status."
                            default:
                                e = "Network error: \(u.localizedDescription)"
                            }
                        } else if (error as NSError).domain == NSURLErrorDomain {
                            e = "Cannot reach Asta backend. Start it with:\n  cd ~/asta && ./asta.sh start"
                        } else { e = "Error: \(error.localizedDescription)" }
                        messages[idx].content = e
                        messages[idx].isStreaming = false
                        messages[idx].phase = .done
                    }
                    isLoading = false
                }
            }
        }
        currentStreamTask = streamTask
    }

    private static func stripToolsUsed(from content: String) -> (main: String, toolsUsed: String?) {
        guard let range = content.range(of: #"\n+Tools used:[^\n]*(\n|$)"#, options: [.regularExpression, .backwards])
        else { return (content.trimmingCharacters(in: .whitespacesAndNewlines), nil) }
        let before = String(content[..<range.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
        let line   = String(content[range]).trimmingCharacters(in: .whitespacesAndNewlines)
        return (before, line)
    }

    // MARK: - Drag & drop

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        var handled = false
        for provider in providers {
            if provider.hasItemConformingToTypeIdentifier(UTType.fileURL.identifier) {
                provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier) { item, _ in
                    guard let data = item as? Data,
                          let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
                    if let att = ChatAttachment.from(url: url) {
                        Task { @MainActor in withAnimation { attachments.append(att) } }
                    }
                }
                handled = true
            }
            else if provider.hasItemConformingToTypeIdentifier(UTType.image.identifier) {
                provider.loadDataRepresentation(forTypeIdentifier: UTType.image.identifier) { data, _ in
                    guard let data else { return }
                    let att = ChatAttachment.from(data: data, name: "image.png", mime: "image/png")
                    Task { @MainActor in withAnimation { attachments.append(att) } }
                }
                handled = true
            }
        }
        return handled
    }

    // MARK: - File picker

    private func pickFile() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = ChatAttachment.acceptedTypes
        panel.begin { response in
            guard response == .OK else { return }
            for url in panel.urls {
                if let att = ChatAttachment.from(url: url) {
                    Task { @MainActor in withAnimation { attachments.append(att) } }
                }
            }
        }
    }
}

// MARK: - Markdown rendering view (NSTextView-based for proper formatting)

struct MarkdownView: View {
    let content: String
    let textColor: Color

    var body: some View {
        let nsColor = NSColor(textColor)
        let attrString = Self.renderToAttributedString(content, textColor: nsColor)
        Text(attrString)
            .textSelection(.enabled)
    }

    /// Convert our NSAttributedString rendering to SwiftUI AttributedString
    private static func renderToAttributedString(_ content: String, textColor: NSColor) -> AttributedString {
        let nsAttr = renderMarkdown(content, textColor: textColor)
        return (try? AttributedString(nsAttr, including: \.appKit)) ?? AttributedString(content)
    }

    /// Convert markdown text to styled NSAttributedString.
    /// Handles: **bold**, *italic*, `code`, ```code blocks```, # headings, - lists, newlines.
    static func renderMarkdown(_ text: String, textColor: NSColor) -> NSAttributedString {
        let result = NSMutableAttributedString()
        let baseFont = NSFont.systemFont(ofSize: 14)
        let boldFont = NSFont.boldSystemFont(ofSize: 14)
        let italicFont = NSFont.systemFont(ofSize: 14).with(traits: .italicFontMask)
        let codeFont = NSFont.monospacedSystemFont(ofSize: 12.5, weight: .regular)
        let headingFont = NSFont.boldSystemFont(ofSize: 16)
        let heading2Font = NSFont.boldSystemFont(ofSize: 15)

        let baseAttrs: [NSAttributedString.Key: Any] = [
            .font: baseFont,
            .foregroundColor: textColor,
            .paragraphStyle: {
                let p = NSMutableParagraphStyle()
                p.lineSpacing = 3
                p.paragraphSpacing = 6
                return p
            }()
        ]

        let lines = text.components(separatedBy: "\n")
        var inCodeBlock = false
        var codeBlockContent = ""
        // codeBlockLanguage reserved for future syntax highlighting

        for (lineIndex, line) in lines.enumerated() {
            // Code block fences
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("```") {
                if inCodeBlock {
                    // End code block
                    inCodeBlock = false
                    let codeAttrs: [NSAttributedString.Key: Any] = [
                        .font: codeFont,
                        .foregroundColor: NSColor.secondaryLabelColor,
                        .backgroundColor: NSColor.quaternaryLabelColor.withAlphaComponent(0.15),
                        .paragraphStyle: {
                            let p = NSMutableParagraphStyle()
                            p.lineSpacing = 2
                            p.paragraphSpacing = 6
                            return p
                        }()
                    ]
                    if !codeBlockContent.isEmpty {
                        // Remove trailing newline from code block
                        let trimmed = codeBlockContent.hasSuffix("\n")
                            ? String(codeBlockContent.dropLast())
                            : codeBlockContent
                        result.append(NSAttributedString(string: trimmed, attributes: codeAttrs))
                        result.append(NSAttributedString(string: "\n", attributes: baseAttrs))
                    }
                    codeBlockContent = ""
                    continue
                } else {
                    // Start code block
                    inCodeBlock = true
                    let fence = line.trimmingCharacters(in: .whitespaces)
                    _ = String(fence.dropFirst(3)).trimmingCharacters(in: .whitespaces) // language hint
                    continue
                }
            }

            if inCodeBlock {
                codeBlockContent += line + "\n"
                continue
            }

            // Headings
            if line.hasPrefix("### ") {
                let heading = String(line.dropFirst(4))
                var attrs = baseAttrs
                attrs[.font] = heading2Font
                result.append(NSAttributedString(string: heading, attributes: attrs))
                result.append(NSAttributedString(string: "\n", attributes: baseAttrs))
                continue
            }
            if line.hasPrefix("## ") {
                let heading = String(line.dropFirst(3))
                var attrs = baseAttrs
                attrs[.font] = heading2Font
                result.append(NSAttributedString(string: heading, attributes: attrs))
                result.append(NSAttributedString(string: "\n", attributes: baseAttrs))
                continue
            }
            if line.hasPrefix("# ") {
                let heading = String(line.dropFirst(2))
                var attrs = baseAttrs
                attrs[.font] = headingFont
                result.append(NSAttributedString(string: heading, attributes: attrs))
                result.append(NSAttributedString(string: "\n", attributes: baseAttrs))
                continue
            }

            // Horizontal rule
            let trimmedLine = line.trimmingCharacters(in: .whitespaces)
            if trimmedLine == "---" || trimmedLine == "***" || trimmedLine == "___" {
                result.append(NSAttributedString(string: "\n", attributes: baseAttrs))
                continue
            }

            // Bullet lists
            let isUnorderedList = trimmedLine.hasPrefix("- ") || trimmedLine.hasPrefix("* ")
            let isOrderedList = trimmedLine.range(of: #"^\d+\.\s"#, options: .regularExpression) != nil

            if isUnorderedList || isOrderedList {
                let listText: String
                if isUnorderedList {
                    let content = String(trimmedLine.dropFirst(2))
                    listText = "  \u{2022} \(content)"
                } else {
                    listText = "  \(trimmedLine)"
                }
                let styledLine = Self.applyInlineStyles(listText, baseAttrs: baseAttrs, boldFont: boldFont, italicFont: italicFont, codeFont: codeFont, textColor: textColor)
                result.append(styledLine)
                result.append(NSAttributedString(string: "\n", attributes: baseAttrs))
                continue
            }

            // Regular text with inline formatting
            let styledLine = Self.applyInlineStyles(line, baseAttrs: baseAttrs, boldFont: boldFont, italicFont: italicFont, codeFont: codeFont, textColor: textColor)
            result.append(styledLine)
            if lineIndex < lines.count - 1 {
                result.append(NSAttributedString(string: "\n", attributes: baseAttrs))
            }
        }

        // If code block was never closed, flush remaining
        if inCodeBlock && !codeBlockContent.isEmpty {
            let codeAttrs: [NSAttributedString.Key: Any] = [
                .font: codeFont,
                .foregroundColor: NSColor.secondaryLabelColor,
                .backgroundColor: NSColor.quaternaryLabelColor.withAlphaComponent(0.15),
            ]
            result.append(NSAttributedString(string: codeBlockContent, attributes: codeAttrs))
        }

        return result
    }

    /// Apply inline markdown styles: **bold**, *italic*, `code`, [links](url)
    static func applyInlineStyles(
        _ text: String,
        baseAttrs: [NSAttributedString.Key: Any],
        boldFont: NSFont,
        italicFont: NSFont,
        codeFont: NSFont,
        textColor: NSColor
    ) -> NSAttributedString {
        let result = NSMutableAttributedString()

        // Pattern matching order matters: bold+italic first, then bold, italic, code, links
        let patterns: [(regex: String, handler: (String, [NSAttributedString.Key: Any]) -> NSAttributedString)] = [
            // Bold+italic ***text***
            (#"\*\*\*(.+?)\*\*\*"#, { match, attrs in
                var a = attrs
                a[.font] = NSFontManager.shared.convert(boldFont, toHaveTrait: .italicFontMask)
                return NSAttributedString(string: match, attributes: a)
            }),
            // Bold **text**
            (#"\*\*(.+?)\*\*"#, { match, attrs in
                var a = attrs
                a[.font] = boldFont
                return NSAttributedString(string: match, attributes: a)
            }),
            // Italic *text*
            (#"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)"#, { match, attrs in
                var a = attrs
                a[.font] = italicFont
                return NSAttributedString(string: match, attributes: a)
            }),
            // Inline code `text`
            (#"`([^`]+)`"#, { match, attrs in
                var a = attrs
                a[.font] = codeFont
                a[.foregroundColor] = NSColor.secondaryLabelColor
                a[.backgroundColor] = NSColor.quaternaryLabelColor.withAlphaComponent(0.15)
                return NSAttributedString(string: " \(match) ", attributes: a)
            }),
        ]

        // Simple approach: process the string sequentially
        var remaining = text
        while !remaining.isEmpty {
            // Find the earliest match across all patterns
            var earliestRange: Range<String.Index>? = nil
            var earliestPattern: Int? = nil
            var earliestCapture: String = ""

            for (i, p) in patterns.enumerated() {
                if let match = remaining.range(of: p.regex, options: .regularExpression) {
                    if earliestRange == nil || match.lowerBound < earliestRange!.lowerBound {
                        earliestRange = match
                        earliestPattern = i
                        // Extract capture group (text without delimiters)
                        if let nsRange = Range(NSRange(match, in: remaining), in: remaining) {
                            let full = String(remaining[nsRange])
                            // Remove markdown delimiters
                            if full.hasPrefix("***") && full.hasSuffix("***") {
                                earliestCapture = String(full.dropFirst(3).dropLast(3))
                            } else if full.hasPrefix("**") && full.hasSuffix("**") {
                                earliestCapture = String(full.dropFirst(2).dropLast(2))
                            } else if full.hasPrefix("`") && full.hasSuffix("`") {
                                earliestCapture = String(full.dropFirst(1).dropLast(1))
                            } else if full.hasPrefix("*") && full.hasSuffix("*") {
                                earliestCapture = String(full.dropFirst(1).dropLast(1))
                            } else {
                                earliestCapture = full
                            }
                        }
                    }
                }
            }

            if let range = earliestRange, let patternIdx = earliestPattern {
                // Add text before the match
                let before = String(remaining[remaining.startIndex..<range.lowerBound])
                if !before.isEmpty {
                    result.append(NSAttributedString(string: before, attributes: baseAttrs))
                }
                // Add the styled match
                let styled = patterns[patternIdx].handler(earliestCapture, baseAttrs)
                result.append(styled)
                remaining = String(remaining[range.upperBound...])
            } else {
                // No more matches — add remaining text
                result.append(NSAttributedString(string: remaining, attributes: baseAttrs))
                break
            }
        }

        return result
    }
}

// MARK: - NSFont extension for traits

extension NSFont {
    func with(traits: NSFontTraitMask) -> NSFont {
        NSFontManager.shared.convert(self, toHaveTrait: traits)
    }
}

// MARK: - Message segment parser (splits text and inline images)

enum MessageSegment {
    case text(String)
    case image(url: URL, alt: String)

    /// Split content on `![alt](url)` patterns. Returns a single `.text` segment when
    /// there are no image matches (fast path for the vast majority of messages).
    /// Handles both remote URLs (https://) and inline base64 data URLs (data:image/...).
    static func parse(_ content: String) -> [MessageSegment] {
        guard content.contains("![") else { return [.text(content)] }
        // Match both https:// remote URLs and data: base64 inline images
        guard let regex = try? NSRegularExpression(
            pattern: #"!\[([^\]]*)\]\(((?:https?://|data:image/)[^\)]+)\)"#
        ) else {
            return [.text(content)]
        }
        let ns = content as NSString
        let matches = regex.matches(in: content, range: NSRange(location: 0, length: ns.length))
        guard !matches.isEmpty else { return [.text(content)] }

        var segments: [MessageSegment] = []
        var cursor = 0
        for match in matches {
            let matchRange = match.range
            if matchRange.location > cursor {
                let pre = ns.substring(with: NSRange(location: cursor, length: matchRange.location - cursor))
                if !pre.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    segments.append(.text(pre))
                }
            }
            let alt = match.range(at: 1).location != NSNotFound ? ns.substring(with: match.range(at: 1)) : ""
            let urlStr = match.range(at: 2).location != NSNotFound ? ns.substring(with: match.range(at: 2)) : ""
            if let url = URL(string: urlStr) {
                segments.append(.image(url: url, alt: alt))
            }
            cursor = matchRange.location + matchRange.length
        }
        if cursor < ns.length {
            let tail = ns.substring(from: cursor)
            if !tail.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                segments.append(.text(tail))
            }
        }
        return segments
    }
}

// MARK: - Remote image view (supports animated GIFs via NSImageView.animates)

struct RemoteImageView: View {
    let url: URL
    @State private var image: NSImage?
    @State private var failed = false

    var body: some View {
        Group {
            if let img = image {
                AnimatedNSImageView(image: img)
                    .aspectRatio(contentMode: .fit)
                    .frame(maxWidth: 480, maxHeight: 360)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            } else if failed {
                // Fallback: show the URL as a tappable link
                Link(url.absoluteString, destination: url)
                    .font(.system(size: 12))
                    .foregroundStyle(Color.accentColor)
            } else {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.secondary.opacity(0.08))
                    .frame(height: 80)
                    .overlay(ProgressView().scaleEffect(0.65))
            }
        }
        .task(id: url) {
            image = nil; failed = false
            // Handle inline base64 data URLs (e.g. from image_gen tool: data:image/png;base64,...)
            if url.scheme == "data" {
                let raw = url.absoluteString
                if let commaIdx = raw.firstIndex(of: ",") {
                    let b64 = String(raw[raw.index(after: commaIdx)...])
                    if let data = Data(base64Encoded: b64, options: .ignoreUnknownCharacters),
                       let img = NSImage(data: data) {
                        image = img
                        return
                    }
                }
                failed = true
            } else if let (data, _) = try? await URLSession.shared.data(from: url),
                      let img = NSImage(data: data) {
                image = img
            } else {
                failed = true
            }
        }
    }
}

/// NSViewRepresentable that wraps NSImageView with `animates = true` for GIF playback.
private struct AnimatedNSImageView: NSViewRepresentable {
    let image: NSImage

    func makeNSView(context: Context) -> NSImageView {
        let iv = NSImageView()
        iv.animates = true
        iv.imageScaling = .scaleProportionallyDown
        return iv
    }

    func updateNSView(_ iv: NSImageView, context: Context) {
        iv.image = image
    }
}
