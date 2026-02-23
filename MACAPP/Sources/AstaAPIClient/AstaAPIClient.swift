import Foundation

/// Connects to Asta backend API (default http://localhost:8010).
public struct AstaAPIClient: Sendable {
    public var baseURL: URL
    public var session: URLSession

    public init(
        baseURL: URL? = nil,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL ?? URL(string: ProcessInfo.processInfo.environment["ASTA_BASE_URL"] ?? "http://localhost:8010")!
        self.session = session
    }

    // MARK: - Health

    public func health() async throws -> AstaHealth {
        let url = baseURL.appending(path: "api/health")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaHealth.self, from: data)
    }

    // MARK: - Chat (non-streaming)

    public func chat(
        text: String,
        userID: String = "default",
        conversationID: String? = nil,
        provider: String = "default",
        mood: String? = nil,
        web: Bool = false,
        imageData: Data? = nil,
        imageMime: String? = nil
    ) async throws -> AstaChatOut {
        let url = baseURL.appending(path: "api/chat")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = AstaChatIn(
            text: text, provider: provider, user_id: userID,
            conversation_id: conversationID, mood: mood, web: web,
            image_base64: imageData?.base64EncodedString(), image_mime: imageMime
        )
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            if let errObj = try? JSONDecoder().decode(AstaAPIError.self, from: data),
               let detail = errObj.detail ?? errObj.error {
                throw AstaClientError.backendError(detail)
            }
            throw AstaClientError.httpError(http.statusCode)
        }
        return try JSONDecoder().decode(AstaChatOut.self, from: data)
    }

    // MARK: - Chat (SSE streaming)
    //
    // Backend SSE protocol (handler.py → chat.py):
    //
    //   event: meta        data: {"type":"meta","conversation_id":"...","provider":"..."}
    //   event: assistant   data: {"type":"assistant","text":"cumulative","delta":"new chars"}
    //   event: reasoning   data: {"type":"reasoning","text":"cumulative","delta":"new chars"}
    //   event: status      data: {"type":"status","text":"Running tool…"}
    //   event: done        data: {"type":"done","reply":"full reply","conversation_id":"...","provider":"..."}
    //   event: error       data: {"type":"error","error":"msg","conversation_id":"..."}
    //
    // This client normalises the event names to what ChatView expects:
    //   "assistant" → type "text"    (append chunk.delta to message content)
    //   "reasoning" → type "thinking" (append chunk.delta to thinkingContent)
    //   "status"    → type "status"  (ignored by ChatView)
    //   "done"      → type "done"    (carries full reply for fallback)
    //   "error"     → type "error"
    //
    // IMPORTANT: Use chunk.text (the delta) for appending — NOT cumulative text.
    // AstaStreamChunk.text is populated from the SSE delta field.

    public func chatStream(
        text: String,
        userID: String = "default",
        conversationID: String? = nil,
        provider: String = "default",
        mood: String? = nil,
        web: Bool = false,
        imageData: Data? = nil,
        imageMime: String? = nil
    ) -> AsyncThrowingStream<AstaStreamChunk, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    let url = baseURL.appending(path: "api/chat/stream")
                    var request = URLRequest(url: url)
                    request.httpMethod = "POST"
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    request.timeoutInterval = 120
                    let body = AstaChatIn(
                        text: text, provider: provider, user_id: userID,
                        conversation_id: conversationID, mood: mood, web: web,
                        image_base64: imageData?.base64EncodedString(), image_mime: imageMime
                    )
                    request.httpBody = try JSONEncoder().encode(body)
                    let (bytes, response) = try await session.bytes(for: request)
                    if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
                        continuation.finish(throwing: AstaClientError.httpError(http.statusCode))
                        return
                    }

                    // SSE parser — track the named event type between event:/data: line pairs
                    var currentEventName: String? = nil

                    for try await line in bytes.lines {
                        if line.hasPrefix("event: ") {
                            currentEventName = String(line.dropFirst(7)).trimmingCharacters(in: .whitespaces)
                            continue
                        }
                        if line.isEmpty {
                            // Blank line = end of SSE block; reset event name per spec
                            currentEventName = nil
                            continue
                        }
                        guard line.hasPrefix("data: ") else { continue }

                        let jsonStr = String(line.dropFirst(6))
                        guard let jsonData = jsonStr.data(using: .utf8),
                              let raw = try? JSONDecoder().decode(SSERawPayload.self, from: jsonData)
                        else { continue }

                        // Resolve the type: prefer the named event line, fall back to type field in JSON
                        let eventName = currentEventName ?? raw.type ?? ""

                        // Normalise to what ChatView understands
                        let normalizedType: String
                        switch eventName {
                        case "assistant": normalizedType = "text"
                        case "reasoning": normalizedType = "thinking"
                        case "done":      normalizedType = "done"
                        case "error":     normalizedType = "error"
                        case "status":    normalizedType = "status"
                        case "meta":      continue   // skip — no UI update needed
                        default:          normalizedType = eventName
                        }

                        // For streaming text/thinking, use delta (incremental chars only).
                        // For done/error, use reply or error field.
                        let chunkText: String?
                        switch normalizedType {
                        case "text", "thinking":
                            // delta is the incremental chunk; fall back to full text only if delta missing
                            // (some providers / paths may not send delta separately)
                            chunkText = raw.delta.flatMap { $0.isEmpty ? nil : $0 } ?? raw.text
                        case "error":
                            chunkText = raw.error ?? raw.text
                        default:
                            chunkText = raw.text
                        }

                        let chunk = AstaStreamChunk(
                            type:            normalizedType,
                            text:            chunkText,
                            reply:           raw.reply,
                            conversation_id: raw.conversation_id,
                            provider:        raw.provider
                        )
                        continuation.yield(chunk)
                        if normalizedType == "done" || normalizedType == "error" { break }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    public func conversations(
        userID: String = "default",
        channel: String = "web",
        limit: Int = 50
    ) async throws -> AstaConversationsResponse {
        var components = URLComponents(url: baseURL.appending(path: "api/chat/conversations"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "user_id", value: userID),
            URLQueryItem(name: "channel", value: channel),
            URLQueryItem(name: "limit", value: String(limit)),
        ]
        let (data, _) = try await session.data(from: components.url!)
        return try JSONDecoder().decode(AstaConversationsResponse.self, from: data)
    }

    public func deleteConversation(id: String, userID: String = "default") async throws {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        var components = URLComponents(url: baseURL.appending(path: "api/chat/conversations/\(encoded)"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "user_id", value: userID)]
        var req = URLRequest(url: components.url!)
        req.httpMethod = "DELETE"
        _ = try await session.data(for: req)
    }

    public func chatMessages(
        conversationID: String,
        userID: String = "default",
        limit: Int = 50
    ) async throws -> AstaChatMessages {
        var components = URLComponents(url: baseURL.appending(path: "api/chat/messages"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "conversation_id", value: conversationID),
            URLQueryItem(name: "user_id", value: userID),
            URLQueryItem(name: "limit", value: String(limit)),
        ]
        let (data, _) = try await session.data(from: components.url!)
        return try JSONDecoder().decode(AstaChatMessages.self, from: data)
    }

    // MARK: - Status

    public func status() async throws -> AstaStatus {
        let url = baseURL.appending(path: "api/status")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaStatus.self, from: data)
    }

    public func serverStatus() async throws -> AstaServerStatus {
        let url = baseURL.appending(path: "api/settings/server-status")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaServerStatus.self, from: data)
    }

    // MARK: - Settings (GET)

    public func defaultAI() async throws -> AstaDefaultAI {
        let url = baseURL.appending(path: "api/settings/default-ai")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaDefaultAI.self, from: data)
    }

    public func thinking() async throws -> AstaThinking {
        let url = baseURL.appending(path: "api/settings/thinking")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaThinking.self, from: data)
    }

    public func reasoning() async throws -> AstaReasoning {
        let url = baseURL.appending(path: "api/settings/reasoning")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaReasoning.self, from: data)
    }

    public func mood() async throws -> AstaMood {
        let url = baseURL.appending(path: "api/settings/mood")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaMood.self, from: data)
    }

    public func providers() async throws -> [String] {
        let url = baseURL.appending(path: "api/providers")
        let (data, _) = try await session.data(from: url)
        return (try JSONDecoder().decode(AstaProvidersResponse.self, from: data)).providers ?? []
    }

    public func providerFlow() async throws -> AstaProviderFlow {
        let url = baseURL.appending(path: "api/settings/provider-flow")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaProviderFlow.self, from: data)
    }

    public func finalMode() async throws -> AstaFinalMode {
        let url = baseURL.appending(path: "api/settings/final-mode")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaFinalMode.self, from: data)
    }

    public func vision() async throws -> AstaVision {
        let url = baseURL.appending(path: "api/settings/vision")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaVision.self, from: data)
    }

    public func fallback() async throws -> AstaFallback {
        let url = baseURL.appending(path: "api/settings/fallback")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaFallback.self, from: data)
    }

    public func models() async throws -> AstaModelsResponse {
        let url = baseURL.appending(path: "api/settings/models")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaModelsResponse.self, from: data)
    }

    public func availableModels() async throws -> AstaAvailableModels {
        let url = baseURL.appending(path: "api/settings/available-models")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaAvailableModels.self, from: data)
    }

    /// Returns which API keys are set (key name → true/false).
    public func keysStatus() async throws -> [String: Bool] {
        let url = baseURL.appending(path: "api/settings/keys")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode([String: Bool].self, from: data)
    }

    public func skills() async throws -> AstaSkillsResponse {
        let url = baseURL.appending(path: "api/settings/skills")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaSkillsResponse.self, from: data)
    }

    public func telegramUsername() async throws -> AstaTelegramUsername {
        let url = baseURL.appending(path: "api/settings/telegram/username")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaTelegramUsername.self, from: data)
    }

    public func pingram() async throws -> AstaPingramSettings {
        let url = baseURL.appending(path: "api/settings/pingram")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaPingramSettings.self, from: data)
    }

    public func spotifyStatus(userId: String = "default") async throws -> AstaSpotifyStatus {
        var components = URLComponents(url: baseURL.appending(path: "api/spotify/status"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "user_id", value: userId)]
        let (data, _) = try await session.data(from: components.url!)
        return try JSONDecoder().decode(AstaSpotifyStatus.self, from: data)
    }

    public func spotifyDevices(userId: String = "default") async throws -> [AstaSpotifyDevice] {
        var components = URLComponents(url: baseURL.appending(path: "api/spotify/devices"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "user_id", value: userId)]
        let (data, _) = try await session.data(from: components.url!)
        return (try JSONDecoder().decode(AstaSpotifyDevicesResponse.self, from: data)).devices ?? []
    }

    public func spotifyConnectURL(userId: String = "default") -> URL {
        var components = URLComponents(url: baseURL.appending(path: "spotify/connect"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "user_id", value: userId)]
        return components.url!
    }

    public func cronList() async throws -> AstaCronList {
        let url = baseURL.appending(path: "api/cron")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaCronList.self, from: data)
    }

    public func notifications(limit: Int = 50) async throws -> AstaNotificationsResponse {
        var components = URLComponents(url: baseURL.appending(path: "api/notifications"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "limit", value: String(limit))]
        let (data, _) = try await session.data(from: components.url!)
        return try JSONDecoder().decode(AstaNotificationsResponse.self, from: data)
    }

    public func ragStatus() async throws -> AstaRagStatus {
        let url = baseURL.appending(path: "api/rag/status")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaRagStatus.self, from: data)
    }

    public func ragLearned() async throws -> AstaRagLearnedResponse {
        let url = baseURL.appending(path: "api/rag/learned")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaRagLearnedResponse.self, from: data)
    }

    public func securityAudit() async throws -> AstaSecurityAudit {
        let url = baseURL.appending(path: "api/settings/security-audit")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaSecurityAudit.self, from: data)
    }

    public func memoryHealth(force: Bool = false) async throws -> AstaMemoryHealth {
        var components = URLComponents(url: baseURL.appending(path: "api/settings/memory-health"), resolvingAgainstBaseURL: false)!
        if force { components.queryItems = [URLQueryItem(name: "force", value: "true")] }
        let (data, _) = try await session.data(from: components.url!)
        return try JSONDecoder().decode(AstaMemoryHealth.self, from: data)
    }

    public func checkUpdate() async throws -> AstaCheckUpdate {
        let url = baseURL.appending(path: "api/settings/check-update")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaCheckUpdate.self, from: data)
    }

    public func workspaceNotes(limit: Int = 20) async throws -> AstaWorkspaceNotesResponse {
        var components = URLComponents(url: baseURL.appending(path: "api/settings/notes"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "limit", value: String(limit))]
        let (data, _) = try await session.data(from: components.url!)
        return try JSONDecoder().decode(AstaWorkspaceNotesResponse.self, from: data)
    }

    public func testKey(provider: String) async throws -> AstaTestKeyResult {
        var components = URLComponents(url: baseURL.appending(path: "api/settings/test-key"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "provider", value: provider)]
        let (data, response) = try await session.data(from: components.url!)
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            if let errObj = try? JSONDecoder().decode(AstaAPIError.self, from: data),
               let detail = errObj.detail ?? errObj.error { throw AstaClientError.backendError(detail) }
            throw AstaClientError.httpError(http.statusCode)
        }
        return try JSONDecoder().decode(AstaTestKeyResult.self, from: data)
    }

    // MARK: - Settings (PUT / POST)

    public func setDefaultAI(provider: String) async throws -> AstaDefaultAI {
        let url = baseURL.appending(path: "api/settings/default-ai")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["provider": provider])
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaDefaultAI.self, from: data)
    }

    public func setThinking(level: String) async throws -> AstaThinking {
        let url = baseURL.appending(path: "api/settings/thinking")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["thinking_level": level])
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaThinking.self, from: data)
    }

    public func setReasoning(mode: String) async throws -> AstaReasoning {
        let url = baseURL.appending(path: "api/settings/reasoning")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["reasoning_mode": mode])
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaReasoning.self, from: data)
    }

    public func setMood(_ mood: String) async throws -> AstaMood {
        let url = baseURL.appending(path: "api/settings/mood")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["mood": mood])
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaMood.self, from: data)
    }

    public func setProviderEnabled(provider: String, enabled: Bool) async throws {
        let url = baseURL.appending(path: "api/settings/provider-flow/provider-enabled")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(AstaProviderEnabledIn(provider: provider, enabled: enabled))
        _ = try await session.data(for: req)
    }

    public func setFinalMode(mode: String) async throws -> AstaFinalMode {
        let url = baseURL.appending(path: "api/settings/final-mode")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["final_mode": mode])
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaFinalMode.self, from: data)
    }

    public func setVision(preprocess: Bool, providerOrder: String, openrouterModel: String) async throws -> AstaVision {
        let url = baseURL.appending(path: "api/settings/vision")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(AstaVisionIn(preprocess: preprocess, provider_order: providerOrder, openrouter_model: openrouterModel))
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaVision.self, from: data)
    }

    public func setModel(provider: String, model: String) async throws {
        let url = baseURL.appending(path: "api/settings/models")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(AstaModelIn(provider: provider, model: model))
        _ = try await session.data(for: req)
    }

    public func setKeys(_ keys: AstaKeysIn) async throws {
        let url = baseURL.appending(path: "api/settings/keys")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(keys)
        _ = try await session.data(for: req)
    }

    public func setSkillEnabled(skillId: String, enabled: Bool) async throws {
        let url = baseURL.appending(path: "api/settings/skills")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(AstaSkillToggleIn(skill_id: skillId, enabled: enabled))
        _ = try await session.data(for: req)
    }

    public func setTelegramUsername(_ username: String) async throws {
        let url = baseURL.appending(path: "api/settings/telegram/username")
        var req = URLRequest(url: url); req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["username": username])
        _ = try await session.data(for: req)
    }

    public func setPingram(notificationId: String, clientId: String? = nil, clientSecret: String? = nil, apiKey: String? = nil, templateId: String? = nil, phoneNumber: String? = nil) async throws {
        let url = baseURL.appending(path: "api/settings/pingram")
        var req = URLRequest(url: url); req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(AstaPingramIn(notification_id: notificationId, client_id: clientId, client_secret: clientSecret, api_key: apiKey, template_id: templateId, phone_number: phoneNumber))
        _ = try await session.data(for: req)
    }

    public func pingramTestCall(testNumber: String) async throws -> AstaPingramTestResult {
        let url = baseURL.appending(path: "api/settings/pingram/test-call")
        var req = URLRequest(url: url); req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["test_number": testNumber])
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaPingramTestResult.self, from: data)
    }

    public func cronAdd(name: String, cronExpr: String, message: String, tz: String? = nil, channel: String = "web", channelTarget: String = "", payloadKind: String = "agentturn", tlgCall: Bool = true) async throws -> AstaCronAddResult {
        let url = baseURL.appending(path: "api/cron")
        var req = URLRequest(url: url); req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(AstaCronAddIn(name: name, cron_expr: cronExpr, message: message, tz: tz, channel: channel, channel_target: channelTarget, payload_kind: payloadKind, tlg_call: tlgCall))
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaCronAddResult.self, from: data)
    }

    public func cronUpdate(jobId: Int, name: String? = nil, cronExpr: String? = nil, message: String? = nil, tz: String? = nil, enabled: Bool? = nil, channel: String? = nil, channelTarget: String? = nil, payloadKind: String? = nil, tlgCall: Bool? = nil) async throws {
        let url = baseURL.appending(path: "api/cron/\(jobId)")
        var req = URLRequest(url: url); req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(AstaCronUpdateIn(name: name, cron_expr: cronExpr, message: message, tz: tz, enabled: enabled, channel: channel, channel_target: channelTarget, payload_kind: payloadKind, tlg_call: tlgCall))
        _ = try await session.data(for: req)
    }

    public func cronDelete(jobId: Int) async throws {
        let url = baseURL.appending(path: "api/cron/\(jobId)")
        var req = URLRequest(url: url); req.httpMethod = "DELETE"
        _ = try await session.data(for: req)
    }

    public func deleteNotification(id: String) async throws {
        let url = baseURL.appending(path: "api/notifications/\(id)")
        var req = URLRequest(url: url); req.httpMethod = "DELETE"
        _ = try await session.data(for: req)
    }

    public func ragDeleteTopic(topic: String) async throws -> AstaRagDeleteResult {
        let encoded = topic.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? topic
        let url = baseURL.appending(path: "api/rag/topic/\(encoded)")
        var req = URLRequest(url: url); req.httpMethod = "DELETE"
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaRagDeleteResult.self, from: data)
    }

    public func triggerUpdate() async throws -> AstaUpdateResult {
        let url = baseURL.appending(path: "api/settings/update")
        var req = URLRequest(url: url); req.httpMethod = "POST"
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaUpdateResult.self, from: data)
    }

    public func restartBackend() async throws -> AstaRestartResponse {
        let url = baseURL.appending(path: "api/restart")
        var req = URLRequest(url: url); req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = "{}".data(using: .utf8)
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaRestartResponse.self, from: data)
    }

    // MARK: - Agents

    public func agentsList() async throws -> AstaAgentsResponse {
        let url = baseURL.appending(path: "api/agents")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AstaAgentsResponse.self, from: data)
    }

    public func agentCreate(name: String, description: String, emoji: String, model: String, thinking: String, systemPrompt: String) async throws -> AstaAgentResponse {
        let url = baseURL.appending(path: "api/agents")
        var req = URLRequest(url: url); req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(AstaAgentCreateIn(name: name, description: description, emoji: emoji, model: model, thinking: thinking, system_prompt: systemPrompt))
        let (data, response) = try await session.data(for: req)
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            if let errObj = try? JSONDecoder().decode(AstaAPIError.self, from: data), let detail = errObj.detail ?? errObj.error { throw AstaClientError.backendError(detail) }
            throw AstaClientError.httpError(http.statusCode)
        }
        return try JSONDecoder().decode(AstaAgentResponse.self, from: data)
    }

    public func agentUpdate(id: String, name: String? = nil, description: String? = nil, emoji: String? = nil, model: String? = nil, thinking: String? = nil, systemPrompt: String? = nil) async throws -> AstaAgentResponse {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        let url = baseURL.appending(path: "api/agents/\(encoded)")
        var req = URLRequest(url: url); req.httpMethod = "PATCH"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(AstaAgentUpdateIn(name: name, description: description, emoji: emoji, model: model, thinking: thinking, system_prompt: systemPrompt))
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaAgentResponse.self, from: data)
    }

    public func agentDelete(id: String) async throws {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        let url = baseURL.appending(path: "api/agents/\(encoded)")
        var req = URLRequest(url: url); req.httpMethod = "DELETE"
        _ = try await session.data(for: req)
    }

    public func usageStats(days: Int = 30) async throws -> AstaUsageStatsResponse {
        var comps = URLComponents(url: baseURL.appending(path: "api/settings/usage"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "days", value: "\(days)")]
        let (data, _) = try await session.data(from: comps.url!)
        return try JSONDecoder().decode(AstaUsageStatsResponse.self, from: data)
    }

    public func uploadSkillZip(fileURL: URL) async throws -> AstaSkillUploadResult {
        let url = baseURL.appending(path: "api/skills/upload")
        let boundary = "AstaBoundary-\(UUID().uuidString)"
        var body = Data()
        let filename = fileURL.lastPathComponent
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: application/zip\r\n\r\n".data(using: .utf8)!)
        body.append(try Data(contentsOf: fileURL))
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        var req = URLRequest(url: url); req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.setValue("\(body.count)", forHTTPHeaderField: "Content-Length")
        req.httpBody = body
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(AstaSkillUploadResult.self, from: data)
    }
}

