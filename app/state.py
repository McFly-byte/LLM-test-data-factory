"""共享状态与数据模型定义（TypedDict，便于 LangGraph 状态合并与讲解）。"""

from __future__ import annotations

from typing import List, Literal, NotRequired, TypedDict


class TopicPlan(TypedDict):
    """主题规划：一个主题桶及其子主题与配额。"""

    topic: str
    subtopics: List[str]
    target_knowledge_count: int
    target_qa_count: int


class KnowledgeItem(TypedDict):
    """知识条目：后续可写入向量库的语料单元。"""

    kid: str
    topic: str
    subtopic: str
    title: str
    content: str
    keywords: List[str]
    # 若生成时参考了外部检索结果，可写入对应网页 URL，便于后续事实核查与评测
    sources: NotRequired[List[str]]


QuestionType = Literal["fact", "comparison", "troubleshooting", "best_practice", "boundary"]
Difficulty = Literal["easy", "medium", "hard"]
ReviewStatus = Literal["pending", "accepted", "rejected"]


class QASample(TypedDict, total=False):
    """QA 样本：绑定证据知识条目 id，带审核与修订元数据。"""

    qid: str
    topic: str
    subtopic: str
    question_type: QuestionType
    difficulty: Difficulty
    query: str
    answer: str
    evidence_kids: List[str]
    review_status: ReviewStatus
    review_reason: str
    revised_times: int
    risk_tags: NotRequired[List[str]]


class FactoryState(TypedDict, total=False):
    """数据工厂运行时状态（LangGraph StateGraph 共享状态）。"""

    domain: str
    target_knowledge_chars: int
    target_qa_count: int
    topic_plans: List[TopicPlan]
    current_topic_index: int
    knowledge_items: List[KnowledgeItem]
    qa_samples: List[QASample]
    pending_qa: List[QASample]
    accepted_qa: List[QASample]
    rejected_qa: List[QASample]
    duplicate_threshold: float
    max_revision_rounds: int
    export_dir: str
    done: bool


def new_factory_state(
    *,
    domain: str,
    target_knowledge_chars: int,
    target_qa_count: int,
    duplicate_threshold: float,
    max_revision_rounds: int,
    export_dir: str,
) -> FactoryState:
    """构造初始工厂状态。"""
    return FactoryState(
        domain=domain,
        target_knowledge_chars=target_knowledge_chars,
        target_qa_count=target_qa_count,
        topic_plans=[],
        current_topic_index=0,
        knowledge_items=[],
        qa_samples=[],
        pending_qa=[],
        accepted_qa=[],
        rejected_qa=[],
        duplicate_threshold=duplicate_threshold,
        max_revision_rounds=max_revision_rounds,
        export_dir=export_dir,
        done=False,
    )
