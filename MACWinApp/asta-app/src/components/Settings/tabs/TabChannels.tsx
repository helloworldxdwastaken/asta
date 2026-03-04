import { useState, useEffect } from "react";
import { getTelegramUsername, setTelegramUsername, getPingram, setPingram, testPingramCall, setKeys, getKeyStatus } from "../../../lib/api";
import { IconCheck } from "../../../lib/icons";

const TG_COMMANDS = [
  { cmd: "/start", desc: "Start chatting with Asta" },
  { cmd: "/status", desc: "Show backend status" },
  { cmd: "/exec_mode", desc: "Toggle exec mode on/off" },
  { cmd: "/thinking", desc: "Set thinking level" },
  { cmd: "/reasoning", desc: "Set reasoning mode" },
];

export default function TabChannels() {
  const [tgUser, setTgUser] = useState("");
  const [tgToken, setTgToken] = useState("");
  const [tgTokenSet, setTgTokenSet] = useState(false);
  const [tgSaved, setTgSaved] = useState(false);
  const [tgTokenSaved, setTgTokenSaved] = useState(false);
  const [pgToken, setPgToken] = useState("");
  const [pgPhone, setPgPhone] = useState("");
  const [pgClientId, setPgClientId] = useState("");
  const [pgClientSecret, setPgClientSecret] = useState("");
  const [pgNotifId, setPgNotifId] = useState("");
  const [pgSaved, setPgSaved] = useState(false);
  const [testResult, setTestResult] = useState<"ok" | "fail" | null>(null);

  useEffect(() => {
    getTelegramUsername().then(r => setTgUser(r.username ?? "")).catch(()=>{});
    getKeyStatus().then(r => setTgTokenSet(!!r.telegram_bot_token)).catch(()=>{});
    getPingram().then(r => {
      setPgToken(r.api_key ?? "");
      setPgPhone(r.phone_number ?? "");
      setPgClientId(r.client_id ?? "");
      setPgClientSecret(r.client_secret ?? "");
      setPgNotifId(r.notification_id ?? "");
    }).catch(()=>{});
  }, []);

  async function saveTgUsername() {
    await setTelegramUsername(tgUser);
    setTgSaved(true); setTimeout(() => setTgSaved(false), 2000);
  }
  async function saveTgToken() {
    if (!tgToken.trim()) return;
    await setKeys({ telegram_bot_token: tgToken.trim() });
    setTgTokenSaved(true); setTgTokenSet(true);
    setTimeout(() => setTgTokenSaved(false), 2000);
  }
  async function savePg() {
    await setPingram({ api_key: pgToken, phone_number: pgPhone, client_id: pgClientId, client_secret: pgClientSecret, notification_id: pgNotifId });
    setPgSaved(true); setTimeout(() => setPgSaved(false), 2000);
  }
  async function testPg() {
    if (!pgPhone.trim()) { setTestResult("fail"); setTimeout(() => setTestResult(null), 3000); return; }
    try { const r: any = await testPingramCall(pgPhone.trim()); setTestResult(r.ok ? "ok" : "fail"); } catch { setTestResult("fail"); }
    setTimeout(() => setTestResult(null), 3000);
  }

  return (
    <div className="text-label space-y-6">
      <h2 className="text-16 font-semibold">Channels</h2>

      <Section title="Telegram">
        <div className="space-y-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-11 text-label-tertiary">Bot Token</label>
              {tgTokenSet && <span className="text-11 text-success">set</span>}
            </div>
            <div className="flex gap-2">
              <input type="password" value={tgToken} onChange={e => setTgToken(e.target.value)}
                placeholder={tgTokenSet ? "Leave blank to keep existing" : "123456:ABC-DEF..."}
                className="flex-1 bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors" />
              <button onClick={saveTgToken} className="text-12 accent-gradient text-white px-4 py-2 rounded-mac shrink-0 shadow-glow-sm transition-all duration-200 active:scale-[0.97]">
                {tgTokenSaved ? <IconCheck size={14} /> : "Save token"}
              </button>
            </div>
          </div>
          <div>
            <label className="text-11 text-label-tertiary block mb-1">Bot Username</label>
            <div className="flex gap-2">
              <input type="text" value={tgUser} onChange={e => setTgUser(e.target.value)} placeholder="@YourBotUsername"
                className="flex-1 bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors" />
              <button onClick={saveTgUsername} className="text-12 accent-gradient text-white px-4 py-2 rounded-mac shrink-0 shadow-glow-sm transition-all duration-200 active:scale-[0.97]">
                {tgSaved ? <IconCheck size={14} /> : "Save"}
              </button>
            </div>
          </div>
          <div className="bg-white/[.04] rounded-mac p-3">
            <p className="text-11 text-label-tertiary font-medium mb-2">Available Commands</p>
            <div className="space-y-1">
              {TG_COMMANDS.map(c => (
                <div key={c.cmd} className="flex gap-3 text-12">
                  <span className="font-mono text-accent shrink-0">{c.cmd}</span>
                  <span className="text-label-tertiary">{c.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      <Section title="Pingram (Voice Calls)">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-11 text-label-tertiary block mb-1">Phone Number</label>
              <input type="text" value={pgPhone} onChange={e => setPgPhone(e.target.value)} placeholder="+1234567890"
                className="w-full bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors" />
            </div>
            <div>
              <label className="text-11 text-label-tertiary block mb-1">API Token</label>
              <input type="password" value={pgToken} onChange={e => setPgToken(e.target.value)}
                className="w-full bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-11 text-label-tertiary block mb-1">Client ID</label>
              <input type="text" value={pgClientId} onChange={e => setPgClientId(e.target.value)}
                className="w-full bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors" />
            </div>
            <div>
              <label className="text-11 text-label-tertiary block mb-1">Client Secret</label>
              <input type="password" value={pgClientSecret} onChange={e => setPgClientSecret(e.target.value)}
                className="w-full bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors" />
            </div>
          </div>
          <div>
            <label className="text-11 text-label-tertiary block mb-1">Notification ID (optional)</label>
            <input type="text" value={pgNotifId} onChange={e => setPgNotifId(e.target.value)}
              className="w-full bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors" />
          </div>
          <div className="flex gap-2">
            <button onClick={savePg} className="text-12 accent-gradient text-white px-5 py-2 rounded-mac shadow-glow-sm transition-all duration-200 active:scale-[0.97]">
              {pgSaved ? "Saved" : "Save"}
            </button>
            <button onClick={testPg} className={`text-12 px-4 py-2 rounded-mac transition-all duration-200 border ${
              testResult === "ok" ? "bg-success/[.12] text-success border-success/20" : testResult === "fail" ? "bg-danger/[.12] text-danger border-danger/20" : "bg-white/[.05] hover:bg-white/[.08] text-label-secondary border-separator"
            }`}>
              {testResult === "ok" ? "Call sent" : testResult === "fail" ? "Failed" : "Test Call"}
            </button>
          </div>
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (<section><h3 className="text-10 font-bold text-label-tertiary uppercase tracking-widest mb-3">{title}</h3>{children}</section>);
}