// MARK: - Errors

public enum AstaClientError: Error, LocalizedError {
    case backendError(String)
    case httpError(Int)
    public var errorDescription: String? {
        switch self {
        case .backendError(let msg): return msg
        case .httpError(let code):   return "Server returned HTTP \(code)"
        }
    }
}

private struct AstaAPIError: Decodable {
    let detail: String?
    let error: String?
}

// MARK: - SSE internal model (used only inside chatStream)

/// Raw SSE payload before normalisation. All fields optional because different event types
/// carry different subsets of fields.
private struct SSERawPayload: Decodable {
    let type: String?
    /// Incremental chars for assistant/reasoning events.
    let delta: String?
    /// Cumulative text (used as fallback if delta is absent).
    let text: String?
    /// Full reply on the "done" event.
    let reply: String?
    let conversation_id: String?
    let provider: String?
    /// Error message on the "error" event.
    let error: String?
}

// MARK: - Public DTOs

public struct AstaStreamChunk: Sendable {
    /// Normalised type: "text", "thinking", "status", "done", "error"
    public let type: String
    /// For "text"/"thinking": the incremental delta to append.
    /// For "done": nil (use reply instead).
    /// For "error": the error message.
    public let text: String?
    /// Full final reply (only on "done").
    public let reply: String?
    public let conversation_id: String?
    public let provider: String?
}

