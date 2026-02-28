import SwiftUI
import AppKit
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
    @State private var deletingAgent: AstaAgent?
    @State private var searchText = ""
    @State private var filterMode: AgentFilter = .all
    @State private var selectedCategoryTab = "All"
    private let preferredCategoryOrder = [
        "Marketing", "Research", "Engineering", "Data", "Knowledge",
        "Operations", "Sales", "Support", "Design", "General",
    ]

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

    private var categoryTabs: [String] {
        let discovered = Set(filteredAgents.map(agentCategory))
        guard !discovered.isEmpty else { return ["All"] }
        var ordered: [String] = []
        for category in preferredCategoryOrder where discovered.contains(category) {
            ordered.append(category)
        }
        let extras = discovered.subtracting(Set(ordered))
            .sorted { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }
        return ["All"] + ordered + extras
    }

    private var visibleAgents: [AstaAgent] {
        let activeTab = categoryTabs.contains(selectedCategoryTab) ? selectedCategoryTab : "All"
        guard activeTab != "All" else { return filteredAgents }
        return filteredAgents.filter { agentCategory($0) == activeTab }
    }

    private func agentCategory(_ agent: AstaAgent) -> String {
        let raw = (agent.category ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if !raw.isEmpty {
            return raw
        }
        let hay = [agent.id, agent.name, agent.description]
            .joined(separator: " ")
            .lowercased()
        if hay.contains("seo") || hay.contains("copy") || hay.contains("marketing") || hay.contains("growth") {
            return "Marketing"
        }
        if hay.contains("research") || hay.contains("competitor") || hay.contains("intel") {
            return "Research"
        }
        if hay.contains("code") || hay.contains("engineer") || hay.contains("dev") {
            return "Engineering"
        }
        if hay.contains("data") || hay.contains("analytics") {
            return "Data"
        }
        if hay.contains("knowledge") || hay.contains("curator") || hay.contains("docs") {
            return "Knowledge"
        }
        if hay.contains("ops") || hay.contains("operation") {
            return "Operations"
        }
        if hay.contains("sales") {
            return "Sales"
        }
        if hay.contains("support") || hay.contains("helpdesk") {
            return "Support"
        }
        if hay.contains("design") || hay.contains("creative") {
            return "Design"
        }
        return "General"
    }

    private func categorySymbol(_ category: String) -> String {
        switch category.lowercased() {
        case "marketing": return "megaphone.fill"
        case "research": return "magnifyingglass.circle.fill"
        case "engineering": return "hammer.fill"
        case "data": return "chart.bar.fill"
        case "knowledge": return "book.closed.fill"
        case "operations": return "gearshape.2.fill"
        case "sales": return "cart.fill"
        case "support": return "bubble.left.and.bubble.right.fill"
        case "design": return "paintpalette.fill"
        default: return "person.2.fill"
        }
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
            } else if visibleAgents.isEmpty && !appState.agentsLoading {
                searchEmptyState
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(categoryTabs, id: \.self) { tab in
                                    Button {
                                        selectedCategoryTab = tab
                                    } label: {
                                        HStack(spacing: 6) {
                                            if tab != "All" {
                                                Image(systemName: categorySymbol(tab))
                                                    .font(.system(size: 11, weight: .semibold))
                                            }
                                            Text(tab)
                                                .font(.system(size: 12, weight: .semibold))
                                        }
                                        .foregroundStyle(selectedCategoryTab == tab ? Color.white : Color.primary)
                                        .padding(.horizontal, 10)
                                        .padding(.vertical, 6)
                                        .background(
                                            Capsule(style: .continuous)
                                                .fill(selectedCategoryTab == tab ? Color.accentColor : Color.primary.opacity(0.06))
                                        )
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                        .padding(.horizontal, 20)

                        LazyVGrid(
                            columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)],
                            spacing: 12
                        ) {
                            ForEach(visibleAgents) { agent in
                                AgentCard(
                                    agent: agent,
                                    category: agentCategory(agent),
                                    isEnabled: agent.enabled ?? true,
                                    onToggleEnabled: {
                                        Task { await appState.setAgentEnabled(id: agent.id, enabled: !(agent.enabled ?? true)) }
                                    },
                                    onEdit: { editingAgent = agent },
                                    onDelete: { deletingAgent = agent }
                                )
                            }
                        }
                        .padding(.horizontal, 20)
                    }
                    .padding(.vertical, 14)
                }
            }
        }
        .task { await appState.loadAgents() }
        .onChange(of: categoryTabs.joined(separator: "|")) { _ in
            if !categoryTabs.contains(selectedCategoryTab) {
                selectedCategoryTab = "All"
            }
        }
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
        .confirmationDialog(
            deletingAgent == nil ? "Delete agent?" : "Delete \(deletingAgent?.name ?? "agent")?",
            isPresented: Binding(
                get: { deletingAgent != nil },
                set: { newValue in if !newValue { deletingAgent = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                guard let agent = deletingAgent else { return }
                deletingAgent = nil
                Task { await appState.deleteAgent(id: agent.id) }
            }
            Button("Cancel", role: .cancel) {
                deletingAgent = nil
            }
        } message: {
            Text("This permanently removes the agent and its SKILL.md file.")
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

// MARK: - Agent Card

private struct AgentCard: View {
    let agent: AstaAgent
    let category: String
    let isEnabled: Bool
    let onToggleEnabled: () -> Void
    let onEdit: () -> Void
    let onDelete: () -> Void
    @State private var isHovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 10) {
                AgentAvatarCircle(icon: agent.icon, avatar: agent.avatar, size: 46, symbolSize: 18)
                VStack(alignment: .leading, spacing: 3) {
                    Text(agent.name)
                        .font(.system(size: 13, weight: .semibold))
                        .lineLimit(1)
                    if !agent.description.isEmpty {
                        Text(agent.description)
                        .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                    }
                }
                Spacer()
            }

            HStack(spacing: 8) {
                badge(category, color: .blue)
                if !agent.model.isEmpty {
                    badge(agent.model, color: .secondary)
                }
                badge(isEnabled ? "Added" : "Not Added", color: isEnabled ? .green : .secondary)
                Spacer(minLength: 0)
                if let allowed = agent.skills {
                    Text(allowed.isEmpty ? "Allowed skills: none" : "Allowed skills: \(allowed.count)")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                } else {
                    Text("Allowed skills: all")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            HStack(spacing: 6) {
                if let knowledgePath = agent.knowledge_path, !knowledgePath.isEmpty {
                    Text("Knowledge: \(knowledgePath)")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }

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
                Spacer()
                Button("Edit") { onEdit() }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .opacity(isHovered ? 1 : 0.8)
                Button("Delete", role: .destructive) { onDelete() }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .opacity(isHovered ? 1 : 0.8)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(isHovered ? Color.primary.opacity(0.05) : Color.primary.opacity(0.02))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(Color.primary.opacity(0.08), lineWidth: 0.6)
        )
        .contentShape(Rectangle())
        .onHover { isHovered = $0 }
        .animation(.easeOut(duration: 0.1), value: isHovered)
    }

    private func badge(_ text: String, color: Color) -> some View {
        Text(text)
            .font(.caption2.weight(.semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.12))
            .clipShape(Capsule())
    }
}

private struct AgentAvatarCircle: View {
    let icon: String?
    let avatar: String?
    let size: CGFloat
    let symbolSize: CGFloat

    var body: some View {
        ZStack {
            Circle()
                .fill(Color.accentColor.opacity(0.12))
                .frame(width: size, height: size)
            if let image = localAvatarImage {
                Image(nsImage: image)
                    .resizable()
                    .scaledToFill()
                    .frame(width: size, height: size)
                    .clipShape(Circle())
            } else if let remoteURL = remoteAvatarURL {
                AsyncImage(url: remoteURL) { phase in
                    switch phase {
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFill()
                            .frame(width: size, height: size)
                            .clipShape(Circle())
                    default:
                        fallbackIcon
                    }
                }
            } else {
                fallbackIcon
            }
        }
    }

    private var remoteAvatarURL: URL? {
        guard let url = normalizedAvatarURL else { return nil }
        return url.isFileURL ? nil : url
    }

    private var localAvatarImage: NSImage? {
        guard let url = normalizedAvatarURL, url.isFileURL else { return nil }
        return NSImage(contentsOf: url)
    }

    private var normalizedAvatarURL: URL? {
        guard let avatar, !avatar.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return nil
        }
        let raw = avatar.trimmingCharacters(in: .whitespacesAndNewlines)
        if raw.hasPrefix("http://") || raw.hasPrefix("https://") || raw.hasPrefix("file://") {
            return URL(string: raw)
        }
        let expanded = (raw as NSString).expandingTildeInPath
        return URL(fileURLWithPath: expanded)
    }

    @ViewBuilder
    private var fallbackIcon: some View {
        Image(systemName: resolvedIcon)
            .font(.system(size: symbolSize, weight: .semibold))
            .foregroundStyle(Color.accentColor)
    }

    private var resolvedIcon: String {
        let trimmed = icon?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return trimmed.isEmpty ? "person.crop.circle.fill" : trimmed
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
    @State private var iconName = "person.crop.circle.fill"
    @State private var avatar = ""
    @State private var category = ""
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
    private let iconSuggestions = [
        "person.crop.circle.fill",
        "megaphone.fill",
        "magnifyingglass.circle.fill",
        "doc.text.magnifyingglass",
        "chart.bar.fill",
        "chart.line.uptrend.xyaxis",
        "hammer.fill",
        "wrench.and.screwdriver.fill",
        "sparkles",
        "brain.head.profile",
        "book.closed.fill",
        "book.pages.fill",
        "target",
        "bolt.fill",
        "shield.fill",
        "briefcase.fill",
        "cart.fill",
        "bubble.left.and.bubble.right.fill",
        "paintpalette.fill",
        "gearshape.2.fill",
        "server.rack",
        "globe",
        "waveform.path.ecg",
        "graduationcap.fill",
    ]
    private let categorySuggestions = [
        "General", "Marketing", "Research", "Engineering", "Data",
        "Knowledge", "Operations", "Sales", "Support", "Design",
    ]

    private var agentAssignableSkills: [AstaSkillItem] {
        let agentIDs = Set(appState.agentsList.map { $0.id.lowercased() })
        let deduped = Dictionary(
            uniqueKeysWithValues: appState.skillsList.map { ($0.id.lowercased(), $0) }
        )
        return deduped.values
            .filter { item in
                let sid = item.id.lowercased()
                if sid.isEmpty { return false }
                if item.is_agent == true { return false }
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

                    HStack(alignment: .top, spacing: 14) {
                        VStack(alignment: .leading, spacing: 8) {
                            fieldLabel("Preview")
                            AgentAvatarCircle(icon: iconName, avatar: avatar, size: 58, symbolSize: 24)
                        }

                        VStack(alignment: .leading, spacing: 8) {
                            fieldLabel("Name")
                            TextField("e.g. Competitor Analyst", text: $name)
                                .textFieldStyle(.roundedBorder)

                            fieldLabel("Description")
                            TextField("e.g. Researches competitors and market trends", text: $description)
                                .textFieldStyle(.roundedBorder)

                            fieldLabel("Category")
                            HStack(spacing: 8) {
                                Menu {
                                    ForEach(categorySuggestions, id: \.self) { c in
                                        Button(c) { category = c }
                                    }
                                } label: {
                                    HStack(spacing: 4) {
                                        Image(systemName: "square.grid.2x2")
                                        Text("Pick category")
                                    }
                                }
                                .menuStyle(.borderlessButton)
                                TextField("e.g. Marketing", text: $category)
                                    .textFieldStyle(.roundedBorder)
                            }

                            fieldLabel("Avatar image (optional)")
                            TextField("https://... or /Users/.../avatar.png", text: $avatar)
                                .textFieldStyle(.roundedBorder)
                        }
                    }

                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(iconSuggestions, id: \.self) { icon in
                                Button {
                                    iconName = icon
                                } label: {
                                    ZStack {
                                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                                            .fill(iconName == icon ? Color.accentColor.opacity(0.18) : Color.primary.opacity(0.05))
                                            .frame(width: 34, height: 34)
                                        Image(systemName: icon)
                                            .font(.system(size: 14, weight: .semibold))
                                            .foregroundStyle(iconName == icon ? Color.accentColor : .secondary)
                                    }
                                }
                                .buttonStyle(.plain)
                            }
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
                                    if iconName == "person.crop.circle.fill" { iconName = template.icon }
                                    if category.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { category = template.category }
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
                name = a.name; description = a.description
                iconName = (a.icon?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false)
                    ? (a.icon ?? "person.crop.circle.fill")
                    : "person.crop.circle.fill"
                avatar = a.avatar ?? ""
                category = a.category ?? ""
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
        let trimCategory = category.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimAvatar = avatar.trimmingCharacters(in: .whitespacesAndNewlines)
        let allowedSkills = resolveAllowedSkillsForSave()
        if let existing {
            await appState.updateAgent(
                id: existing.id, name: trimName, description: description,
                emoji: "🤖",
                icon: iconName,
                avatar: trimAvatar,
                category: trimCategory,
                model: model, thinking: thinking, systemPrompt: systemPrompt,
                allowedSkills: allowedSkills
            )
        } else {
            await appState.createAgent(
                name: trimName, description: description,
                emoji: "🤖",
                icon: iconName,
                avatar: trimAvatar,
                category: trimCategory,
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
        let name: String
        let icon: String
        let category: String
        let description: String
        let prompt: String
    }

    private let promptTemplates: [PromptTemplate] = [
        PromptTemplate(
            name: "Competitor Analyst",
            icon: "magnifyingglass.circle.fill",
            category: "Research",
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
            icon: "hammer.fill",
            category: "Engineering",
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
            icon: "book.closed.fill",
            category: "Research",
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
            icon: "chart.bar.fill",
            category: "Data",
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
            icon: "doc.text.magnifyingglass",
            category: "Marketing",
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
