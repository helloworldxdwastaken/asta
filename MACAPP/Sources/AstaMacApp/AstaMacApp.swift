import SwiftUI
import AppKit
import AstaAPIClient

// MARK: - Entry point

@main
struct AstaMacApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @StateObject private var appState = AppState()
    @AppStorage("AstaMacApp.hasCompletedSetup") private var hasCompletedSetup = false
    @State private var showSetup = false

    var body: some Scene {
        let _ = {
            AppDelegate.sharedAppState = appState
            MainWindowController.shared.appState = appState
        }()

        WindowGroup(id: "main") {
            ContentView(appState: appState)
                .onAppear {
                    // Show setup only on first launch, never again
                    if !hasCompletedSetup {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                            showSetup = true
                        }
                    }
                }
                .sheet(isPresented: $showSetup) {
                    SetupWelcomeView(appState: appState) {
                        hasCompletedSetup = true
                        showSetup = false
                    }
                    .frame(width: 480, height: 500)
                }
        }
        .defaultSize(width: 960, height: 680)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}

// MARK: - AppState

@MainActor
final class AppState: ObservableObject {
    @Published var client = AstaAPIClient(baseURL: AppState.savedBaseURL())

    static func savedBaseURL() -> URL? {
        guard let str = UserDefaults.standard.string(forKey: "AstaMacApp.backendURL"),
              !str.isEmpty, let url = URL(string: str) else { return nil }
        return url
    }

    func setBackendURL(_ urlString: String) {
        let trimmed = urlString.trimmingCharacters(in: .whitespacesAndNewlines)
        UserDefaults.standard.set(trimmed, forKey: "AstaMacApp.backendURL")
        client = AstaAPIClient(baseURL: trimmed.isEmpty ? nil : URL(string: trimmed))
    }

    @Published var status: AstaStatus?
    @Published var health: AstaHealth?
    @Published var defaultAI: AstaDefaultAI?
    @Published var thinking: AstaThinking?
    @Published var reasoning: AstaReasoning?
    @Published var providerFlow: AstaProviderFlow?
    @Published var providers: [String] = []
    @Published var serverStatus: AstaServerStatus?
    @Published var error: String?
    @Published var loading = false
    @Published var selectedProvider: String = ""
    @Published var selectedThinking: String = "off"
    @Published var selectedReasoning: String = "off"
    @Published var selectedMood: String = "normal"
    @Published var finalMode: AstaFinalMode?
    @Published var selectedFinalMode: String = "off"
    @Published var vision: AstaVision?
    @Published var fallback: AstaFallback?
    @Published var modelsResponse: AstaModelsResponse?
    @Published var availableModels: AstaAvailableModels?
    @Published var keysStatus: [String: Bool]?
    @Published var skillsList: [AstaSkillItem] = []
    @Published var telegramUsername: AstaTelegramUsername?
    @Published var pingramSettings: AstaPingramSettings?
    @Published var spotifyConnected: Bool = false
    @Published var spotifyDevices: [AstaSpotifyDevice] = []
    @Published var cronJobs: [AstaCronJob] = []
    @Published var notificationsList: [AstaNotification] = []
    @Published var panelLoading = false
    @Published var updateInfo: AstaCheckUpdate?
    @Published var workspaceNotes: [AstaWorkspaceNote] = []
    @Published var ragStatus: AstaRagStatus?
    @Published var ragTopics: [AstaRagTopic] = []
    @Published var securityAudit: AstaSecurityAudit?
    @Published var memoryHealth: AstaMemoryHealth?
    @Published var agentsList: [AstaAgent] = []
    @Published var agentsLoading = false
    @Published var agentsError: String?
    
    // Learning Mode - when enabled, the next message will be saved to memory
    @Published var learningModeEnabled = false

    var connected: Bool { health?.status == "ok" }

    // MARK: - Tailscale / tunnel
    let tailscale = TailscaleManager.shared

    func load() async {
        loading = true; error = nil
        defer { loading = false }

        // Use the configured backend URL directly
        let primaryStr = UserDefaults.standard.string(forKey: "AstaMacApp.backendURL") ?? "http://localhost:8010"
        if let url = URL(string: primaryStr), url.absoluteString != client.baseURL.absoluteString {
            client = AstaAPIClient(baseURL: url)
        }

        do {
            async let h  = client.health()
            async let s  = client.status()
            async let d  = client.defaultAI()
            async let t  = client.thinking()
            async let r  = client.reasoning()
            async let mo = client.mood()
            async let p  = client.providers()
            async let pf = client.providerFlow()
            async let m  = client.models()
            health         = try await h
            status         = try await s
            defaultAI      = try await d
            thinking       = try await t
            reasoning      = try await r
            providers      = try await p
            providerFlow   = try await pf
            modelsResponse = try? await m
            serverStatus   = try? await client.serverStatus()
            if let p = defaultAI?.provider, !p.isEmpty { selectedProvider = p }
            if let l = thinking?.level,    !l.isEmpty  { selectedThinking  = l }
            if let m = reasoning?.reasoning_mode, !m.isEmpty { selectedReasoning = m }
            if let mood = try? await mo, let v = mood.mood, !v.isEmpty { selectedMood = v }
        } catch { self.error = error.localizedDescription }
    }

