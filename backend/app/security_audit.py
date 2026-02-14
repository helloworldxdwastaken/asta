"""Lightweight security audit warnings for Asta runtime config."""
from __future__ import annotations

from app.config import get_settings
from app.exec_tool import get_effective_exec_bins

_DANGEROUS_EXEC_BINS = {
    "bash",
    "sh",
    "zsh",
    "python",
    "python3",
    "node",
    "npm",
    "curl",
    "wget",
}


async def collect_security_warnings(db, user_id: str = "default") -> dict:
    settings = get_settings()
    findings: list[dict] = []

    if settings.exec_security == "full":
        findings.append(
            {
                "id": "exec.mode.full",
                "severity": "critical",
                "title": "Exec security is set to full",
                "detail": "Any shell command can run. This greatly increases accidental or malicious command risk.",
                "remediation": "Use ASTA_EXEC_SECURITY=allowlist and keep allowed bins minimal.",
            }
        )
    else:
        effective_bins = await get_effective_exec_bins(db, user_id)
        risky = sorted(b for b in effective_bins if b in _DANGEROUS_EXEC_BINS)
        if risky:
            findings.append(
                {
                    "id": "exec.allowlist.risky_bins",
                    "severity": "warn",
                    "title": "Exec allowlist contains high-risk binaries",
                    "detail": f"Risky bins in allowlist: {', '.join(risky)}",
                    "remediation": "Remove broad shell/network binaries unless explicitly required for trusted workflows.",
                }
            )

    invalid_tg_ids = sorted(settings.telegram_allowlist_invalid)
    if invalid_tg_ids:
        preview = ", ".join(invalid_tg_ids[:5]) + (f" (+{len(invalid_tg_ids) - 5} more)" if len(invalid_tg_ids) > 5 else "")
        findings.append(
            {
                "id": "telegram.allowlist.invalid_entries",
                "severity": "warn",
                "title": "Telegram allowlist contains non-numeric entries",
                "detail": f"Ignored entries: {preview}",
                "remediation": "Use numeric Telegram sender IDs only in ASTA_TELEGRAM_ALLOWED_IDS.",
            }
        )

    has_critical = any((f.get("severity") == "critical") for f in findings)
    return {
        "has_critical": has_critical,
        "findings": findings,
    }

