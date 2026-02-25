import SwiftUI
import AppKit
import UniformTypeIdentifiers
import AstaAPIClient

// MARK: - Settings sheet

struct SettingsView: View {
    @ObservedObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    enum Tab: String, CaseIterable, Identifiable {
        case general   = "General"
        case persona   = "Persona"
        case models    = "Models"
        case keys      = "API Keys"
        case spotify   = "Spotify"
        case skills    = "Skills"
        case knowledge = "Knowledge"
        case channels  = "Channels"
        case cron      = "Schedule"
        case google    = "Google"
        case tailscale = "Connection"
        case permissions = "Permissions"
        case about     = "About"
        var id: String { rawValue }
        var icon: String {
            switch self {
            case .general:      return "gearshape"
            case .persona:      return "person.crop.circle"
            case .models:       return "cpu"
            case .keys:         return "key"
            case .spotify:      return "music.note"
            case .skills:       return "puzzlepiece.extension"
            case .knowledge:    return "brain.head.profile"
            case .channels:     return "link"
            case .cron:         return "clock"
            case .google:       return "globe"
            case .tailscale:    return "antenna.radiowaves.left.and.right"
            case .permissions:  return "hand.raised"
            case .about:        return "info.circle"
            }
        }
        /// Provider ID to render a branded logo instead of an SF Symbol. nil = use icon.
        var brandProvider: String? {
            switch self {
            case .spotify:   return "spotify"
            case .google:    return "google"
            case .channels:  return "telegram"
            default:         return nil
            }
        }
    }

    @State private var tab: Tab = .general

    var body: some View {
        HStack(spacing: 0) {
            // ── Left sidebar ─────────────────────────────────────────────
            VStack(spacing: 0) {
                // App title + connection status
                VStack(alignment: .leading, spacing: 6) {
                    Text("Settings")
                        .font(.system(size: 14, weight: .semibold))
                    HStack(spacing: 5) {
                        Circle()
                            .fill(appState.connected ? Color.green : Color.red)
                            .frame(width: 6, height: 6)
                        Text(appState.connected ? "Online" : "Offline")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 14).padding(.top, 20).padding(.bottom, 10)

                Divider().opacity(0.5)

                // Tab list
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: 1) {
                        ForEach(Tab.allCases) { t in
                            Button {
                                withAnimation(.easeOut(duration: 0.12)) { tab = t }
                            } label: {
                                HStack(spacing: 8) {
                                    if let bp = t.brandProvider {
                                        ProviderLogo(provider: bp, size: 18)
                                            .frame(width: 18, height: 18)
                                            .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                                            .opacity(tab == t ? 1.0 : 0.65)
                                    } else {
                                        Image(systemName: t.icon)
                                            .font(.system(size: 12, weight: .medium))
                                            .frame(width: 16, alignment: .center)
                                            .foregroundStyle(tab == t ? Color.accentColor : Color(nsColor: .secondaryLabelColor))
                                    }
                                    Text(t.rawValue)
                                        .font(.system(size: 13))
                                        .foregroundStyle(tab == t ? Color.accentColor : Color(nsColor: .labelColor))
                                    Spacer()
                                }
                                .padding(.horizontal, 10).padding(.vertical, 7)
                                .background(tab == t ? Color.accentColor.opacity(0.1) : Color.clear)
                                .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 8).padding(.vertical, 8)
                }

                Spacer(minLength: 0)
            }
            .frame(width: 170)
            .background(Color(nsColor: .controlBackgroundColor))

            Divider()

            // ── Content area ─────────────────────────────────────────────
            VStack(spacing: 0) {
                // Per-tab header + close
                HStack {
                    Text(tab.rawValue)
                        .font(.system(size: 15, weight: .semibold))
                    Spacer()
                    Button { dismiss() } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 18))
                            .foregroundStyle(Color(nsColor: .tertiaryLabelColor))
                    }
                    .buttonStyle(.plain)
                    .keyboardShortcut(.escape, modifiers: [])
                }
                .padding(.horizontal, 22).padding(.top, 18).padding(.bottom, 12)

                Divider()

                ScrollView {
                    Group {
                        switch tab {
                        case .general:      GeneralSettingsTab(appState: appState)
                        case .persona:      PersonaSettingsTab(appState: appState)
                        case .models:       ModelsSettingsTab(appState: appState)
                        case .keys:         KeysSettingsTab(appState: appState)
                        case .spotify:      SpotifySettingsTab(appState: appState)
                        case .skills:       SkillsSettingsTab(appState: appState)
                        case .knowledge:    KnowledgeSettingsTab(appState: appState)
                        case .channels:     ChannelsSettingsTab(appState: appState)
                        case .cron:         CronSettingsTab(appState: appState)
                        case .google:       GoogleWorkspaceSettingsTab()
                        case .tailscale:    TailscaleSettingsTab(appState: appState)
                        case .permissions:  PermissionsSettingsTab()
                        case .about:        AboutSettingsTab(appState: appState)
                        }
                    }
                    .padding(.bottom, 20)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(maxWidth: .infinity)
        }
        .frame(width: 820, height: 580)
        .background(Color(nsColor: .windowBackgroundColor))
        .task { await appState.loadSettings() }
    }
}

// MARK: - General

struct GeneralSettingsTab: View {
    @ObservedObject var appState: AppState
    private let thinkingOptions  = ["off","minimal","low","medium","high","xhigh"]
    private let reasoningOptions = ["off","on","stream"]
    private let finalModeOptions = ["off","strict"]
    private let moodOptions      = ["normal","friendly","serious"]

    var body: some View {
        Form {
            Section {
                Picker("Default provider", selection: Binding(
                    get: { appState.selectedProvider },
                    set: { new in Task { await appState.setDefaultAI(new) } }
                )) {
                    ForEach(providerNames(), id: \.self) { p in
                        Label {
                            Text(astaProviderDisplayName(p))
                        } icon: {
                            ProviderLogo(provider: p, size: 16)
                                .clipShape(RoundedRectangle(cornerRadius: 3, style: .continuous))
                        }
                        .tag(p)
                    }
                }
                Text("Which AI answers in Chat and Telegram.").font(.caption).foregroundStyle(.secondary)
            } header: { Text("AI Provider") }

            Section {
                ForEach(providerFlowItems(), id: \.provider) { item in
                    Toggle(isOn: Binding(
                        get: { item.enabled ?? true },
                        set: { new in Task { await appState.setProviderEnabled(item.provider, enabled: new) } }
                    )) {
                        HStack(spacing: 10) {
                            ProviderLogo(provider: item.provider, size: 26)
                                .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                            VStack(alignment: .leading, spacing: 1) {
                                Text(astaProviderDisplayName(item.label ?? item.provider))
                                    .font(.system(size: 13))
                                if item.auto_disabled == true {
                                    Text("auto-disabled — no key set")
                                        .font(.caption).foregroundStyle(.secondary)
                                } else if item.connected != true {
                                    Text("not connected").font(.caption).foregroundStyle(.orange)
                                }
                            }
                        }
                    }
                    .disabled(item.connected != true)
                }
            } header: { Text("Enable / disable providers") }
             footer: { Text("Add API keys in the Keys tab to connect cloud providers.") }

            Section {
                Picker("Thinking level", selection: Binding(
                    get: { appState.selectedThinking },
                    set: { new in Task { await appState.setThinking(new) } }
                )) { ForEach(thinkingOptions, id: \.self) { Text($0).tag($0) } }
                Picker("Reasoning mode", selection: Binding(
                    get: { appState.selectedReasoning },
                    set: { new in Task { await appState.setReasoning(new) } }
                )) { ForEach(reasoningOptions, id: \.self) { Text($0).tag($0) } }
                Picker("Final mode", selection: Binding(
                    get: { appState.selectedFinalMode },
                    set: { new in Task { await appState.setFinalMode(new) } }
                )) { ForEach(finalModeOptions, id: \.self) { Text($0).tag($0) } }
            } header: { Text("Thinking & Reasoning") }

            Section {
                Picker("Chat mood", selection: Binding(
                    get: { appState.selectedMood },
                    set: { new in Task { await appState.setMood(new) } }
                )) { ForEach(moodOptions, id: \.self) { m in Text(m.capitalized).tag(m) } }
                Text("Changes the tone of AI replies in Chat and Telegram.").font(.caption).foregroundStyle(.secondary)
            } header: { Text("Mood") }

            if let err = appState.error {
                Section { Text(err).font(.caption).foregroundStyle(.red) }
            }
        }
        .formStyle(.grouped)
    }
    private func providerNames() -> [String] { appState.providers.isEmpty ? ["claude","ollama","openrouter","openai","google","groq"] : appState.providers }
    private func providerFlowItems() -> [AstaProviderFlowItem] { appState.providerFlow?.providers ?? [] }
}

