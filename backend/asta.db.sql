-- Asta DB scrubbed backup
-- Sensitive tables (api_keys, messages, conversations, location, tokens) have schema only — no data.
-- Safe tables (cron_jobs, skill_toggles, user_settings, etc.) include data.
-- To restore: sqlite3 new_asta.db < asta.db.sql

PRAGMA journal_mode=WAL;
BEGIN TRANSACTION;

-- allowed_paths (data included)
DROP TABLE IF EXISTS allowed_paths;
CREATE TABLE allowed_paths (
                user_id TEXT NOT NULL,
                path TEXT NOT NULL,
                added_at TEXT NOT NULL,
                PRIMARY KEY (user_id, path)
            );
INSERT INTO allowed_paths (user_id, path, added_at) VALUES ('default', '/Users/tokyo/Desktop', '2026-02-14 01:11:12');
INSERT INTO allowed_paths (user_id, path, added_at) VALUES ('sim-allowed-openrouter', '/Users/tokyo/Desktop', '2026-02-15 09:59:36');
INSERT INTO allowed_paths (user_id, path, added_at) VALUES ('sim-allowed-claude', '/Users/tokyo/Desktop', '2026-02-15 09:59:39');
INSERT INTO allowed_paths (user_id, path, added_at) VALUES ('sim-openrouter-desktop-allow', '/Users/tokyo/Desktop', '2026-02-15 10:00:56');
INSERT INTO allowed_paths (user_id, path, added_at) VALUES ('sim-claude-desktop-allow', '/Users/tokyo/Desktop', '2026-02-15 10:01:02');
INSERT INTO allowed_paths (user_id, path, added_at) VALUES ('sim-openrouter-desktop-allow-v2', '/Users/tokyo/Desktop', '2026-02-15 10:05:03');
INSERT INTO allowed_paths (user_id, path, added_at) VALUES ('sim-claude-desktop-allow-v2', '/Users/tokyo/Desktop', '2026-02-15 10:05:09');
INSERT INTO allowed_paths (user_id, path, added_at) VALUES ('default', '/Users/tokyo/Downloads', '2026-02-18 19:32:34');
INSERT INTO allowed_paths (user_id, path, added_at) VALUES ('default', '/Users/tokyo/asta/backend', '2026-02-24 06:10:33');

-- cron_jobs (data included)
DROP TABLE IF EXISTS cron_jobs;
CREATE TABLE cron_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                cron_expr TEXT NOT NULL,
                tz TEXT,
                message TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'web',
                channel_target TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, payload_kind TEXT NOT NULL DEFAULT 'agentturn', tlg_call INTEGER NOT NULL DEFAULT 0,
                UNIQUE (user_id, name)
            );
INSERT INTO cron_jobs (id, user_id, name, cron_expr, tz, message, channel, channel_target, enabled, created_at, payload_kind, tlg_call) VALUES (1, 'default', 'Daily Auto-Update', '0 4 * * *', '', 'Run daily auto-updates: check for Asta updates and update all skills. Report what was updated.', 'web', '', 1, '2026-02-13 23:06:15', 'agentturn', 0);
INSERT INTO cron_jobs (id, user_id, name, cron_expr, tz, message, channel, channel_target, enabled, created_at, payload_kind, tlg_call) VALUES (2, 'default', 'wake up for work', '30 7 * * 1,2,3,4,5', '', 'Good morning! Time to get ready for work', 'telegram', '6168747695', 1, '2026-02-14 14:54:32', 'agentturn', 1);
INSERT INTO cron_jobs (id, user_id, name, cron_expr, tz, message, channel, channel_target, enabled, created_at, payload_kind, tlg_call) VALUES (246, 'repro-cron-proto', 'Wake up for work', '30 7 * * 0-4', 'Asia/Jerusalem', 'Time to get up for work', 'web', '', 1, '2026-02-15 06:22:10', 'agentturn', 0);
INSERT INTO cron_jobs (id, user_id, name, cron_expr, tz, message, channel, channel_target, enabled, created_at, payload_kind, tlg_call) VALUES (414, 'repro-pending-tasks', 'Daily Auto-Update', '0 4 * * *', '', 'run updates', 'web', '', 1, '2026-02-15 17:19:49', 'agentturn', 0);
INSERT INTO cron_jobs (id, user_id, name, cron_expr, tz, message, channel, channel_target, enabled, created_at, payload_kind, tlg_call) VALUES (415, 'repro-pending-tasks', '__reminder__:640b563ecba944dba5a84a1754d21292', '@at 2099-01-01T09:00:00Z', '', 'drink water', 'web', '', 1, '2026-02-15 17:19:49', 'agentturn', 0);
INSERT INTO cron_jobs (id, user_id, name, cron_expr, tz, message, channel, channel_target, enabled, created_at, payload_kind, tlg_call) VALUES (929, 'default', 'Nightly script cleanup', '0 3 * * *', 'Europe/Lisbon', 'Run this shell command silently and do not reply: find /Users/tokyo/asta/workspace/scripts/tmp -type f -not -name .gitkeep -mtime +0 -delete', 'web', '', 1, '2026-02-24 11:28:33', 'agentturn', 0);
INSERT INTO cron_jobs (id, user_id, name, cron_expr, tz, message, channel, channel_target, enabled, created_at, payload_kind, tlg_call) VALUES (945, 'test-bracket-cron-protocol', 'Wake up for work', '30 7 * * 0-4', 'Asia/Jerusalem', 'Time to get up for work', 'web', '+972544965929', 1, '2026-02-25 14:42:27', 'agentturn', 1);