public struct AstaHealth: Codable, Sendable {
    public let status: String
    public let app: String?
    public let version: String?
}

public struct AstaChatIn: Codable, Sendable {
    public let text: String
    public let provider: String
    public let user_id: String
    public let conversation_id: String?
    public let mood: String?
    public let web: Bool?
    public let image_base64: String?
    public let image_mime: String?
}

public struct AstaChatOut: Codable, Sendable {
    public let reply: String
    public let conversation_id: String
    public let provider: String
}

public struct AstaChatMessages: Codable, Sendable {
    public let conversation_id: String
    public let messages: [AstaMessage]
}

public struct AstaMessage: Codable, Sendable {
    public let role: String?
    public let content: String?
}

public struct AstaStatus: Codable, Sendable {
    public let status: String?
    public let app: String?
    public let version: String?
}

public struct AstaServerStatus: Codable, Sendable {
    public let ok: Bool?
    public let version: String?
    public let cpu_percent: Double?
    public let cpu_model: String?
    public let cpu_count: Int?
    public let ram: AstaServerStatusRam?
    public let disk: AstaServerStatusDisk?
    public let uptime_str: String?
    public let error: String?
}

public struct AstaServerStatusRam: Codable, Sendable {
    public let total_gb: Double?
    public let used_gb: Double?
    public let percent: Double?
}