// MARK: - Persona

struct PersonaSettingsTab: View {
    @ObservedObject var appState: AppState

    @State private var soulText: String = ""
    @State private var userText: String = ""
    @State private var isLoading = true
    @State private var isSaving = false
    @State private var saveStatus: String? = nil
    @State private var selectedSection: PersonaSection = .soul

    enum PersonaSection: String, CaseIterable, Identifiable {
        case soul = "Soul"
        case user = "About Me"
        var id: String { rawValue }
        var icon: String {
            switch self {
            case .soul: return "sparkles"
            case .user: return "person.fill"
            }
        }
        var subtitle: String {
            switch self {
            case .soul: return "Asta's personality, tone and behaviour"
            case .user: return "Your name, location and preferences"
            }
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            if isLoading {
                ProgressView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                // Section picker
                HStack(spacing: 8) {
                    ForEach(PersonaSection.allCases) { section in
                        Button {
                            withAnimation(.easeOut(duration: 0.12)) { selectedSection = section }
                        } label: {
                            Label(section.rawValue, systemImage: section.icon)
                                .font(.system(size: 13, weight: selectedSection == section ? .semibold : .regular))
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(selectedSection == section ? Color.accentColor.opacity(0.15) : Color.clear)
                                .foregroundStyle(selectedSection == section ? Color.accentColor : Color(nsColor: .secondaryLabelColor))
                                .cornerRadius(7)
                        }
                        .buttonStyle(.plain)
                    }
                    Spacer()
                    if let status = saveStatus {
                        Text(status)
                            .font(.caption)
                            .foregroundStyle(status.contains("✓") ? Color.green : Color(nsColor: .secondaryLabelColor))
                            .transition(.opacity)
                    }
                    Button {
                        Task { await save() }
                    } label: {
                        if isSaving {
                            ProgressView().scaleEffect(0.7)
                        } else {
                            Text("Save")
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isSaving)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)

                Divider()

                // Editor area
                VStack(alignment: .leading, spacing: 6) {
                    Text(selectedSection.subtitle)
                        .font(.caption)
                        .foregroundStyle(Color(nsColor: .secondaryLabelColor))
                        .padding(.horizontal, 16)
                        .padding(.top, 10)

                    TextEditor(text: selectedSection == .soul ? $soulText : $userText)
                        .font(.system(.body, design: .monospaced))
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .padding(8)
                        .background(Color(nsColor: .textBackgroundColor))
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color(nsColor: .separatorColor), lineWidth: 0.5)
                        )
                        .padding(.horizontal, 16)
                        .padding(.bottom, 16)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .task { await load() }
    }

    private func load() async {
        isLoading = true
        do {
            let persona = try await appState.client.fetchPersona()
            soulText = persona.soul
            userText = persona.user
        } catch {
            soulText = "# Error loading SOUL.md\n\(error.localizedDescription)"
        }
        isLoading = false
    }

    private func save() async {
        isSaving = true
        saveStatus = nil
        do {
            try await appState.client.savePersona(
                soul: selectedSection == .soul ? soulText : nil,
                user: selectedSection == .user ? userText : nil
            )
            saveStatus = "✓ Saved"
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { saveStatus = nil }
        } catch {
            saveStatus = "Error: \(error.localizedDescription)"
        }
        isSaving = false
    }
}

// MARK: - Models

struct ModelsSettingsTab: View {
    @ObservedObject var appState: AppState
    @State private var usageRows: [AstaUsageRow] = []
    @State private var usageLoading = true

    var body: some View {
        Form {
            Section {
                Text("Leave a provider on its default, or choose / type a specific model string.").font(.caption).foregroundStyle(.secondary)
            }
            if let models = appState.modelsResponse?.models {
                Section {
                    ForEach(Array(models.keys.sorted()), id: \.self) { provider in
                        let current = models[provider] ?? ""
                        let opts = modelOptions(for: provider)
                        if opts.isEmpty {
                            ModelTextField(provider: provider, label: astaProviderDisplayName(provider), current: current, appState: appState)
                        } else {
                            Picker(astaProviderDisplayName(provider), selection: Binding(
                                get: { current.isEmpty ? "(default)" : current },
                                set: { new in Task { await appState.setModel(provider: provider, model: new == "(default)" ? "" : new) } }
                            )) {
                                Text("(default)").tag("(default)")
                                ForEach(opts, id: \.self) { Text($0).tag($0) }
                            }
                        }
                    }
                } header: { Text("Model per provider") }
            } else {
                Section { ProgressView().frame(maxWidth: .infinity) }
            }

            // Token usage (last 30 days)
            Section {
                if usageLoading {
                    ProgressView().frame(maxWidth: .infinity)
                } else if usageRows.isEmpty {
                    Text("No usage data yet. Counts appear after conversations.")
                        .font(.caption).foregroundStyle(.secondary)
                } else {
                    Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 4) {
                        GridRow {
                            Text("Provider").font(.caption).foregroundStyle(.secondary).gridColumnAlignment(.leading)
                            Text("Input").font(.caption).foregroundStyle(.secondary).gridColumnAlignment(.trailing)
                            Text("Output").font(.caption).foregroundStyle(.secondary).gridColumnAlignment(.trailing)
                            Text("Calls").font(.caption).foregroundStyle(.secondary).gridColumnAlignment(.trailing)
                        }
                        Divider()
                        ForEach(usageRows) { row in
                            GridRow {
                                Text(row.provider).font(.system(size: 12))
                                Text(fmtTokens(row.input_tokens)).font(.system(size: 12)).gridColumnAlignment(.trailing)
                                Text(fmtTokens(row.output_tokens)).font(.system(size: 12)).gridColumnAlignment(.trailing)
                                Text("\(row.calls)").font(.system(size: 12)).gridColumnAlignment(.trailing)
                            }
                        }
                    }
                }
            } header: { Text("Token usage (last 30 days)") }
        }
        .formStyle(.grouped)
        .task { await loadUsage() }
    }

    private func fmtTokens(_ n: Int) -> String {
        if n >= 1_000_000 { return String(format: "%.1fM", Double(n) / 1_000_000) }
        if n >= 1_000 { return String(format: "%.1fK", Double(n) / 1_000) }
        return "\(n)"
    }

    private func loadUsage() async {
        guard appState.connected else { usageLoading = false; return }
        usageLoading = true
        if let resp = try? await appState.client.usageStats(days: 30) {
            usageRows = resp.usage
        }
        usageLoading = false
    }

    private func modelOptions(for provider: String) -> [String] {
        guard let a = appState.availableModels else { return [] }
        switch provider {
        case "ollama":      return a.ollama ?? []
        case "openrouter":  return a.openrouter ?? []
        case "claude":      return a.claude ?? []
        case "openai":      return a.openai ?? []
        case "google":      return a.google ?? []
        case "groq":        return a.groq ?? []
        default:            return []
        }
    }
}

// MARK: - API Keys

struct KeysSettingsTab: View {
    @ObservedObject var appState: AppState
    @State private var newKeys: [String: String] = [:]
    @State private var testing: [String: Bool] = [:]
    @State private var results: [String: String] = [:]

