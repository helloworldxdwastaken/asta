import { useState, useEffect } from "react";
import { login as apiLogin, register as apiRegister } from "../../lib/api";
import { setAuth } from "../../lib/auth";
import { getVersion } from "@tauri-apps/api/app";

interface Props { onLogin: () => void; }

/* ── 8-bit pixel sprites (pure CSS/SVG, no external assets) ─────────────── */

function PixelSprite({ shape, color, size, style }: {
  shape: "cross" | "diamond" | "heart" | "star" | "block" | "arrow";
  color: string; size: number; style?: React.CSSProperties;
}) {
  const px = size;
  const sprites: Record<string, React.ReactNode> = {
    cross: (
      <svg width={px * 5} height={px * 5} viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
        <rect x="2" y="0" width="1" height="1" fill={color} />
        <rect x="0" y="2" width="1" height="1" fill={color} />
        <rect x="1" y="1" width="1" height="1" fill={color} />
        <rect x="2" y="2" width="1" height="1" fill={color} />
        <rect x="3" y="1" width="1" height="1" fill={color} />
        <rect x="4" y="2" width="1" height="1" fill={color} />
        <rect x="2" y="4" width="1" height="1" fill={color} />
        <rect x="1" y="3" width="1" height="1" fill={color} />
        <rect x="3" y="3" width="1" height="1" fill={color} />
      </svg>
    ),
    diamond: (
      <svg width={px * 5} height={px * 5} viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
        <rect x="2" y="0" width="1" height="1" fill={color} />
        <rect x="1" y="1" width="1" height="1" fill={color} />
        <rect x="3" y="1" width="1" height="1" fill={color} />
        <rect x="0" y="2" width="1" height="1" fill={color} />
        <rect x="4" y="2" width="1" height="1" fill={color} />
        <rect x="1" y="3" width="1" height="1" fill={color} />
        <rect x="3" y="3" width="1" height="1" fill={color} />
        <rect x="2" y="4" width="1" height="1" fill={color} />
      </svg>
    ),
    heart: (
      <svg width={px * 7} height={px * 6} viewBox="0 0 7 6" style={{ imageRendering: "pixelated" }}>
        <rect x="1" y="0" width="2" height="1" fill={color} />
        <rect x="4" y="0" width="2" height="1" fill={color} />
        <rect x="0" y="1" width="7" height="1" fill={color} />
        <rect x="0" y="2" width="7" height="1" fill={color} />
        <rect x="1" y="3" width="5" height="1" fill={color} />
        <rect x="2" y="4" width="3" height="1" fill={color} />
        <rect x="3" y="5" width="1" height="1" fill={color} />
      </svg>
    ),
    star: (
      <svg width={px * 5} height={px * 5} viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
        <rect x="2" y="0" width="1" height="1" fill={color} />
        <rect x="0" y="2" width="5" height="1" fill={color} />
        <rect x="2" y="1" width="1" height="1" fill={color} />
        <rect x="1" y="1" width="1" height="1" fill={color} opacity="0.5" />
        <rect x="3" y="1" width="1" height="1" fill={color} opacity="0.5" />
        <rect x="2" y="3" width="1" height="1" fill={color} />
        <rect x="1" y="4" width="1" height="1" fill={color} />
        <rect x="3" y="4" width="1" height="1" fill={color} />
      </svg>
    ),
    block: (
      <svg width={px * 3} height={px * 3} viewBox="0 0 3 3" style={{ imageRendering: "pixelated" }}>
        <rect width="3" height="3" fill={color} />
        <rect x="0" y="0" width="1" height="1" fill="white" opacity="0.3" />
      </svg>
    ),
    arrow: (
      <svg width={px * 5} height={px * 5} viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
        <rect x="2" y="0" width="1" height="1" fill={color} />
        <rect x="1" y="1" width="3" height="1" fill={color} />
        <rect x="0" y="2" width="5" height="1" fill={color} />
        <rect x="2" y="3" width="1" height="1" fill={color} />
        <rect x="2" y="4" width="1" height="1" fill={color} />
      </svg>
    ),
  };
  return (
    <div className="pixel-block absolute pointer-events-none" style={style}>
      {sprites[shape]}
    </div>
  );
}

