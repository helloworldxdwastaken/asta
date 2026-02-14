from app.routers.chat import _normalize_wa_number, _whatsapp_sender_allowed


def test_normalize_wa_number_strips_suffix_and_symbols():
    assert _normalize_wa_number("+1 (555) 123-4567@s.whatsapp.net") == "15551234567"


def test_whatsapp_policy_self_chat_only_allows_owner_only():
    assert _whatsapp_sender_allowed(
        whitelist={"15550001111"},
        owner_number="15551234567",
        self_chat_only=True,
        raw_number="15551234567@s.whatsapp.net",
    )
    assert not _whatsapp_sender_allowed(
        whitelist={"15550001111"},
        owner_number="15551234567",
        self_chat_only=True,
        raw_number="15550001111@s.whatsapp.net",
    )


def test_whatsapp_policy_whitelist_applies_when_present():
    assert _whatsapp_sender_allowed(
        whitelist={"15550001111"},
        owner_number="",
        self_chat_only=False,
        raw_number="15550001111@s.whatsapp.net",
    )
    assert not _whatsapp_sender_allowed(
        whitelist={"15550001111"},
        owner_number="",
        self_chat_only=False,
        raw_number="15550009999@s.whatsapp.net",
    )


def test_whatsapp_policy_empty_whitelist_allows_all_when_not_self_only():
    assert _whatsapp_sender_allowed(
        whitelist=set(),
        owner_number="",
        self_chat_only=False,
        raw_number="15550009999@s.whatsapp.net",
    )