    private struct ProviderKey {
        let name: String; let provider: String; let key: String; let url: String; let hint: String
    }
    private let providerKeys: [ProviderKey] = [
        ProviderKey(name: "Claude",   provider: "claude",     key: "anthropic_api_key",  url: "https://console.anthropic.com/settings/keys", hint: "Starts with sk-ant-…"),
        ProviderKey(name: "OpenRouter",  provider: "openrouter", key: "openrouter_api_key", url: "https://openrouter.ai/keys",                   hint: "Starts with sk-or-…  (free tier available)"),
        ProviderKey(name: "OpenAI",   provider: "openai",     key: "openai_api_key",     url: "https://platform.openai.com/api-keys",          hint: "Starts with sk-…"),
        ProviderKey(name: "Google Gemini", provider: "google",   key: "gemini_api_key",     url: "https://aistudio.google.com/apikey",            hint: "Get free key from Google AI Studio (not Google Cloud)"),
        ProviderKey(name: "Hugging Face", provider: "huggingface", key: "huggingface_api_key", url: "https://huggingface.co/settings/tokens", hint: "Used for FLUX.1-dev image fallback"),
        ProviderKey(name: "Groq",     provider: "groq",       key: "groq_api_key",       url: "https://console.groq.com/keys",                 hint: "Free tier — very fast inference"),
        ProviderKey(name: "Telegram Bot", provider: "telegram", key: "telegram_bot_token", url: "https://t.me/BotFather",                        hint: "Create via @BotFather on Telegram → /newbot"),
        ProviderKey(name: "Notion",   provider: "notion",   key: "notion_api_key", url: "https://www.notion.so/my-integrations",  hint: "Internal integration token"),
        ProviderKey(name: "Giphy",    provider: "giphy",    key: "giphy_api_key",  url: "https://developers.giphy.com/dashboard", hint: "For GIF search tool"),
    ]

    var body: some View {
        Form {
            Section {
                Text("API keys are stored locally and only sent to the respective service. Use the Test button to verify a key works.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            ForEach(providerKeys, id: \.key) { p in
                keySection(p)
            }
            Section {
                Button("Save all pending changes") { saveAll() }
                    .buttonStyle(.borderedProminent).frame(maxWidth: .infinity)
            }
        }
        .formStyle(.grouped)
    }

    @ViewBuilder
    private func keySection(_ p: ProviderKey) -> some View {
        let isSet = appState.keysStatus?[p.key] == true
        let hasInput = !(newKeys[p.key] ?? "").isEmpty
        Section {
            // Status row
            HStack {
                ProviderLogo(provider: p.provider, size: 32)
                    .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(p.name).font(.system(size: 13, weight: .semibold))
                    Text(p.hint).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                HStack(spacing: 5) {
                    Circle().fill(isSet ? Color.green : Color.gray.opacity(0.5)).frame(width: 7, height: 7)
                    Text(isSet ? "Active" : "Not set").font(.caption).foregroundStyle(isSet ? .green : .secondary)
                }
            }
            // Input
            SecureField(isSet ? "Replace existing key…" : "Paste key here", text: binding(for: p.key))
                .font(.system(.body, design: .monospaced))
            // Actions row
            HStack {
                Link("Get key →", destination: URL(string: p.url)!).font(.caption)
                Spacer()
                if hasInput {
                    Button("Save") { save(keyName: p.key) }.buttonStyle(.borderedProminent).controlSize(.small)
                }
                if isSet {
                    if testing[p.provider] == true {
                        ProgressView().controlSize(.small)
                    } else if let r = results[p.provider] {
                        Text(r).font(.caption).foregroundStyle(r == "OK" ? .green : .orange)
                    } else {
                        Button("Test") { testKey(provider: p.provider) }.buttonStyle(.bordered).controlSize(.small)
                    }
                }
            }
        } header: { Text(p.name) }
    }

    private func binding(for key: String) -> Binding<String> {
        Binding(get: { newKeys[key] ?? "" }, set: { newKeys[key] = $0 })
    }

    private func testKey(provider: String) {
        testing[provider] = true; results[provider] = nil
        Task {
            if let r = await appState.testKey(provider: provider) {
                testing[provider] = false
                results[provider] = r.ok == true ? "OK" : (r.error ?? "Failed")
            } else { testing[provider] = false; results[provider] = "Error" }
        }
    }

    private func save(keyName: String) {
        Task {
            var k = AstaKeysIn()
            applyKey(keyName: keyName, value: newKeys[keyName] ?? "", to: &k)
            await appState.setKeys(k)
            newKeys.removeValue(forKey: keyName)
        }
    }

    private func saveAll() {
        Task {
            var k = AstaKeysIn()
            for (key, value) in newKeys where !value.isEmpty { applyKey(keyName: key, value: value, to: &k) }
            await appState.setKeys(k); newKeys.removeAll()
        }
    }

    private func applyKey(keyName: String, value: String, to k: inout AstaKeysIn) {
        guard !value.isEmpty else { return }
        switch keyName {
        case "anthropic_api_key":  k.anthropic_api_key  = value
        case "openrouter_api_key": k.openrouter_api_key = value
        case "openai_api_key":     k.openai_api_key     = value
        case "gemini_api_key":     k.gemini_api_key     = value
        case "huggingface_api_key": k.huggingface_api_key = value
        case "groq_api_key":       k.groq_api_key       = value
        case "telegram_bot_token": k.telegram_bot_token = value
        case "notion_api_key":     k.notion_api_key = value
        case "giphy_api_key":      k.giphy_api_key  = value
        default: break
        }
    }
}

// MARK: - Spotify (separate tab — needs two keys + OAuth flow)

struct SpotifySettingsTab: View {
    @ObservedObject var appState: AppState
    @State private var clientId = ""
    @State private var clientSecret = ""
    @State private var saving = false
    @State private var msg: String?
    @State private var polling = false
    @State private var pollTimer: Timer?

    private var keysSet: Bool {
        appState.keysStatus?["spotify_client_id"] == true && appState.keysStatus?["spotify_client_secret"] == true
    }

    var body: some View {
        Form {
            Section {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Spotify Integration")
                            .font(.system(size: 13, weight: .semibold))
                        Text("Lets Asta play music, get playback info, and control Spotify.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    HStack(spacing: 5) {
                        Circle().fill(appState.spotifyConnected ? Color.green : (keysSet ? Color.orange : Color.gray.opacity(0.5))).frame(width: 7, height: 7)
                        Text(appState.spotifyConnected ? "Connected" : (keysSet ? "Keys set" : "Not set"))
                            .font(.caption).foregroundStyle(appState.spotifyConnected ? .green : (keysSet ? .orange : .secondary))
                    }
                }
            }

            // State 1: Keys not set — show setup instructions + credential fields
            if !keysSet {
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("How to get Spotify credentials:").font(.caption.weight(.semibold))
                        Text("1. Go to developer.spotify.com/dashboard").font(.caption).foregroundStyle(.secondary)
                        Text("2. Log in and click Create App").font(.caption).foregroundStyle(.secondary)
                        Text("3. Copy the Client ID and Client Secret below").font(.caption).foregroundStyle(.secondary)
                        Text("4. In the app settings, add this Redirect URI:").font(.caption).foregroundStyle(.secondary)
                        Text("   http://localhost:8010/spotify/callback").font(.system(.caption, design: .monospaced)).foregroundStyle(.secondary).textSelection(.enabled)
                    }
                    .padding(.vertical, 4)
                    Link("Open Spotify Developer Dashboard →", destination: URL(string: "https://developer.spotify.com/dashboard")!)
                        .font(.caption)
                } header: { Text("Setup instructions") }
            }

