import sys, json
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "starters"))
sys.path.insert(0, str(_ROOT / "starters" / "hw02"))
from agent import run_agent


result = run_agent("读取 practice.drawio，找出名字为空的图元并补上合适的名称，最后复查确认没有问题")
print(json.dumps(result, ensure_ascii=False, indent=2))
print("\n判定：stop_reason =", result.get("stop_reason"),
      "| turns =", result.get("turns"), "| tool_calls =", result.get("tool_calls"))
