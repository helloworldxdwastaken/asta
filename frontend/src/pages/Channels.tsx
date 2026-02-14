import { useState, useEffect, useCallback } from "react";
import type { Status } from "../api/client";
import { api } from "../api/client";

function WhatsAppQr({ status }: { status: Status | null }) {
    const [state, setState] = useState<{ connected?: boolean; qr?: string | null; error?: string } | null>(null);
    const [allowedNumbers, setAllowedNumbers] = useState("");
    const [ownerNumber, setOwnerNumber] = useState("");
    const [selfChatOnly, setSelfChatOnly] = useState(false);
    const [policySaving, setPolicySaving] = useState(false);
    const [policyMsg, setPolicyMsg] = useState<string | null>(null);

    const fetchQr = useCallback(() => {
        api.whatsappQr()
            .then(setState)
            .catch((e) => setState({ connected: false, qr: null, error: e.message }));
    }, []);

    const fetchPolicy = useCallback(() => {
        api.whatsappPolicy()
            .then((p) => {
                setAllowedNumbers((p.allowed_numbers || []).join(", "));
                setOwnerNumber(p.owner_number || "");
                setSelfChatOnly(!!p.self_chat_only);
            })
            .catch(() => { });
    }, []);

    useEffect(() => {
        fetchQr();
        fetchPolicy();
        const t = setInterval(fetchQr, 4000);
        return () => clearInterval(t);
    }, [fetchQr, fetchPolicy]);

    const savePolicy = async () => {
        setPolicySaving(true);
        setPolicyMsg(null);
        try {
            const out = await api.setWhatsappPolicy({
                allowed_numbers: allowedNumbers,
                self_chat_only: selfChatOnly,
                owner_number: ownerNumber,
            });
            setAllowedNumbers((out.allowed_numbers || []).join(", "));
            setOwnerNumber(out.owner_number || "");
            setSelfChatOnly(!!out.self_chat_only);
            setPolicyMsg("WhatsApp policy saved.");
        } catch (e) {
            setPolicyMsg("Error: " + ((e as Error).message || String(e)));
        } finally {
            setPolicySaving(false);
        }
    };
    const ownerMissing = selfChatOnly && !ownerNumber.trim();

    const wa = status?.channels?.whatsapp;
    const waBadge = (() => {
        if (!wa?.configured) return { label: "Not configured", tone: "neutral" as const };
        if (wa.connected || state?.connected) return { label: "Connected", tone: "ok" as const };
        if (!wa.reachable) return { label: "Bridge offline", tone: "warn" as const };
        if (wa.has_qr || state?.qr) return { label: "Scan QR", tone: "pending" as const };
        if (wa.connecting) return { label: "Connecting", tone: "pending" as const };
        return { label: "Disconnected", tone: "warn" as const };
    })();

    return (
        <div className="channel-section">
            <div className="channel-header">
                <div className="channel-icon whatsapp-icon">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" /></svg>
                </div>
                <div>
                    <h3>WhatsApp (Beta)</h3>
                    <p className="help">Best for quick voice notes and daily replies.</p>
                </div>
                <span className={`status-badge ${waBadge.tone === "ok" ? "ok" : waBadge.tone === "warn" ? "warn" : waBadge.tone === "pending" ? "pending" : ""}`}>{waBadge.label}</span>
            </div>

            <div className="channel-body">
                {state?.error && !state?.qr && (
                    <div className="alert alert-error">
                        {state.error} <br />Run: <code>cd services/whatsapp && npm install && npm run start</code>
                    </div>
                )}

                {!state?.connected && state?.qr && (
                    <div className="qr-container">
                        <img src={state.qr} alt="WhatsApp QR" className="qr-code" />
                        <p className="help">Open WhatsApp → Settings → Linked devices → Link a device</p>
                    </div>
                )}

                {!state?.connected && !state?.qr && !state?.error && (
                    <p className="help">Loading QR code... Ensure the bridge service is running.</p>
                )}

                {state?.connected && (
                    <div className="channel-connected-info">
                        <p>Your WhatsApp (Beta) account is connected. Asta can read and reply to messages.</p>
                        <button
                            className="btn btn-danger"
                            style={{ marginTop: '1rem' }}
                            onClick={() => {
                                if (confirm("Disconnect WhatsApp? You will need to scan QR again.")) {
                                    api.whatsappLogout().then(() => fetchQr());
                                }
                            }}
                        >
                            Disconnect
                        </button>
                    </div>
                )}

                <div className="field" style={{ marginTop: "1rem" }}>
                    <label className="label" htmlFor="wa-owner">Owner number (for self-chat mode)</label>
                    <input
                        id="wa-owner"
                        type="text"
                        className="input"
                        placeholder="e.g. +15551234567"
                        value={ownerNumber}
                        onChange={(e) => setOwnerNumber(e.target.value)}
                    />
                    <p className="help">Use your full number with country code (E.164 style). Spaces and + are fine; Asta normalizes to digits.</p>
                </div>

                <div className="field" style={{ marginTop: "0.75rem" }}>
                    <label className="label" htmlFor="wa-allow">Allowed sender numbers</label>
                    <input
                        id="wa-allow"
                        type="text"
                        className="input"
                        placeholder="+15551234567, +15550001111"
                        value={allowedNumbers}
                        onChange={(e) => setAllowedNumbers(e.target.value)}
                    />
                    <p className="help">Use full numbers with country code, separated by comma or newline. Leave empty to allow all senders (unless self-chat-only is enabled).</p>
                </div>

                <div className="field" style={{ marginTop: "0.75rem" }}>
                    <label style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
                        <input
                            type="checkbox"
                            checked={selfChatOnly}
                            onChange={(e) => setSelfChatOnly(e.target.checked)}
                        />
                        Self chat only (reply only to owner number)
                    </label>
                </div>
                {ownerMissing && (
                    <div className="alert" style={{ marginTop: "0.5rem" }}>
                        Self-chat-only is enabled but owner number is empty. Add owner number to avoid all inbound messages being ignored.
                    </div>
                )}

                <div className="actions" style={{ marginTop: "0.75rem" }}>
                    <button type="button" className="btn btn-secondary" onClick={savePolicy} disabled={policySaving}>
                        {policySaving ? "Saving…" : "Save policy"}
                    </button>
                </div>
                {policyMsg && (
                    <div className={policyMsg.startsWith("Error:") ? "alert alert-error" : "alert"} style={{ marginTop: "0.75rem" }}>
                        {policyMsg}
                    </div>
                )}
            </div>
        </div>
    );
}