    func loadSettings() async {
        panelLoading = true; error = nil
        defer { panelLoading = false }
        if health == nil || defaultAI == nil { await load() }
        async let visionF      = client.vision()
        async let finalModeF   = client.finalMode()
        async let fallbackF    = client.fallback()
        async let modelsF      = client.models()
        async let availModelsF = client.availableModels()
        async let keysF        = client.keysStatus()
        async let skillsF      = client.skills()
        async let telegramF    = client.telegramUsername()
        async let pingramF     = client.pingram()
        async let spotifyF     = client.spotifyStatus()
        async let cronF        = client.cronList()
        async let notifF       = client.notifications()
        async let updateF      = client.checkUpdate()
        async let notesF       = client.workspaceNotes(limit: 20)
        async let ragStatusF   = client.ragStatus()
        async let ragLearnedF  = client.ragLearned()
        async let securityF    = client.securityAudit()
        async let memoryF      = client.memoryHealth()
        if let v  = try? await visionF    { vision = v }
        if let fm = try? await finalModeF { finalMode = fm; if let m = fm.final_mode, !m.isEmpty { selectedFinalMode = m } }
        if let fb = try? await fallbackF  { fallback = fb }
        if let m  = try? await modelsF    { modelsResponse = m }
        if let a  = try? await availModelsF { availableModels = a }
        if let k  = try? await keysF      { keysStatus = k }
        if let sk = try? await skillsF    { skillsList = sk.skills ?? [] }
        if let tg = try? await telegramF  { telegramUsername = tg }
        if let pg = try? await pingramF   { pingramSettings = pg }
        if let sp = try? await spotifyF   { spotifyConnected = sp.connected == true }
        if let cr = try? await cronF      { cronJobs = cr.cron_jobs ?? [] }
        if let n  = try? await notifF     { notificationsList = n.notifications ?? [] }
        if let u  = try? await updateF    { updateInfo = u }
        if let no = try? await notesF     { workspaceNotes = no.notes ?? [] }
        if let rg = try? await ragStatusF { ragStatus = rg }
        if let rl = try? await ragLearnedF { ragTopics = rl.topics ?? [] }
        if let sc = try? await securityF  { securityAudit = sc }
        if let me = try? await memoryF    { memoryHealth = me }
        await loadAgents()
    }