            // Credential fields (always available for updating)
            Section {
                SecureField(keysSet ? "Replace Client ID…" : "Client ID", text: $clientId)
                    .font(.system(.body, design: .monospaced))
                SecureField(keysSet ? "Replace Client Secret…" : "Client Secret", text: $clientSecret)
                    .font(.system(.body, design: .monospaced))
                HStack {
                    if let m = msg {
                        Text(m).font(.caption).foregroundStyle(m.contains("aved") ? .green : .red)
                    }
                    Spacer()
                    Button(saving ? "Saving…" : "Save Spotify keys") {
                        saving = true; msg = nil
                        Task {
                            var k = AstaKeysIn()
                            if !clientId.isEmpty     { k.spotify_client_id     = clientId }
                            if !clientSecret.isEmpty { k.spotify_client_secret = clientSecret }
                            await appState.setKeys(k)
                            msg = appState.error ?? "Saved!"
                            clientId = ""; clientSecret = ""; saving = false
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled((clientId.isEmpty && clientSecret.isEmpty) || saving)
                }
            } header: { Text("Credentials") }

            // State 2: Keys set but not connected — show Connect button
            if keysSet && !appState.spotifyConnected {
                Section {
                    Text("Click Connect to open Spotify login in your browser. Asta will detect the connection automatically.")
                        .font(.caption).foregroundStyle(.secondary)
                    HStack {
                        Button("Connect to Spotify") {
                            appState.connectSpotify()
                            startPolling()
                        }
                        .buttonStyle(.borderedProminent)
                        if polling {
                            ProgressView().controlSize(.small).padding(.leading, 8)
                            Text("Waiting for Spotify…").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                } header: { Text("Authentication") }
            }

            // State 3: Connected — show status + devices
            if appState.spotifyConnected {
                Section {
                    Label("Connected to Spotify", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green).font(.subheadline)
                } header: { Text("Status") }

                Section {
                    if appState.spotifyDevices.isEmpty {
                        Text("No active devices found. Open Spotify on a device to see it here.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    ForEach(appState.spotifyDevices) { device in
                        HStack(spacing: 10) {
                            Image(systemName: deviceIcon(device.type))
                                .foregroundStyle(device.is_active == true ? .green : .secondary)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(device.name ?? device.id).font(.system(size: 13, weight: .medium))
                                Text(device.type ?? "unknown").font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if device.is_active == true {
                                Text("Active").font(.caption).foregroundStyle(.green)
                            }
                        }
                    }
                    Button("Refresh devices") {
                        Task { await appState.loadSpotifyStatus() }
                    }.buttonStyle(.bordered).controlSize(.small)
                } header: { Text("Devices") }

                Section {
                    Button(role: .destructive) {
                        Task {
                            await appState.disconnectSpotify()
                        }
                    } label: {
                        Label("Disconnect Spotify", systemImage: "minus.circle")
                    }
                    Text("Removes stored tokens. You can reconnect anytime.")
                        .font(.caption).foregroundStyle(.secondary)
                } header: { Text("Manage") }
            }
        }
        .formStyle(.grouped)
        .task { await appState.loadSpotifyStatus() }
        .onDisappear { stopPolling() }
    }

    private func deviceIcon(_ type: String?) -> String {
        switch type?.lowercased() {
        case "computer":    return "laptopcomputer"
        case "smartphone":  return "iphone"
        case "speaker":     return "hifispeaker"
        default:            return "speaker.wave.2"
        }
    }

    private func startPolling() {
        polling = true
        pollTimer?.invalidate()
        pollTimer = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { _ in
            Task { @MainActor in
                await appState.loadSpotifyStatus()
                if appState.spotifyConnected { stopPolling() }
            }
        }
    }

    private func stopPolling() {
        pollTimer?.invalidate(); pollTimer = nil; polling = false
    }
}

// MARK: - Skills

struct SkillsSettingsTab: View {
    @ObservedObject var appState: AppState
    @State private var uploadMsg: String?
    @State private var uploading = false

    var body: some View {
        Form {
            Section {
                let availableSkills = appState.skillsList.filter { $0.available != false }
                if availableSkills.isEmpty && !appState.panelLoading {
                    Text("No skills loaded. Skills extend what Asta can do — upload a ZIP below.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                ForEach(availableSkills, id: \.id) { skill in
                    Toggle(isOn: Binding(
                        get: { skill.enabled ?? true },
                        set: { new in Task { await appState.setSkillEnabled(skillId: skill.id, enabled: new) } }
                    )) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(skill.name ?? skill.id)
                            if let d = skill.description, !d.isEmpty {
                                Text(d).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                            }
                        }
                    }
                }
                if appState.panelLoading && appState.skillsList.isEmpty {
                    ProgressView().frame(maxWidth: .infinity)
                }
            } header: { Text("Installed skills") }

            let unavailableSkills = appState.skillsList.filter { $0.available == false }
            if !unavailableSkills.isEmpty {
                Section {
                    ForEach(unavailableSkills, id: \.id) { skill in
                        HStack(spacing: 10) {
                            Image(systemName: "exclamationmark.circle").foregroundStyle(.orange).font(.system(size: 13))
                            VStack(alignment: .leading, spacing: 2) {
                                Text(skill.name ?? skill.id).font(.system(size: 13))
                                if let hint = skill.action_hint {
                                    Text(hint).font(.caption).foregroundStyle(.orange).lineLimit(2)
                                }
                            }
                        }
                        .opacity(0.7)
                    }
                } header: { Text("Needs setup") }
            }

            Section {
                Text("Skills are ZIP files containing a SKILL.md and optional scripts. They teach Asta new tools.")
                    .font(.caption).foregroundStyle(.secondary)
                Button("Upload skill ZIP…") {
                    uploadMsg = nil
                    let p = NSOpenPanel()
                    p.allowedContentTypes = [.zip]
                    p.begin { r in
                        guard r == .OK, let url = p.url else { return }
                        uploading = true
                        Task {
                            let ok = await appState.uploadSkillZip(fileURL: url)
                            uploadMsg = ok ? "✓ Uploaded. Restart backend if needed." : (appState.error ?? "Upload failed.")
                            uploading = false
                        }
                    }
                }
                .disabled(uploading)
                if let m = uploadMsg {
                    Text(m).font(.caption).foregroundStyle(m.hasPrefix("✓") ? .green : .red)
                }
            } header: { Text("Upload new skill") }
        }
        .formStyle(.grouped)
    }
}

// MARK: - Knowledge (RAG / Learning)

struct KnowledgeSettingsTab: View {
    @ObservedObject var appState: AppState
    @State private var deleting: String?

    var body: some View {
        Form {
            // Status
            Section {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Knowledge Base")
                            .font(.system(size: 13, weight: .semibold))
                        Text("Asta can learn from documents and conversations using RAG (Retrieval-Augmented Generation).")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    HStack(spacing: 5) {
                        Circle().fill(appState.ragStatus?.ok == true ? Color.green : Color.orange).frame(width: 7, height: 7)
                        Text(appState.ragStatus?.ok == true ? "Active" : "Inactive")
                            .font(.caption).foregroundStyle(appState.ragStatus?.ok == true ? .green : .orange)
                    }
                }
                if let provider = appState.ragStatus?.provider, !provider.isEmpty {
                    HStack {
                        Text("Embedding provider").font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        Text(provider).font(.caption)
                    }
                }
                if appState.ragStatus?.store_error == true, let detail = appState.ragStatus?.detail {
                    Label(detail, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption).foregroundStyle(.orange)
                }
            } header: { Text("Status") }

            // Memory Health
            if let mem = appState.memoryHealth {
                Section {
                    HStack { Text("Vector count").font(.caption).foregroundStyle(.secondary); Spacer(); Text("\(mem.vector_count ?? 0)").font(.caption) }
                    HStack { Text("Chunk count").font(.caption).foregroundStyle(.secondary); Spacer(); Text("\(mem.chunk_count ?? 0)").font(.caption) }
                    if let size = mem.store_size_mb {
                        HStack { Text("Store size").font(.caption).foregroundStyle(.secondary); Spacer(); Text(String(format: "%.1f MB", size)).font(.caption) }
                    }
                    if let err = mem.error, !err.isEmpty {
                        Label(err, systemImage: "exclamationmark.triangle").font(.caption).foregroundStyle(.red)
                    }
                } header: { Text("Memory Health") }
            }

            // Learned Topics
            Section {
                if appState.ragTopics.isEmpty {
                    Text("No learned topics yet. Use learning mode in chat to teach Asta new information.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                ForEach(appState.ragTopics, id: \.topic) { topic in
                    HStack(spacing: 10) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(topic.topic ?? "Unknown").font(.system(size: 13, weight: .medium))
                            Text("\(topic.chunks_count ?? 0) chunks").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if deleting == topic.topic {
                            ProgressView().controlSize(.small)
                        } else {
                            Button(role: .destructive) {
                                guard let name = topic.topic else { return }
                                deleting = name
                                Task {
                                    await appState.deleteRagTopic(topic: name)
                                    deleting = nil
                                }
                            } label: {
                                Image(systemName: "trash").font(.caption)
                            }
                            .buttonStyle(.borderless)
                        }
                    }
                }
            } header: { Text("Learned Topics") }

            // Usage instructions
            Section {
                VStack(alignment: .leading, spacing: 6) {
                    Text("How to use learning mode:").font(.caption.weight(.semibold))
                    Text("1. Toggle learning mode on in the chat toolbar").font(.caption).foregroundStyle(.secondary)
                    Text("2. Send a message — Asta will save it to memory").font(.caption).foregroundStyle(.secondary)
                    Text("3. Toggle learning mode off to return to normal chat").font(.caption).foregroundStyle(.secondary)
                    Text("Asta will automatically retrieve relevant knowledge when answering questions.").font(.caption).foregroundStyle(.secondary)
                }
                .padding(.vertical, 4)
            } header: { Text("Usage") }
        }
        .formStyle(.grouped)
    }
}

// MARK: - Channels (Telegram, Pingram)

struct ChannelsSettingsTab: View {
    @ObservedObject var appState: AppState

