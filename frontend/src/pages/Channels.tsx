import { useState, useEffect, useCallback } from "react";
import type { Status } from "../api/client";
import { api } from "../api/client";

/** Platform logo URLs (favicons) for channel headers */
const CHANNEL_LOGOS: Record<string, { url: string; initial: string }> = {
  whatsapp: { url: "https://web.whatsapp.com/favicon.ico", initial: "W" },
  telegram: { url: "https://telegram.org/favicon.ico", initial: "T" },
  pingram: { url: "https://www.notificationapi.com/favicon.ico", initial: "P" },
};

function ChannelLogo({ platform, size = 48 }: { platform: string; size?: number }) {
  const [fallback, setFallback] = useState(false);
  const info = CHANNEL_LOGOS[platform] ?? { url: "", initial: "?" };
  if (fallback || !info.url) {
    return (
      <div
        className="channel-icon channel-icon-fallback"
        style={{
          width: size,
          height: size,
          borderRadius: 12,
          background: "var(--accent-soft)",
          color: "var(--accent)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 700,
          fontSize: size * 0.5,
        }}
      >
        {info.initial}
      </div>
    );
  }
  return (
    <img
      src={info.url}
      alt=""
      width={size}
      height={size}
      className="channel-icon channel-icon-img"
      style={{ borderRadius: 12, objectFit: "contain", background: "var(--surface-hover)" }}
      onError={() => setFallback(true)}
    />
  );
}

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
                <ChannelLogo platform="whatsapp" size={48} />
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

    const saveToken = async () => {
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
                <ChannelLogo platform="telegram" size={48} />
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
                    Bot menu commands: <code>/start</code>, <code>/status</code>, <code>/exec_mode</code>, <code>/thinking</code>, <code>/reasoning</code>.
                </div>

                <div className="field-row" style={{ marginTop: '1rem' }}>
                    <input
                        type="password"
                        placeholder={isSet ? "••••••••••••••••" : "Paste token from @BotFather"}
                        value={token}
                        onChange={(e) => setToken(e.target.value)}
                        className="input"
                        style={{ maxWidth: '100%' }}
                    />
                    <button type="button" onClick={saveToken} disabled={saving || !token.trim()} className="btn btn-primary">
                        {saving ? "Saving…" : "Save token"}
                    </button>
                    {isSet && (
                        <button
                            type="button"
                            onClick={() => {
                                if (confirm("Remove Telegram token? The bot will stop working.")) {
                                    api.setSettingsKeys({ telegram_bot_token: "" }).then(() => {
                                        onSaved();
                                        setMsg("Token removed.");
                                    });
                                }
                            }}
                            className="btn btn-danger"
                            style={{ marginLeft: '0.5rem' }}
                        >
                            Remove
                        </button>
                    )}
                </div>

                {msg && <div className={msg.startsWith("Error:") ? "alert alert-error" : "alert"} style={{ marginTop: "0.75rem" }}>{msg}</div>}
            </div>
        </div>
    );
}

