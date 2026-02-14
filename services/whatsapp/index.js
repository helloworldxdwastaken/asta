import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  getContentType
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
let isConnecting = false;
let reconnectTimer = null;
let reconnectAttempts = 0;
const lidToPn = new Map();
const botSentMessageIds = new Map();
const BOT_SENT_TTL_MS = 5 * 60 * 1000;
let ownerPnJid = '';
let lastDisconnect = null;
let lastConnectedAt = null;
const bridgeStartedAt = Date.now();

function cleanupBotSentMessageIds() {
  const now = Date.now();
  for (const [id, ts] of botSentMessageIds.entries()) {
    if ((now - ts) > BOT_SENT_TTL_MS) botSentMessageIds.delete(id);
  }
}

function trackBotSentMessageId(id) {
  const key = String(id || '').trim();
  if (!key) return;
  cleanupBotSentMessageIds();
  botSentMessageIds.set(key, Date.now());
}

function wasBotSentMessage(id) {
  cleanupBotSentMessageIds();
  const key = String(id || '').trim();
  if (!key) return false;
  if (!botSentMessageIds.has(key)) return false;
  botSentMessageIds.delete(key);
  return true;
}

function normalizeJid(jid) {
  const raw = String(jid || '').trim();
  if (!raw) return '';
  if (!raw.includes('@')) return raw;
  const [user, server] = raw.split('@', 2);
  const cleanUser = String(user || '').split(':')[0];
  return `${cleanUser}@${server}`;
}

function rememberLidMapping(lid, jid, source = 'unknown') {
  const lidKey = normalizeJid(lid);
  const pnJid = normalizeJid(jid);
  if (!lidKey || !pnJid) return;
  if (!lidKey.endsWith('@lid')) return;
  if (!pnJid.includes('@s.whatsapp.net')) return;
  lidToPn.set(lidKey, pnJid);
  logger.info(`LID mapped (${source}): ${lidKey} -> ${pnJid}`);
}

function extractTextContent(message) {
  if (!message || typeof message !== 'object') return '';
  if (typeof message.conversation === 'string' && message.conversation.trim()) return message.conversation;
  if (typeof message.extendedTextMessage?.text === 'string' && message.extendedTextMessage.text.trim()) return message.extendedTextMessage.text;
  if (typeof message.imageMessage?.caption === 'string' && message.imageMessage.caption.trim()) return message.imageMessage.caption;
  if (typeof message.videoMessage?.caption === 'string' && message.videoMessage.caption.trim()) return message.videoMessage.caption;
  if (typeof message.buttonsResponseMessage?.selectedDisplayText === 'string' && message.buttonsResponseMessage.selectedDisplayText.trim()) {
    return message.buttonsResponseMessage.selectedDisplayText;
  }
  if (typeof message.templateButtonReplyMessage?.selectedDisplayText === 'string' && message.templateButtonReplyMessage.selectedDisplayText.trim()) {
    return message.templateButtonReplyMessage.selectedDisplayText;
  }
  if (typeof message.listResponseMessage?.title === 'string' && message.listResponseMessage.title.trim()) return message.listResponseMessage.title;
  if (typeof message.listResponseMessage?.singleSelectReply?.selectedRowId === 'string' && message.listResponseMessage.singleSelectReply.selectedRowId.trim()) {
    return message.listResponseMessage.singleSelectReply.selectedRowId;
  }

  // Common wrappers for modern WA messages
  const nested =
    message.ephemeralMessage?.message ||
    message.viewOnceMessage?.message ||
    message.viewOnceMessageV2?.message ||
    message.viewOnceMessageV2Extension?.message ||
    message.documentWithCaptionMessage?.message;

  if (nested) return extractTextContent(nested);
  return '';
}

function disconnectReasonName(statusCode) {
  for (const [name, code] of Object.entries(DisconnectReason)) {
    if (code === statusCode) return name;
  }
  return 'unknown';
}

