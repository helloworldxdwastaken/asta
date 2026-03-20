import { useState, useEffect } from "react";
import { getKeyStatus, setKeys } from "../../../lib/api";

export default function TabGoogle() {
  const [geminiKey, setGeminiKey] = useState("");
  const [hasGemini, setHasGemini] = useState(false);
  const [savingGemini, setSavingGemini] = useState(false);
  const [savedGemini, setSavedGemini] = useState(false);

  const [saJson, setSaJson] = useState("");
  const [hasSa, setHasSa] = useState(false);
  const [savingSa, setSavingSa] = useState(false);
  const [savedSa, setSavedSa] = useState(false);
  const [saError, setSaError] = useState("");

  useEffect(() => {
    getKeyStatus().then(r => {
      setHasGemini(!!r.gemini_api_key);
      setHasSa(!!r.google_service_account);
    }).catch(() => {});
  }, []);

  async function saveGemini() {
    if (!geminiKey.trim()) return;
    setSavingGemini(true);
    await setKeys({ gemini_api_key: geminiKey });
    setSavingGemini(false); setSavedGemini(true); setHasGemini(true);
    setTimeout(() => setSavedGemini(false), 2000);
  }

  async function saveSa() {
    const raw = saJson.trim();
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw);
      if (!parsed.client_email || !parsed.private_key) {
        setSaError("JSON must contain client_email and private_key fields.");
        return;
      }
    } catch {
      setSaError("Invalid JSON. Paste the full service account JSON file contents.");
      return;
    }
    setSaError("");
    setSavingSa(true);
    await setKeys({ google_service_account: raw });
    setSavingSa(false); setSavedSa(true); setHasSa(true);
    setTimeout(() => setSavedSa(false), 2000);
  }

  const inputCls =
    "w-full bg-white/[.04] border border-separator rounded-mac px-3 py-2 text-13 font-mono text-label outline-none focus:border-accent/50";
  const btnCls =
    "text-12 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-4 py-1.5 rounded-lg transition-colors shrink-0";

  return (
    <div className="text-label space-y-8">
      <div>
        <h2 className="text-15 font-semibold mb-1">Google</h2>
        <p className="text-13 text-label-secondary">
          Connect Google services — Gemini AI, Search Console, Calendar, and more.
        </p>
      </div>

      {/* Gemini API Key */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-13 font-medium">Gemini API Key</label>
          <span className={`text-11 ${hasGemini ? "text-success" : "text-label-tertiary"}`}>
            {hasGemini ? "● set" : "○ not set"}
          </span>
        </div>
        <p className="text-12 text-label-tertiary">
          For using Google Gemini as an AI provider.
          Get one at{" "}
          <span className="text-accent">aistudio.google.com/apikey</span>
        </p>
        <div className="flex gap-2">
          <input
            type="password"
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
            placeholder="Leave blank to keep existing"
            className={inputCls}
          />
          <button onClick={saveGemini} disabled={savingGemini || !geminiKey.trim()} className={btnCls}>
            {savedGemini ? "Saved" : savingGemini ? "…" : "Save"}
          </button>
        </div>
      </div>

      <hr className="border-separator" />

      {/* Service Account */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-13 font-medium">Service Account JSON</label>
          <span className={`text-11 ${hasSa ? "text-success" : "text-label-tertiary"}`}>
            {hasSa ? "● set" : "○ not set"}
          </span>
        </div>
        <p className="text-12 text-label-tertiary">
          A service account enables server-to-server access for Google APIs like
          Indexing, Calendar, Search Console, and Drive — no browser login needed.
        </p>
        <textarea
          value={saJson}
          onChange={(e) => { setSaJson(e.target.value); setSaError(""); }}
          placeholder='Paste the full JSON contents of your service account key file...'
          rows={6}
          className={`${inputCls} resize-y min-h-[80px]`}
        />
        {saError && <p className="text-12 text-red-400">{saError}</p>}
        <div className="flex justify-end">
          <button onClick={saveSa} disabled={savingSa || !saJson.trim()} className={btnCls}>
            {savedSa ? "Saved" : savingSa ? "…" : "Save"}
          </button>
        </div>
      </div>

      <hr className="border-separator" />

      {/* Setup Guide */}
      <div className="space-y-3">
        <h3 className="text-13 font-medium">Setup Guide</h3>
        <div className="text-12 text-label-secondary space-y-3 leading-relaxed">
          <div>
            <p className="font-medium text-label mb-1">1. Create a Google Cloud project</p>
            <p>
              Go to{" "}
              <span className="text-accent">console.cloud.google.com</span>{" "}
              and create a project (or use an existing one).
            </p>
          </div>
          <div>
            <p className="font-medium text-label mb-1">2. Enable APIs</p>
            <p>
              In your project, go to <strong>APIs & Services &gt; Enable APIs</strong> and enable
              the APIs you need:
            </p>
            <ul className="list-disc list-inside ml-2 mt-1 space-y-0.5 text-label-tertiary">
              <li>Indexing API — for submitting URLs to Google Search</li>
              <li>Google Calendar API — for reading/writing calendar events</li>
              <li>Google Drive API — for file access</li>
              <li>Search Console API — for checking indexing status</li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-label mb-1">3. Create a service account</p>
            <p>
              Go to <strong>IAM & Admin &gt; Service Accounts</strong>, create one,
              then <strong>Keys &gt; Add Key &gt; JSON</strong>. A{" "}
              <code className="text-11 bg-white/[.06] px-1 py-0.5 rounded">.json</code>{" "}
              file will download — paste its contents above.
            </p>
          </div>
          <div>
            <p className="font-medium text-label mb-1">4. Grant access</p>
            <ul className="list-disc list-inside ml-2 space-y-0.5 text-label-tertiary">
              <li>
                <strong>Search Console:</strong> Add the service account email as an
                Owner in{" "}
                <span className="text-accent">search.google.com/search-console</span>
              </li>
              <li>
                <strong>Calendar:</strong> Share your calendar with the service account
                email (give "Make changes to events" permission)
              </li>
              <li>
                <strong>Drive:</strong> Share folders/files with the service account email
              </li>
            </ul>
          </div>
          <p className="text-11 text-label-tertiary mt-2">
            The service account email looks like:{" "}
            <code className="bg-white/[.06] px-1 py-0.5 rounded">
              name@project.iam.gserviceaccount.com
            </code>
          </p>
        </div>
      </div>
    </div>
  );
}
