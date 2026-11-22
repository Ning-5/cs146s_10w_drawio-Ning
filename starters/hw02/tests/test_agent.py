import sys, json
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "starters"))
sys.path.insert(0, str(_ROOT / "starters" / "hw02"))
from agent import run_agent


# 预设剧本：读 → 检查 → 改 → 复查 → 回答（5 步）
script = [
    {"content": None, "tool_calls": [{"id": "c1", "function": {"name": "read_diagram", "arguments": {"name": ""}}}]},
    {"content": None, "tool_calls": [{"id": "c2", "function": {"name": "inspect_diagram", "arguments": {"name": ""}}}]},
    {"content": None, "tool_calls": [{"id": "c3", "function": {"name": "apply_changes", "arguments": {
        "expected_version": "PLACEHOLDER",
        "operations": [{"op": "rename_node", "page_id": "page-a", "cell_id": "n2", "label": "节点2"}]}}}]},
    {"content": None, "tool_calls": [{"id": "c4", "function": {"name": "inspect_diagram", "arguments": {"name": ""}}}]},
    {"content": "修复完成：已为图元 n2 补上名称。", "tool_calls": None},
]

state = {"version": None}
def fake_model(messages, tools):
    if state["version"] is None:
        for m in reversed(messages):
            if m.get("role") == "tool" and '"snapshot"' in m.get("content", ""):
                d = json.loads(m["content"])
                if d.get("ok") and d.get("data", {}).get("version"):
                    state["version"] = d["data"]["version"]
    step = script[0]
    if step is not None and step.get("tool_calls"):
        for call in step["tool_calls"]:
            args = call["function"]["arguments"]
            if args.get("expected_version") == "PLACEHOLDER" and state["version"]:
                args["expected_version"] = state["version"]
    return script.pop(0)

result = run_agent("把 page-a 里名字为空的图元补上名称", model=fake_model)
print(json.dumps(result, ensure_ascii=False, indent=2))
print("\n判定：stop_reason =", result["stop_reason"],
      "| turns =", result["turns"], "| tool_calls =", result["tool_calls"])
