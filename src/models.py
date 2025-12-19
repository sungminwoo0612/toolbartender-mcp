from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# pydantic v2/v1 호환: 오타 필드가 조용히 무시되지 않도록 차단(extra=forbid)
try:
    from pydantic import ConfigDict  # v2
    _PVD = 2
except Exception:
    ConfigDict = None  # type: ignore
    _PVD = 1


class PlanStep(BaseModel):
    step_id: str
    tool_name: str
    args: Dict[str, Any]
    on_fail: Optional[Dict[str, Any]] = None

    if _PVD == 2:
        model_config = ConfigDict(extra="forbid")  # type: ignore
    else:
        class Config:
            extra = "forbid"


class Plan(BaseModel):
    plan_id: str
    intent: str

    steps: List[PlanStep] = []
    assumptions: List[str] = []

    # create/update/delete/send 등 사용자 확인이 필요한 항목(문자열 리스트)
    required_confirmations: List[str] = []

    # 실행 에이전트에게 주는 힌트(선택)
    execution_hint: Optional[str] = None

    if _PVD == 2:
        model_config = ConfigDict(extra="forbid")  # type: ignore
    else:
        class Config:
            extra = "forbid"
