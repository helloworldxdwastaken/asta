import SwiftUI
import AstaAPIClient

// MARK: - Agents Settings Tab
//
// OpenClaw-style named agents for Asta.
// Each agent is backed by workspace/skills/<slug>/SKILL.md with is_agent: true.
// The main Asta can delegate to any agent via sessions_spawn.

struct AgentsSettingsTab: View {
    @ObservedObject var appState: AppState
    @State private var showCreate = false
    @State private var editingAgent: AstaAgent?
    @State private var searchText = ""
    @State private var filterMode: AgentFilter = .all

    private enum AgentFilter: String, CaseIterable, Identifiable {
        case all = "All"
        case added = "Added"
        case notAdded = "Not Added"
        var id: String { rawValue }
    }

    private var filteredAgents: [AstaAgent] {
        let q = searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return appState.agentsList
            .filter { agent in
                let enabled = agent.enabled ?? true
                if filterMode == .added && !enabled { return false }
                if filterMode == .notAdded && enabled { return false }
                if q.isEmpty { return true }
                let hay = [agent.id, agent.name, agent.description].joined(separator: " ").lowercased()
                return hay.contains(q)
            }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // ── Header ────────────────────────────────────────────────────
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Agents")
                        .font(.system(size: 15, weight: .semibold))
                    Text("Specialist AIs with their own name, personality, and expertise. The main Asta can delegate tasks to them automatically.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer()
                if appState.agentsLoading { ProgressView().controlSize(.small) }
                Button {
                    showCreate = true
                } label: {
                    Label("New Agent", systemImage: "plus")
                        .font(.system(size: 12, weight: .medium))
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.small)
            }
            .padding(.horizontal, 20)
            .padding(.top, 20)
            .padding(.bottom, 14)

            HStack(spacing: 10) {
                TextField("Search agents…", text: $searchText)
                    .textFieldStyle(.roundedBorder)
                Picker("Filter", selection: $filterMode) {
                    ForEach(AgentFilter.allCases) { mode in
                        Text(mode.rawValue).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 300)
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 10)

            Divider()

            if let err = appState.agentsError {
                Text(err)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .padding(.horizontal, 20)
                    .padding(.top, 12)
            }

            // ── Agent list ────────────────────────────────────────────────
            if appState.agentsList.isEmpty && !appState.agentsLoading {
                emptyState
            } else if filteredAgents.isEmpty && !appState.agentsLoading {
                searchEmptyState
            } else {
                ScrollView {
                    LazyVStack(spacing: 1) {
                        ForEach(filteredAgents) { agent in
                            AgentRow(
                                agent: agent,
                                isEnabled: agent.enabled ?? true,
                                onToggleEnabled: {
                                    Task { await appState.setAgentEnabled(id: agent.id, enabled: !(agent.enabled ?? true)) }
                                },
                                onEdit: { editingAgent = agent },
                                onDelete: { Task { await appState.deleteAgent(id: agent.id) } }
                            )
                            Divider().padding(.leading, 64)
                        }
                    }
                    .padding(.bottom, 20)
                }
            }
        }
        .task { await appState.loadAgents() }
        .sheet(isPresented: $showCreate) {
            AgentEditorSheet(appState: appState, existing: nil) {
                Task { await appState.loadAgents() }
            }
        }
        .sheet(item: $editingAgent) { agent in
            AgentEditorSheet(appState: appState, existing: agent) {
                Task { await appState.loadAgents() }
            }
        }
    }

    // MARK: Empty state

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer(minLength: 40)
            ZStack {
                Circle()
                    .fill(Color.accentColor.opacity(0.1))
                    .frame(width: 64, height: 64)
                Image(systemName: "person.2")
                    .font(.system(size: 26, weight: .light))
                    .foregroundStyle(Color.accentColor)
            }
            VStack(spacing: 6) {
                Text("No agents yet")
                    .font(.system(size: 14, weight: .semibold))
                Text("Create specialist AIs like a Competitor Analyst,\nCode Reviewer, or Research Assistant.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            Button("Create first agent") { showCreate = true }
                .buttonStyle(.borderedProminent)
            Spacer()
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 40)
    }

