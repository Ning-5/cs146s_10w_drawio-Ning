"""汇总最近一次 run 的结果：三种模式的通过率对比。"""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
run_dirs = [d for d in (root / ".runtime" / "hw01").iterdir() if d.is_dir()]
run_dir = sorted(run_dirs)[-1]  # 取最新一次 run

rows = []
for f in sorted(run_dir.glob("*.json")):
    rows.append(json.loads(f.read_text(encoding="utf-8")))

print(f"共 {len(rows)} 条记录，来自 {run_dir.name}\n")
print(f"{'case':<6}{'mode':<10}{'rpt':<4}{'耗时':<8}{'json':<8}{'边字段':<8}{'边引用':<8}")
print("-" * 52)

stats = {}
for r in rows:
    c = r["checks"]
    j = "✓" if str(c.get("json_parse", "")).startswith("pass") else "✗"
    ef = "✓" if str(c.get("edge_fields", "")).startswith("pass") else "✗"
    er = "✓" if str(c.get("edge_refs", "")).startswith("pass") else "✗"
    print(f"{r['caseId']:<6}{r['mode']:<10}{r['repeat']:<4}"
          f"{r['elapsedSec']:<8}{j:<8}{ef:<8}{er:<8}")
    s = stats.setdefault(r["mode"], {"n": 0, "j": 0, "ef": 0, "er": 0})
    s["n"] += 1
    s["j"] += j == "✓"
    s["ef"] += ef == "✓"
    s["er"] += er == "✓"

print("\n=== 三种模式通过率对比 ===")
for mode, s in stats.items():
    print(f"{mode:<10} JSON解析 {s['j']}/{s['n']}   "
          f"边字段 {s['ef']}/{s['n']}   边引用 {s['er']}/{s['n']}")