function TelegramSettings({ keysStatus, onSaved, status }: { keysStatus: Record<string, boolean>; onSaved: () => void; status: Status | null }) {
    const [token, setToken] = useState("");
    const [saving, setSaving] = useState(false);
    const [msg, setMsg] = useState<string | null>(null);
    const isSet = keysStatus["telegram_bot_token"];

    const save = async () => {
        if (!token.trim()) return;
        setSaving(true);
        setMsg(null);
        try {
            await api.setSettingsKeys({ telegram_bot_token: token.trim() });
            onSaved();
            setToken("");
            setMsg("Token saved. Restart the backend for the bot to connect.");
        } catch (e) {
            setMsg("Error: " + ((e as Error).message || String(e)));
        } finally {
            setSaving(false);
        }
    };

    const tgConfigured = !!status?.channels?.telegram?.configured || isSet;
    return (
        <div className="channel-section">
            <div className="channel-header">
                <div className="channel-icon telegram-icon">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" /></svg>
                </div>
                <div>
                    <h3>Telegram</h3>
                    <p className="help">Most stable channel for everyday chat.</p>
                </div>
                <span className={`status-badge ${tgConfigured ? "ok" : ""}`}>{tgConfigured ? "Ready" : "Not configured"}</span>
            </div>

            <div className="channel-body">
                <p className="help">
                    Create a bot at <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="link">t.me/BotFather</a>.
                </p>
                <div className="alert" style={{ marginTop: "0.75rem" }}>
                    Bot menu commands: <code>/start</code>, <code>/status</code>, <code>/exec_mode</code>, <code>/thinking</code>, <code>/reasoning</code>. If they don&apos;t appear, restart backend and reopen the bot chat.
                </div>

                <div className="field-row" style={{ marginTop: '1rem' }}>
                    <input
                        type="password"
                        placeholder={isSet ? "Leave blank to keep current" : "Paste token from @BotFather"}
                        value={token}
                        onChange={(e) => setToken(e.target.value)}
                        className="input"
                        style={{ maxWidth: '100%' }}
                    />
                    <button type="button" onClick={save} disabled={saving || !token.trim()} className="btn btn-primary">
                        {saving ? "Saving…" : "Save"}
                    </button>
                    {isSet && (
                        <button
                            type="button"
                            onClick={() => {
                                if (confirm("Remove Telegram token? The bot will stop working.")) {
                                    setToken("");
                                    api.setSettingsKeys({ telegram_bot_token: "" }).then(() => {
                                        onSaved();
                                        setMsg("Token removed. Restart backend to fully stop the bot.");
                                    });
                                }
                            }}
                            className="btn btn-danger"
                            style={{ marginLeft: '0.5rem' }}
                        >
                            Remove Token
                        </button>
                    )}
                </div>

                {msg && <div className={msg.startsWith("Error:") ? "alert alert-error" : "alert"} style={{ marginTop: "0.75rem" }}>{msg}</div>}
            </div>
        </div>
    );
}