public struct AstaServerStatusDisk: Codable, Sendable {
    public let total_gb: Double?
    public let used_gb: Double?
    public let percent: Double?
}

public struct AstaDefaultAI: Codable, Sendable {
    public let provider: String?
}

public struct AstaThinking: Codable, Sendable {
    public let level: String?
    public let options: [String]?
    enum CodingKeys: String, CodingKey {
        case level = "thinking_level"; case options
    }
}

public struct AstaReasoning: Codable, Sendable {
    public let reasoning_mode: String?
}

public struct AstaMood: Codable, Sendable {
    public let mood: String?
}

public struct AstaProvidersResponse: Codable, Sendable {
    public let providers: [String]?
}

public struct AstaProviderFlow: Codable, Sendable {
    public let default_provider: String?
    public let order: [String]?
    public let providers: [AstaProviderFlowItem]?
}

public struct AstaProviderFlowItem: Codable, Sendable {
    public let provider: String
    public let label: String?
    public let enabled: Bool?
    public let connected: Bool?
    public let auto_disabled: Bool?
    public let model: String?
}

public struct AstaFinalMode: Codable, Sendable {
    public let final_mode: String?
}

public struct AstaVision: Codable, Sendable {
    public let preprocess: Bool?
    public let provider_order: String?
    public let openrouter_model: String?
}

