"""LLM env resolution for Zhipu / BigModel OpenAI-compatible API."""

import pytest

import interview_simulator.model_layer.llm_factory as llm_factory


def test_llm_enabled_requires_judge_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)
    assert llm_factory.llm_enabled() is False
    monkeypatch.setenv("JUDGE_API_KEY", "test-key")
    assert llm_factory.llm_enabled() is True


def test_is_llm_scoring_and_report_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)
    assert llm_factory.is_llm_scoring_enabled() is False
    assert llm_factory.is_llm_report_enabled() is False

    monkeypatch.setenv("JUDGE_API_KEY", "k")
    monkeypatch.setenv("USE_LLM_SCORING", "true")
    monkeypatch.setenv("USE_LLM_REPORT", "false")
    assert llm_factory.is_llm_scoring_enabled() is True
    assert llm_factory.is_llm_report_enabled() is False


def test_resolve_llm_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_API_KEY", "k")
    monkeypatch.delenv("JUDGE_BASE_URL", raising=False)
    monkeypatch.delenv("JUDGE_MODEL", raising=False)
    cfg = llm_factory.resolve_llm_config()
    assert cfg.api_key == "k"
    assert cfg.base_url == llm_factory.DEFAULT_JUDGE_BASE_URL
    assert cfg.model == llm_factory.DEFAULT_JUDGE_MODEL


def test_resolve_llm_config_custom_base_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_API_KEY", "k")
    monkeypatch.setenv("JUDGE_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    monkeypatch.setenv("JUDGE_MODEL", "glm-4-flash")
    cfg = llm_factory.resolve_llm_config()
    assert cfg.base_url.endswith("/")
    assert cfg.model == "glm-4-flash"


def test_create_llm_uses_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_API_KEY", "k")
    monkeypatch.setenv("JUDGE_BASE_URL", "https://example.com/v1/")
    monkeypatch.setenv("JUDGE_MODEL", "glm-4")
    llm = llm_factory.create_llm(agent="test", operation="t")
    base = str(getattr(llm, "openai_api_base", "") or getattr(llm, "base_url", ""))
    assert base.startswith("https://example.com")


def test_create_judge_llm_zero_temperature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_API_KEY", "k")
    llm = llm_factory.create_judge_llm()
    assert llm.temperature == 0.0
