"""HW1 提示词实验室：三种提示方式 × 案例 × 重复，批量生成并评估。"""
import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from ollama import Client

ROOT = Path(__file__).resolve().parents[2]  # 仓库根目录

# ---------------------------------------------------------------------------
# 三份提示词模板：brief（最少指引）、contract（规则清单）、schema（结构化输出）
# 注意：模板里 JSON 示例的大括号要用 {{ }} 转义，否则 .format() 会报错。
# ---------------------------------------------------------------------------
PROMPTS = {
    "brief": "请把下面的流程描述转成 JSON 流程图规格。{text}",
    "contract": (
        "请把下面的流程描述转成 JSON 流程图规格，严格遵守：\n"
        "1. 顶层字段：nodes、edges、questions\n"
        '2. 节点格式：{{"id": "英文小写标识", "label": "中文步骤名"}}\n'
        '3. 边格式：{{"source": "起点id", "target": "终点id", "label": "简短说明"}}\n'
        "4. id 用英文小写单词，不重复\n"
        "5. 不确定或歧义处写进 questions，不要擅自决定\n"
        "6. 只输出 JSON，不要多余文字\n\n流程描述：{text}"
    ),
    "schema": "请把下面的流程描述转成符合给定 Schema 的 JSON。{text}",
}


def generate(case: dict, mode: str, schema: dict) -> str:
    # TODO: 调用 Ollama，三种生成方式使用相同的模型和生成设置。
    client = Client(
        host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        timeout=300,
    )
    model = os.getenv("OLLAMA_MODEL", "qwen3:4b-q4_K_M")

    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPTS[mode].format(text=case["text"])}],
    }
    if mode == "schema":
        kwargs["format"] = schema  # Ollama 的结构化输出：强制按 Schema 生成

    response = client.chat(**kwargs)
    return response.message.content


def evaluate(case: dict, content: str, schema: dict) -> tuple:
    # TODO: 分别记录 JSON/Schema 检查、图关系检查及需要人工判断的含义。
    result = {"caseId": case["id"], "checks": {}, "manual": []}

    # --- A 类检查 1：能否解析成 JSON ---
    try:
        spec = json.loads(content)
        result["checks"]["json_parse"] = "pass"
    except json.JSONDecodeError as exc:
        result["checks"]["json_parse"] = f"fail: {exc}"
        return result, result["checks"]  # 解析都失败，后面的检查没法做

    # --- 结构预检：合法 JSON 不等于结构正确，先验类型再取字段 ---
    if not isinstance(spec, dict):
        result["checks"]["json_parse"] = "fail: 顶层不是 JSON 对象"
        return result, result["checks"]
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    if not isinstance(nodes, list) or not all(isinstance(n, dict) for n in nodes):
        result["checks"]["json_parse"] = "fail: nodes 不是字典列表"
        return result, result["checks"]
    if not isinstance(edges, list) or not all(isinstance(e, dict) for e in edges):
        result["checks"]["json_parse"] = "fail: edges 不是字典列表"
        return result, result["checks"]

    # --- A 类检查 2：字段名是否符合 Schema ---
    schema_props = schema.get("properties", {})
    edge_required = set(
        schema_props.get("edges", {}).get("items", {}).get("required", [])
    )
    bad_edges = [
        e for e in edges
        if edge_required and not edge_required.issubset(e.keys())
    ]
    result["checks"]["edge_fields"] = "pass" if not bad_edges else f"fail: {len(bad_edges)} 条边字段缺失"

    # --- A 类检查 3：边的引用是否指向真实节点 ---
    node_ids = {n.get("id") for n in nodes}
    dangling = [
        e for e in edges
        if e.get("source") not in node_ids or e.get("target") not in node_ids
    ]
    result["checks"]["edge_refs"] = "pass" if not dangling else f"fail: {len(dangling)} 条边引用了不存在的节点"

    # --- A 类检查 4：节点 id 是否重复 ---
    ids = [n.get("id") for n in nodes]
    dup = len(ids) != len(set(ids))
    result["checks"]["unique_ids"] = "fail: id 重复" if dup else "pass"

    # --- B 类：留给人工判断的提示（把原文和输出存下来供人看） ---
    result["manual"] = [
        "步骤是否完整无遗漏", "顺序是否符合原文", "是否编造了原文没有的步骤",
        "歧义是否进了 questions 而非擅自决定",
    ]
    return spec, result["checks"]


def run(split: str) -> None:
    cases = json.loads((ROOT / "materials/cases/prompt-cases.json").read_text(encoding="utf-8"))
    schema = json.loads(Path(__file__).with_name("spec.schema.json").read_text(encoding="utf-8"))

    selected = [c for c in cases if c["split"] == split]
    run_id = time.strftime("%Y%m%d-%H%M%S")  # 用时间戳做独立 run_id
    out_dir = ROOT / ".runtime" / "hw01" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    model = os.getenv("OLLAMA_MODEL", "qwen3:4b-q4_K_M")

    for mode in ["brief", "contract", "schema"]:
        for case in selected:
            for repeat in (1, 2):
                started = time.perf_counter()
                error = ""
                try:
                    content = generate(case, mode, schema)
                except Exception as exc:  # 模型调用失败也要记录，不能让整轮中断
                    content, error = "", f"{type(exc).__name__}: {exc}"
                elapsed = round(time.perf_counter() - started, 2)

                if content:
                    try:
                        _, checks = evaluate(case, content, schema)
                    except Exception as exc:  # 离谱输出也不能毁掉整轮实验
                        checks = {"json_parse": f"fail: 评估异常 {type(exc).__name__}: {exc}"}
                else:
                    checks = {"json_parse": f"fail: {error}"}

                record = {
                    "caseId": case["id"], "split": split, "mode": mode,
                    "repeat": repeat, "model": model, "promptVersion": "v1",
                    "elapsedSec": elapsed, "error": error,
                    "output": content, "checks": checks,
                }
                name = f"{case['id']}-{mode}-r{repeat}.json"
                (out_dir / name).write_text(
                    json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[{case['id']} {mode} r{repeat}] {elapsed}s "
                      f"json_parse={checks.get('json_parse', '?')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "eval"])
    args = parser.parse_args()
    run(args.split)
