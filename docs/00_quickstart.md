# Quickstart (5 min)

## 1) Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
# http://localhost:3333/mcp

## 2) Test with Inspector
```bash
npx @modelcontextprotocol/inspector
# open http://localhost:6274
# connect to http://localhost:3333/mcp
```

## 3) Call `plan_create` tool (example)
(inspector에서 tool 호출로 테스크 권장)

```
Goal 예시: 
"오늘 오후 8시 판교에서 강남으로 이동 계획 세워줘"

available_tools 예시: 
["calendar.read", "map.route"]
```