    private var searchEmptyState: some View {
        VStack(spacing: 8) {
            Spacer(minLength: 32)
            Text("No matching agents")
                .font(.system(size: 13, weight: .semibold))
            Text("Try a different search term or switch filter.")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 40)
    }

}

// MARK: - Agent Row

private struct AgentRow: View {
    let agent: AstaAgent
    let isEnabled: Bool
    let onToggleEnabled: () -> Void
    let onEdit: () -> Void
    let onDelete: () -> Void
    @State private var isHovered = false

    var body: some View {
        HStack(spacing: 14) {
            // Emoji badge
            ZStack {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(Color.accentColor.opacity(0.1))
                    .frame(width: 44, height: 44)
                Text(agent.emoji.isEmpty ? "🤖" : agent.emoji)
                    .font(.system(size: 22))
            }

            // Info
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 8) {
                    Text(agent.name)
                        .font(.system(size: 13, weight: .semibold))
                    if !agent.model.isEmpty {
                        Text(agent.model)
                            .font(.caption2.weight(.medium))
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.secondary.opacity(0.1))
                            .clipShape(Capsule())
                    }
                    Text(isEnabled ? "Added" : "Not Added")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(isEnabled ? Color.green : .secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background((isEnabled ? Color.green : Color.secondary).opacity(0.12))
                        .clipShape(Capsule())
                }
                if !agent.description.isEmpty {
                    Text(agent.description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                if !agent.system_prompt.isEmpty {
                    Text(agent.system_prompt.prefix(80) + (agent.system_prompt.count > 80 ? "…" : ""))
                        .font(.caption2)
                        .foregroundStyle(Color.secondary.opacity(0.7))
                        .lineLimit(1)
                }
                if let knowledgePath = agent.knowledge_path, !knowledgePath.isEmpty {
                    Text("Knowledge: \(knowledgePath)")
                        .font(.caption2)
                        .foregroundStyle(Color.secondary.opacity(0.65))
                        .lineLimit(1)
                }
                if let allowed = agent.skills {
                    Text(allowed.isEmpty ? "Allowed skills: none" : "Allowed skills: \(allowed.count)")
                        .font(.caption2)
                        .foregroundStyle(Color.secondary.opacity(0.65))
                        .lineLimit(1)
                } else {
                    Text("Allowed skills: all")
                        .font(.caption2)
                        .foregroundStyle(Color.secondary.opacity(0.65))
                        .lineLimit(1)
                }
            }

            Spacer()

            HStack(spacing: 6) {
                if isEnabled {
                    Button("Remove") { onToggleEnabled() }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                } else {
                    Button("Add") { onToggleEnabled() }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                }
                if isHovered {
                    Button("Edit") { onEdit() }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                    Button("Delete", role: .destructive) { onDelete() }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 10)
        .background(isHovered ? Color.primary.opacity(0.03) : Color.clear)
        .contentShape(Rectangle())
        .onHover { isHovered = $0 }
        .animation(.easeOut(duration: 0.1), value: isHovered)
    }
}

// MARK: - Agent Editor Sheet

struct AgentEditorSheet: View {
    @ObservedObject var appState: AppState
    let existing: AstaAgent?
    let onSave: () -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var description = ""
    @State private var emoji = "🤖"
    @State private var model = ""
    @State private var thinking = ""
    @State private var systemPrompt = ""
    @State private var selectedSkillIDs: Set<String> = []
    @State private var didInitSkillSelection = false
    @State private var saving = false
    @State private var error: String?

    private var isNew: Bool { existing == nil }
    private var title: String { isNew ? "New Agent" : "Edit Agent" }

    private let thinkingOptions = ["", "off", "minimal", "low", "medium", "high", "xhigh"]
    private let emojiSuggestions = ["🤖", "🔍", "💼", "📊", "🧑‍💻", "📝", "🎯", "⚡", "🧠", "🔬", "📈", "🛡️", "🎨", "📚"]

    private var agentAssignableSkills: [AstaSkillItem] {
        let agentIDs = Set(appState.agentsList.map { $0.id.lowercased() })
        let deduped = Dictionary(
            uniqueKeysWithValues: appState.skillsList.map { ($0.id.lowercased(), $0) }
        )
        return deduped.values
            .filter { item in
                let sid = item.id.lowercased()
                if sid.isEmpty { return false }
                if agentIDs.contains(sid) { return false }
                return true
            }
            .sorted { lhs, rhs in
                let l = (lhs.name ?? lhs.id).lowercased()
                let r = (rhs.name ?? rhs.id).lowercased()
                return l < r
            }
    }

    private var allAssignableSkillIDs: [String] {
        agentAssignableSkills.map(\.id)
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text(title)
                    .font(.system(size: 15, weight: .semibold))
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 18))
                        .foregroundStyle(Color(nsColor: .tertiaryLabelColor))
                }
                .buttonStyle(.plain)
                .keyboardShortcut(.escape, modifiers: [])
            }
            .padding(.horizontal, 24)
            .padding(.top, 20)
            .padding(.bottom, 16)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 20) {

                    // ── Identity ──────────────────────────────────────────
                    sectionHeader("Identity")

                    HStack(spacing: 14) {
                        // Emoji picker
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Icon").font(.caption).foregroundStyle(.secondary)
                            Menu {
                                ForEach(emojiSuggestions, id: \.self) { e in
                                    Button(e) { emoji = e }
                                }
                                Divider()
                                Button("Custom…") {
                                    // user can just type in the field below
                                }
                            } label: {
                                Text(emoji.isEmpty ? "🤖" : emoji)
                                    .font(.system(size: 28))
                                    .frame(width: 52, height: 52)
                                    .background(Color.accentColor.opacity(0.1))
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                            }
                            .menuStyle(.borderlessButton)
                            TextField("", text: $emoji)
                                .font(.caption)
                                .frame(width: 52)
                                .textFieldStyle(.roundedBorder)
                        }

                        VStack(alignment: .leading, spacing: 8) {
                            fieldLabel("Name")
                            TextField("e.g. Competitor Analyst", text: $name)
                                .textFieldStyle(.roundedBorder)

                            fieldLabel("Description")
                            TextField("e.g. Researches competitors and market trends", text: $description)
                                .textFieldStyle(.roundedBorder)
                        }
                    }

                    // ── System Prompt ─────────────────────────────────────
                    sectionHeader("System Prompt")
                    Text("Define this agent's personality, expertise, and how it should behave.")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    TextEditor(text: $systemPrompt)
                        .font(.system(.body, design: .monospaced))
                        .frame(minHeight: 140)
                        .padding(8)
                        .background(Color(nsColor: .textBackgroundColor))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.secondary.opacity(0.2)))

                    // Prompt templates
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(promptTemplates, id: \.name) { template in
                                Button(template.name) {
                                    systemPrompt = template.prompt
                                    if name.isEmpty { name = template.name }
                                    if description.isEmpty { description = template.description }
                                    if emoji.isEmpty || emoji == "🤖" { emoji = template.emoji }
                                }
                                .buttonStyle(.bordered)
                                .controlSize(.small)
                                .font(.caption)
                            }
                        }
                    }

                    // ── Model overrides ───────────────────────────────────
                    sectionHeader("Model Overrides (optional)")
                    Text("Leave blank to use Asta's default. Useful to give this agent a stronger or cheaper model.")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 4) {
                            fieldLabel("Model")
                            TextField("e.g. claude-opus-4-5 or openai/gpt-4o", text: $model)
                                .textFieldStyle(.roundedBorder)
                        }

                        VStack(alignment: .leading, spacing: 4) {
                            fieldLabel("Thinking")
                            Picker("", selection: $thinking) {
                                ForEach(thinkingOptions, id: \.self) { opt in
                                    Text(opt.isEmpty ? "(default)" : opt).tag(opt)
                                }
                            }
                            .labelsHidden()
                            .frame(width: 130)
                        }
                    }

                    // ── Allowed skills ─────────────────────────────────────
                    sectionHeader("Allowed Skills")
                    Text("Choose which skills this agent can use. If all are selected, no explicit filter is stored.")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    HStack(spacing: 8) {
                        Button("Select all") {
                            selectedSkillIDs = Set(allAssignableSkillIDs)
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)

                        Button("Clear") {
                            selectedSkillIDs.removeAll()
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)

                        Spacer()
                        Text("\(selectedSkillIDs.count) / \(allAssignableSkillIDs.count) selected")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }

                    if agentAssignableSkills.isEmpty {
                        Text("No skills available yet.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    } else {
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                            ForEach(agentAssignableSkills, id: \.id) { skill in
                                let isSelected = selectedSkillIDs.contains(skill.id)
                                Button {
                                    if isSelected {
                                        selectedSkillIDs.remove(skill.id)
                                    } else {
                                        selectedSkillIDs.insert(skill.id)
                                    }
                                } label: {
                                    HStack(spacing: 8) {
                                        Image(systemName: isSelected ? "checkmark.square.fill" : "square")
                                            .foregroundStyle(isSelected ? Color.accentColor : .secondary)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(skill.name ?? skill.id)
                                                .font(.caption.weight(.medium))
                                                .foregroundStyle(.primary)
                                                .lineLimit(1)
                                            Text(skill.id)
                                                .font(.caption2)
                                                .foregroundStyle(.secondary)
                                                .lineLimit(1)
                                        }
                                        Spacer(minLength: 0)
                                    }
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 8)
                                    .background(
                                        RoundedRectangle(cornerRadius: 8)
                                            .fill(isSelected ? Color.accentColor.opacity(0.12) : Color.primary.opacity(0.04))
                                    )
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }

                    // How delegation works
                    GroupBox {
                        VStack(alignment: .leading, spacing: 6) {
                            Label("How agent delegation works", systemImage: "info.circle")
                                .font(.caption.weight(.semibold))
                            Text("When you ask the main Asta something, it can automatically spawn this agent in the background to handle tasks matching its specialty. You can also explicitly say \"ask the Competitor Analyst to…\" and Asta will delegate.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }

                    if let err = error {
                        Text(err).font(.caption).foregroundStyle(.red)
                    }
                }
                .padding(24)
            }

            Divider()

            // Footer
            HStack {
                Button("Cancel") { dismiss() }
                Spacer()
                Button(saving ? "Saving…" : (isNew ? "Create Agent" : "Save Changes")) {
                    Task { await save() }
                }
                .buttonStyle(.borderedProminent)
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || saving)
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 16)
        }
        .frame(width: 560, height: 680)
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear {
            if let a = existing {
                name = a.name; description = a.description; emoji = a.emoji
                model = a.model; thinking = a.thinking; systemPrompt = a.system_prompt
            }
            if appState.skillsList.isEmpty {
                Task { await appState.loadSettings() }
            }
            initializeSkillSelectionIfNeeded()
        }
        .onChange(of: appState.skillsList.map(\.id).joined(separator: ",")) { _ in
            initializeSkillSelectionIfNeeded()
        }
    }

    // MARK: Helpers

    @ViewBuilder
    private func sectionHeader(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(.secondary)
            .textCase(.uppercase)
            .tracking(0.5)
    }

    @ViewBuilder
    private func fieldLabel(_ text: String) -> some View {
        Text(text).font(.caption).foregroundStyle(.secondary)
    }

    private func initializeSkillSelectionIfNeeded() {
        if didInitSkillSelection {
            return
        }
        let all = Set(allAssignableSkillIDs)
        if all.isEmpty {
            return
        }
        if let existing, let allowed = existing.skills {
            selectedSkillIDs = Set(allowed).intersection(all)
        } else {
            selectedSkillIDs = all
        }
        didInitSkillSelection = true
    }

    private func resolveAllowedSkillsForSave() -> [String]? {
        let all = Set(allAssignableSkillIDs)
        if all.isEmpty {
            return nil
        }
        let selectedOrdered = allAssignableSkillIDs.filter { selectedSkillIDs.contains($0) }
        if Set(selectedOrdered) == all {
            // nil means "no explicit filter" (all skills allowed)
            return nil
        }
        return selectedOrdered
    }

    private func save() async {
        saving = true; error = nil
        let trimName = name.trimmingCharacters(in: .whitespaces)
        let allowedSkills = resolveAllowedSkillsForSave()
        if let existing {
            await appState.updateAgent(
                id: existing.id, name: trimName, description: description,
                emoji: emoji, model: model, thinking: thinking, systemPrompt: systemPrompt,
                allowedSkills: allowedSkills
            )
        } else {
            await appState.createAgent(
                name: trimName, description: description, emoji: emoji,
                model: model, thinking: thinking, systemPrompt: systemPrompt,
                allowedSkills: allowedSkills
            )
        }
        if let err = appState.agentsError { self.error = err; saving = false; return }
        onSave()
        dismiss()
        saving = false
    }

    // MARK: Prompt templates

    private struct PromptTemplate {
        let name: String; let emoji: String; let description: String; let prompt: String
    }

    private let promptTemplates: [PromptTemplate] = [
        PromptTemplate(
            name: "Competitor Analyst",
            emoji: "🔍",
            description: "Researches competitors and market trends",
            prompt: """
You are a sharp competitive intelligence analyst. Your job is to research topics, monitor competitors, identify market shifts, and surface actionable insights.

When asked to research a competitor, market, or topic:
1. Use web_search to gather data from multiple sources (news, official sites, social, job boards)
2. Cross-reference findings and note any conflicts or gaps
3. Write a structured markdown report with: Executive Summary → Key Findings → Details → Sources
4. Always include sources with URLs and dates
5. Save the report using the write_file tool at path: research/[topic]_report.md (e.g. research/tesla_report.md)
6. Tell the user the exact file path where the report was saved

Always save the file — don't ask, just do it. Then give a short summary in chat.
"""
        ),
        PromptTemplate(
            name: "Code Reviewer",
            emoji: "🧑‍💻",
            description: "Reviews code for bugs, security issues, and best practices",
            prompt: """
You are a senior software engineer focused on code quality. Your role is to review code and provide constructive, specific feedback.

When reviewing code:
1. Check for correctness, edge cases, and potential bugs
2. Flag security vulnerabilities (SQL injection, XSS, auth issues, etc.)
3. Suggest better patterns, naming, and structure where relevant
4. Note performance concerns for hot paths
5. Keep feedback actionable — "do X instead of Y because Z"

Be direct. Don't praise code that has real issues. Prioritize critical bugs over style.
"""
        ),
        PromptTemplate(
            name: "Research Assistant",
            emoji: "📚",
            description: "Deep dives into topics and produces structured reports",
            prompt: """
You are a thorough research assistant. You find, synthesize, and present information clearly.

For any research task:
1. Use web_search across multiple sources — academic, news, official docs, practitioner blogs
2. Cross-reference and note conflicts between sources
3. Structure output: Summary → Key Findings → Details → Sources
4. Cite everything with URLs and dates — recency matters
5. Flag what you're uncertain about or couldn't verify
6. Save the full report using write_file at path: research/[topic]_report.md
7. Tell the user the exact file path

Always save the file automatically — don't ask first.
"""
        ),
        PromptTemplate(
            name: "Data Analyst",
            emoji: "📊",
            description: "Analyzes data and produces insights and visualizations",
            prompt: """
You are a data analyst who turns raw data into clear insights.

When given data or asked to analyze something:
1. Identify the key question to answer
2. Describe the data: shape, distributions, missing values, outliers
3. Surface patterns, trends, and anomalies
4. Produce clear conclusions with supporting numbers
5. Suggest follow-up analyses if relevant

Prefer tables and structured output over walls of text. Be precise with numbers.
"""
        ),
        PromptTemplate(
            name: "Writing Editor",
            emoji: "📝",
            description: "Edits and improves writing for clarity and impact",
            prompt: """
You are a sharp editor who makes writing clearer, stronger, and more impactful.

When editing:
1. Fix grammar, spelling, and punctuation silently (don't enumerate each fix)
2. Improve clarity — cut jargon, shorten sentences, remove filler
3. Strengthen the opening and closing
4. Flag structural issues: buried lede, weak argument flow, repetition
5. Preserve the author's voice — don't rewrite, improve

Return the edited version plus a brief note on the 2-3 most important changes made.
"""
        ),
    ]
}
