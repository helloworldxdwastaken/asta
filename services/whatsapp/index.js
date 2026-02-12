import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore
} from '@whiskeysockets/baileys';
import { pino } from 'pino';
import express from 'express';
import qrcode from 'qrcode';
import qrcodeTerminal from 'qrcode-terminal';
import fs from 'fs';

const logger = pino({ level: 'info' });
const ASTA_API_URL = process.env.ASTA_API_URL || 'http://localhost:8010';
const PORT = process.env.PORT || 3001;
const AUTH_DIR = './auth_info_baileys';

const app = express();
app.use(express.json());

let sock;
let qrCodeData = null;
let isConnected = false;

async function connectToWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version, isLatest } = await fetchLatestBaileysVersion();
  logger.info(`using WA v${version.join('.')}, isLatest: ${isLatest}`);

  sock = makeWASocket({
    version,
    logger,
    printQRInTerminal: true,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    generateHighQualityLinkPreview: true,
  });

  sock.ev.process(
    async (events) => {
      if (events['connection.update']) {
        const update = events['connection.update'];
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
          qrCodeData = qr;
          logger.info('QR Code generated');
          // qrcodeTerminal.generate(qr, { small: true }); // makeWASocket handles this with printQRInTerminal: true
        }

        if (connection === 'close') {
          const shouldReconnect = (lastDisconnect?.error)?.output?.statusCode !== DisconnectReason.loggedOut;
          logger.error('connection closed due to ', lastDisconnect?.error, ', reconnecting ', shouldReconnect);
          isConnected = false;
          qrCodeData = null;
          if (shouldReconnect) {
            connectToWhatsApp();
          } else {
            logger.error('Connection closed. You are logged out.');
          }
        } else if (connection === 'open') {
          logger.info('opened connection');
          isConnected = true;
          qrCodeData = null;

          // Auto-whitelist owner
          if (sock?.user?.id) {
            const userJid = sock.user.id;
            const number = userJid.split(':')[0]; // remove :device@server
            registerOwner(number);
          }
        }
      }

      if (events['creds.update']) {
        await saveCreds();
      }

      if (events['messages.upsert']) {
        const upsert = events['messages.upsert'];
        if (upsert.type === 'notify') {
          for (const msg of upsert.messages) {
            try {
              if (!msg.message) continue;
              const from = msg.key.remoteJid;
              if (msg.key.fromMe) continue;

              // Basic text message support for now
              const text = msg.message.conversation || msg.message.extendedTextMessage?.text;

              if (text) {
                logger.info(`Received message from ${from}: ${text.substring(0, 50)}...`);
                await forwardToAsta(from, text);
              }
            } catch (err) {
              logger.error({ err }, 'Error processing message');
            }
          }
        }
      }
    }
  );
}

async function forwardToAsta(from, text) {
  try {
    const res = await fetch(`${ASTA_API_URL}/api/incoming/whatsapp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_number: from, message: text }),
    });

    if (!res.ok) {
      logger.error(`Failed to forward to Asta: ${res.status} ${res.statusText}`);
      return;
    }

    const data = await res.json();
    if (data.reply) {
      await sock.sendMessage(from, { text: data.reply });
      logger.info(`Replied to ${from}`);
    }
  } catch (err) {
    logger.error({ err }, 'Error forwarding to Asta');
  }
}

async function registerOwner(number) {
  try {
    await fetch(`${ASTA_API_URL}/api/settings/whatsapp/owner`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ number }),
    });
    logger.info(`Registered owner: ${number}`);
  } catch (err) {
    logger.error({ err }, 'Failed to register owner');
  }
}

// API Endpoints for Asta

app.get('/qr', async (req, res) => {
  if (isConnected) {
    return res.json({ connected: true });
  }
  if (!qrCodeData) {
    return res.json({ connected: false, qr: null });
  }
  try {
    const dataUrl = await qrcode.toDataURL(qrCodeData);
    res.json({ connected: false, qr: dataUrl });
  } catch (err) {
    res.status(500).json({ error: 'Failed to generate QR image' });
  }
});

app.get('/status', (req, res) => {
  res.json({ connected: isConnected });
});

app.post('/send', async (req, res) => {
  const { to, message } = req.body;
  if (!sock || !isConnected) {
    return res.status(503).json({ error: 'WhatsApp not connected' });
  }
  try {
    await sock.sendMessage(to, { text: message });
    res.json({ success: true });
  } catch (err) {
    logger.error({ err }, 'Failed to send message');
    res.status(500).json({ error: 'Failed to send message' });
  }
});

// Start
connectToWhatsApp();

app.post('/logout', async (req, res) => {
  try {
    if (sock) {
      await sock.logout();
      isConnected = false;
      qrCodeData = null;
    }
    // Remove auth folder
    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
    logger.info('Logged out and cleared auth session.');

    // Reconnect to generate new QR
    connectToWhatsApp();

    res.json({ success: true });
  } catch (err) {
    logger.error({ err }, 'Logout failed');
    res.status(500).json({ error: 'Logout failed' });
  }
});

app.listen(PORT, () => {
  logger.info(`WhatsApp bridge listening on port ${PORT}`);
});
