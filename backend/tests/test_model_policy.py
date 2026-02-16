from app.model_policy import (
    OPENROUTER_DEFAULT_MODEL_CHAIN,
    classify_openrouter_model_csv,
    coerce_openrouter_model_csv,
    is_openrouter_tool_model,
    split_model_csv,
)


def test_split_model_csv_dedupes_and_trims():
    assert split_model_csv("  a , b, a ,, ") == ["a", "b"]


def test_openrouter_policy_matches_kimi_and_trinity_families():
    assert is_openrouter_tool_model("moonshotai/kimi-k2.5")
    assert is_openrouter_tool_model("moonshotai/kimi-k2-thinking")
    assert is_openrouter_tool_model("arcee-ai/trinity-large-preview:free")
    assert not is_openrouter_tool_model("openai/gpt-4o-mini")


def test_classify_openrouter_model_csv_filters_unsupported_models():
    allowed, rejected = classify_openrouter_model_csv(
        "openrouter/moonshotai/kimi-k2.5,openai/gpt-4o-mini,arcee-ai/trinity-large-preview:free"
    )
    assert allowed == ["moonshotai/kimi-k2.5", "arcee-ai/trinity-large-preview:free"]
    assert rejected == ["openai/gpt-4o-mini"]


def test_coerce_openrouter_model_csv_falls_back_to_default_chain():
    normalized, rejected = coerce_openrouter_model_csv("openai/gpt-4o-mini")
    assert rejected == ["openai/gpt-4o-mini"]
    assert normalized == OPENROUTER_DEFAULT_MODEL_CHAIN
