// Maps provider/service IDs to their icon files in /providers/
// Matches ProviderLogo.swift from the Mac app

const ICON_MAP: Record<string, { file: string; ext: string }> = {
  claude:      { file: "calude_anthropic", ext: "png" },
  anthropic:   { file: "calude_anthropic", ext: "png" },
  openai:      { file: "openai_chagpt",   ext: "svg" },
  google:      { file: "Google_Gemini_icon_2025", ext: "svg" },
  gemini:      { file: "Google_Gemini_icon_2025", ext: "svg" },
  groq:        { file: "groqlogo",         ext: "svg" },
  openrouter:  { file: "openrouter-icon",  ext: "svg" },
  ollama:      { file: "ollama-icon",      ext: "svg" },
  telegram:    { file: "Telegram_logo",    ext: "svg" },
  notion:      { file: "Notion-logo",      ext: "svg" },
  giphy:       { file: "giphylogo",        ext: "svg" },
  spotify:     { file: "Spotify_icon",     ext: "svg" },
  pingram:     { file: "pingramlogo",      ext: "png" },
  pexels:      { file: "pexels",           ext: "svg" },
  pixabay:     { file: "pixabay",          ext: "svg" },
  youtube:     { file: "youtube",          ext: "svg" },
  github:      { file: "github",          ext: "svg" },
  huggingface: { file: "huggingface",    ext: "svg" },
};

// Hash-based HSV colour for unknown providers (matches Swift DefaultProviderLogo)
function hashColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  const hue = Math.abs(h) % 360;
  return `hsl(${hue}, 55%, 55%)`;
}

interface Props {
  provider: string;
  size?: number;
  className?: string;
}

export default function ProviderLogo({ provider, size = 28, className }: Props) {
  const key = provider.toLowerCase();
  const icon = ICON_MAP[key];

  if (icon) {
    return (
      <img
        src={`/providers/${icon.file}.${icon.ext}`}
        alt={provider}
        width={size}
        height={size}
        className={`object-contain ${className ?? ""}`}
        style={{ width: size, height: size }}
        draggable={false}
      />
    );
  }

  // Letter-based fallback
  const letter = provider.charAt(0).toUpperCase();
  const bg = hashColor(provider);

  return (
    <div
      className={`flex items-center justify-center text-white font-bold shrink-0 ${className ?? ""}`}
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.22,
        backgroundColor: bg,
        fontSize: size * 0.46,
        lineHeight: 1,
      }}
    >
      {letter}
    </div>
  );
}