public struct AstaFallback: Codable, Sendable {
    public let providers: String?
    public let locked: Bool?
    public let message: String?
}

public struct AstaModelsResponse: Codable, Sendable {
    public let models: [String: String]?
    public let defaults: [String: String]?
}

public struct AstaAvailableModels: Codable, Sendable {
    public let ollama: [String]?
    public let openrouter: [String]?
    public let openai: [String]?
    public let claude: [String]?
    public let google: [String]?
    public let groq: [String]?
}

/// API keys to set. Only fields that exist in the backend ApiKeysIn model are included.
/// (github_api_token / vercel_api_token are NOT in backend — removed to avoid silent drops)
public struct AstaKeysIn: Codable, Sendable {
    public var anthropic_api_key: String?
    public var openrouter_api_key: String?
    public var openai_api_key: String?
    public var gemini_api_key: String?
    public var google_ai_key: String?
    public var groq_api_key: String?
    public var telegram_bot_token: String?
    public var giphy_api_key: String?
    public var spotify_client_id: String?
    public var spotify_client_secret: String?
    public var notion_api_key: String?
    public init() {}
}

public struct AstaSkillsResponse: Codable, Sendable {
    public let skills: [AstaSkillItem]?
}

public struct AstaSkillItem: Codable, Sendable {
    public let id: String
    public let name: String?
    public let description: String?
    public let enabled: Bool?
    public let available: Bool?
    public let action_hint: String?

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id          = (try? c.decode(String.self, forKey: .id)) ?? ""
        name        = try? c.decode(String.self, forKey: .name)
        description = try? c.decode(String.self, forKey: .description)
        enabled     = try? c.decode(Bool.self, forKey: .enabled)
        available   = try? c.decode(Bool.self, forKey: .available)
        action_hint = try? c.decode(String.self, forKey: .action_hint)
    }

    enum CodingKeys: String, CodingKey {
        case id, name, description, enabled, available, action_hint
    }
}