    @State private var telegramUsername = ""
    @State private var telegramToken = ""
    @State private var pingramClientId = ""
    @State private var pingramClientSecret = ""
    @State private var pingramApiKey = ""
    @State private var pingramNotificationId = "cron_alert"
    @State private var pingramPhone = ""
    @State private var pingramMsg: String?

    private var telegramSet: Bool { appState.keysStatus?["telegram_bot_token"] == true }

    var body: some View {
        Form {
            // ── Telegram ──────────────────────────────────────────────────
            Section {
                HStack(spacing: 10) {
                    ProviderLogo(provider: "telegram", size: 32)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Telegram Bot")
                            .font(.system(size: 13, weight: .semibold))
                        Text("Chat with Asta from your phone via a Telegram bot.").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    statusDot(telegramSet)
                }
                TextField("Your Telegram username (e.g. @you)", text: $telegramUsername)
                    .onSubmit { Task { await appState.setTelegramUsername(telegramUsername) } }
                SecureField(telegramSet ? "Replace bot token…" : "Bot token from @BotFather", text: $telegramToken)
                    .font(.system(.body, design: .monospaced))
                HStack {
                    Link("Create bot via @BotFather →", destination: URL(string: "https://t.me/BotFather")!).font(.caption)
                    Spacer()
                    if !telegramToken.isEmpty {
                        Button("Save token") {
                            Task {
                                var k = AstaKeysIn()
                                k.telegram_bot_token = telegramToken
                                await appState.setKeys(k)
                                telegramToken = ""
                            }
                        }.buttonStyle(.borderedProminent).controlSize(.small)
                    }
                    if !telegramUsername.isEmpty {
                        Button("Save username") {
                            Task { await appState.setTelegramUsername(telegramUsername) }
                        }.buttonStyle(.bordered).controlSize(.small)
                    }
                }
                Text("Commands the bot supports: /start, /status, /exec_mode, /thinking, /reasoning")
                    .font(.caption2).foregroundStyle(.secondary)
            } header: { Text("Telegram") }

            // ── Voice calls (Pingram / NotificationAPI) ───────────────────
            Section {
                HStack(spacing: 10) {
                    ProviderLogo(provider: "pingram", size: 32)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Voice Calls (Pingram)")
                            .font(.system(size: 13, weight: .semibold))
                        Text("Asta can call your phone via NotificationAPI when reminders fire.").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    statusDot((appState.pingramSettings?.client_id ?? "").isEmpty == false && appState.pingramSettings?.is_secret_set == true)
                }
                TextField("Your phone number (E.164 format, e.g. +1234567890)", text: $pingramPhone)
                TextField("Client ID (from NotificationAPI dashboard)", text: $pingramClientId)
                SecureField(appState.pingramSettings?.is_secret_set == true ? "Replace Client Secret…" : "Client Secret", text: $pingramClientSecret)
                SecureField(appState.pingramSettings?.api_key_set == true ? "API Key (optional, set)" : "API Key (optional)", text: $pingramApiKey)
                TextField("Notification ID (default: cron_alert)", text: $pingramNotificationId)
                HStack {
                    Link("NotificationAPI dashboard →", destination: URL(string: "https://app.notificationapi.com")!).font(.caption)
                    Spacer()
                    if let m = pingramMsg { Text(m).font(.caption).foregroundStyle(.secondary) }
                    Button("Save") {
                        Task {
                            await appState.setPingram(
                                notificationId: pingramNotificationId,
                                clientId: pingramClientId.isEmpty ? nil : pingramClientId,
                                clientSecret: pingramClientSecret.isEmpty ? nil : pingramClientSecret,
                                apiKey: pingramApiKey.isEmpty ? nil : pingramApiKey,
                                templateId: nil,
                                phoneNumber: pingramPhone.isEmpty ? nil : pingramPhone
                            )
                            pingramMsg = appState.error ?? "Saved."
                            pingramClientSecret = ""; pingramApiKey = ""
                        }
                    }.buttonStyle(.borderedProminent).controlSize(.small)
                    Button("Test call") {
                        let num = pingramPhone.isEmpty ? (appState.pingramSettings?.phone_number ?? "") : pingramPhone
                        guard !num.isEmpty else { pingramMsg = "Set a phone number first."; return }
                        Task {
                            let ok = await appState.pingramTestCall(testNumber: num)
                            pingramMsg = ok ? "Test call triggered!" : (appState.error ?? "Failed.")
                        }
                    }.buttonStyle(.bordered).controlSize(.small)
                }
            } header: { Text("Voice Calls (Pingram)") }
        }
        .formStyle(.grouped)
        .onAppear {
            telegramUsername = appState.telegramUsername?.username ?? ""
            if let pg = appState.pingramSettings {
                pingramClientId = pg.client_id ?? ""
                pingramNotificationId = pg.notification_id ?? "cron_alert"
                pingramPhone = pg.phone_number ?? ""
            }
        }
    }

    private func statusDot(_ connected: Bool) -> some View {
        HStack(spacing: 5) {
            Circle().fill(connected ? Color.green : Color.gray.opacity(0.5)).frame(width: 7, height: 7)
            Text(connected ? "Connected" : "Not set").font(.caption).foregroundStyle(connected ? .green : .secondary)
        }
    }
}

// MARK: - Schedule / Cron

struct CronSettingsTab: View {
    @ObservedObject var appState: AppState
    @State private var editJob: AstaCronJob?
    @State private var showEdit = false
    @State private var showAdd = false

    var body: some View {
        Form {
            Section {
                if appState.cronJobs.isEmpty {
                    Text("No scheduled jobs. Click + to add one.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                ForEach(Array(appState.cronJobs.enumerated()), id: \.offset) { _, job in
                    if let id = job.id, let name = job.name {
                        HStack(spacing: 12) {
                            Toggle("", isOn: Binding(
                                get: { job.enabled ?? true },
                                set: { new in Task { await appState.cronUpdate(jobId: id, name: nil, cronExpr: nil, message: nil, tz: nil, enabled: new, channel: nil, channelTarget: nil, payloadKind: nil, tlgCall: nil) } }
                            ))
                            .labelsHidden()
                            .toggleStyle(.switch)
                            .controlSize(.small)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(name).font(.system(size: 13, weight: .medium))
                                Text("\(job.cron_expr ?? "?") · \(job.message ?? "")")
                                    .font(.caption).foregroundStyle(.secondary).lineLimit(1)
                                Text(job.channel ?? "web").font(.caption2).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Button("Edit") { editJob = job; showEdit = true }.controlSize(.small)
                            Button("Delete", role: .destructive) { Task { await appState.cronDelete(jobId: id) } }.controlSize(.small)
                        }
                        .padding(.vertical, 2)
                    }
                }
            } header: {
                HStack {
                    Text("Scheduled jobs")
                    Spacer()
                    Button { showAdd = true } label: {
                        Image(systemName: "plus").font(.system(size: 12, weight: .medium))
                    }
                    .buttonStyle(.borderless)
                }
            }
        }
        .formStyle(.grouped)
        .sheet(isPresented: $showEdit) {
            if let job = editJob {
                CronEditSheet(appState: appState, job: job) { editJob = nil; showEdit = false }
            }
        }
        .sheet(isPresented: $showAdd) {
            CronAddSheet(appState: appState) { showAdd = false }
        }
    }
}

// MARK: - Permissions

// MARK: - Google Workspace
struct GoogleWorkspaceSettingsTab: View {
    @State private var gogInstalled: Bool? = nil
    @State private var authAccounts: [String] = []
    @State private var authError: String? = nil
    @State private var isChecking = false
    @State private var showAddInstructions = false