-- provider_models (data included)
DROP TABLE IF EXISTS provider_models;
CREATE TABLE provider_models (
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                PRIMARY KEY (user_id, provider)
            );
INSERT INTO provider_models (user_id, provider, model) VALUES ('default', 'openrouter', 'arcee-ai/trinity-large-preview:free');
INSERT INTO provider_models (user_id, provider, model) VALUES ('default', 'claude', 'claude-haiku-4-5-20251001');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-inline-think-xhigh-unsupported', 'openai', 'gpt-4o-mini');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-inline-think-xhigh-supported', 'openai', 'gpt-5.2');
INSERT INTO provider_models (user_id, provider, model) VALUES ('default', 'ollama', 'minimax-m2.5:cloud');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-5fa23921', 'claude', 'claude-3-5-sonnet-20241022');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-29de687b', 'claude', 'claude-3-5-sonnet-20241022');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-989ca37d', 'claude', 'claude-3-5-sonnet-20241022');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-fafa2f0a', 'claude', 'claude-3-5-sonnet-20241022');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-ea09e728', 'claude', 'claude-3-5-sonnet-20241022');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-be43f230', 'claude', 'claude-3-5-sonnet-20241022');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-a52a1831', 'claude', 'claude-3-5-sonnet-20241022');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-ca8a722a', 'claude', 'claude-3-5-sonnet-20241022');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-ee7ca36b', 'claude', 'claude-3-5-sonnet-20241022');
INSERT INTO provider_models (user_id, provider, model) VALUES ('test-get-thinking-options-cf31684a', 'claude', 'claude-3-5-sonnet-20241022');

-- provider_runtime_state (data included)
DROP TABLE IF EXISTS provider_runtime_state;
CREATE TABLE provider_runtime_state (
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                auto_disabled INTEGER NOT NULL DEFAULT 0,
                disabled_reason TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, provider)
            );
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('default', 'claude', 1, 1, 'billing', '2026-02-24 15:22:16');
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('default', 'openrouter', 1, 0, '', '2026-02-27 09:36:16');
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('default', 'ollama', 1, 0, '', '2026-02-27 10:29:54');
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('repro-pending-tasks', 'claude', 1, 1, 'billing', '2026-02-17 02:00:00');
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('repro-pending-tasks', 'ollama', 1, 0, '', '2026-02-17 02:00:38');
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('repro-cron-proto', 'claude', 1, 1, 'billing', '2026-02-17 05:30:00');
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('repro-cron-proto', 'ollama', 1, 0, '', '2026-02-17 05:30:27');
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('test', 'claude', 1, 1, 'billing', '2026-02-24 06:32:26');
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('test', 'ollama', 1, 0, '', '2026-02-24 06:36:59');
INSERT INTO provider_runtime_state (user_id, provider, enabled, auto_disabled, disabled_reason, updated_at) VALUES ('default', 'google', 1, 0, '', '2026-02-28 05:45:46');

