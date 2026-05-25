"""Structured output parsing compatible with GLM / models that wrap JSON in markdown fences."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from interview_simulator.model_layer.score_rubric import normalize_evaluation_scores
from interview_simulator.model_layer.report_schemas import InterviewLLMReport
from interview_simulator.model_layer.schemas import GeneratedQuestion, QuestionCritique

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?", re.IGNORECASE)
_TRAILING_FENCE_RE = re.compile(r"\n?```\s*$")
_SCORE_NUMERIC_RE = re.compile(
    r"(technical_depth|clarity|relevance|技术深度|表达清晰|相关性|技术|清晰|相关)"
    r"\s*[:：]\s*([0-5])\s*(?:分|/5)?",
    re.IGNORECASE,
)
_SCORE_FIELD_ALIASES = {
    "技术深度": "technical_depth",
    "技术": "technical_depth",
    "表达清晰": "clarity",
    "清晰": "clarity",
    "相关性": "relevance",
    "相关": "relevance",
}


def extract_json_text(raw: str) -> str:
    """Strip ```json fences and surrounding prose; return JSON object/array substring."""

    text = raw.strip()
    if not text:
        raise ValueError("Empty model response")

    if text.startswith("```"):
        text = _FENCE_RE.sub("", text)
        text = _TRAILING_FENCE_RE.sub("", text).strip()

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        match = re.search(pattern, text)
        if match:
            candidate = match.group(0)
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not locate valid JSON in model output: {text[:200]!r}…")


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "yes", "1", "on"):
        return True
    if text in ("false", "no", "0", "off"):
        return False
    return True


def _strip_fences(text: str) -> str:
    if text.strip().startswith("```"):
        text = _FENCE_RE.sub("", text.strip())
        text = _TRAILING_FENCE_RE.sub("", text).strip()
    return text


def _repair_glm_json(blob: str) -> str:
    """Fix common GLM JSON typos (unquoted tokens, duplicated colons)."""

    fixed = blob
    fixed = re.sub(
        r'"(is_sufficiently_specific)"\s*:\s*[a-z_]+"\s*:\s*(true|false)',
        r'"\1": \2',
        fixed,
        flags=re.IGNORECASE,
    )
    fixed = re.sub(
        r':\s*([a-z_][a-z0-9_]*)\s*"\s*:\s*(true|false|null)',
        r': \2',
        fixed,
        flags=re.IGNORECASE,
    )
    return fixed


def _try_load_json_dict(text: str) -> dict[str, Any] | None:
    stripped = _strip_fences(text)
    candidates: list[str] = [stripped]
    match = re.search(r"\{[\s\S]*\}", stripped)
    if match:
        candidates.append(match.group(0))
        candidates.append(_repair_glm_json(match.group(0)))

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            raw = json.loads(candidate)
            if isinstance(raw, dict):
                return raw
        except json.JSONDecodeError:
            continue
    return None


def _parse_question_critique_loose(text: str) -> dict[str, Any]:
    """Regex fallback when GLM returns broken JSON for self-critique."""

    content = _strip_fences(text)
    difficulty = True
    relevance = True

    diff_m = re.search(
        r"(?:difficulty_adequate|is_sufficiently_challenging|sufficiently_challenging)"
        r'\s*["\s:]*\s*(true|false)',
        content,
        re.IGNORECASE,
    )
    if diff_m:
        difficulty = _coerce_bool(diff_m.group(1))

    rel_m = re.search(
        r"(?:relevance_adequate|is_sufficiently_specific|relevant_to_jd_and_resume)"
        r'[^:]*:\s*"?([^,}\n"]+)',
        content,
        re.IGNORECASE,
    )
    if rel_m:
        tail = rel_m.group(1).strip()
        if tail.lower() in ("true", "false"):
            relevance = _coerce_bool(tail)
        elif re.search(r"\btrue\b", tail, re.IGNORECASE):
            relevance = True
        elif re.search(r"\bfalse\b", tail, re.IGNORECASE):
            relevance = False

    hint: str | None = None
    hint_m = re.search(r'improvement_hint["\s:]*+(null|"([^"]*)")', content, re.IGNORECASE)
    if hint_m:
        hint = None if hint_m.group(1).lower() == "null" else hint_m.group(2)

    reasoning = ""
    reason_m = re.search(r'reasoning["\s:]*+"([^"]*)"', content, re.IGNORECASE)
    if reason_m:
        reasoning = reason_m.group(1)
    else:
        reasoning = "Critique parsed from GLM non-standard JSON."

    return {
        "difficulty_adequate": difficulty,
        "relevance_adequate": relevance,
        "reasoning": reasoning,
        "improvement_hint": hint,
    }