    var body: some View {
        Form {
            Section {
                Text("Connect your Google account so Asta can read Gmail, Calendar, Drive, and Contacts without prompting you every time.")
                    .font(.caption).foregroundStyle(.secondary)
            }

            // Install status
            Section {
                HStack(spacing: 12) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 8).fill(Color.blue.opacity(0.12)).frame(width: 36, height: 36)
                        Image(systemName: "terminal.fill").font(.system(size: 16)).foregroundStyle(.blue)
                    }
                    VStack(alignment: .leading, spacing: 3) {
                        Text("gog CLI").font(.system(size: 13, weight: .semibold))
                        Text("Command-line tool for Google Workspace (Gmail, Calendar, Drive).")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    if let installed = gogInstalled {
                        if installed {
                            Label("Installed", systemImage: "checkmark.circle.fill").font(.caption).foregroundStyle(.green)
                        } else {
                            Button("Install") {
                                NSWorkspace.shared.open(URL(string: "https://gogcli.sh")!)
                            }.buttonStyle(.borderedProminent).controlSize(.small)
                        }
                    } else {
                        ProgressView().scaleEffect(0.7)
                    }
                }
                .padding(.vertical, 4)
                if gogInstalled == false {
                    Text("Install with: brew install gogcli — then restart Asta.")
                        .font(.caption).foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
            } header: { Text("CLI Tool") }

            // Connected accounts
            Section {
                if isChecking {
                    HStack { ProgressView(); Text("Checking…").font(.caption).foregroundStyle(.secondary) }
                } else if let err = authError {
                    HStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                        Text(err).font(.caption).foregroundStyle(.secondary)
                    }
                } else if authAccounts.isEmpty {
                    HStack(spacing: 8) {
                        Image(systemName: "person.crop.circle.badge.xmark").foregroundStyle(.secondary)
                        Text("No Google account connected.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                } else {
                    ForEach(authAccounts, id: \.self) { account in
                        HStack(spacing: 10) {
                            Image(systemName: "person.crop.circle.fill").foregroundStyle(.blue)
                            Text(account).font(.system(size: 13))
                            Spacer()
                            Button("Disconnect") {
                                runGogCommand("gog auth remove --force \(account)") { _ in
                                    Task { await checkStatus() }
                                }
                            }
                            .buttonStyle(.bordered).controlSize(.small)
                            .foregroundStyle(.red)
                        }
                        .padding(.vertical, 2)
                    }
                }

                Button(authAccounts.isEmpty ? "Connect Google Account" : "Add Another Account") {
                    showAddInstructions = true
                }
                .buttonStyle(.borderedProminent)
                .disabled(gogInstalled == false)

            } header: { Text("Connected Accounts") }

            // Permissions info
            Section {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Required macOS permissions for Google Workspace:")
                        .font(.caption.weight(.semibold))
                    permRow(icon: "envelope.fill",  color: .blue,   title: "Automation → Mail",       desc: "Needed if using Gmail via Mail.app automation")
                    permRow(icon: "calendar",         color: .red,    title: "Automation → Calendar",    desc: "Needed if using Calendar.app automation")
                    permRow(icon: "terminal.fill",    color: .green,  title: "Full Disk Access",         desc: "Lets gog CLI read/write files without per-file prompts")
                    Button("Open Privacy & Security") {
                        NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy")!)
                    }.buttonStyle(.bordered).controlSize(.small)
                }
                .padding(.vertical, 4)
            } header: { Text("macOS Permissions") }

            // Refresh
            Section {
                Button("Refresh Status") { Task { await checkStatus() } }
                    .buttonStyle(.bordered)
            }
        }
        .formStyle(.grouped)
        .sheet(isPresented: $showAddInstructions) {
            addAccountSheet
        }
        .task { await checkStatus() }
    }

    @ViewBuilder
    private var addAccountSheet: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text("Connect Google Account").font(.title2.weight(.semibold))
                Spacer()
                Button { showAddInstructions = false } label: {
                    Image(systemName: "xmark.circle.fill").font(.system(size: 18)).foregroundStyle(.secondary)
                }.buttonStyle(.plain)
            }

            Text("Run this in Terminal to authenticate (one time only):")
                .font(.subheadline).foregroundStyle(.secondary)

            VStack(alignment: .leading, spacing: 8) {
                codeBlock("# 1. Point gog at your OAuth credentials (from Google Cloud Console):")
                codeBlock("gog auth credentials /path/to/client_secret.json")
                codeBlock("")
                codeBlock("# 2. Add your account (grants Gmail, Calendar, Drive, Contacts):")
                codeBlock("gog auth add you@gmail.com --services gmail,calendar,drive,contacts")
                codeBlock("")
                codeBlock("# 3. Verify:")
                codeBlock("gog auth list")
            }
            .padding(12)
            .background(Color.primary.opacity(0.06))
            .clipShape(RoundedRectangle(cornerRadius: 8))

            HStack(spacing: 10) {
                Link("Get OAuth Credentials →", destination: URL(string: "https://console.cloud.google.com/apis/credentials")!)
                    .font(.caption)
                Link("gog docs →", destination: URL(string: "https://gogcli.sh")!)
                    .font(.caption)
            }

            Button("Done — Refresh Status") {
                showAddInstructions = false
                Task { await checkStatus() }
            }.buttonStyle(.borderedProminent)
        }
        .padding(28)
        .frame(width: 480)
    }

    @ViewBuilder
    private func permRow(icon: String, color: Color, title: String, desc: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon).foregroundStyle(color).frame(width: 16)
            VStack(alignment: .leading, spacing: 1) {
                Text(title).font(.caption.weight(.semibold))
                Text(desc).font(.caption2).foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private func codeBlock(_ text: String) -> some View {
        Text(text.isEmpty ? " " : text)
            .font(.system(.caption, design: .monospaced))
            .textSelection(.enabled)
            .foregroundStyle(text.hasPrefix("#") ? Color.secondary : Color.primary)
    }

    private func checkStatus() async {
        isChecking = true; authError = nil
        defer { isChecking = false }

        // Check if gog binary is available
        let whichResult = await shellRun("which gog")
        gogInstalled = whichResult.exitCode == 0 && !whichResult.output.isEmpty

        guard gogInstalled == true else { authAccounts = []; return }

        // Get auth list
        let listResult = await shellRun("gog auth list")
        if listResult.exitCode != 0 || listResult.output.isEmpty {
            authAccounts = []
        } else {
            // Parse output — each line is an account email or "email [services]"
            let lines = listResult.output.components(separatedBy: "\n")
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty && !$0.hasPrefix("#") && !$0.lowercased().contains("account") }
            // Extract just the email from lines like "me@gmail.com [gmail,calendar]"
            authAccounts = lines.compactMap { line -> String? in
                let parts = line.components(separatedBy: " ")
                let email = parts.first ?? ""
                return email.contains("@") ? email : nil
            }
        }
    }

    private func runGogCommand(_ cmd: String, completion: @escaping (Bool) -> Void) {
        Task {
            let result = await shellRun(cmd)
            completion(result.exitCode == 0)
        }
    }

    private struct ShellResult { let output: String; let exitCode: Int32 }

    private func shellRun(_ cmd: String) async -> ShellResult {
        await Task.detached(priority: .utility) {
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/bin/zsh")
            proc.arguments = ["-l", "-c", cmd]  // -l = login shell so PATH includes /opt/homebrew/bin
            let pipe = Pipe()
            proc.standardOutput = pipe
            proc.standardError  = pipe
            do {
                try proc.run()
                proc.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                return ShellResult(output: output, exitCode: proc.terminationStatus)
            } catch {
                return ShellResult(output: error.localizedDescription, exitCode: 1)
            }
        }.value
    }
}

// MARK: - Permissions
struct PermissionsSettingsTab: View {
    @State private var accessGranted = AXIsProcessTrusted()
    @State private var fdaGranted     = PermissionsSettingsTab.fullDiskAccessGranted()
    @State private var terminalGranted = false