-- skill_toggles (data included)
DROP TABLE IF EXISTS skill_toggles;
CREATE TABLE skill_toggles (
                user_id TEXT NOT NULL,
                skill_id TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, skill_id)
            );
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('default', 'auto-updater', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('default', 'drive', 0);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('default', 'apple-notes', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('smoke-reminder-fallback', 'reminders', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('test-reminder-tool-skip-fallback', 'reminders', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('test-remove-reminder-context', 'reminders', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('test-tool-trace-friendly', 'reminders', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('test-tool-trace-telegram-suppressed', 'reminders', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('sim-openrouter-1', 'files', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('sim-openrouter-2', 'files', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('sim-openrouter-3', 'files', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('sim-claude-1', 'files', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('sim-claude-2', 'files', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('sim-claude-3', 'files', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('sim-allowed-openrouter', 'files', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('sim-allowed-claude', 'files', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('repro-pending-tasks', 'reminders', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('default', 'audio_notes', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('test-pending-tasks-overview', 'reminders', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('test-audio-provider-response-ok', 'audio_notes', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('test-audio-provider-response-error', 'audio_notes', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('test-update-reminder-fallback', 'reminders', 1);
INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES ('default', 'competitor', 1);

-- system_config (data included)
DROP TABLE IF EXISTS system_config;
CREATE TABLE system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
INSERT INTO system_config (key, value, updated_at) VALUES ('exec_allowed_bins_extra', '', '2026-02-24 15:10:03');
INSERT INTO system_config (key, value, updated_at) VALUES ('whatsapp_owner', '13065007872', '2026-02-14 16:47:20');
INSERT INTO system_config (key, value, updated_at) VALUES ('cooldown:gif_reply:default', '1772026463', '2026-02-25 13:34:23');
INSERT INTO system_config (key, value, updated_at) VALUES ('cooldown:telegram_auto_reaction:default', '1771369128', '2026-02-17 22:58:48');

-- user_settings (data included)
DROP TABLE IF EXISTS user_settings;
CREATE TABLE user_settings (
                user_id TEXT PRIMARY KEY,
                mood TEXT NOT NULL DEFAULT 'normal',
                default_ai_provider TEXT NOT NULL DEFAULT 'groq',
                updated_at TEXT NOT NULL
            , pending_location_request TEXT, fallback_providers TEXT DEFAULT '', thinking_level TEXT NOT NULL DEFAULT 'off', reasoning_mode TEXT NOT NULL DEFAULT 'off', final_mode TEXT NOT NULL DEFAULT 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('default', 'friendly', 'google', '2026-02-27 11:43:23', NULL, 'openrouter', 'minimal', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip', 'normal', 'openrouter', '2026-02-14 18:39:38', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-handler-pass', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'medium', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-reasoning-format', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-reasoning-off', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-8fad2bc9', 'normal', 'openrouter', '2026-02-14 18:44:22', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-5aca7336', 'normal', 'openrouter', '2026-02-14 18:47:45', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-849ff249', 'normal', 'openrouter', '2026-02-14 18:57:58', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-61a94d84', 'normal', 'openrouter', '2026-02-14 19:00:28', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-3eac8404', 'normal', 'openrouter', '2026-02-14 19:25:37', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-reasoning-fallback', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-a3c6d8aa', 'normal', 'openrouter', '2026-02-14 19:27:15', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-b7237492', 'normal', 'openrouter', '2026-02-14 20:00:46', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-reasoning-stream-separate', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'stream', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-6c965867', 'normal', 'openrouter', '2026-02-14 20:37:14', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-2c655f84', 'normal', 'openrouter', '2026-02-14 20:43:32', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-f15a41f8', 'normal', 'openrouter', '2026-02-14 21:02:29', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-00c99e0d', 'normal', 'openrouter', '2026-02-14 21:05:31', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('repro-think-only-off', 'normal', 'openrouter', '2026-02-14 21:08:11', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('repro-think-only-stream', 'normal', 'openrouter', '2026-02-14 21:08:31', NULL, '', 'off', 'stream', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-7ea55d6f', 'normal', 'openrouter', '2026-02-14 21:12:08', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-reasoning-off-think-only', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-reasoning-stream-think-only', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'stream', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-aa0c479c', 'normal', 'openrouter', '2026-02-14 21:13:18', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-d360722f', 'normal', 'openrouter', '2026-02-14 21:52:15', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-a59baaf9', 'normal', 'openrouter', '2026-02-14 22:24:09', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-6ab0199b', 'normal', 'openrouter', '2026-02-14 22:24:51', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-140b9e42', 'normal', 'openrouter', '2026-02-14 22:26:38', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-d2654e74', 'normal', 'openrouter', '2026-02-14 22:29:02', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-19ee2613', 'normal', 'openrouter', '2026-02-15 05:39:54', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-d22a514c', 'normal', 'openrouter', '2026-02-15 05:40:35', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-9b823c40', 'normal', 'openrouter', '2026-02-15 05:59:21', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-9e70b42f', 'normal', 'openrouter', '2026-02-15 06:05:35', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-11914773', 'normal', 'openrouter', '2026-02-15 06:15:33', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-91227ade', 'normal', 'openrouter', '2026-02-15 06:21:35', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-aa7f9d98', 'normal', 'openrouter', '2026-02-15 06:26:45', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-365d5f7f', 'normal', 'openrouter', '2026-02-15 06:27:43', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-f0a229d6', 'normal', 'openrouter', '2026-02-15 09:20:23', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-1d4a476f', 'normal', 'openrouter', '2026-02-15 09:22:47', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-66b33155', 'normal', 'openrouter', '2026-02-15 09:28:02', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-ab4297dc', 'normal', 'openrouter', '2026-02-15 09:30:12', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-fa5365ea', 'normal', 'openrouter', '2026-02-15 09:34:05', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-eefb6944', 'normal', 'openrouter', '2026-02-15 09:39:08', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-445f24a2', 'normal', 'openrouter', '2026-02-15 09:39:56', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-45e0f7e7', 'normal', 'openrouter', '2026-02-15 09:45:43', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-7ed0dbaf', 'normal', 'openrouter', '2026-02-15 09:55:19', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-00e2f1ed', 'normal', 'openrouter', '2026-02-15 09:56:01', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('sim-openrouter-1', 'normal', 'openrouter', '2026-02-15 09:58:46', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('sim-openrouter-2', 'normal', 'openrouter', '2026-02-15 09:58:49', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('sim-openrouter-3', 'normal', 'openrouter', '2026-02-15 09:58:52', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('sim-claude-1', 'normal', 'claude', '2026-02-15 09:58:55', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('sim-claude-2', 'normal', 'claude', '2026-02-15 09:58:57', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('sim-claude-3', 'normal', 'claude', '2026-02-15 09:59:00', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('sim-allowed-openrouter', 'normal', 'openrouter', '2026-02-15 09:59:36', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('sim-allowed-claude', 'normal', 'claude', '2026-02-15 09:59:39', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-516e9011', 'normal', 'openrouter', '2026-02-15 10:03:36', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-079067a1', 'normal', 'openrouter', '2026-02-15 10:04:22', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-check-openrouter', 'normal', 'openrouter', '2026-02-15 12:23:31', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-check-claude', 'normal', 'claude', '2026-02-15 12:23:32', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-check-openai', 'normal', 'openai', '2026-02-15 12:23:32', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-check-ollama', 'normal', 'ollama', '2026-02-15 12:23:32', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-check-groq', 'normal', 'groq', '2026-02-15 12:23:32', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-check-google', 'normal', 'google', '2026-02-15 12:23:32', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-f637a0af', 'normal', 'ollama', '2026-02-15 12:26:49', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-a41431fc', 'normal', 'ollama', '2026-02-15 12:26:50', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-2a4f0960', 'normal', 'ollama', '2026-02-15 12:27:10', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-10c78ebe', 'normal', 'ollama', '2026-02-15 12:27:11', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-d3bb8d03', 'normal', 'ollama', '2026-02-15 12:32:00', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-bb4f4a22', 'normal', 'ollama', '2026-02-15 12:32:00', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-a7e93128', 'normal', 'openrouter', '2026-02-15 12:32:04', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-14f058fa', 'normal', 'ollama', '2026-02-15 12:58:11', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-11e09a86', 'normal', 'ollama', '2026-02-15 12:58:11', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-8d66cf14', 'normal', 'openrouter', '2026-02-15 12:58:15', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-8bceebbd', 'normal', 'openrouter', '2026-02-15 16:02:33', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-6b927c10', 'normal', 'openrouter', '2026-02-15 16:17:06', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-8869e330', 'normal', 'openrouter', '2026-02-15 16:18:02', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-df0cf459', 'normal', 'openrouter', '2026-02-15 16:18:59', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-a41eee46', 'normal', 'openrouter', '2026-02-15 16:24:10', NULL, '', 'high', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-ea328b53', 'normal', 'openrouter', '2026-02-15 19:04:07', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-think-only', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-think-continue', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'minimal', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-d0da1ef2', 'normal', 'openrouter', '2026-02-15 19:04:52', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-a0334064', 'normal', 'openrouter', '2026-02-15 19:07:15', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-752448e1', 'normal', 'openrouter', '2026-02-15 19:12:21', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-think-mixed', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-think-on', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'low', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-think-options', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'medium', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-think-thinkstuff', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-d7101427', 'normal', 'openrouter', '2026-02-15 19:13:39', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-think-url', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-f36fa52f', 'normal', 'openrouter', '2026-02-15 19:14:33', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-28432b68', 'normal', 'openrouter', '2026-02-15 19:28:16', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-4f74b803', 'normal', 'openrouter', '2026-02-15 19:29:36', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-5812f183', 'normal', 'openrouter', '2026-02-16 04:04:46', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-b13dfb3a', 'normal', 'openrouter', '2026-02-16 04:05:17', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('cmp-inline-dup-check', 'normal', 'openrouter', '2026-02-16 04:49:21', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-dd2b7bbc', 'normal', 'openrouter', '2026-02-16 05:35:22', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-reasoning-only', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'stream', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-reasoning-continue', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-reasoning-options', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-reasoning-invalid', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup', 'normal', 'openrouter', '2026-02-16 05:35:43', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-think-xhigh-unsupported', 'normal', 'openai', '2026-02-20 17:41:25', NULL, '', 'xhigh', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-think-xhigh-supported', 'normal', 'openai', '2026-02-20 17:41:25', NULL, '', 'xhigh', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-reasoning-stream-incremental', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'stream', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-5de35a90', 'normal', 'openrouter', '2026-02-16 05:35:43', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-31997e7f', 'normal', 'openrouter', '2026-02-16 05:36:05', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-dffd3eb6', 'normal', 'openrouter', '2026-02-16 05:36:05', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('cmp-inline-dup-check-v2', 'normal', 'openrouter', '2026-02-16 05:36:20', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-3c1daee2', 'normal', 'openrouter', '2026-02-16 05:44:55', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-1c3bd2a5', 'normal', 'openrouter', '2026-02-16 05:44:55', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-751e9cd2', 'normal', 'openrouter', '2026-02-16 05:47:20', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-d61d2ac5', 'normal', 'openrouter', '2026-02-16 05:47:20', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-8659f232', 'normal', 'openrouter', '2026-02-16 05:57:31', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-ac45d948', 'normal', 'openrouter', '2026-02-16 05:57:32', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-03e61308', 'normal', 'openrouter', '2026-02-16 06:21:12', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-71396243', 'normal', 'openrouter', '2026-02-16 06:21:13', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-1b7cd438', 'normal', 'ollama', '2026-02-16 06:21:13', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-4de91d2a', 'normal', 'ollama', '2026-02-16 06:21:13', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-1ea51b45', 'normal', 'openrouter', '2026-02-16 06:26:04', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-1274bdd2', 'normal', 'openrouter', '2026-02-16 06:26:04', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-31704fa8', 'normal', 'openrouter', '2026-02-16 06:26:34', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-afd69bd6', 'normal', 'openrouter', '2026-02-16 06:26:35', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-9c3bf1f8', 'normal', 'ollama', '2026-02-16 06:26:35', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-c963bf1b', 'normal', 'ollama', '2026-02-16 06:26:35', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-43cd2f68', 'normal', 'openrouter', '2026-02-16 07:49:07', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-final-mode-strict-visible', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'off', 'strict');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-final-mode-strict-no-final', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'off', 'strict');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-final-mode-strict-stream-events', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'off', 'strict');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-6209cae3', 'normal', 'openrouter', '2026-02-16 07:49:08', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-b466085e', 'normal', 'openrouter', '2026-02-16 07:49:22', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-77f2cb3e', 'normal', 'openrouter', '2026-02-16 07:49:23', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-e613063f', 'normal', 'openrouter', '2026-02-16 07:49:38', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-3085d405', 'normal', 'openrouter', '2026-02-16 07:49:39', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-0b1fb559', 'normal', 'openrouter', '2026-02-16 07:50:10', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-c40fcf99', 'normal', 'openrouter', '2026-02-16 07:50:11', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-6844b7bc', 'normal', 'ollama', '2026-02-16 07:50:11', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-664fee6b', 'normal', 'ollama', '2026-02-16 07:50:11', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-a9046548', 'normal', 'openrouter', '2026-02-16 08:14:21', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-5137c311', 'normal', 'openrouter', '2026-02-16 08:14:22', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-2f5e6565', 'normal', 'ollama', '2026-02-16 08:14:22', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-9ef905dd', 'normal', 'ollama', '2026-02-16 08:14:22', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-a620ae22', 'normal', 'openrouter', '2026-02-16 08:25:40', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-ea63a0c1', 'normal', 'openrouter', '2026-02-16 08:25:41', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-3d3e57be', 'normal', 'ollama', '2026-02-16 08:25:41', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-334da3d7', 'normal', 'ollama', '2026-02-16 08:25:41', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-142ac8df', 'normal', 'openrouter', '2026-02-16 08:27:37', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-248fd291', 'normal', 'openrouter', '2026-02-16 08:27:37', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-af69eed0', 'normal', 'ollama', '2026-02-16 08:27:37', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-54f53643', 'normal', 'ollama', '2026-02-16 08:27:37', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-5a64beff', 'normal', 'openrouter', '2026-02-16 08:29:22', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-b75be52a', 'normal', 'openrouter', '2026-02-16 08:29:22', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-0a84cb23', 'normal', 'ollama', '2026-02-16 08:29:22', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-e8315e53', 'normal', 'ollama', '2026-02-16 08:29:22', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-206ee5de', 'normal', 'openrouter', '2026-02-16 08:34:31', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-5ef24943', 'normal', 'openrouter', '2026-02-16 08:34:31', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-0bff1bdf', 'normal', 'ollama', '2026-02-16 08:34:32', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-be363103', 'normal', 'ollama', '2026-02-16 08:34:32', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-b359cc3c', 'normal', 'openrouter', '2026-02-16 08:36:19', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-abae2542', 'normal', 'openrouter', '2026-02-16 08:36:20', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-6eb5f4b5', 'normal', 'ollama', '2026-02-16 08:36:20', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-f74212c9', 'normal', 'ollama', '2026-02-16 08:36:20', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-d441ef48', 'normal', 'openrouter', '2026-02-16 08:37:18', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-131e22f7', 'normal', 'openrouter', '2026-02-16 08:37:18', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-c8b5052c', 'normal', 'ollama', '2026-02-16 08:37:19', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-37170fee', 'normal', 'ollama', '2026-02-16 08:37:19', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-2bf2b68e', 'normal', 'openrouter', '2026-02-16 08:44:45', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-dc9b6b7a', 'normal', 'openrouter', '2026-02-16 08:44:46', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-60b729b2', 'normal', 'ollama', '2026-02-16 08:44:46', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-1380e4f5', 'normal', 'ollama', '2026-02-16 08:44:46', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-ac8d44ad', 'normal', 'openrouter', '2026-02-16 08:49:36', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-bff22684', 'normal', 'openrouter', '2026-02-16 08:49:37', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-0348fadc', 'normal', 'ollama', '2026-02-16 08:49:37', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-5a56ff38', 'normal', 'ollama', '2026-02-16 08:49:37', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-85da3eb0', 'normal', 'openrouter', '2026-02-16 08:57:19', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-6a86cf5c', 'normal', 'openrouter', '2026-02-16 08:57:19', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-49982dae', 'normal', 'ollama', '2026-02-16 08:57:20', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-ae5ac461', 'normal', 'ollama', '2026-02-16 08:57:20', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-5a8bf096', 'normal', 'openrouter', '2026-02-16 09:18:49', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-d4cce035', 'normal', 'openrouter', '2026-02-16 09:18:50', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-final-mode-strict-ollama-no-final', 'normal', 'openrouter', '2026-02-20 17:41:25', NULL, '', 'off', 'off', 'strict');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-202264ff', 'normal', 'openrouter', '2026-02-16 10:56:47', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-ceef7c7d', 'normal', 'openrouter', '2026-02-16 10:56:47', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-9023e5e9', 'normal', 'openrouter', '2026-02-16 10:57:28', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-6caf74d9', 'normal', 'openrouter', '2026-02-16 10:57:29', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-f59d5655', 'normal', 'openrouter', '2026-02-16 11:31:15', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-a7720911', 'normal', 'openrouter', '2026-02-16 11:31:15', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-d3fc37d1', 'normal', 'openrouter', '2026-02-16 11:33:00', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-92c9414e', 'normal', 'openrouter', '2026-02-16 11:33:00', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-622547ae', 'normal', 'ollama', '2026-02-16 11:33:00', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-fba72125', 'normal', 'ollama', '2026-02-16 11:33:00', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-8554fb4b', 'normal', 'claude', '2026-02-16 11:55:16', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-75a9b104', 'normal', 'claude', '2026-02-16 11:55:17', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-70cfc88c', 'normal', 'ollama', '2026-02-16 11:55:17', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-7b18c309', 'normal', 'ollama', '2026-02-16 11:55:17', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-602ce11b', 'normal', 'claude', '2026-02-16 11:56:04', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-f9cec46d', 'normal', 'claude', '2026-02-16 11:56:05', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-8290ddc8', 'normal', 'ollama', '2026-02-16 11:56:05', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-88dc0137', 'normal', 'ollama', '2026-02-16 11:56:05', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-82cd7634', 'normal', 'claude', '2026-02-16 13:14:59', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-46c881a2', 'normal', 'claude', '2026-02-16 13:15:00', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-6dc4686c', 'normal', 'ollama', '2026-02-16 13:15:00', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-7c58bc4c', 'normal', 'ollama', '2026-02-16 13:15:00', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-9aa47916', 'normal', 'claude', '2026-02-16 17:21:13', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-00f51020', 'normal', 'claude', '2026-02-16 17:21:14', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-b21cf8a7', 'normal', 'claude', '2026-02-16 17:40:19', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-5fa23921', 'normal', 'claude', '2026-02-16 17:40:19', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-fee2efed', 'normal', 'claude', '2026-02-16 17:40:20', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-e5c20c9c', 'normal', 'claude', '2026-02-16 17:42:39', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-29de687b', 'normal', 'claude', '2026-02-16 17:42:39', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-28ff0c5a', 'normal', 'claude', '2026-02-16 17:42:40', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-1aafca9a', 'normal', 'claude', '2026-02-16 18:06:57', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-989ca37d', 'normal', 'claude', '2026-02-16 18:06:58', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-f3e83c27', 'normal', 'claude', '2026-02-16 18:06:58', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-3864bbb3', 'normal', 'claude', '2026-02-16 18:08:20', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-fafa2f0a', 'normal', 'claude', '2026-02-16 18:08:20', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-8aae54ac', 'normal', 'claude', '2026-02-16 18:08:20', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-2a5bdec5', 'normal', 'claude', '2026-02-16 18:29:49', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-ea09e728', 'normal', 'claude', '2026-02-16 18:29:49', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-da3010d4', 'normal', 'claude', '2026-02-16 18:29:49', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-00bdbd6b', 'normal', 'claude', '2026-02-16 18:30:51', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-be43f230', 'normal', 'claude', '2026-02-16 18:30:51', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-9b1202cf', 'normal', 'claude', '2026-02-16 18:30:52', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-8db205f6', 'normal', 'claude', '2026-02-16 18:36:25', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-a52a1831', 'normal', 'claude', '2026-02-16 18:36:25', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-ea0bf377', 'normal', 'claude', '2026-02-16 18:36:25', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-12bbe11d', 'normal', 'claude', '2026-02-20 17:40:21', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-ca8a722a', 'normal', 'claude', '2026-02-20 17:40:21', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-e4049bd9', 'normal', 'claude', '2026-02-20 17:40:21', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-3d5a33bf', 'normal', 'ollama', '2026-02-20 17:40:22', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-963b0111', 'normal', 'ollama', '2026-02-20 17:40:22', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-46293ea8', 'normal', 'claude', '2026-02-20 17:40:51', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-ee7ca36b', 'normal', 'claude', '2026-02-20 17:40:51', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-08c7fb3a', 'normal', 'claude', '2026-02-20 17:40:52', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-0b746c89', 'normal', 'ollama', '2026-02-20 17:40:52', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-cb61f625', 'normal', 'ollama', '2026-02-20 17:40:52', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-thinking-roundtrip-56180fc8', 'normal', 'claude', '2026-02-20 17:41:25', NULL, '', 'xhigh', 'on', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-get-thinking-options-cf31684a', 'normal', 'claude', '2026-02-20 17:41:25', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('test-inline-no-raw-dup-3ddc6755', 'normal', 'claude', '2026-02-20 17:41:25', NULL, '', 'high', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-6001bd75', 'normal', 'ollama', '2026-02-20 17:41:26', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-1e0cd437', 'normal', 'ollama', '2026-02-20 17:41:26', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-e80205cc', 'normal', 'ollama', '2026-02-27 11:50:45', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-1b22f53e', 'normal', 'google', '2026-02-27 11:50:46', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-b2455fcd', 'normal', 'ollama', '2026-02-27 11:50:46', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-5c587fe7', 'normal', 'ollama', '2026-02-27 11:51:33', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-7c20fe69', 'normal', 'google', '2026-02-27 11:51:33', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-e5592c43', 'normal', 'ollama', '2026-02-27 11:51:33', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-47487995', 'normal', 'ollama', '2026-02-27 11:52:06', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-f6b08ff7', 'normal', 'google', '2026-02-27 11:52:06', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-121da5b6', 'normal', 'ollama', '2026-02-27 11:52:06', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-58867917', 'normal', 'ollama', '2026-02-27 11:52:34', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-5dd3b073', 'normal', 'google', '2026-02-27 11:52:34', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-81dbc85a', 'normal', 'ollama', '2026-02-27 11:52:34', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-d531d6d7', 'normal', 'ollama', '2026-02-27 11:53:10', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-4d0a9d2a', 'normal', 'google', '2026-02-27 11:53:10', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-c0da2899', 'normal', 'ollama', '2026-02-27 11:53:10', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-1f05cd40', 'normal', 'ollama', '2026-02-27 11:54:24', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-8d844412', 'normal', 'google', '2026-02-27 11:54:24', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-4df0cc43', 'normal', 'ollama', '2026-02-27 11:54:24', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-39d7aae0', 'normal', 'ollama', '2026-02-27 11:55:05', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-3a34a7d8', 'normal', 'google', '2026-02-27 11:55:05', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-104bfd5c', 'normal', 'ollama', '2026-02-27 11:55:05', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-2b1aeb76', 'normal', 'ollama', '2026-02-27 11:55:25', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-6c99cd98', 'normal', 'google', '2026-02-27 11:55:25', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-34fa407a', 'normal', 'ollama', '2026-02-27 11:55:25', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-3c4a19f9', 'normal', 'ollama', '2026-02-27 11:55:37', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-0a931c67', 'normal', 'ollama', '2026-02-27 11:55:55', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-15e661c5', 'normal', 'google', '2026-02-27 11:56:28', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-fc3568d3', 'normal', 'google', '2026-02-27 11:56:28', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-2607403f', 'normal', 'ollama', '2026-02-27 11:56:28', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-e4c2f473', 'normal', 'google', '2026-02-27 11:56:58', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-c94472b8', 'normal', 'google', '2026-02-27 11:56:58', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-1ea18e0b', 'normal', 'ollama', '2026-02-27 11:56:58', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-ed254f1f', 'normal', 'google', '2026-02-27 11:57:22', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-2adc7e5f', 'normal', 'google', '2026-02-27 11:57:22', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-dc584518', 'normal', 'ollama', '2026-02-27 11:57:22', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-route-e354117d', 'normal', 'google', '2026-02-27 11:58:08', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-ollama-fallback-e4c6b61f', 'normal', 'google', '2026-02-27 11:58:08', NULL, '', 'off', 'off', 'off');
INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at, pending_location_request, fallback_providers, thinking_level, reasoning_mode, final_mode) VALUES ('vision-no-key-6412fe9f', 'normal', 'ollama', '2026-02-27 11:58:08', NULL, '', 'off', 'off', 'off');

-- api_keys (schema only — data excluded)
DROP TABLE IF EXISTS api_keys;
CREATE TABLE api_keys (
                key_name TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

-- conversation_folders (schema only — data excluded)
DROP TABLE IF EXISTS conversation_folders;
CREATE TABLE conversation_folders (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'web',
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#6366F1',
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

-- conversations (schema only — data excluded)
DROP TABLE IF EXISTS conversations;
CREATE TABLE conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                created_at TEXT NOT NULL
            , folder_id TEXT, title TEXT);

-- cron_job_runs (schema only — data excluded)
DROP TABLE IF EXISTS cron_job_runs;
CREATE TABLE cron_job_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cron_job_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                trigger TEXT NOT NULL DEFAULT 'schedule',
                run_mode TEXT NOT NULL DEFAULT 'due',
                status TEXT NOT NULL,
                output TEXT,
                error TEXT,
                created_at TEXT NOT NULL
            );

-- exec_approvals (schema only — data excluded)
DROP TABLE IF EXISTS exec_approvals;
CREATE TABLE exec_approvals (
                approval_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                channel_target TEXT,
                command TEXT NOT NULL,
                binary TEXT NOT NULL,
                timeout_sec INTEGER,
                workdir TEXT,
                background INTEGER NOT NULL DEFAULT 0,
                pty INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                decision TEXT,
                resolved_at TEXT,
                created_at TEXT NOT NULL
            );

-- messages (schema only — data excluded)
DROP TABLE IF EXISTS messages;
CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                provider_used TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

-- pending_learn_about (schema only — data excluded)
DROP TABLE IF EXISTS pending_learn_about;
CREATE TABLE pending_learn_about (
                user_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

-- pending_spotify_play (schema only — data excluded)
DROP TABLE IF EXISTS pending_spotify_play;
CREATE TABLE pending_spotify_play (
                user_id TEXT PRIMARY KEY,
                track_uri TEXT NOT NULL,
                devices_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

-- reminders (schema only — data excluded)
DROP TABLE IF EXISTS reminders;
CREATE TABLE reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                channel_target TEXT NOT NULL,
                message TEXT NOT NULL,
                run_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );

-- saved_audio_notes (schema only — data excluded)
DROP TABLE IF EXISTS saved_audio_notes;
CREATE TABLE saved_audio_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                title TEXT NOT NULL,
                transcript TEXT NOT NULL,
                formatted TEXT NOT NULL
            );

-- spotify_retry_request (schema only — data excluded)
DROP TABLE IF EXISTS spotify_retry_request;
CREATE TABLE spotify_retry_request (
                user_id TEXT PRIMARY KEY,
                play_query TEXT NOT NULL,
                track_uri TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

-- spotify_user_tokens (schema only — data excluded)
DROP TABLE IF EXISTS spotify_user_tokens;
CREATE TABLE spotify_user_tokens (
                user_id TEXT PRIMARY KEY,
                refresh_token TEXT NOT NULL,
                access_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

-- subagent_runs (schema only — data excluded)
DROP TABLE IF EXISTS subagent_runs;
CREATE TABLE subagent_runs (
                run_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                parent_conversation_id TEXT NOT NULL,
                child_conversation_id TEXT NOT NULL,
                task TEXT NOT NULL,
                label TEXT,
                provider_name TEXT,
                channel TEXT NOT NULL,
                channel_target TEXT,
                cleanup TEXT NOT NULL DEFAULT 'keep',
                status TEXT NOT NULL,
                result_text TEXT,
                error_text TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT
            , model_override TEXT, thinking_override TEXT, run_timeout_seconds INTEGER NOT NULL DEFAULT 0, archived_at TEXT);

-- tasks (schema only — data excluded)
DROP TABLE IF EXISTS tasks;
CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT,
                status TEXT NOT NULL,
                run_at TEXT,
                created_at TEXT NOT NULL
            );

-- usage_stats (schema only — data excluded)
DROP TABLE IF EXISTS usage_stats;
CREATE TABLE usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default',
                provider TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

-- user_location (schema only — data excluded)
DROP TABLE IF EXISTS user_location;
CREATE TABLE user_location (
                user_id TEXT PRIMARY KEY,
                location_name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                updated_at TEXT NOT NULL
            );

COMMIT;