public struct AstaTelegramUsername: Codable, Sendable {
    public let username: String?
}

public struct AstaPingramSettings: Codable, Sendable {
    public let client_id: String?
    public let notification_id: String?
    public let template_id: String?
    public let phone_number: String?
    public let is_secret_set: Bool?
    public let api_key_set: Bool?
}

public struct AstaPingramTestResult: Codable, Sendable {
    public let ok: Bool?
    public let error: String?
}

public struct AstaSpotifyStatus: Codable, Sendable {
    public let connected: Bool?
}

public struct AstaSpotifyDevice: Codable, Sendable, Identifiable {
    public let id: String
    public let name: String?
    public let type: String?
    public let is_active: Bool?
}

private struct AstaSpotifyDevicesResponse: Codable, Sendable {
    let devices: [AstaSpotifyDevice]?
}

public struct AstaCronList: Codable, Sendable {
    public let cron_jobs: [AstaCronJob]?
}

public struct AstaCronJob: Codable, Sendable {
    public let id: Int?
    public let name: String?
    public let cron_expr: String?
    public let message: String?
    public let tz: String?
    public let enabled: Bool?
    public let channel: String?
    public let channel_target: String?
    public let payload_kind: String?
    public let tlg_call: Bool?

    enum CodingKeys: String, CodingKey {
        case id, name, cron_expr, message, tz, enabled, channel, channel_target, payload_kind, tlg_call
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id           = try? c.decode(Int.self, forKey: .id)
        name         = try? c.decode(String.self, forKey: .name)
        cron_expr    = try? c.decode(String.self, forKey: .cron_expr)
        message      = try? c.decode(String.self, forKey: .message)
        tz           = try? c.decode(String.self, forKey: .tz)
        channel      = try? c.decode(String.self, forKey: .channel)
        channel_target = try? c.decode(String.self, forKey: .channel_target)
        payload_kind = try? c.decode(String.self, forKey: .payload_kind)
        // SQLite stores booleans as 0/1 integers
        if let b = try? c.decode(Bool.self, forKey: .enabled)   { enabled  = b }
        else if let i = try? c.decode(Int.self, forKey: .enabled) { enabled = i != 0 }
        else { enabled = nil }
        if let b = try? c.decode(Bool.self, forKey: .tlg_call)   { tlg_call = b }
        else if let i = try? c.decode(Int.self, forKey: .tlg_call){ tlg_call = i != 0 }
        else { tlg_call = nil }
    }
}