    func setDefaultAI(_ provider: String) async {
        do { defaultAI = try await client.setDefaultAI(provider: provider); selectedProvider = provider }
        catch { self.error = error.localizedDescription }
    }
    func setThinking(_ level: String) async {
        do { thinking = try await client.setThinking(level: level); selectedThinking = level }
        catch { self.error = error.localizedDescription }
    }
    func setReasoning(_ mode: String) async {
        do { reasoning = try await client.setReasoning(mode: mode); selectedReasoning = mode }
        catch { self.error = error.localizedDescription }
    }
    func setProviderEnabled(_ provider: String, enabled: Bool) async {
        do { try await client.setProviderEnabled(provider: provider, enabled: enabled); providerFlow = try await client.providerFlow() }
        catch { self.error = error.localizedDescription }
    }
    func setFinalMode(_ mode: String) async {
        do { finalMode = try await client.setFinalMode(mode: mode); selectedFinalMode = mode }
        catch { self.error = error.localizedDescription }
    }
    func setVision(preprocess: Bool, providerOrder: String, openrouterModel: String) async {
        do { vision = try await client.setVision(preprocess: preprocess, providerOrder: providerOrder, openrouterModel: openrouterModel) }
        catch { self.error = error.localizedDescription }
    }
    func setModel(provider: String, model: String) async {
        do { try await client.setModel(provider: provider, model: model); modelsResponse = try await client.models() }
        catch { self.error = error.localizedDescription }
    }
    func setSkillEnabled(skillId: String, enabled: Bool) async {
        do { try await client.setSkillEnabled(skillId: skillId, enabled: enabled); skillsList = (try await client.skills()).skills ?? [] }
        catch { self.error = error.localizedDescription }
    }
    func setTelegramUsername(_ username: String) async {
        do { try await client.setTelegramUsername(username); telegramUsername = try await client.telegramUsername() }
        catch { self.error = error.localizedDescription }
    }
    func setPingram(notificationId: String, clientId: String?, clientSecret: String?, apiKey: String?, templateId: String?, phoneNumber: String?) async {
        do { try await client.setPingram(notificationId: notificationId, clientId: clientId, clientSecret: clientSecret, apiKey: apiKey, templateId: templateId, phoneNumber: phoneNumber); pingramSettings = try await client.pingram() }
        catch { self.error = error.localizedDescription }
    }
    func pingramTestCall(testNumber: String) async -> Bool {
        do { let r = try await client.pingramTestCall(testNumber: testNumber); return r.ok == true }
        catch { self.error = error.localizedDescription; return false }
    }
    func loadSpotifyStatus() async {
        do {
            let s = try await client.spotifyStatus()
            spotifyConnected = s.connected == true
            if spotifyConnected { spotifyDevices = try await client.spotifyDevices() }
            else { spotifyDevices = [] }
        } catch { self.error = error.localizedDescription }
    }
    func connectSpotify() {
        let url = client.spotifyConnectURL()
        NSWorkspace.shared.open(url)
    }
    func cronAdd(name: String, cronExpr: String, message: String, tz: String?, channel: String, channelTarget: String, payloadKind: String, tlgCall: Bool) async {
        do { _ = try await client.cronAdd(name: name, cronExpr: cronExpr, message: message, tz: tz, channel: channel, channelTarget: channelTarget, payloadKind: payloadKind, tlgCall: tlgCall); cronJobs = (try await client.cronList()).cron_jobs ?? [] }
        catch { self.error = error.localizedDescription }
    }
    func cronUpdate(jobId: Int, name: String?, cronExpr: String?, message: String?, tz: String?, enabled: Bool?, channel: String?, channelTarget: String?, payloadKind: String?, tlgCall: Bool?) async {
        do { try await client.cronUpdate(jobId: jobId, name: name, cronExpr: cronExpr, message: message, tz: tz, enabled: enabled, channel: channel, channelTarget: channelTarget, payloadKind: payloadKind, tlgCall: tlgCall); cronJobs = (try await client.cronList()).cron_jobs ?? [] }
        catch { self.error = error.localizedDescription }
    }
    func cronDelete(jobId: Int) async {
        do { try await client.cronDelete(jobId: jobId); cronJobs = cronJobs.filter { $0.id != jobId } }
        catch { self.error = error.localizedDescription }
    }
    func deleteNotification(id: String) async {
        do { try await client.deleteNotification(id: id); notificationsList.removeAll { $0.id == id } }
        catch { self.error = error.localizedDescription }
    }
    func deleteRagTopic(topic: String) async {
        do { _ = try await client.ragDeleteTopic(topic: topic); ragTopics = (try await client.ragLearned()).topics ?? [] }
        catch { self.error = error.localizedDescription }
    }
    func refreshKeysStatus() async {
        do { keysStatus = try await client.keysStatus() }
        catch { self.error = error.localizedDescription }
    }
    func triggerUpdate() async {
        do { _ = try await client.triggerUpdate(); updateInfo = nil; error = nil }
        catch { self.error = error.localizedDescription }
    }
    func restartBackend() async {
        do { _ = try await client.restartBackend(); error = nil }
        catch { self.error = error.localizedDescription }
    }
    func refreshServerStatus() async throws {
        serverStatus = try await client.serverStatus()
    }
    func uploadSkillZip(fileURL: URL) async -> Bool {
        do {
            let r = try await client.uploadSkillZip(fileURL: fileURL)
            if r.ok == true { skillsList = (try await client.skills()).skills ?? []; return true }
            self.error = "Upload failed"; return false
        } catch { self.error = error.localizedDescription; return false }
    }
    func setKeys(_ keys: AstaKeysIn) async {
        do { try await client.setKeys(keys); keysStatus = try await client.keysStatus() }
        catch { self.error = error.localizedDescription }
    }
    func testKey(provider: String) async -> AstaTestKeyResult? {
        do { return try await client.testKey(provider: provider) }
        catch { self.error = error.localizedDescription; return nil }
    }
    func setMood(_ mood: String) async {
        do { _ = try await client.setMood(mood); selectedMood = mood }
        catch { self.error = error.localizedDescription }
    }

