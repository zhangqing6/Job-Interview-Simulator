"""Question–answer alignment and duplicate-answer penalties."""

from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from interview_simulator.model_layer.score_alignment import (
    PriorRound,
    alignment_score,
    calibrate_evaluation,
    heuristic_evaluate,
    lexical_overlap,
)


def test_lexical_overlap_detects_shared_terms() -> None:
    q = "请解释 Redis 缓存穿透与布隆过滤器的原理"
    a = "缓存穿透是指查询不存在的数据；可用布隆过滤器预判键是否存在。"
    assert alignment_score(q, a) > 0.15


def test_duplicate_answer_on_different_questions_detected() -> None:
    from interview_simulator.model_layer.score_alignment import is_duplicate_across_questions

    q1 = "描述微服务中的分布式事务方案"
    q2 = "Kubernetes 中 Pod 的生命周期有哪些阶段"
    same = (
        "我通常使用 Saga 模式处理跨服务一致性，结合消息队列做补偿。"
        "也会关注幂等性与最终一致性。"
    )
    assert is_duplicate_across_questions(
        q2,
        same,
        [PriorRound(question=q1, answer=same)],
    )


def test_off_topic_generic_answer_gets_low_heuristic_scores() -> None:
    q = "解释 Python GIL 对多线程 CPU 密集任务的影响"
    a = "我认为团队协作与沟通能力非常重要，平时会做 code review 并写文档。"
    out = heuristic_evaluate(question=q, answer=a)
    assert out.relevance <= 1
    assert out.technical_depth <= 1


def test_on_topic_answer_can_score_higher() -> None:
    q = "解释 Python GIL 对多线程 CPU 密集任务的影响"
    a = (
        "GIL 保证同一时刻只有一个线程执行 Python 字节码，"
        "CPU 密集多线程无法利用多核，常改用多进程或 C 扩展释放 GIL。"
    )
    out = heuristic_evaluate(question=q, answer=a)
    assert out.relevance >= 3
    assert out.technical_depth >= 3
