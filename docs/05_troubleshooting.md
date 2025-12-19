# Troubleshooting

## 1) 405 Method Not Allowed
- HEAD 요청(`curl -I`)은 서버/프록시에서 막힐 수 있습니다.
- Inspector 또는 GET/POST 기반의 MCP 호출로 확인하세요.

## 2) PlayMCP에서 "tools.tools[*].name 정규식" 에러
- ToolBartender가 노출하는 MCP tool name이 `plan.create`처럼 점(.)을 포함하면 막힙니다.
- `plan_create` / `plan_validate` / `plan_render_prompt` / `plan_explain`처럼 ASCII로 변경하세요.

## 3) 설명(용도) 한글 vs 영문
- PlayMCP UI는 한국어 설명이 자연스럽습니다.
- 코드의 tool description을 한국어로 맞추고,
  README는 한/영 병행(짧게)로 가져가면 심사/포트폴리오 둘 다 잡습니다.
