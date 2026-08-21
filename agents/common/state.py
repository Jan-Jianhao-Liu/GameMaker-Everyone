"""LangGraph 状态对象。

AgentState 是 StateGraph 在所有节点间传递的共享状态。
列表字段用 Annotated[list, operator.add] 让 LangGraph 自动累加（reducer），
节点返回 {"defects": [new_defect]} 时追加而非覆盖。
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

RoleName = str  # designer | supervisor | artist3d | artist2d | coder | qa


class AgentState(TypedDict, total=False):
    """五角色流水线共享状态。

    字段语义：
    - task_id: 流水线实例 ID（对应 LangGraph thread_id）
    - user_request: 用户原始需求文本
    - gdd / manifest / art_spec: 三份契约文档（dict）
    - gold_samples: 金样本 {asset_type: sample_asset}，需人工确认后填入
    - produced_assets: 已生产资产列表（按拓扑序追加）
    - build_result: 构建结果（path / status / checksum）
    - defects: QA 缺陷列表（累加）
    - errors: 校验错误信息列表（累加）
    - retries: {role: count} 各角色重试计数
    - current_role: 当前正在执行的角色（supervisor 退回时改写）
    - status: running | paused_human | paused_question | completed | failed
    - human_feedback: 人工卡点反馈（GDD 确认 / 三轮超限 / 金样本 / 发布）
    - pause_type: 暂停类型（checkpoint | question），用于前端区分 UI
    - pending_question: 当前待回答的追问（dict: role/question/options/context）
    - answered_questions: 已回答的追问列表（累加）
    """

    task_id: str
    user_request: str
    gdd: dict
    manifest: dict
    art_spec: dict
    gold_samples: dict[str, dict]
    produced_assets: Annotated[list[dict], operator.add]
    build_result: dict
    defects: Annotated[list[dict], operator.add]
    errors: Annotated[list[str], operator.add]
    retries: dict[str, int]
    current_role: RoleName
    status: str
    human_feedback: str
    pause_type: str
    pending_question: dict
    answered_questions: Annotated[list[dict], operator.add]
