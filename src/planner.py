from __future__ import annotations

import re
import uuid
from typing import List, Optional, Tuple

from models import Plan, PlanStep


# -------------------------
# 1) intent heuristics (minimal)
# -------------------------
def _classify_intent(goal: str) -> str:
    g = goal.strip()

    # schedule ops
    if any(k in g for k in ("취소", "삭제")) and any(k in g for k in ("일정", "스케줄", "미팅", "회의")):
        return "schedule_cancel"
    if any(k in g for k in ("변경", "수정", "옮겨", "재조정")) and any(k in g for k in ("일정", "스케줄", "미팅", "회의")):
        return "schedule_update"
    if any(k in g for k in ("잡아", "등록", "추가", "생성")) and any(k in g for k in ("일정", "스케줄", "미팅", "회의")):
        return "schedule_create"

    # route / 이동
    if any(k in g for k in ("에서", "까지", "으로", "→", "->", "이동", "가는", "가야")):
        return "route"

    # paper / news (확장용; 도구가 없으면 steps는 생성되지 않음)
    if "논문" in g and any(k in g for k in ("검색", "서치", "찾아", "요약")):
        return "paper_search_summarize_email"
    if "뉴스" in g and any(k in g for k in ("분석", "요약", "정리")) and any(k in g for k in ("카톡", "카카오", "보내")):
        return "news_analyze_kakao_send"

    return "unknown"


# -------------------------
# 2) slot extractors (minimal)
# -------------------------
def _infer_date_token(goal: str) -> str:
    # explicit date (YYYY-MM-DD)
    m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", goal)
    if m:
        return m.group(0)

    if "오늘" in goal:
        return "today"
    if "내일" in goal:
        return "tomorrow"

    return "unknown"


def _infer_hhmm(goal: str) -> Optional[str]:
    g = goal.strip()

    # 1) 20:30 / 8:30
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", g)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"

    # 2) "오전/오후 8시(30분)"
    m = re.search(r"(오전|오후)\s*(\d{1,2})시(?:\s*(\d{1,2})분)?", g)
    if m:
        ampm = m.group(1)
        hh = int(m.group(2))
        mm = int(m.group(3) or 0)

        if ampm == "오후" and hh < 12:
            hh += 12
        if ampm == "오전" and hh == 12:
            hh = 0

        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"

    # 3) "저녁 8시" / "밤 11시" 같은 표현은 보수적으로 오후로 취급(저녁/밤)
    m = re.search(r"(저녁|밤)\s*(\d{1,2})시(?:\s*(\d{1,2})분)?", g)
    if m:
        hh = int(m.group(2))
        mm = int(m.group(3) or 0)
        if hh < 12:
            hh += 12
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"

    return None


def _infer_route(goal: str) -> Tuple[Optional[str], Optional[str]]:
    g = goal.strip()

    # 1) "A에서 B로/까지"
    m_list = re.findall(r"(.+?)에서\s*(.+?)(?:으로|까지)", g)
    if m_list:
        frm, to = m_list[-1]
        return frm.strip(), to.strip()

    # 2) "A -> B" / "A → B"
    m = re.search(r"(.+?)\s*(?:->|→)\s*(.+)", g)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    return None, None


def _infer_email(goal: str) -> Optional[str]:
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", goal)
    return m.group(0) if m else None


def _infer_title(goal: str) -> Optional[str]:
    # "제목: xxx" / "제목=xxx"
    m = re.search(r"제목\s*[:=]\s*([^,\n]+)", goal)
    if m:
        return m.group(1).strip()

    # 따옴표 안
    m = re.search(r"[\"“”']([^\n\r\t]{2,50})[\"“”']", goal)
    if m:
        return m.group(1).strip()

    return None


# -------------------------
# 3) Plan builder (compiler-style)
#    - 가능한 tool만 steps로 생성
#    - slot이 부족하면 steps 비워두고 assumptions로 안내
# -------------------------
def _is_write_like(tool_name: str) -> bool:
    # 보수적으로 write로 간주
    suffixes = (".create", ".write", ".update", ".delete", ".send")
    return tool_name.endswith(suffixes)