function scheduleReconnect(reason = 'unknown') {
  if (reconnectTimer || isConnecting) return;
  const delay = Math.min(30_000, 1_000 * (2 ** Math.min(reconnectAttempts, 5)));
  reconnectAttempts += 1;
  logger.warn({ reason, delayMs: delay, attempt: reconnectAttempts }, 'Scheduling WhatsApp reconnect');
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectToWhatsApp();
  }, delay);
}

async function connectToWhatsApp() {
  if (isConnecting) return;
  isConnecting = true;
  try {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version, isLatest } = await fetchLatestBaileysVersion();
    logger.info(`using WA v${version.join('.')}, isLatest: ${isLatest}`);

    sock = makeWASocket({
      version,
      logger,
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
            qrcodeTerminal.generate(qr, { small: true });
          }

          if (connection === 'close') {
            const statusCode = Number(
              (lastDisconnect?.error)?.output?.statusCode
              ?? (lastDisconnect?.error)?.statusCode
              ?? 0
            );
            const reason = disconnectReasonName(statusCode);
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            const disconnectError = String(lastDisconnect?.error || '');
            lastDisconnect = {
              at: new Date().toISOString(),
              status_code: statusCode,
              reason,
              reconnecting: shouldReconnect,
              error: disconnectError || null,
            };
            logger.error(
              {
                statusCode,
                reason,
                error: disconnectError,
                reconnecting: shouldReconnect,
              },
              'connection closed'
            );
            isConnected = false;
            qrCodeData = null;
            if (shouldReconnect) {
              scheduleReconnect(reason);
            } else {
              // Logged out sessions need a fresh auth state + new QR.
              try {
                fs.rmSync(AUTH_DIR, { recursive: true, force: true });
              } catch (err) {
                logger.error({ err }, 'Failed to clear auth session after logout');
              }
              logger.error('Connection closed and session logged out. New QR will be generated.');
              scheduleReconnect('loggedOut');
            }
          } else if (connection === 'open') {
            logger.info('opened connection');
            isConnected = true;
            qrCodeData = null;
            reconnectAttempts = 0;
            lastConnectedAt = new Date().toISOString();

            // Auto-whitelist owner
            if (sock?.user?.id) {
              const userJid = sock.user.id;
              const number = userJid.split(':')[0]; // remove :device@server
              ownerPnJid = normalizeJid(`${number}@s.whatsapp.net`);
              registerOwner(number);
            }
          }
        }

        if (events['creds.update']) {
          await saveCreds();
        }

        if (events['messages.upsert']) {
          const upsert = events['messages.upsert'];
          if (upsert.type === 'notify' || upsert.type === 'append') {
            for (const msg of upsert.messages) {
              try {
                if (!msg.message) continue;
                const from = normalizeJid(msg.key.remoteJid);
                const messageId = String(msg.key?.id || '').trim();
                if (msg.key.fromMe) {
                  // Avoid feedback loop: ignore bridge-originated replies.
                  if (wasBotSentMessage(messageId)) {
                    continue;
                  }
                  // Allow owner self-chat prompts (fromMe=true) in owner's own chat.
                  const key = msg.key || {};
                  const senderPn = normalizeJid(key.senderPn);
                  const participantPn = normalizeJid(key.participantPn);
                  const mappedFrom = from && from.endsWith('@lid') ? normalizeJid(lidToPn.get(from)) : '';
                  const isOwnerSelfChat = !!ownerPnJid && (
                    from === ownerPnJid ||
                    mappedFrom === ownerPnJid ||
                    senderPn === ownerPnJid ||
                    participantPn === ownerPnJid
                  );
                  if (!isOwnerSelfChat) {
                    logger.info(`Skipping fromMe message outside owner self-chat (${from})`);
                    continue;
                  }
                }

                // Basic text message support for now
                const text = extractTextContent(msg.message);

                if (text) {
                  const key = msg.key || {};
                  rememberLidMapping(key.senderLid, key.senderPn, 'message.key');
                  rememberLidMapping(key.participantLid, key.participantPn, 'message.key');

                  let policyFrom = normalizeJid(key.senderPn) || normalizeJid(key.participantPn) || from;
                  if (!policyFrom && from) policyFrom = from;
                  if (from && from.endsWith('@lid') && (!policyFrom || policyFrom.endsWith('@lid'))) {
                    const mapped = lidToPn.get(from);
                    if (mapped) policyFrom = mapped;
                  }
                  logger.info(`Received message from ${from} (policy sender: ${policyFrom}): ${text.substring(0, 50)}...`);
                  await forwardToAsta(from, text, policyFrom);
                }
                else {
                  const contentType = getContentType(msg.message) || 'unknown';
                  logger.info(`Ignoring non-text message from ${from} (type=${contentType})`);
                }
              } catch (err) {
                logger.error({ err }, 'Error processing message');
              }
            }
          }
        }

        if (events['chats.phoneNumberShare']) {
          const share = events['chats.phoneNumberShare'];
          rememberLidMapping(share?.lid, share?.jid, 'chats.phoneNumberShare');
        }

        if (events['contacts.upsert']) {
          for (const c of events['contacts.upsert'] || []) {
            const lid = c?.lid || (String(c?.id || '').endsWith('@lid') ? c.id : '');
            const jid = c?.jid || (String(c?.id || '').includes('@s.whatsapp.net') ? c.id : '');
            rememberLidMapping(lid, jid, 'contacts.upsert');
          }
        }

        if (events['contacts.update']) {
          for (const c of events['contacts.update'] || []) {
            const lid = c?.lid || (String(c?.id || '').endsWith('@lid') ? c.id : '');
            const jid = c?.jid || (String(c?.id || '').includes('@s.whatsapp.net') ? c.id : '');
            rememberLidMapping(lid, jid, 'contacts.update');
          }
        }
      }
    );
  } catch (err) {
    logger.error({ err }, 'Failed to initialize WhatsApp socket');
    scheduleReconnect('initError');
  } finally {
    isConnecting = false;
  }
}

