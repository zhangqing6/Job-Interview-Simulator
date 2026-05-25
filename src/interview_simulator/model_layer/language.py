"""Interview output language (candidate-facing text + report/scoring prose)."""

from __future__ import annotations

from typing import Literal

InterviewLanguage = Literal["zh", "en"]


def question_language_rule(lang: InterviewLanguage) -> str:
    if lang == "zh":
        return (
            "Language: Write `question_text` in Simplified Chinese (简体中文) only. "
            "The candidate must read natural, professional Chinese. "
            "`chain_of_thought` may be Chinese or English."
        )
    return (
        "Language: Write `question_text` in English only. "
        "The candidate must read natural, professional English. "
        "`chain_of_thought` may be in English."
    )


def critique_language_rule(lang: InterviewLanguage) -> str:
    if lang == "zh":
        return "Language: Write `reasoning` and any `improvement_hint` in Simplified Chinese (简体中文)."
    return "Language: Write `reasoning` and any `improvement_hint` in English."


def scorer_language_rule(lang: InterviewLanguage) -> str:
    if lang == "zh":
        return (
            "Language: Write `reasoning` and each `key_facts` entry in Simplified Chinese (简体中文). "
            "Scoring: technical_depth、clarity、relevance 各为 0–5 整数；"
            "系统加权分=0.3×技术+0.2×清晰+0.5×相关；提前结束看累计两次加权≤1.5。"
            "禁止三分制或分数映射。"
        )
    return (
        "Language: Write `reasoning` and each `key_facts` entry in English. "
        "Scoring: integers 0–5 per axis (0–1 fail, 2–3 partial, 4–5 good); no remapping."
    )


def report_language_rule(lang: InterviewLanguage) -> str:
    if lang == "zh":
        return (
            "Language: Write overall_assessment, closing_summary, strengths, "
            "improvement_suggestions, and recommended_study_topics in Simplified Chinese (简体中文)."
        )
    return (
        "Language: Write overall_assessment, closing_summary, strengths, "
        "improvement_suggestions, and recommended_study_topics in English."
    )


def duplicate_answer_warning(lang: InterviewLanguage) -> str:
    if lang == "zh":
        return (
            "检测到您在不同题目下提交了高度雷同的回答，且未针对当前问题作答。"
            "本次不予评分，请阅读当前题目后重新作答（仅一次机会）。"
        )
    return (
        "Your answer closely repeats a response given under a different question and does not "
        "address the current prompt. No score for this attempt — please answer this question "
        "again (one retry)."
    )


def duplicate_answer_finalize_message(lang: InterviewLanguage) -> str:
    if lang == "zh":
        return "累计两次答非所问或答案雷同，面试结束，正在生成报告。"
    return "Interview ended: repeated off-topic/duplicate answers. Generating report."


def low_avg_warning_message(lang: InterviewLanguage, *, remaining: int) -> str:
    if lang == "zh":
        return (
            f"累计加权分≤1.5（0.3×技术+0.2×清晰+0.5×相关）再 {remaining} 次将结束面试。"
        )
    return (
        f"{remaining} more round(s) with weighted score ≤ 1.5 "
        "(0.3×depth + 0.2×clarity + 0.5×relevance) will end the interview."
    )


def low_avg_finalize_message(lang: InterviewLanguage) -> str:
    if lang == "zh":
        return "累计两次加权分≤1.5（0.3×技术+0.2×清晰+0.5×相关），面试结束，正在生成报告。"
    return (
        "Interview ended: two rounds with weighted score ≤ 1.5 "
        "(0.3×depth + 0.2×clarity + 0.5×relevance). Generating report."
    )


def follow_up_dimension(lang: InterviewLanguage, prior_question: str) -> str:
    if lang == "zh":
        return f"在同一话题上追问（使用简体中文），基于上一题：\n{prior_question}"
    return f"Follow-up in the same thread (in English). Prior question:\n{prior_question}"


def stream_language_suffix(lang: InterviewLanguage) -> str:
    if lang == "zh":
        return "\n\n请仅用简体中文输出给候选人的面试问题正文，不要 JSON、不要解释。"
    return "\n\nRespond with the interview question text for the candidate in English only (no JSON, no preamble)."


__all__ = [
    "InterviewLanguage",
    "critique_language_rule",
    "duplicate_answer_finalize_message",
    "duplicate_answer_warning",
    "follow_up_dimension",
    "low_avg_finalize_message",
    "low_avg_warning_message",
    "question_language_rule",
    "report_language_rule",
    "scorer_language_rule",
    "stream_language_suffix",
]