    var body: some View {
        Form {
            Section {
                Text("Asta needs these permissions to work correctly. Click Grant to open System Settings.")
                    .font(.caption).foregroundStyle(.secondary)
            }

            // Accessibility
            Section {
                PermissionRow(
                    icon: "hand.raised.fill",
                    iconColor: .blue,
                    title: "Accessibility",
                    description: "Required for the global Option+Space hotkey to work from any app.",
                    granted: accessGranted
                ) {
                    Task {
                        _ = await AstaPermissionManager.requestAccessibility(interactive: true)
                        accessGranted = AXIsProcessTrusted()
                    }
                } openSettings: {
                    AstaPermissionManager.openAccessibilitySettings()
                }
            } header: { Text("Hotkey") }

            // Full Disk Access (for file/skill reading)
            Section {
                PermissionRow(
                    icon: "internaldrive.fill",
                    iconColor: .orange,
                    title: "Full Disk Access",
                    description: "Lets skills read files from anywhere on your Mac (documents, downloads, etc.).",
                    granted: fdaGranted
                ) {
                    openPrivacyPane(id: "Privacy_AllFiles")
                } openSettings: {
                    openPrivacyPane(id: "Privacy_AllFiles")
                }
            } header: { Text("File access (for skills)") }

            // Terminal / Automation (for running commands)
            Section {
                PermissionRow(
                    icon: "terminal.fill",
                    iconColor: .green,
                    title: "Automation → Terminal",
                    description: "Needed for skills that run shell commands or scripts on your Mac.",
                    granted: terminalGranted
                ) {
                    openPrivacyPane(id: "Privacy_Automation")
                } openSettings: {
                    openPrivacyPane(id: "Privacy_Automation")
                }
                Text("If Asta prompts for permission when running a command, click OK in the system dialog.")
                    .font(.caption).foregroundStyle(.secondary)
            } header: { Text("Terminal/script execution") }
        }
        .formStyle(.grouped)
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            accessGranted   = AXIsProcessTrusted()
            fdaGranted      = PermissionsSettingsTab.fullDiskAccessGranted()
            terminalGranted = false
        }
    }

    private func openPrivacyPane(id: String) {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?\(id)") {
            NSWorkspace.shared.open(url)
        }
    }

    static func fullDiskAccessGranted() -> Bool {
        let path = "/Library/Application Support"
        return (try? FileManager.default.contentsOfDirectory(atPath: path)) != nil
    }
}

struct PermissionRow: View {
    let icon: String; let iconColor: Color
    let title: String; let description: String
    let granted: Bool
    var grant: () -> Void; var openSettings: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 8).fill(iconColor.opacity(0.15)).frame(width: 36, height: 36)
                Image(systemName: icon).font(.system(size: 16)).foregroundStyle(iconColor)
            }
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.system(size: 13, weight: .semibold))
                Text(description).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            if granted {
                Label("Granted", systemImage: "checkmark.circle.fill").font(.caption).foregroundStyle(.green)
            } else {
                HStack(spacing: 6) {
                    Button("Grant") { grant() }.buttonStyle(.borderedProminent).controlSize(.small)
                    Button("Settings") { openSettings() }.buttonStyle(.bordered).controlSize(.small)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - About

struct AboutSettingsTab: View {
    @ObservedObject var appState: AppState
    @State private var updateMsg: String?
    @State private var checking = false

    private var version: String { appState.status?.version ?? appState.health?.version ?? "—" }

    var body: some View {
        VStack(spacing: 20) {
            Spacer(minLength: 20)
            Image(nsImage: NSApp.applicationIconImage)
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: 80, height: 80)
            VStack(spacing: 6) {
                Text("Asta").font(.title.weight(.bold))
                Text("Version \(version)").font(.subheadline).foregroundStyle(.secondary)
                Text("Created by Tokyo · Built with ❤️").font(.caption).foregroundStyle(.secondary)
            }
            if appState.updateInfo?.update_available == true {
                Button("Update to \(appState.updateInfo?.remote ?? "latest")") { Task { await appState.triggerUpdate() } }
                    .buttonStyle(.borderedProminent).tint(.orange)
            }
            Button(checking ? "Checking…" : "Check for updates") {
                checking = true; updateMsg = nil
                Task {
                    let r = try? await appState.client.checkUpdate()
                    if r?.update_available == true { updateMsg = "Update available: \(r?.remote ?? "")" }
                    else { updateMsg = "You're on the latest version." }
                    checking = false
                }
            }
            .buttonStyle(.bordered).disabled(checking)
            if let m = updateMsg { Text(m).font(.caption).foregroundStyle(.secondary) }
            Spacer()
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 60)
    }
}

// MARK: - Shared helpers

struct BackendURLField: View {
    @ObservedObject var appState: AppState
    @State private var urlText = ""
    @State private var saved = false
    var body: some View {
        HStack {
            TextField("http://localhost:8010", text: $urlText).textFieldStyle(.roundedBorder)
            Button("Save") {
                appState.setBackendURL(urlText); saved = true
                Task { await appState.load() }
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { saved = false }
            }.disabled(urlText.trimmingCharacters(in: .whitespaces).isEmpty)
            if saved { Image(systemName: "checkmark.circle.fill").foregroundStyle(.green) }
        }
        .onAppear { urlText = UserDefaults.standard.string(forKey: "AstaMacApp.backendURL") ?? "" }
    }
}

struct ModelTextField: View {
    let provider: String; var label: String? = nil
    let current: String; @ObservedObject var appState: AppState
    @State private var text = ""
    var body: some View {
        TextField(label ?? provider, text: $text)
            .onSubmit { Task { await appState.setModel(provider: provider, model: text.trimmingCharacters(in: .whitespacesAndNewlines)) } }
            .onAppear { text = current }
    }
}

struct CronAddSheet: View {
    @ObservedObject var appState: AppState
    let onDismiss: () -> Void
    @State private var name = ""; @State private var cronExpr = ""; @State private var message = ""
    @State private var tz = ""; @State private var channel = "web"; @State private var channelTarget = ""
    @State private var payloadKind = "agentturn"; @State private var tlgCall = true
    @State private var saving = false
    var body: some View {
        NavigationStack {
            Form {
                Section("Job") {
                    TextField("Name", text: $name)
                    TextField("Cron expression (e.g. 0 8 * * * = 8am daily)", text: $cronExpr)
                    TextField("Message to send", text: $message)
                    TextField("Timezone (optional, e.g. America/New_York)", text: $tz)
                }
                Section("Delivery") {
                    Picker("Channel", selection: $channel) {
                        Text("Web (in-app)").tag("web")
                        Text("Telegram").tag("telegram")
                    }
                    TextField("Channel target (chat_id for Telegram)", text: $channelTarget)
                    Picker("Mode", selection: $payloadKind) {
                        Text("Call AI (agentturn)").tag("agentturn")
                        Text("Notify only").tag("systemevent")
                    }
                    Toggle("Voice call when triggered", isOn: $tlgCall)
                }
            }
            .formStyle(.grouped)
            .navigationTitle("New Job")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { onDismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        guard !name.isEmpty, !cronExpr.isEmpty, !message.isEmpty else { return }
                        saving = true
                        Task {
                            await appState.cronAdd(name: name, cronExpr: cronExpr, message: message, tz: tz.isEmpty ? nil : tz, channel: channel, channelTarget: channelTarget, payloadKind: payloadKind, tlgCall: tlgCall)
                            saving = false; onDismiss()
                        }
                    }
                    .disabled(saving || name.isEmpty || cronExpr.isEmpty || message.isEmpty)
                }
            }
        }
        .frame(width: 480, height: 460)
    }
}

