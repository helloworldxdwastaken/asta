// OpenClaw-style context/usage bar for the tray menu (token or system usage).
import SwiftUI
import AppKit

struct ContextUsageBar: View {
    let usedTokens: Int
    let contextTokens: Int
    var width: CGFloat? = nil
    var height: CGFloat = 6

    private static let okGreen: NSColor = .init(name: nil) { appearance in
        let base = NSColor.systemGreen
        let match = appearance.bestMatch(from: [.aqua, .darkAqua])
        if match == .darkAqua { return base }
        return base.blended(withFraction: 0.24, of: .black) ?? base
    }

    private static let trackFill: NSColor = .init(name: nil) { appearance in
        let match = appearance.bestMatch(from: [.aqua, .darkAqua])
        if match == .darkAqua { return NSColor.white.withAlphaComponent(0.14) }
        return NSColor.black.withAlphaComponent(0.12)
    }

    private static let trackStroke: NSColor = .init(name: nil) { appearance in
        let match = appearance.bestMatch(from: [.aqua, .darkAqua])
        if match == .darkAqua { return NSColor.white.withAlphaComponent(0.22) }
        return NSColor.black.withAlphaComponent(0.2)
    }

    private var clampedFractionUsed: Double {
        guard contextTokens > 0 else { return 0 }
        return min(1, max(0, Double(usedTokens) / Double(contextTokens)))
    }

    private var percentUsed: Int? {
        guard contextTokens > 0, usedTokens > 0 else { return nil }
        return min(100, Int(round(clampedFractionUsed * 100)))
    }

    private var tint: Color {
        guard let pct = percentUsed else { return .secondary }
        if pct >= 95 { return Color(nsColor: .systemRed) }
        if pct >= 80 { return Color(nsColor: .systemOrange) }
        if pct >= 60 { return Color(nsColor: .systemYellow) }
        return Color(nsColor: Self.okGreen)
    }

    var body: some View {
        let fraction = clampedFractionUsed
        Group {
            if let w = width, w > 0 {
                barBody(width: w, fraction: fraction)
                    .frame(width: w, height: height)
            } else {
                GeometryReader { proxy in
                    barBody(width: proxy.size.width, fraction: fraction)
                        .frame(width: proxy.size.width, height: height)
                }
                .frame(height: height)
            }
        }
        .accessibilityLabel("Usage")
        .accessibilityValue(contextTokens > 0 ? "\(Int(round(clampedFractionUsed * 100))) percent used" : "Unknown")
    }

    @ViewBuilder
    private func barBody(width: CGFloat, fraction: Double) -> some View {
        let radius = height / 2
        let trackFill = Color(nsColor: Self.trackFill)
        let trackStroke = Color(nsColor: Self.trackStroke)
        let fillWidth = max(1, floor(width * CGFloat(fraction)))

        ZStack(alignment: .leading) {
            RoundedRectangle(cornerRadius: radius, style: .continuous)
                .fill(trackFill)
                .overlay {
                    RoundedRectangle(cornerRadius: radius, style: .continuous)
                        .strokeBorder(trackStroke, lineWidth: 0.75)
                }
            RoundedRectangle(cornerRadius: radius, style: .continuous)
                .fill(tint)
                .frame(width: fillWidth)
                .mask { RoundedRectangle(cornerRadius: radius, style: .continuous) }
        }
    }
}
