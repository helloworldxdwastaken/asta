/**
 * Asta WhatsApp bridge (whatsapp-web.js).
 * Receives messages, POSTs to Asta backend /api/incoming/whatsapp, sends reply.
 * Exposes GET /qr so the Asta panel can show a QR code to connect WhatsApp.
 * Set ASTA_API_URL (e.g. http://localhost:8010) and run: node index.js
 */
import pkg from "whatsapp-web.js";
const { Client, LocalAuth } = pkg;
import qrcodeTerminal from "qrcode-terminal";
import qrcode from "qrcode";
import express from "express";

const ASTA_API_URL = process.env.ASTA_API_URL || "http://localhost:8010";
const PORT = parseInt(process.env.PORT || "3001", 10);

let lastQr = null;
let connected = false;

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: "./.wweb_auth" }),
});

client.on("qr", (qr) => {
  lastQr = qr;
  connected = false;
  console.log("Scan this QR with WhatsApp (Linked Devices):");
  qrcodeTerminal.generate(qr, { small: true });
});

client.on("ready", () => {
  connected = true;
  lastQr = null;
  console.log("WhatsApp bridge ready. Forwarding to Asta at", ASTA_API_URL);
});

client.on("message", async (msg) => {
  if (msg.fromMe) return;
  const from = msg.from;
  const body = msg.body?.trim();
  if (!body) return;

  try {
    const res = await fetch(`${ASTA_API_URL}/api/incoming/whatsapp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from_number: from, message: body }),
    });
    if (!res.ok) {
      await msg.reply("Asta error: " + (await res.text()).slice(0, 200));
      return;
    }
    const data = await res.json();
    const reply = data.reply || "";
    if (reply) await msg.reply(reply.slice(0, 4096));
  } catch (e) {
    console.error("WhatsApp bridge error:", e);
    await msg.reply("Asta is unavailable. Try again later.");
  }
});

const app = express();

app.get("/qr", async (req, res) => {
  try {
    if (connected) {
      return res.json({ connected: true });
    }
    if (!lastQr) {
      return res.json({ connected: false, qr: null });
    }
    const dataUrl = await qrcode.toDataURL(lastQr);
    res.json({ connected: false, qr: dataUrl });
  } catch (e) {
    res.status(500).json({ connected: false, qr: null, error: String(e.message) });
  }
});

app.get("/status", (req, res) => {
  res.json({ connected });
});

app.listen(PORT, () => {
  console.log("WhatsApp bridge HTTP server on port", PORT, "(GET /qr for QR code)");
  client.initialize().catch((e) => {
    console.error("Failed to start WhatsApp client:", e);
    process.exit(1);
  });
});