struct CronEditSheet: View {
    @ObservedObject var appState: AppState
    let job: AstaCronJob; let onDismiss: () -> Void
    @State private var name = ""; @State private var cronExpr = ""; @State private var message = ""
    @State private var tz = ""; @State private var channel = "web"; @State private var channelTarget = ""
    @State private var payloadKind = "agentturn"; @State private var tlgCall = true; @State private var enabled = true
    @State private var saving = false
    var body: some View {
        NavigationStack {
            Form {
                Section("Job") {
                    TextField("Name", text: $name); TextField("Cron expression", text: $cronExpr)
                    TextField("Message", text: $message); TextField("Timezone", text: $tz)
                }
                Section("Delivery") {
                    Picker("Channel", selection: $channel) { Text("Web").tag("web"); Text("Telegram").tag("telegram") }
                    TextField("Channel target", text: $channelTarget)
                    Picker("Mode", selection: $payloadKind) { Text("Call AI").tag("agentturn"); Text("Notify").tag("systemevent") }
                    Toggle("Voice call when triggered", isOn: $tlgCall)
                    Toggle("Enabled", isOn: $enabled)
                }
            }
            .formStyle(.grouped)
            .navigationTitle("Edit job")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { onDismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save") { save() }.disabled(saving) }
            }
            .onAppear {
                name = job.name ?? ""; cronExpr = job.cron_expr ?? ""; message = job.message ?? ""
                tz = job.tz ?? ""; channel = job.channel ?? "web"; channelTarget = job.channel_target ?? ""
                payloadKind = job.payload_kind ?? "agentturn"; tlgCall = job.tlg_call ?? true; enabled = job.enabled ?? true
            }
        }
        .frame(width: 480, height: 500)
    }
    private func save() {
        guard let id = job.id else { return }; saving = true
        Task {
            await appState.cronUpdate(jobId: id, name: name, cronExpr: cronExpr, message: message, tz: tz.isEmpty ? nil : tz, enabled: enabled, channel: channel, channelTarget: channelTarget.isEmpty ? nil : channelTarget, payloadKind: payloadKind, tlgCall: tlgCall)
            saving = false; onDismiss()
        }
    }
}

// MARK: - Connection

struct TailscaleSettingsTab: View {
    @ObservedObject var appState: AppState
    @StateObject private var ts = TailscaleManager.shared
    @State private var tsActionRunning = false
    @State private var serveActionRunning = false
    @State private var copied = false

    private var backendPort: Int {
        let url = UserDefaults.standard.string(forKey: "AstaMacApp.backendURL") ?? "http://localhost:8010"
        if let u = URL(string: url), let port = u.port { return port }
        return 8010
    }

    /// HTTPS link via `tailscale serve` (preferred — actual TLS cert)
    private var httpsLink: String? {
        guard ts.tsServeEnabled, let dns = ts.tsDNSName else { return nil }
        return "https://\(dns)"
    }

    /// Fallback plain HTTP link via Tailscale IP
    private var httpLink: String? {
        guard let ip = ts.tsStatus.ip else { return nil }
        return "http://\(ip):\(backendPort)"
    }

    /// Best available link to show
    private var remoteLink: String? { httpsLink ?? httpLink }

    var body: some View {
        Form {

            // ── 1. Backend URL ─────────────────────────────────────────────
            Section {
                BackendURLField(appState: appState)
                HStack(spacing: 8) {
                    Circle()
                        .fill(appState.connected ? Color.green : Color.red)
                        .frame(width: 7, height: 7)
                    Text(appState.connected ? "Connected" : "Not reachable")
                        .font(.caption).foregroundStyle(.secondary)
                    Spacer()
                    Button("Reconnect") { Task { await appState.load() } }
                        .controlSize(.small).buttonStyle(.bordered)
                }
                Text("Where the backend is running. Default: http://localhost:8010. Use your LAN IP (http://192.168.x.x:8010) to connect from another machine on the same network.")
                    .font(.caption).foregroundStyle(.secondary)
            } header: { Text("Backend") }

            // ── 2. Remote access via Tailscale ────────────────────────────
            Section {
                // Status row
                HStack(spacing: 10) {
                    Image(systemName: tsStatusIcon)
                        .foregroundStyle(tsStatusColor)
                        .font(.system(size: 15))
                    Text(ts.tsStatus.label)
                        .font(.system(size: 13))
                    Spacer()
                    if tsActionRunning {
                        ProgressView().scaleEffect(0.75)
                    } else {
                        tsActionButton
                    }
                }

                // HTTPS tunnel setup — shown when Tailscale is connected
                if ts.tsStatus.isConnected {
                    if ts.tsServeEnabled {
                        // Serve is running — show HTTPS link
                        if let link = httpsLink {
                            linkBox(link: link, badge: "HTTPS")
                        }
                        Button("Disable HTTPS Tunnel") {
                            serveActionRunning = true
                            Task { await ts.teardownServeHTTPS(); serveActionRunning = false }
                        }
                        .buttonStyle(.bordered).controlSize(.small).foregroundStyle(.red)
                        .disabled(serveActionRunning)
                    } else {
                        // Serve not running — offer to set it up
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Enable HTTPS tunnel to access Asta remotely with a secure link.")
                                .font(.caption).foregroundStyle(.secondary)
                            Button(serveActionRunning ? "Setting up…" : "Enable HTTPS Tunnel") {
                                serveActionRunning = true
                                Task { await ts.setupServeHTTPS(port: backendPort); serveActionRunning = false }
                            }
                            .buttonStyle(.borderedProminent).controlSize(.small)
                            .disabled(serveActionRunning)
                        }
                        // Still show the plain HTTP fallback link
                        if let link = httpLink {
                            linkBox(link: link, badge: "HTTP (fallback)")
                        }
                    }
                }

                // Not installed — offer download
                if !ts.tsInstalled {
                    Button("Download Tailscale for Mac") {
                        NSWorkspace.shared.open(URL(string: "https://tailscale.com/download/mac")!)
                    }.buttonStyle(.bordered).controlSize(.small)
                }

                Button("Refresh") { Task { await ts.refreshTailscaleStatus() } }
                    .buttonStyle(.borderless).controlSize(.small)
                    .foregroundStyle(.secondary)

            } header: { Text("Remote Access (Tailscale)") }
              footer: {
                  Text("Enable HTTPS Tunnel on this Mac, then copy the link and set it as the Backend URL on your other device. Both devices must be on the same Tailscale network.")
                      .font(.caption2).foregroundStyle(.secondary)
              }
        }
        .formStyle(.grouped)
        .task { await ts.refreshTailscaleStatus() }
    }

    @ViewBuilder
    private func linkBox(link: String, badge: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text("Your remote link").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                Text(badge)
                    .font(.system(size: 10, weight: .semibold))
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(badge.hasPrefix("HTTPS") ? Color.green.opacity(0.15) : Color.orange.opacity(0.15))
                    .foregroundStyle(badge.hasPrefix("HTTPS") ? Color.green : Color.orange)
                    .clipShape(Capsule())
            }
            HStack(spacing: 8) {
                Text(link)
                    .font(.system(.body, design: .monospaced))
                    .foregroundStyle(.primary)
                    .textSelection(.enabled)
                Spacer()
                Button(copied ? "Copied!" : "Copy") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(link, forType: .string)
                    copied = true
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) { copied = false }
                }
                .buttonStyle(.bordered).controlSize(.small)
                Button("Use here") {
                    appState.setBackendURL(link)
                    Task { await appState.load() }
                }
                .buttonStyle(.bordered).controlSize(.small)
                .help("Set this as the backend URL on this device")
            }
            .padding(10)
            .background(Color.accentColor.opacity(0.07))
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }

    @ViewBuilder private var tsActionButton: some View {
        switch ts.tsStatus {
        case .notInstalled:
            EmptyView()
        case .notLoggedIn:
            Button("Log in") {
                tsActionRunning = true
                Task { await ts.loginTailscale(); tsActionRunning = false }
            }.buttonStyle(.borderedProminent).controlSize(.small)
        case .disconnected:
            Button("Connect") {
                tsActionRunning = true
                Task { await ts.connectTailscale(); tsActionRunning = false }
            }.buttonStyle(.borderedProminent).controlSize(.small)
        case .connecting:
            EmptyView()
        case .connected:
            Button("Disconnect") {
                tsActionRunning = true
                Task { await ts.disconnectTailscale(); tsActionRunning = false }
            }.buttonStyle(.bordered).controlSize(.small).foregroundStyle(.red)
        }
    }

    private var tsStatusColor: Color {
        switch ts.tsStatus {
        case .connected:              return .green
        case .connecting, .notLoggedIn: return .orange
        default:                      return .secondary
        }
    }
    private var tsStatusIcon: String {
        switch ts.tsStatus {
        case .connected:   return "checkmark.circle.fill"
        case .connecting:  return "arrow.triangle.2.circlepath"
        case .notLoggedIn: return "person.crop.circle.badge.exclamationmark"
        case .notInstalled: return "xmark.circle"
        default:           return "circle"
        }
    }
}
