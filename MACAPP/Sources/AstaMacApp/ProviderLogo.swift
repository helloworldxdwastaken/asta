import SwiftUI
import AppKit

// MARK: - Brand colours (used for letter-based fallbacks)

private enum Brand {
static let github      = Color(red: 0.086, green: 0.086, blue: 0.086) // near-black
    static let vercel      = Color(red: 0.0,   green: 0.0,   blue: 0.0  ) // black
}

// MARK: - Bundle image loader

/// Loads a provider image from the app bundle's Resources/providers/ folder.
private struct BundleImageLogo: View {
    let file: String   // filename without extension
    let ext: String    // file extension, e.g. "svg" or "png"
    let size: CGFloat

    @State private var nsImage: NSImage? = nil

    var body: some View {
        Group {
            if let img = nsImage {
                Image(nsImage: img)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
            } else {
                // Placeholder while loading (or if bundle lookup fails)
                RoundedRectangle(cornerRadius: size * 0.22, style: .continuous)
                    .fill(Color.secondary.opacity(0.15))
                    .overlay(
                        Image(systemName: "cpu")
                            .font(.system(size: size * 0.4))
                            .foregroundStyle(Color.secondary)
                    )
            }
        }
        .frame(width: size, height: size)
        .onAppear { nsImage = loadImage() }
    }

    private func loadImage() -> NSImage? {
        // Try Resources/providers/ subfolder first (release build)
        if let url = Bundle.main.url(forResource: file, withExtension: ext, subdirectory: "providers") {
            return NSImage(contentsOf: url)
        }
        // Fallback: try flat Resources/ or anywhere in main bundle
        if let url = Bundle.main.url(forResource: file, withExtension: ext) {
            return NSImage(contentsOf: url)
        }
        return nil
    }
}

// MARK: - ProviderLogo

/// Brand-coloured logo badge for a given provider/service ID.
/// Uses real asset images when available (from the app bundle), otherwise falls back to drawn logos.
struct ProviderLogo: View {
    let provider: String
    var size: CGFloat = 28

    var body: some View {
        Group {
            switch provider.lowercased() {
            case "claude", "anthropic":
                BundleImageLogo(file: "calude_anthropic", ext: "png", size: size)
            case "openai":
                BundleImageLogo(file: "openai_chagpt", ext: "svg", size: size)
            case "google", "gemini":
                BundleImageLogo(file: "Google_Gemini_icon_2025", ext: "svg", size: size)
            case "groq":
                BundleImageLogo(file: "groqlogo", ext: "svg", size: size)
            case "openrouter":
                BundleImageLogo(file: "openrouter-icon", ext: "svg", size: size)
            case "ollama":
                BundleImageLogo(file: "ollama-icon", ext: "svg", size: size)
            case "telegram":
                BundleImageLogo(file: "Telegram_logo", ext: "svg", size: size)
            case "notion":
                BundleImageLogo(file: "Notion-logo", ext: "svg", size: size)
            case "giphy":
                BundleImageLogo(file: "giphylogo", ext: "svg", size: size)
            case "spotify":
                BundleImageLogo(file: "Spotify_icon", ext: "svg", size: size)
            case "pingram":
                BundleImageLogo(file: "pingramlogo", ext: "png", size: size)
            case "github":
                LetterLogo(letter: "G", color: Brand.github, size: size)
            case "vercel":
                LetterLogo(letter: "▲", color: Brand.vercel, size: size)
            default:
                DefaultProviderLogo(name: provider, size: size)
            }
        }
    }
}

// MARK: - Generic letter logo

struct LetterLogo: View {
    let letter: String
    let color: Color
    let size: CGFloat
    var textColor: Color = .white
    var round: Bool = false

    var body: some View {
        ZStack {
            if round {
                Circle().fill(color)
            } else {
                RoundedRectangle(cornerRadius: size * 0.22, style: .continuous).fill(color)
            }
            Text(letter)
                .font(.system(size: size * (letter.count > 1 ? 0.34 : 0.46), weight: .bold, design: .rounded))
                .foregroundStyle(textColor)
        }
        .frame(width: size, height: size)
    }
}

// MARK: - Default fallback

private struct DefaultProviderLogo: View {
    let name: String
    let size: CGFloat
    private var initial: String { name.prefix(1).uppercased() }
    private var color: Color {
        let h = abs(name.hashValue) % 360
        return Color(hue: Double(h) / 360.0, saturation: 0.6, brightness: 0.65)
    }
    var body: some View {
        LetterLogo(letter: initial, color: color, size: size)
    }
}