def create_plan(goal: str, available_tools: List[str]) -> Plan:
    plan_id = f"plan-{uuid.uuid4().hex[:8]}"
    intent_type = _classify_intent(goal)

    assumptions: List[str] = [
        "steps는 available_tools에 존재하는 tool_name만 포함합니다.",
        "create/update/delete/send 류는 사용자 확인(required_confirmations) 후 실행합니다.",
    ]

    avail = set(available_tools or [])
    steps: List[PlanStep] = []

    # --- route ---
    if intent_type == "route":
        frm, to = _infer_route(goal)
        date_token = _infer_date_token(goal)
        hhmm = _infer_hhmm(goal)

        if not frm or not to:
            assumptions.append("출발/도착을 파싱하지 못했습니다. 예: '판교에서 강남으로' 또는 '판교 -> 강남'")
            # slot이 없으면 step 생성 안 함 (하드코딩 fallback은 하지 않음)
        else:
            # calendar.read (optional)
            if "calendar.read" in avail:
                steps.append(
                    PlanStep(step_id="step-1", tool_name="calendar.read", args={"date": date_token})
                )
            # map.route
            if "map.route" in avail:
                args = {"from": frm, "to": to}
                if hhmm:
                    args["depart_time"] = hhmm
                steps.append(
                    PlanStep(step_id=f"step-{len(steps)+1}", tool_name="map.route", args=args)
                )

    # --- schedule create/update/cancel (minimal; schema는 client/toolbox 쪽 스펙에 맞춰 조정) ---
    elif intent_type == "schedule_create":
        title = _infer_title(goal)
        date_token = _infer_date_token(goal)
        hhmm = _infer_hhmm(goal)

        if not title:
            assumptions.append('일정 제목(title)을 파싱하지 못했습니다. 예: "제목: 미팅" 또는 "\'미팅\' 일정 잡아줘"')
        if not hhmm:
            assumptions.append("시간(hh:mm)을 파싱하지 못했습니다. 예: '오늘 20:00' 또는 '오후 8시'")
        if title and hhmm:
            if "calendar.read" in avail:
                steps.append(PlanStep(step_id="step-1", tool_name="calendar.read", args={"date": date_token}))
            if "calendar.create" in avail:
                # 최소 스키마(가정): title + start_time
                steps.append(
                    PlanStep(
                        step_id=f"step-{len(steps)+1}",
                        tool_name="calendar.create",
                        args={"title": title, "date": date_token, "time": hhmm},
                    )
                )

    elif intent_type == "schedule_update":
        assumptions.append("schedule_update는 event 식별자(event_ref)와 변경사항(changes)이 필요합니다.")
        # 존재하면 질문/assumptions로 유도, 여기서는 steps 생성 안 함

    elif intent_type == "schedule_cancel":
        assumptions.append("schedule_cancel은 취소할 일정 식별자(event_ref) 또는 제목이 필요합니다.")
        # 존재하면 질문/assumptions로 유도, 여기서는 steps 생성 안 함

    # --- paper / news (확장용) ---
    elif intent_type == "paper_search_summarize_email":
        to_email = _infer_email(goal)
        # query는 간단히 goal 전체에서 추출하기 어렵기 때문에 기본은 없음
        if not to_email:
            assumptions.append("받을 이메일(to_email)을 찾지 못했습니다. 예: user@example.com")
        assumptions.append("논문 검색 키워드(query)는 goal에 명확히 포함하는 것을 권장합니다. 예: '논문 검색: retrieval augmented generation'")

        # tool이 모두 있는 경우에만 step 생성
        if to_email and "paper.search" in avail and "paper.summarize" in avail and "email.send" in avail:
            steps.append(PlanStep(step_id="step-1", tool_name="paper.search", args={"query": goal}))
            steps.append(PlanStep(step_id="step-2", tool_name="paper.summarize", args={"query": goal}))
            steps.append(PlanStep(step_id="step-3", tool_name="email.send", args={"to": to_email}))

    elif intent_type == "news_analyze_kakao_send":
        assumptions.append("뉴스 주제(topic)와 카톡 대상(target)을 goal에 명확히 포함하는 것을 권장합니다.")
        if "news.search" in avail and "news.summarize" in avail and "kakao.send" in avail:
            steps.append(PlanStep(step_id="step-1", tool_name="news.search", args={"topic": goal}))
            steps.append(PlanStep(step_id="step-2", tool_name="news.summarize", args={"topic": goal}))
            steps.append(PlanStep(step_id="step-3", tool_name="kakao.send", args={"target": "me"}))

    else:
        assumptions.append("의도를 분류하지 못했습니다. goal을 더 구체적으로 작성하거나, 필요한 도구를 활성화하세요.")

    # available_tools 비어 있는 경우 안내
    if not available_tools:
        if not steps:
            assumptions.append("available_tools가 비어 있어 step을 생성하지 않았습니다. PlayMCP에서 필요한 MCP를 활성화한 뒤 다시 호출하세요.")

    # required confirmations
    required_confirmations: List[str] = []
    for s in steps:
        if _is_write_like(s.tool_name):
            required_confirmations.append(f"{s.tool_name} requires user confirmation")

    return Plan(
        plan_id=plan_id,
        intent=goal,
        steps=steps,
        assumptions=assumptions,
        required_confirmations=required_confirmations,
        execution_hint="Execute steps sequentially using tool_name and args as-is. Summarize each step result.",
    )