    // MARK: - Agents
    func loadAgents() async {
        agentsLoading = true; agentsError = nil
        defer { agentsLoading = false }
        do { agentsList = try await client.agentsList().agents }
        catch { agentsError = error.localizedDescription }
    }
    func createAgent(name: String, description: String, emoji: String, model: String, thinking: String, systemPrompt: String) async {
        do {
            let r = try await client.agentCreate(name: name, description: description, emoji: emoji, model: model, thinking: thinking, systemPrompt: systemPrompt)
            agentsList.append(r.agent)
        } catch { agentsError = error.localizedDescription }
    }
    func updateAgent(id: String, name: String, description: String, emoji: String, model: String, thinking: String, systemPrompt: String) async {
        do {
            let r = try await client.agentUpdate(id: id, name: name, description: description, emoji: emoji, model: model, thinking: thinking, systemPrompt: systemPrompt)
            if let idx = agentsList.firstIndex(where: { $0.id == id }) { agentsList[idx] = r.agent }
        } catch { agentsError = error.localizedDescription }
    }
    func deleteAgent(id: String) async {
        do { try await client.agentDelete(id: id); agentsList.removeAll { $0.id == id } }
        catch { agentsError = error.localizedDescription }
    }
}

// MARK: - Global helpers

func astaProviderDisplayName(_ id: String) -> String {
    switch id.lowercased() {
    case "claude":      return "Claude"
    case "ollama":      return "Ollama (local)"
    case "openrouter":  return "OpenRouter"
    case "openai":      return "OpenAI"
    case "google":      return "Google (Gemini)"
    case "groq":        return "Groq"
    default:            return id
    }
}

// MARK: - First-run setup (modal sheet, not a separate window)

struct SetupWelcomeView: View {
    @ObservedObject var appState: AppState
    var onComplete: () -> Void

    @State private var step = 0
    @State private var checking = true
    @State private var detectedInstall: AstaInstaller.DetectionResult?
    @State private var settingUp = false
    @State private var apiKeyInput = ""
    @State private var onboardingURL = ""

    private var isDefaultLocalURL: Bool {
        let u = onboardingURL.trimmingCharacters(in: .whitespaces)
        return u.isEmpty || u == "http://localhost:8010" || u == "http://127.0.0.1:8010"
    }