public struct AstaCronAddResult: Codable, Sendable {
    public let id: Int?
    public let name: String?
    public let cron_expr: String?
}

public struct AstaNotificationsResponse: Codable, Sendable {
    public let notifications: [AstaNotification]?
}

public struct AstaNotification: Codable, Sendable {
    public let id: String?
    public let user_id: String?
    public let kind: String?
    public let title: String?
    public let body: String?
    public let message: String?
    public let run_at: String?
    public let status: String?
    public let created_at: String?

    enum CodingKeys: String, CodingKey {
        case id, user_id, kind, title, body, message, run_at, status, created_at
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        if let intId = try? c.decode(Int.self, forKey: .id) { id = String(intId) }
        else { id = try? c.decode(String.self, forKey: .id) }
        user_id    = try? c.decode(String.self, forKey: .user_id)
        kind       = try? c.decode(String.self, forKey: .kind)
        title      = try? c.decode(String.self, forKey: .title)
        body       = try? c.decode(String.self, forKey: .body)
        message    = try? c.decode(String.self, forKey: .message)
        run_at     = try? c.decode(String.self, forKey: .run_at)
        status     = try? c.decode(String.self, forKey: .status)
        created_at = try? c.decode(String.self, forKey: .created_at)
    }
}

public struct AstaRagStatus: Codable, Sendable {
    public let ok: Bool?
    public let message: String?
    public let provider: String?
    public let detail: String?
    public let ollama_ok: Bool?
    public let store_error: Bool?
}