async function forwardToAsta(rawFrom, text, policyFrom = null) {
  try {
    const res = await fetch(`${ASTA_API_URL}/api/incoming/whatsapp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from_number: policyFrom || rawFrom,
        reply_to: rawFrom,
        message: text,
      }),
    });

    if (!res.ok) {
      logger.error(`Failed to forward to Asta: ${res.status} ${res.statusText}`);
      return;
    }

    const data = await res.json();
    if (data?.ignored) {
      logger.warn(`Backend ignored message by policy from ${policyFrom || rawFrom}`);
      return;
    }
    if (data.reply) {
      const sent = await sock.sendMessage(rawFrom, { text: data.reply });
      trackBotSentMessageId(sent?.key?.id);
      logger.info(`Replied to ${rawFrom}`);
      return;
    }
    logger.info(`No reply generated for ${rawFrom}`);
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
  const state = !isConnected
    ? (isConnecting ? 'connecting' : (qrCodeData ? 'awaiting_qr' : 'disconnected'))
    : 'connected';
  res.json({
    connected: isConnected,
    connecting: isConnecting,
    has_qr: !!qrCodeData,
    state,
    reconnect_attempts: reconnectAttempts,
    owner_jid: ownerPnJid || null,
    last_connected_at: lastConnectedAt,
    last_disconnect: lastDisconnect,
    uptime_sec: Math.floor((Date.now() - bridgeStartedAt) / 1000),
  });
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
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (sock) {
      await sock.logout();
      isConnected = false;
      qrCodeData = null;
    }
    // Remove auth folder
    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
    logger.info('Logged out and cleared auth session.');

    // Reconnect to generate new QR
    reconnectAttempts = 0;
    scheduleReconnect('manualLogout');

    res.json({ success: true });
  } catch (err) {
    logger.error({ err }, 'Logout failed');
    res.status(500).json({ error: 'Logout failed' });
  }
});

app.listen(PORT, () => {
  logger.info(`WhatsApp bridge listening on port ${PORT}`);
});