def _parse_answer_evaluation_prose(text: str) -> dict[str, Any]:
    """GLM often returns markdown lists instead of JSON for scoring."""

    scores: dict[str, int] = {}
    for match in _SCORE_NUMERIC_RE.finditer(text):
        raw_field = match.group(1)
        field = _SCORE_FIELD_ALIASES.get(raw_field, raw_field.lower())
        if field not in scores:
            scores[field] = int(match.group(2))

    reasoning = ""
    reason_block = re.search(r"Reasoning:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
    if reason_block:
        reasoning = reason_block.group(1).strip()
    elif scores:
        reasoning = text.strip()[:800]
    else:
        reasoning = text.strip()[:800] or "No scoring reasoning provided."

    key_facts: list[str] = []
    facts_block = re.search(
        r"(?:key[_\s]?facts|关键事实)\s*[:：]\s*(.*)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if facts_block:
        block = facts_block.group(1).strip()
        for line in block.splitlines():
            line = re.sub(r"^[\s\-*•\d.)]+", "", line).strip()
            if line and len(line) > 3:
                key_facts.append(line[:200])
        key_facts = key_facts[:5]

    if not scores:
        raise ValueError(f"Could not parse evaluation scores from prose: {text[:200]!r}…")
    data: dict[str, Any] = {
        "reasoning": reasoning,
        "key_facts": key_facts,
        **scores,
    }
    return normalize_evaluation_scores(data)


_H2_SPLIT_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _split_markdown_h2_sections(text: str) -> dict[str, str]:
    """Split ``## Heading`` blocks into a lowercase title → body map."""

    body = _strip_fences(text).strip()
    body = re.sub(r"^#\s+[^\n]+\n+", "", body, count=1)
    sections: dict[str, str] = {}
    matches = list(_H2_SPLIT_RE.finditer(body))
    if not matches:
        return sections
    for idx, match in enumerate(matches):
        title = match.group(1).strip().lower()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        sections[title] = body[start:end].strip()
    return sections


def _section_body(sections: dict[str, str], *keywords: str) -> str:
    for title, content in sections.items():
        if any(kw in title for kw in keywords):
            return content
    return ""


def _parse_bullet_list(block: str) -> list[str]:
    items: list[str] = []
    for line in block.splitlines():
        cleaned = re.sub(r"^[\s\-*•\d.)]+", "", line).strip()
        if cleaned and len(cleaned) > 1:
            items.append(cleaned)
    if items:
        return items[:12]
    paragraph = " ".join(block.split())
    return [paragraph] if paragraph else []


def _parse_interview_report_markdown(text: str) -> dict[str, Any]:
    """GLM often returns a Markdown debrief instead of JSON for the final report."""

    sections = _split_markdown_h2_sections(text)
    if not sections and text.strip():
        overall = text.strip()
        return {
            "overall_assessment": overall[:4000],
            "strengths": [],
            "improvement_suggestions": [],
            "recommended_study_topics": [],
            "closing_summary": overall[:800],
        }

    overall = _section_body(
        sections,
        "总体评估",
        "overall assessment",
        "overall evaluation",
        "综合评估",
        "holistic",
    )
    strengths_block = _section_body(sections, "优势", "strength", "亮点", "highlights")
    improve_block = _section_body(
        sections,
        "改进建议",
        "改进方向",
        "待改进",
        "improvement",
        "actionable",
    )
    study_block = _section_body(
        sections,
        "推荐学习",
        "学习主题",
        "study topic",
        "recommended study",
        "复习主题",
    )
    closing = _section_body(
        sections,
        "总结",
        "closing",
        "结语",
        "wrap-up",
        "wrap up",
        "conclusion",
    )

    strengths = _parse_bullet_list(strengths_block)
    improvements = _parse_bullet_list(improve_block)
    topics = _parse_bullet_list(study_block)

    if not overall:
        overall = " ".join(sections.values())[:4000] or text.strip()[:4000]
    if not closing:
        closing = overall[:800] if len(overall) > 200 else overall

    if not overall.strip():
        raise ValueError(f"Could not parse interview report markdown: {text[:200]!r}…")

    return {
        "overall_assessment": overall.strip(),
        "strengths": strengths,
        "improvement_suggestions": improvements,
        "recommended_study_topics": topics,
        "closing_summary": closing.strip(),
    }


def _loads_structured_dict(text: str, model: type[BaseModel]) -> dict[str, Any]:
    """JSON first; for known schemas, fall back to GLM prose / repaired formats."""

    parsed = _try_load_json_dict(text)
    if parsed is not None:
        return parsed

    try:
        raw = json.loads(extract_json_text(text))
        if isinstance(raw, dict):
            return raw
    except ValueError:
        pass

    if issubclass(model, AnswerEvaluationResult):
        return _parse_answer_evaluation_prose(text)
    if issubclass(model, QuestionCritique):
        return _parse_question_critique_loose(text)
    if issubclass(model, InterviewLLMReport):
        return _parse_interview_report_markdown(text)

    raise ValueError(f"Could not parse structured output for {model.__name__}: {text[:200]!r}…")


def _message_content(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def _first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _normalize_for_schema(data: dict[str, Any], model: type[BaseModel]) -> dict[str, Any]:
    """Map common GLM field aliases and fill safe defaults for omitted keys."""

    out = dict(data)

    if issubclass(model, GeneratedQuestion):
        if not out.get("question_text"):
            q = _first_present(out, "question_text", "question", "interview_question", "content")
            if q:
                out["question_text"] = q
        if not out.get("chain_of_thought"):
            cot = _first_present(out, "chain_of_thought", "reasoning", "thought", "analysis")
            if cot:
                out["chain_of_thought"] = cot

    if issubclass(model, QuestionCritique):
        if "difficulty_adequate" not in out:
            alias = _first_present(
                out,
                "difficulty_adequate",
                "is_sufficiently_challenging",
                "sufficiently_challenging",
                "challenging_adequate",
            )
            if alias is not None:
                out["difficulty_adequate"] = _coerce_bool(alias)
        if "relevance_adequate" not in out:
            alias = _first_present(
                out,
                "relevance_adequate",
                "is_sufficiently_specific",
                "sufficiently_specific",
                "relevant_to_jd_and_resume",
                "relevance_adequate",
            )
            if alias is not None:
                out["relevance_adequate"] = _coerce_bool(alias)
        out.setdefault("difficulty_adequate", True)
        out.setdefault("relevance_adequate", True)
        out.setdefault("reasoning", out.get("reasoning") or "No critique reasoning provided.")

    if issubclass(model, AnswerEvaluationResult):
        out = normalize_evaluation_scores(out)
        for field in ("technical_depth", "clarity", "relevance"):
            if field not in out or out[field] is None:
                out[field] = 0
        out.setdefault("reasoning", "No scoring reasoning provided.")
        out.setdefault("key_facts", [])

    if issubclass(model, InterviewLLMReport):
        if not out.get("overall_assessment"):
            alias = _first_present(
                out,
                "overall_assessment",
                "overall_evaluation",
                "assessment",
                "summary",
                "evaluation",
            )
            if alias:
                out["overall_assessment"] = str(alias)
        out.setdefault("strengths", [])
        out.setdefault("improvement_suggestions", [])
        out.setdefault("recommended_study_topics", [])
        if not out.get("closing_summary") and out.get("overall_assessment"):
            out["closing_summary"] = out["overall_assessment"]
        if not out.get("overall_assessment") and out.get("closing_summary"):
            out["overall_assessment"] = out["closing_summary"]

    return out


def parse_structured_message(
    message: BaseMessage,
    model: type[T],
    *,
    defaults: dict[str, Any] | None = None,
) -> T:
    content = _message_content(message)
    merged = _normalize_for_schema(_loads_structured_dict(content, model), model)
    if defaults:
        for key, value in defaults.items():
            if key not in merged or merged[key] in (None, ""):
                merged[key] = value

    return model.model_validate(merged)


def make_structured_chain(
    prompt: ChatPromptTemplate,
    llm: BaseChatModel,
    schema: type[T],
    *,
    inherit_fields: tuple[str, ...] = (),
) -> Runnable:
    """Prompt → LLM → parse; copy ``inherit_fields`` from request payload when GLM omits them."""

    def _defaults_from(inputs: dict[str, Any]) -> dict[str, Any]:
        return {k: inputs[k] for k in inherit_fields if k in inputs}

    def _run(inputs: dict[str, Any]) -> T:
        msg = (prompt | llm).invoke(inputs)
        return parse_structured_message(msg, schema, defaults=_defaults_from(inputs))

    async def _arun(inputs: dict[str, Any]) -> T:
        msg = await (prompt | llm).ainvoke(inputs)
        return parse_structured_message(msg, schema, defaults=_defaults_from(inputs))

    return RunnableLambda(_run, afunc=_arun)


def with_structured_output_compat(
    llm: BaseChatModel,
    schema: type[T],
    *,
    inherit_fields: tuple[str, ...] = (),
) -> Runnable:
    """Legacy helper: LLM-only runnable (prefer :func:`make_structured_chain`)."""

    def _run(msg: BaseMessage, config: dict | None = None) -> T:
        _ = config
        return parse_structured_message(msg, schema)

    return llm | RunnableLambda(_run)


__all__ = [
    "extract_json_text",
    "make_structured_chain",
    "parse_structured_message",
    "with_structured_output_compat",
]
