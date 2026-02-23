import SwiftUI
import AppKit
import PDFKit
import UniformTypeIdentifiers
import AstaAPIClient

// MARK: - Chat message model

struct ChatMessage: Identifiable, Equatable {
    let id: String
    var role: String
    var content: String
    var thinkingContent: String?
    var toolsUsed: String?
    var provider: String?
    var isStreaming: Bool
    var phase: StreamPhase
    /// File attachments shown on user messages
    var attachments: [ChatAttachment]?

    enum StreamPhase: Equatable {
        case thinking
        case responding
        case done
    }

    init(
        id: String = UUID().uuidString,
        role: String,
        content: String,
        thinkingContent: String? = nil,
        toolsUsed: String? = nil,
        provider: String? = nil,
        isStreaming: Bool = false,
        phase: StreamPhase = .done,
        attachments: [ChatAttachment]? = nil
    ) {
        self.id = id
        self.role = role
        self.content = content
        self.thinkingContent = thinkingContent
        self.toolsUsed = toolsUsed
        self.provider = provider
        self.isStreaming = isStreaming
        self.phase = phase
        self.attachments = attachments
    }
}

// MARK: - File attachment model

struct ChatAttachment: Identifiable, Equatable {
    let id = UUID().uuidString
    let name: String
    let data: Data
    let mime: String
    let kind: Kind

    enum Kind: Equatable {
        case image
        case pdf
        case text
    }

    var isImage: Bool { kind == .image }

    var icon: String {
        switch kind {
        case .image: return "photo"
        case .pdf:   return "doc.richtext"
        case .text:  return "doc.text"
        }
    }

    /// Extract text content for non-image files to prepend to user message.
    var textContent: String? {
        switch kind {
        case .image: return nil
        case .text:  return String(data: data, encoding: .utf8)
        case .pdf:   return Self.extractPDFText(from: data)
        }
    }

    private static func extractPDFText(from data: Data) -> String? {
        guard let doc = PDFDocument(data: data) else { return nil }
        var text = ""
        for i in 0..<min(doc.pageCount, 50) {
            if let page = doc.page(at: i), let content = page.string {
                text += content + "\n"
            }
        }
        return text.isEmpty ? nil : text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - Factory

    static func from(url: URL) -> ChatAttachment? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        let ext = url.pathExtension.lowercased()
        let name = url.lastPathComponent
        let mime = mimeType(for: ext)
        let kind = fileKind(for: ext)
        return ChatAttachment(name: name, data: data, mime: mime, kind: kind)
    }

    static func from(data: Data, name: String, mime: String) -> ChatAttachment {
        let kind: Kind
        if mime.hasPrefix("image/") { kind = .image }
        else if mime == "application/pdf" { kind = .pdf }
        else { kind = .text }
        return ChatAttachment(name: name, data: data, mime: mime, kind: kind)
    }

    static func mimeType(for ext: String) -> String {
        switch ext {
        case "png":                         return "image/png"
        case "jpg", "jpeg":                 return "image/jpeg"
        case "gif":                         return "image/gif"
        case "webp":                        return "image/webp"
        case "pdf":                         return "application/pdf"
        case "txt":                         return "text/plain"
        case "md":                          return "text/markdown"
        case "json":                        return "application/json"
        case "csv":                         return "text/csv"
        case "xml":                         return "text/xml"
        case "html", "htm":                 return "text/html"
        case "py":                          return "text/x-python"
        case "js":                          return "text/javascript"
        case "ts":                          return "text/typescript"
        case "swift":                       return "text/x-swift"
        case "rs":                          return "text/x-rust"
        case "go":                          return "text/x-go"
        case "java":                        return "text/x-java"
        case "c", "h":                      return "text/x-c"
        case "cpp", "cc", "cxx", "hpp":     return "text/x-c++src"
        case "yaml", "yml":                 return "text/yaml"
        case "toml":                        return "text/toml"
        case "sh", "bash", "zsh":           return "text/x-shellscript"
        case "sql":                         return "text/x-sql"
        case "log":                         return "text/plain"
        default:                            return "application/octet-stream"
        }
    }