function PingramSettings() {
    const [clientId, setClientId] = useState("");
    const [clientSecret, setClientSecret] = useState("");
    const [apiKey, setApiKey] = useState("");
    const [notificationId, setNotificationId] = useState("cron_alert");
    const [templateId, setTemplateId] = useState("");
    const [phoneNumber, setPhoneNumber] = useState("");
    const [saving, setSaving] = useState(false);
    const [msg, setMsg] = useState<string | null>(null);
    const [isSecretSet, setIsSecretSet] = useState(false);
    const [isApiKeySet, setIsApiKeySet] = useState(false);

    useEffect(() => {
        api.getPingramSettings().then((s) => {
            setClientId(s.client_id || "");
            setClientSecret(s.client_secret || "");
            setApiKey(s.api_key || "");
            setNotificationId(s.notification_id || "cron_alert");
            setTemplateId(s.template_id || "");
            setPhoneNumber(s.phone_number || "");
            setIsSecretSet(s.is_secret_set);
            setIsApiKeySet(s.api_key_set);
        }).catch(() => { });
    }, []);

    const saveSettings = async () => {
        setSaving(true);
        setMsg(null);
        try {
            await api.setPingramSettings({
                client_id: clientId.trim(),
                client_secret: clientSecret.trim(),
                api_key: apiKey.trim(),
                notification_id: notificationId.trim(),
                template_id: templateId.trim(),
                phone_number: phoneNumber.trim()
            });
            const s = await api.getPingramSettings();
            setClientId(s.client_id || "");
            setClientSecret(s.client_secret || "");
            setApiKey(s.api_key || "");
            setNotificationId(s.notification_id || "cron_alert");
            setTemplateId(s.template_id || "");
            setPhoneNumber(s.phone_number || "");
            setIsSecretSet(s.is_secret_set);
            setIsApiKeySet(s.api_key_set);
            setMsg("Pingram settings saved.");
        } catch (e) {
            setMsg("Error: " + ((e as Error).message || String(e)));
        } finally {
            setSaving(false);
        }
    };

    const testCall = async () => {
        const number = (phoneNumber || "").trim();
        if (!number) {
            setMsg("Error: Enter a phone number in the field above, then click Test call.");
            return;
        }
        if (!isApiKeySet && !isSecretSet && !clientSecret && !apiKey) {
            setMsg("Error: Set and save either API Key or Client ID + Client Secret first.");
            return;
        }
        setSaving(true);
        setMsg(null);
        try {
            const body: Record<string, string> = {
                client_id: clientId,
                client_secret: clientSecret,
                api_key: apiKey,
                notification_id: notificationId,
                test_number: number
            };
            if (templateId.trim()) body.template_id = templateId.trim();
            const r = await fetch(`/api/settings/pingram/test-call`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await r.json();
            if (data.ok) {
                setMsg("Test call triggered! You should receive a call shortly.");
            } else {
                setMsg("Error: " + (data.error || "Failed to trigger call. Check console/logs."));
            }
        } catch (e) {
            setMsg("Error: " + (e as Error).message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="channel-section">
            <div className="channel-header">
                <ChannelLogo platform="pingram" size={48} />
                <div>
                    <h3>Voice Calls (Pingram)</h3>
                    <p className="help">Reliable phone calls via NotificationAPI.</p>
                </div>
                <span className={`status-badge ${(isSecretSet || isApiKeySet) ? "ok" : ""}`}>{(isSecretSet || isApiKeySet) ? "Active" : "Not configured"}</span>
            </div>

            <div className="channel-body">
                <div className="alert alert-info" style={{ marginBottom: '1rem', fontSize: '0.85rem' }}>
                    <strong>How to Setup:</strong>
                    <ol style={{ paddingLeft: '1.2rem', marginTop: '0.4rem' }}>
                        <li>Create a free account at <a href="https://app.notificationapi.com" target="_blank" rel="noreferrer" className="link">notificationapi.com</a></li>
                        <li>Go to <strong>Settings &gt; Environments</strong> and copy your <strong>Client ID</strong> and <strong>Client Secret</strong>.</li>
                        <li>Go to <strong>Notifications</strong> and create one named <code>cron_alert</code>.</li>
                        <li>Enable the <strong>Automated Voice Call</strong> channel for it.</li>
                    </ol>
                </div>

                <div className="field-block" style={{ marginTop: '1rem' }}>
                    <label>Default Phone Number</label>
                    <p className="help">Reminders will call this number by default (E.164 format, e.g. +15551234567).</p>
                    <input
                        type="text"
                        placeholder="+15551234567"
                        value={phoneNumber}
                        onChange={(e) => setPhoneNumber(e.target.value)}
                        className="input"
                    />
                </div>

                <div className="field-group" style={{ marginTop: '1rem' }}>
                    <div className="field-block">
                        <label>Client ID</label>
                        <input
                            type="text"
                            placeholder="NotificationAPI Client ID"
                            value={clientId}
                            onChange={(e) => setClientId(e.target.value)}
                            className="input"
                        />
                    </div>
                    <div className="field-block">
                        <label>Client Secret</label>
                        <input
                            type="password"
                            placeholder={isSecretSet ? "••••••••••••••••" : "NotificationAPI Client Secret"}
                            value={clientSecret}
                            onChange={(e) => setClientSecret(e.target.value)}
                            className="input"
                        />
                    </div>
                    <div className="field-block">
                        <label>API Key</label>
                        <p className="help">From dashboard Production Environment. Use this if voice calls don’t work with Client ID+Secret.</p>
                        <input
                            type="password"
                            placeholder={isApiKeySet ? "••••••••••••••••" : "pingram_sk_…"}
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            className="input"
                        />
                    </div>
                </div>

                <div className="field-group" style={{ marginTop: '1rem' }}>
                    <div className="field-block">
                        <label>Notification ID</label>
                        <input
                            type="text"
                            value={notificationId}
                            onChange={(e) => setNotificationId(e.target.value)}
                            className="input"
                        />
                    </div>
                    <div className="field-block">
                        <label>Custom Template ID</label>
                        <input
                            type="text"
                            placeholder="Optional: template_one"
                            value={templateId}
                            onChange={(e) => setTemplateId(e.target.value)}
                            className="input"
                        />
                    </div>
                </div>

                <div className="field-row" style={{ marginTop: '1.5rem' }}>
                    <button type="button" onClick={saveSettings} disabled={saving} className="btn btn-primary">
                        {saving ? "Saving…" : "Save settings"}
                    </button>
                    <button type="button" onClick={testCall} disabled={saving} className="btn">
                        Test call
                    </button>
                </div>
                {msg && <div className={msg.startsWith("Error:") ? "alert alert-error" : "alert"} style={{ marginTop: "0.75rem" }}>{msg}</div>}
            </div>
            <style>{`
                .pingram-icon { background: #6366f1; }
            `}</style>
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
                <TelegramSettings keysStatus={keysStatus} onSaved={refreshKeys} status={status} />
                <PingramSettings />
                <WhatsAppQr status={status} />
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
            min-width: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        .channel-icon-img { background: var(--surface-hover); }
        .channel-icon-fallback { background: var(--accent-soft); color: var(--accent); }
        
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
