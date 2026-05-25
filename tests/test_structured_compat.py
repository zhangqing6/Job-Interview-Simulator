"""GLM-style markdown-wrapped JSON parsing and missing-field tolerance."""

import pytest
from langchain_core.messages import AIMessage

from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from interview_simulator.model_layer.report_schemas import InterviewLLMReport
from interview_simulator.model_layer.schemas import GeneratedQuestion, QuestionCritique
from interview_simulator.model_layer.structured_compat import (
    extract_json_text,
    parse_structured_message,
)


def test_extract_json_strips_markdown_fence() -> None:
    raw = """```json
{
  "chain_of_thought": "probe async",
  "question_text": "How do you handle backpressure?",
  "expected_depth": "mid"
}
```"""
    text = extract_json_text(raw)
    obj = GeneratedQuestion.model_validate_json(text)
    assert obj.question_text.startswith("How")


def test_parse_structured_message_from_ai_message() -> None:
    msg = AIMessage(
        content='```json\n{"chain_of_thought":"x","question_text":"Q?","expected_depth":"senior"}\n```'
    )
    out = parse_structured_message(msg, GeneratedQuestion)
    assert out.expected_depth == "senior"


def test_missing_expected_depth_uses_defaults_from_request() -> None:
    msg = AIMessage(
        content='{"chain_of_thought":"probe payments","question_text":"Describe your outbox design?"}'
    )
    out = parse_structured_message(
        msg,
        GeneratedQuestion,
        defaults={"expected_depth": "mid"},
    )
    assert out.expected_depth == "mid"
    assert "outbox" in out.question_text.lower()


def test_question_alias_field() -> None:
    msg = AIMessage(
        content='{"chain_of_thought":"x","question":"What is CAP?"}'
    )
    out = parse_structured_message(msg, GeneratedQuestion, defaults={"expected_depth": "junior"})
    assert out.question_text == "What is CAP?"
    assert out.expected_depth == "junior"


def test_extract_json_empty_raises() -> None:
    with pytest.raises(ValueError, match="Empty"):
        extract_json_text("   ")


def test_parse_broken_question_critique_json() -> None:
    broken = """```json
{
  "is_sufficiently_challenging": true,
  "is_sufficiently_specific": relevant_to_jd_and_resume": true,
  "improvement_hint": null
}
```"""
    out = parse_structured_message(AIMessage(content=broken), QuestionCritique)
    assert out.difficulty_adequate is True
    assert out.relevance_adequate is True
    assert out.improvement_hint is None


def test_parse_interview_report_markdown_zh() -> None:
    md = """# 面试评估报告

## 总体评估
候选人技术基础尚可，但在幂等性与 Outbox 细节上深度不足。

## 优势
1. 理解分布式事务基本概念
2. 能结合支付场景举例

## 改进建议
1. 补充 Outbox 落库与投递细节
2. 量化性能与一致性权衡

## 推荐学习主题
1. 分布式事务模式
2. 支付幂等设计

## 总结
建议进入下一轮系统设计面试。"""
    out = parse_structured_message(AIMessage(content=md), InterviewLLMReport)
    assert "Outbox" in out.overall_assessment
    assert len(out.strengths) >= 2
    assert len(out.improvement_suggestions) >= 1
    assert "下一轮" in out.closing_summary


def test_parse_evaluation_markdown_prose() -> None:
    prose = """Scores:
- technical_depth: 4
- clarity: 4
- relevance: 5

Reasoning:
The candidate demonstrates solid understanding of distributed transaction tradeoffs."""
    msg = AIMessage(content=prose)
    out = parse_structured_message(msg, AnswerEvaluationResult)
    assert out.technical_depth == 4
    assert out.clarity == 4
    assert out.relevance == 5
    assert "distributed" in out.reasoning.lower()