    static func fileKind(for ext: String) -> Kind {
        let imageExts: Set = ["png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "tif", "heic"]
        if imageExts.contains(ext) { return .image }
        if ext == "pdf" { return .pdf }
        return .text
    }

    /// All file types we accept in the open panel / drag-drop.
    static var acceptedTypes: [UTType] {
        [
            .png, .jpeg, .gif, .webP, .bmp, .tiff, .heic,
            .pdf,
            .plainText, .utf8PlainText,
            .json, .xml, .yaml, .html,
            .sourceCode, .swiftSource, .cSource, .cPlusPlusSource,
            .pythonScript, .javaScript, .shellScript,
            UTType(filenameExtension: "md") ?? .plainText,
            UTType(filenameExtension: "csv") ?? .plainText,
            UTType(filenameExtension: "log") ?? .plainText,
            UTType(filenameExtension: "toml") ?? .plainText,
            UTType(filenameExtension: "rs") ?? .plainText,
            UTType(filenameExtension: "go") ?? .plainText,
            UTType(filenameExtension: "ts") ?? .plainText,
            UTType(filenameExtension: "tsx") ?? .plainText,
            UTType(filenameExtension: "jsx") ?? .plainText,
            UTType(filenameExtension: "sql") ?? .plainText,
        ]
    }
}

// MARK: - Flow layout for tool pills

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrange(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrange(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y), proposal: .unspecified)
        }
    }

    private func arrange(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, positions: [CGPoint]) {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var currentX: CGFloat = 0
        var currentY: CGFloat = 0
        var lineHeight: CGFloat = 0
        var totalHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentX + size.width > maxWidth && currentX > 0 {
                currentX = 0
                currentY += lineHeight + spacing
                lineHeight = 0
            }
            positions.append(CGPoint(x: currentX, y: currentY))
            lineHeight = max(lineHeight, size.height)
            currentX += size.width + spacing
            totalHeight = currentY + lineHeight
        }
        return (CGSize(width: maxWidth, height: totalHeight), positions)
    }
}

// MARK: - Thinking pulse animation

struct ThinkingPulse: View {
    @State private var isAnimating = false

    var body: some View {
        Circle()
            .fill(Color.purple.opacity(0.6))
            .frame(width: 6, height: 6)
            .scaleEffect(isAnimating ? 1.2 : 0.8)
            .opacity(isAnimating ? 0.4 : 1.0)
            .animation(.easeInOut(duration: 0.6).repeatForever(autoreverses: true), value: isAnimating)
            .onAppear { isAnimating = true }
    }
}

// MARK: - Bouncing dot for loading

struct BounceDot: View {
    let delay: Double
    @State private var isAnimating = false

    var body: some View {
        Circle()
            .fill(Color.secondary.opacity(0.5))
            .frame(width: 6, height: 6)
            .offset(y: isAnimating ? -6 : 0)
            .animation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true), value: isAnimating)
            .onAppear {
                DispatchQueue.main.asyncAfter(deadline: .now() + delay) { isAnimating = true }
            }
    }
}

// MARK: - Chat text field (multi-line, Enter sends, Shift+Enter newline)

struct ChatTextField: NSViewRepresentable {
    @Binding var text: String
    @Binding var requestFocus: Bool
    var onSend: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSScrollView()
        let textView = NSTextView()

        textView.delegate = context.coordinator
        textView.isRichText = false
        textView.allowsUndo = true
        textView.isEditable = true
        textView.isSelectable = true
        textView.drawsBackground = false
        textView.font = .systemFont(ofSize: 14)
        textView.textColor = .labelColor
        textView.insertionPointColor = .labelColor
        textView.textContainerInset = NSSize(width: 8, height: 8)
        textView.textContainer?.lineFragmentPadding = 4
        textView.textContainer?.widthTracksTextView = true
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.setContentHuggingPriority(.defaultLow, for: .horizontal)

        scrollView.documentView = textView
        scrollView.hasVerticalScroller = false
        scrollView.hasHorizontalScroller = false
        scrollView.drawsBackground = false
        scrollView.autohidesScrollers = true

        context.coordinator.textView = textView

        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? NSTextView else { return }
        if textView.string != text {
            textView.string = text
        }
        if requestFocus {
            DispatchQueue.main.async {
                textView.window?.makeFirstResponder(textView)
                requestFocus = false
            }
        }
    }

    class Coordinator: NSObject, NSTextViewDelegate {
        var parent: ChatTextField
        weak var textView: NSTextView?

        init(_ parent: ChatTextField) { self.parent = parent }

        func textDidChange(_ notification: Notification) {
            guard let tv = notification.object as? NSTextView else { return }
            parent.text = tv.string
        }

        func textView(_ textView: NSTextView, doCommandBy commandSelector: Selector) -> Bool {
            if commandSelector == #selector(NSResponder.insertNewline(_:)) {
                // Shift+Enter or Option+Enter → actual newline
                let flags = NSApp.currentEvent?.modifierFlags ?? []
                if flags.contains(.shift) || flags.contains(.option) {
                    textView.insertNewlineIgnoringFieldEditor(nil)
                    return true
                }
                // Plain Enter → send
                parent.onSend()
                return true
            }
            return false
        }
    }
}

// MARK: - Unused legacy shape (kept for compatibility if referenced elsewhere)

struct BubbleShape: Shape {
    var isUser: Bool
    func path(in rect: CGRect) -> Path {
        Path(roundedRect: rect, cornerRadius: isUser ? 18 : 12)
    }
}