export default function Channels() {
    const [keysStatus, setKeysStatus] = useState<Record<string, boolean>>({});
    const [status, setStatus] = useState<Status | null>(null);

    useEffect(() => {
        api.getSettingsKeys().then(setKeysStatus);
        api.status().then(setStatus).catch(() => setStatus(null));
        const t = setInterval(() => {
            api.status().then(setStatus).catch(() => setStatus(null));
        }, 5000);
        return () => clearInterval(t);
    }, []);

    const refreshKeys = () => api.getSettingsKeys().then(setKeysStatus);

    return (
        <div className="channels-page">
            <h1 className="page-title">Channels</h1>
            <p className="page-subtitle">Connect one channel first, test with a simple “hi”, then enable extra policies.</p>

            <div className="channel-quickstart">
                <strong>Quick start</strong>
                <ol>
                    <li>Connect Telegram or scan WhatsApp QR.</li>
                    <li>Send “hi” to confirm replies work.</li>
                    <li>Only then enable allowlists / self-chat policy.</li>
                </ol>
            </div>

            <div className="channels-grid">
                <WhatsAppQr status={status} />
                <TelegramSettings keysStatus={keysStatus} onSaved={refreshKeys} status={status} />
            </div>

            <style>{`
        .channels-page {
            max-width: 900px;
        }
        .page-subtitle {
            color: var(--muted);
            margin-bottom: 1rem;
        }
        .channel-quickstart {
            border: 1px solid var(--border);
            background: var(--surface);
            border-radius: 10px;
            padding: 0.75rem 1rem;
            margin-bottom: 1.25rem;
        }
        .channel-quickstart strong {
            display: block;
            margin-bottom: 0.4rem;
            font-size: 0.9rem;
        }
        .channel-quickstart ol {
            margin: 0;
            padding-left: 1.1rem;
            color: var(--muted);
            font-size: 0.86rem;
        }
        .channels-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1.5rem;
        }
        .channel-section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
        }
        .channel-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }
        .channel-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        .whatsapp-icon { background: #25D366; }
        .telegram-icon { background: #229ED9; }
        
        .channel-header h3 { margin: 0; font-size: 1.1rem; }
        .channel-header .help { margin: 0; font-size: 0.85rem; }
        
        .status-badge {
            margin-left: auto;
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 12px;
            background: var(--bg-hover);
            color: var(--muted);
        }
        .status-badge.ok {
            background: rgba(var(--rgb-success), 0.15);
            color: var(--success);
        }
        .status-badge.warn {
            background: rgba(249, 115, 22, 0.12);
            color: #c2410c;
        }
        .status-badge.pending {
            background: rgba(var(--rgb-accent), 0.12);
            color: var(--accent);
        }
        
        .qr-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            gap: 1rem;
            background: white;
            padding: 1rem;
            border-radius: 8px;
        }
        .qr-code {
            width: 200px;
            height: 200px;
        }
        .channel-connected-info {
            text-align: center;
            color: var(--success);
            padding: 1rem;
            background: rgba(var(--rgb-success), 0.1);
            border-radius: 8px;
        }
        .btn-danger {
            background: #ff4d4f;
            color: white;
            border: none;
        }
        .btn-danger:hover {
            background: #ff7875;
        }
      `}</style>
        </div>
    );
}