export default function LoginPage({ onLogin }: Props) {
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [registered, setRegistered] = useState(false);
  const [version, setVersion] = useState("");

  useEffect(() => { getVersion().then(setVersion).catch(() => {}); }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return;
    if (mode === "register" && password !== confirmPassword) {
      setError("Passwords don't match");
      return;
    }
    if (mode === "register" && password.length < 4) {
      setError("Password must be at least 4 characters");
      return;
    }
    setLoading(true);
    setError("");
    try {
      if (mode === "register") {
        await apiRegister(username.trim(), password);
        setRegistered(true);
        setMode("signin");
        setPassword("");
        setConfirmPassword("");
        setLoading(false);
        return;
      }
      const res = await apiLogin(username.trim(), password);
      setAuth(res.access_token, {
        id: res.user.id,
        username: res.user.username,
        role: res.user.role as "admin" | "user",
      });
      onLogin();
    } catch (err: any) {
      const msg = err?.message || "";
      if (msg.includes("401")) setError("Invalid username or password");
      else if (msg.includes("409")) setError("Username already taken");
      else if (msg.includes("403")) setError("Registration is disabled");
      else setError(mode === "signin" ? "Connection error" : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  function switchMode(m: "signin" | "register") {
    setMode(m);
    setError("");
    setRegistered(false);
    setConfirmPassword("");
  }

  return (
    <div className="relative flex items-center justify-center h-screen bg-surface grain select-none overflow-hidden">
      {/* Scanlines */}
      <div
        className="absolute inset-0 pointer-events-none z-10"
        style={{
          background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)",
          mixBlendMode: "multiply",
        }}
      />

      {/* ── Floating pixel sprites ─────────────────────────────────────────── */}
      <PixelSprite shape="cross" color="var(--accent)" size={4}
        style={{ top: "12%", left: "8%", animationDelay: "0s", animationDuration: "7s" }} />
      <PixelSprite shape="heart" color="var(--accent-end, #FF3D7F)" size={3}
        style={{ top: "22%", right: "10%", animationDelay: "1.2s", animationDuration: "8s" }} />
      <PixelSprite shape="diamond" color="var(--accent)" size={3}
        style={{ bottom: "18%", left: "12%", animationDelay: "2.4s", animationDuration: "9s" }} />
      <PixelSprite shape="star" color="#FFD700" size={4}
        style={{ top: "35%", left: "5%", animationDelay: "0.8s", animationDuration: "6.5s" }} />
      <PixelSprite shape="block" color="var(--accent)" size={5}
        style={{ bottom: "30%", right: "7%", animationDelay: "3s", animationDuration: "7.5s" }} />
      <PixelSprite shape="arrow" color="var(--accent-end, #FF3D7F)" size={3}
        style={{ top: "60%", left: "6%", animationDelay: "1.8s", animationDuration: "8.5s" }} />
      <PixelSprite shape="cross" color="#FFD700" size={3}
        style={{ bottom: "12%", right: "12%", animationDelay: "4s", animationDuration: "7s" }} />
      <PixelSprite shape="heart" color="var(--accent)" size={2}
        style={{ top: "8%", right: "22%", animationDelay: "2s", animationDuration: "9.5s" }} />
      <PixelSprite shape="block" color="var(--accent-end, #FF3D7F)" size={4}
        style={{ top: "50%", right: "5%", animationDelay: "0.5s", animationDuration: "6s" }} />
      <PixelSprite shape="star" color="var(--accent)" size={3}
        style={{ bottom: "8%", left: "25%", animationDelay: "3.5s", animationDuration: "8s" }} />
      <PixelSprite shape="diamond" color="#FFD700" size={2}
        style={{ top: "15%", left: "30%", animationDelay: "1.5s", animationDuration: "10s" }} />
      <PixelSprite shape="arrow" color="var(--accent)" size={3}
        style={{ bottom: "25%", right: "20%", animationDelay: "2.8s", animationDuration: "7.2s" }} />

      {/* ── Ambient glow orbs ──────────────────────────────────────────────── */}
      <div className="absolute w-64 h-64 rounded-full opacity-[0.04] pointer-events-none"
        style={{ background: "radial-gradient(circle, var(--accent), transparent 70%)", top: "10%", left: "-5%", animation: "orb-float 12s ease-in-out infinite" }} />
      <div className="absolute w-48 h-48 rounded-full opacity-[0.03] pointer-events-none"
        style={{ background: "radial-gradient(circle, var(--accent-end, #FF3D7F), transparent 70%)", bottom: "5%", right: "-3%", animation: "orb-float 15s ease-in-out infinite reverse" }} />

      {/* ── Main card ──────────────────────────────────────────────────────── */}
      <div className="relative z-20 animate-scale-in" style={{ width: 360 }}>
        {/* Logo + Title */}
        <div className="flex flex-col items-center mb-8">
          <div className="relative mb-4">
            <img
              src="/appicon.png"
              alt="Asta"
              className="w-20 h-20 rounded-2xl"
              style={{ boxShadow: "0 8px 32px rgba(255,107,44,0.15), 0 0 0 1px rgba(255,255,255,0.06)" }}
            />
          </div>
          <h1 className="text-2xl font-bold text-label tracking-tight">Asta</h1>
          <p className="text-11 text-label-tertiary mt-1 font-mono tracking-widest uppercase">
            {mode === "signin" ? "Welcome back" : "Create account"}
          </p>
        </div>

        {/* Glass form card */}
        <div
          className="rounded-2xl p-6 border border-separator"
          style={{
            background: "var(--surface-glass)",
            backdropFilter: "blur(20px) saturate(160%)",
            WebkitBackdropFilter: "blur(20px) saturate(160%)",
            boxShadow: "0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04)",
          }}
        >
          {/* Mode toggle */}
          <div className="flex gap-1 bg-white/[.04] rounded-mac p-1 mb-5 border border-separator">
            {(["signin", "register"] as const).map(m => (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                className={`flex-1 py-2 rounded-[8px] text-13 font-medium transition-all duration-200 ${
                  mode === m
                    ? "bg-white/[.1] text-label shadow-sm"
                    : "text-label-tertiary hover:text-label-secondary"
                }`}
              >
                {m === "signin" ? "Sign In" : "Register"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              autoFocus
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="Username"
              autoComplete="username"
              className="w-full bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3.5 py-2.5 text-13 text-label outline-none focus:border-accent/50 transition-colors placeholder:text-label-tertiary"
            />
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              className="w-full bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3.5 py-2.5 text-13 text-label outline-none focus:border-accent/50 transition-colors placeholder:text-label-tertiary"
            />
            {mode === "register" && (
              <input
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="Confirm password"
                autoComplete="new-password"
                className="w-full bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3.5 py-2.5 text-13 text-label outline-none focus:border-accent/50 transition-colors placeholder:text-label-tertiary animate-slide-up"
              />
            )}

            {error && (
              <p className="text-12 text-danger text-center py-1 animate-fade-in">{error}</p>
            )}
            {registered && !error && (
              <p className="text-12 text-center py-1 animate-fade-in" style={{ color: "#4ade80" }}>
                Account created — sign in below
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !username.trim() || !password || (mode === "register" && !confirmPassword)}
              className="w-full py-2.5 text-14 accent-gradient text-white rounded-mac font-semibold transition-all duration-200 hover:opacity-90 active:scale-[0.98] disabled:opacity-40 shadow-glow-sm"
            >
              {loading
                ? (mode === "signin" ? "Signing in..." : "Creating account...")
                : (mode === "signin" ? "Sign In" : "Create Account")}
            </button>
          </form>
        </div>

        {/* Version */}
        {version && (
          <p className="text-center text-[10px] text-label-tertiary mt-5 font-mono tracking-widest uppercase opacity-40">
            v{version}
          </p>
        )}
      </div>
    </div>
  );
}