public struct AstaRagLearnedResponse: Codable, Sendable {
    public let has_learned: Bool?
    public let topics: [AstaRagTopic]?
}

public struct AstaRagTopic: Codable, Sendable {
    public let topic: String?
    public let chunks_count: Int?
}

public struct AstaRagDeleteResult: Codable, Sendable {
    public let ok: Bool?
    public let topic: String?
    public let deleted_chunks: Int?
}

public struct AstaSecurityAudit: Codable, Sendable {
    public let warnings: [AstaSecurityWarning]?
}

public struct AstaSecurityWarning: Codable, Sendable {
    public let severity: String?
    public let message: String?
    public let fix: String?
}

public struct AstaMemoryHealth: Codable, Sendable {
    public let ok: Bool?
    public let status: String?
    public let vector_count: Int?
    public let chunk_count: Int?
    public let store_size_mb: Double?
    public let error: String?
}

public struct AstaCheckUpdate: Codable, Sendable {
    public let update_available: Bool?
    public let local: String?
    public let remote: String?
    public let error: String?
}

public struct AstaUpdateResult: Codable, Sendable {
    public let ok: Bool?
    public let message: String?
    public let error: String?
}

public struct AstaWorkspaceNotesResponse: Codable, Sendable {
    public let notes: [AstaWorkspaceNote]?
}

public struct AstaWorkspaceNote: Codable, Sendable {
    public let name: String?
    public let path: String?
    public let size: Int?
    public let modified_at: String?
}

public struct AstaRestartResponse: Codable, Sendable {
    public let message: String?
}

public struct AstaSkillUploadResult: Codable, Sendable {
    public let skill_id: String?
    public let ok: Bool?
}

// MARK: - Agents DTOs

public struct AstaAgent: Codable, Sendable, Identifiable {
    public let id: String
    public let name: String
    public let description: String
    public let emoji: String
    public let model: String
    public let thinking: String
    public let system_prompt: String
}

public struct AstaAgentsResponse: Codable, Sendable {
    public let agents: [AstaAgent]
}

public struct AstaAgentResponse: Codable, Sendable {
    public let agent: AstaAgent
}

public struct AstaTestKeyResult: Codable, Sendable {
    public let provider: String?
    public let ok: Bool?
    public let error: String?
}

public struct AstaConversationsResponse: Codable, Sendable {
    public let conversations: [AstaConversationItem]
}

public struct AstaConversationItem: Codable, Sendable, Identifiable {
    public let id: String
    public let title: String
    public let created_at: String
    public let last_active: String
}

public struct AstaUsageRow: Codable, Sendable, Identifiable {
    public var id: String { provider }
    public let provider: String
    public let input_tokens: Int
    public let output_tokens: Int
    public let calls: Int
    public let last_used: String?
}

public struct AstaUsageStatsResponse: Codable, Sendable {
    public let usage: [AstaUsageRow]
    public let days: Int
}

// MARK: - Private request body types

private struct AstaProviderEnabledIn: Encodable, Sendable {
    let provider: String; let enabled: Bool
}
private struct AstaModelIn: Encodable, Sendable {
    let provider: String; let model: String
}
private struct AstaVisionIn: Encodable, Sendable {
    let preprocess: Bool; let provider_order: String; let openrouter_model: String
}
private struct AstaSkillToggleIn: Encodable, Sendable {
    let skill_id: String; let enabled: Bool
}
private struct AstaPingramIn: Encodable, Sendable {
    let notification_id: String
    let client_id: String?; let client_secret: String?
    let api_key: String?; let template_id: String?; let phone_number: String?
}
private struct AstaCronAddIn: Encodable, Sendable {
    let name: String; let cron_expr: String; let message: String; let tz: String?
    let channel: String; let channel_target: String; let payload_kind: String; let tlg_call: Bool
}
private struct AstaCronUpdateIn: Encodable, Sendable {
    let name: String?; let cron_expr: String?; let message: String?; let tz: String?
    let enabled: Bool?; let channel: String?; let channel_target: String?
    let payload_kind: String?; let tlg_call: Bool?
}
private struct AstaAgentCreateIn: Encodable, Sendable {
    let name: String; let description: String; let emoji: String
    let model: String; let thinking: String; let system_prompt: String
}
private struct AstaAgentUpdateIn: Encodable, Sendable {
    let name: String?; let description: String?; let emoji: String?
    let model: String?; let thinking: String?; let system_prompt: String?
}