    private func saveOnboardingURL() {
        let url = onboardingURL.trimmingCharacters(in: .whitespaces)
        guard !url.isEmpty, URL(string: url) != nil else { return }
        UserDefaults.standard.set(url, forKey: "AstaMacApp.backendURL")
        checking = true
        Task { await appState.load(); checking = false }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Progress dots
            HStack(spacing: 8) {
                ForEach(0..<4, id: \.self) { i in
                    Capsule()
                        .fill(i == step ? Color.accentColor : (i < step ? Color.accentColor.opacity(0.4) : Color.primary.opacity(0.12)))
                        .frame(width: i == step ? 20 : 8, height: 8)
                        .animation(.spring(response: 0.3), value: step)
                }
            }
            .padding(.top, 28).padding(.bottom, 24)

            // Step content
            Group {
                switch step {
                case 0: welcomeStep
                case 1: backendStep
                case 2: apiKeyStep
                default: readyStep
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .animation(.easeOut(duration: 0.2), value: step)

            Divider().padding(.top, 20)

            // Nav buttons
            HStack {
                if step > 0 && step < 3 {
                    Button("Back") { withAnimation { step -= 1 } }.buttonStyle(.bordered)
                }
                Spacer()
                if step == 1 && !appState.connected {
                    Button("Retry") {
                        checking = true
                        Task { await appState.load(); checking = false }
                    }.buttonStyle(.bordered)
                }
                Button(step == 3 ? "Open Asta" : (step == 2 ? "Skip for now" : "Continue")) {
                    if step == 3 { onComplete() }
                    else { withAnimation { step = min(step + 1, 3) } }
                }
                .buttonStyle(.borderedProminent)
                .disabled(step == 1 && !appState.connected && isDefaultLocalURL && !checking)
                if step == 2 && !apiKeyInput.isEmpty {
                    Button("Save & Continue") {
                        Task {
                            var k = AstaKeysIn()
                            if apiKeyInput.hasPrefix("sk-ant") { k.anthropic_api_key = apiKeyInput }
                            else { k.openrouter_api_key = apiKeyInput }
                            await appState.setKeys(k)
                            withAnimation { step = 3 }
                        }
                    }.buttonStyle(.borderedProminent)
                }
            }
            .padding(.horizontal, 28).padding(.vertical, 18)
        }
        .task {
            onboardingURL = UserDefaults.standard.string(forKey: "AstaMacApp.backendURL") ?? "http://localhost:8010"
            detectedInstall = AstaInstaller.detectInstallation()
            await appState.load()
            checking = false
            // Auto-advance past backend step if already connected
            if appState.connected && step == 1 { step = 2 }
        }
    }

    private var welcomeStep: some View {
        VStack(spacing: 16) {
            ZStack {
                Circle().fill(LinearGradient(colors: [Color(red:0.28,green:0.52,blue:0.96), Color(red:0.18,green:0.38,blue:0.86)], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 72, height: 72)
                Text("A").font(.system(size: 30, weight: .bold)).foregroundStyle(.white)
            }
            Text("Welcome to Asta").font(.title.weight(.bold))
            Text("Your personal AI assistant for macOS.\nChat, automate, and connect your tools.")
                .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center).lineSpacing(4)
        }
        .padding(.horizontal, 40)
    }

    private var backendStep: some View {
        VStack(spacing: 16) {
            Image(systemName: "server.rack").font(.system(size: 40)).foregroundStyle(.secondary)
            Text("Connect Backend").font(.title2.weight(.semibold))

            // URL field — always visible so user can enter Tailscale or remote URL
            VStack(alignment: .leading, spacing: 4) {
                Text("Backend URL").font(.caption).foregroundStyle(.secondary)
                HStack(spacing: 6) {
                    TextField("http://localhost:8010", text: $onboardingURL)
                        .textFieldStyle(.roundedBorder)
                        .onSubmit { saveOnboardingURL() }
                    Button("Test") { saveOnboardingURL() }
                        .buttonStyle(.bordered)
                        .disabled(checking)
                }
            }

            if checking {
                ProgressView().padding(.top, 4)
                Text("Checking connection…").font(.caption).foregroundStyle(.secondary)
            } else if appState.connected {
                Label("Backend connected!", systemImage: "checkmark.circle.fill")
                    .font(.headline).foregroundStyle(.green)
                Text("You're good to go.").font(.subheadline).foregroundStyle(.secondary)
            } else {
                VStack(spacing: 12) {
                    if !isDefaultLocalURL {
                        Label("Could not reach that URL. You can still continue and fix the connection later.", systemImage: "exclamationmark.triangle")
                            .font(.caption).foregroundStyle(.orange).multilineTextAlignment(.center)
                    } else {
                        if let install = detectedInstall {
                            Button(settingUp ? "Starting…" : "Start Asta Backend") {
                                settingUp = true
                                Task {
                                    _ = await AstaInstaller.startBackend(at: install.path)
                                    try? await Task.sleep(nanoseconds: 2_500_000_000)
                                    await appState.load()
                                    settingUp = false
                                    if appState.connected { withAnimation { step = 2 } }
                                }
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(settingUp)
                        }
                        Text("Or start manually in Terminal:")
                            .font(.caption).foregroundStyle(.secondary)
                        Text("cd ~/asta && ./asta.sh start")
                            .font(.system(.caption, design: .monospaced))
                            .padding(10).background(Color.primary.opacity(0.07)).cornerRadius(8)
                            .textSelection(.enabled)
                    }
                }
            }
        }
        .padding(.horizontal, 40)
    }

    private var apiKeyStep: some View {
        VStack(spacing: 16) {
            Image(systemName: "key.fill").font(.system(size: 40)).foregroundStyle(Color.accentColor)
            Text("Add an API Key").font(.title2.weight(.semibold))
            Text("Paste a Claude (Anthropic) or OpenRouter key to use cloud AI. You can add more keys in Settings later.")
                .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center).lineSpacing(4)
            SecureField("sk-ant-… or sk-or-…", text: $apiKeyInput)
                .textFieldStyle(.roundedBorder).font(.system(.body, design: .monospaced))
            HStack(spacing: 12) {
                Link("Get Claude key →", destination: URL(string: "https://console.anthropic.com/settings/keys")!)
                    .font(.caption)
                Link("Get OpenRouter key →", destination: URL(string: "https://openrouter.ai/keys")!)
                    .font(.caption)
            }
        }
        .padding(.horizontal, 40)
    }

    private var readyStep: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.seal.fill").font(.system(size: 52)).foregroundStyle(.green)
            Text("You're all set!").font(.title.weight(.bold))
            VStack(spacing: 8) {
                Label("Press ⌘⌥ Space to open Asta anytime", systemImage: "keyboard")
                Label("Click the menu bar icon to show / hide", systemImage: "menubar.rectangle")
                Label("Add more API keys in Settings → Keys", systemImage: "key")
            }
            .font(.subheadline).foregroundStyle(.secondary)
        }
        .padding(.horizontal, 40)
    }
}
