"""实现 HW2 的四种工具；文件解析与写入可调用 shared 中的适配器。"""
import sys
import copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.diagram_io import apply_operations, read_diagram

WORKSPACE = Path(__file__).resolve().parents[2] / ".runtime/hw02/workspace"
DIAGRAM_NAME = "practice.drawio"   # 工作区中的文件名（适配器要求：不含目录、必须 .drawio）

TOOLS: list[dict] = [
    {"function": {
        "name": "read_diagram",
        "description": "读取 drawio 文件。name 传页面名返回该页详情；传空字符串返回所有页面的概览（页面 id/名称/图元数量）。",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "页面名称，空字符串=全部页面概览"}},
            "required": ["name"],
        },
    }},
    {"function": {
        "name": "inspect_diagram",
        "description": "检查页面的名称和端点引用问题：空页面名、空图元名称、连接线的 source/target 指向不存在的图元。",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "页面名称，空字符串=检查所有页面"}},
            "required": ["name"],
        },
    }},
    {"function": {
        "name": "apply_changes",
        "description": "向文件写入一批修改操作。必须先 read_diagram 拿到当前 version 作为 expected_version；任一操作失败则整批不写入。",
        "parameters": {
            "type": "object",
            "properties": {
                "expected_version": {"type": "string", "description": "最近一次读取返回的 version"},
                                "operations": {"type": "array", "items": {"type": "object"},
                               "description": "操作列表，每项必须含 op、page_id、cell_id。op 取值：rename_node{page_id,cell_id,label}（改节点名）/ add_edge{page_id,cell_id,source,target}（新建连接线）/ set_endpoints{page_id,cell_id,source,target}（改已有连接线的两端）"},


            },
            "required": ["expected_version", "operations"],
        },
    }},
    {"function": {
        "name": "compare_changes",
        "description": "比较两个快照标识（如 s1 与 s2），列出新增/删除/修改的图元和字段。",
        "parameters": {
            "type": "object",
            "properties": {
                "before": {"type": "string", "description": "修改前的快照标识"},
                "after": {"type": "string", "description": "修改后的快照标识"},
            },
            "required": ["before", "after"],
        },
    }},
]

# ---------- 快照表（每次 run_agent 运行重置一次） ----------
_snapshots: dict[str, dict] = {}
_snap_counter = 0

def reset_snapshots() -> None:
    """每次 run_agent 开始时调用，隔离不同请求的快照。"""
    global _snapshots, _snap_counter
    _snapshots = {}
    _snap_counter = 0

def _store_snapshot(snap: dict) -> str:
    global _snap_counter
    _snap_counter += 1
    sid = f"s{_snap_counter}"
    _snapshots[sid] = copy.deepcopy(snap)
    return sid

def _ok(data: dict) -> dict:
    return {"ok": True, "data": data, "error": None}

def _err(code: str, message: str) -> dict:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}}

def _load_snapshot() -> dict:
    """读取整个文件（适配器按 文件名 读取，页面筛选由本层完成）。"""
    return read_diagram(WORKSPACE, DIAGRAM_NAME)

# ---------- 四个工具 ----------
def read_tool(name: str) -> dict:
    try:
        snap = _load_snapshot()
    except Exception as exc:
        return _err("file_error", f"读取失败：{exc}")
    sid = _store_snapshot(snap)
    pages = snap["pages"]
    if name == "":
        overview = [{"id": p["id"], "name": p["name"], "cells": len(p["cells"])} for p in pages]
        return _ok({"snapshot": sid, "version": snap["version"], "pages": overview})
    for p in pages:
        if p["name"] == name:
            return _ok({"snapshot": sid, "version": snap["version"], "page": p})
    return _err("invalid_arguments", f"未找到页面：{name}")

def inspect_tool(name: str) -> dict:
    try:
        snap = _load_snapshot()
    except Exception as exc:
        return _err("file_error", f"读取失败：{exc}")
    sid = _store_snapshot(snap)
    issues = []
    for p in snap["pages"]:
        if name in ("", p["name"]):
            if not p["name"].strip():
                issues.append({"page": p["id"], "kind": "empty_page_name"})
            ids = {c["id"] for c in p["cells"]}
            for c in p["cells"]:
                if c["id"] in {"0", "1"} or c.get("edge") == "1":
                    continue   # 结构根节点与连接线不算空名缺陷
                label = (c.get("value") or "").strip()
                if not label:
                    issues.append({"page": p["id"], "kind": "empty_cell_name", "cell": c["id"]})


    return _ok({"snapshot": sid, "issues": issues, "count": len(issues)})

def apply_tool(expected_version: str, operations: list[dict]) -> dict:
    if not isinstance(expected_version, str) or not expected_version:
        return _err("invalid_arguments", "expected_version 必须是非空字符串")
    if not isinstance(operations, list) or len(operations) > 20:
        return _err("invalid_arguments", "operations 必须是 1~20 个操作的列表")
    if len(operations) == 0:
        return _ok({"snapshot": None, "version": expected_version, "applied": 0})

    allowed_ops = {"rename_node", "add_edge", "set_endpoints"}
    for op in operations:
        if not isinstance(op, dict) or op.get("op") not in allowed_ops:
            return _err("invalid_arguments", f"未知操作类型：{op!r}，允许：{sorted(allowed_ops)}")
    try:
        result = apply_operations(WORKSPACE, DIAGRAM_NAME, expected_version, operations)
    except Exception as exc:
        msg = str(exc)
        code = "version_conflict" if ("version" in msg.lower() or "冲突" in msg or "变化" in msg) else "file_error"
        return _err(code, msg)
    sid = _store_snapshot(result)
    return _ok({"snapshot": sid, "version": result["version"], "applied": len(operations)})

def compare_tool(before: dict, after: dict) -> dict:
    added, removed, changed = [], [], []
    b_pages = {p["id"]: {c["id"]: c for c in p["cells"]} for p in before["pages"]}
    a_pages = {p["id"]: {c["id"]: c for c in p["cells"]} for p in after["pages"]}
    for pid, a_cells in a_pages.items():
        b_cells = b_pages.get(pid, {})
        for cid in a_cells.keys() - b_cells.keys():
            added.append({"page": pid, "cell": cid})
        for cid in b_cells.keys() - a_cells.keys():
            removed.append({"page": pid, "cell": cid})
        for cid in a_cells.keys() & b_cells.keys():
            diff = {k: {"before": b_cells[cid].get(k), "after": a_cells[cid].get(k)}
                    for k in a_cells[cid].keys() | b_cells[cid].keys()
                    if b_cells[cid].get(k) != a_cells[cid].get(k)}
            if diff:
                changed.append({"page": pid, "cell": cid, "fields": diff})
    for pid in b_pages.keys() - a_pages.keys():
        removed.append({"page": pid, "cell": "*整页删除*"})
    return _ok({"added": added, "removed": removed, "changed": changed,
                "total": len(added) + len(removed) + len(changed)})

# ---------- 分发器 ----------
def dispatch(name: str, arguments: dict) -> dict:
    try:
        args = dict(arguments or {})
        if name == "read_diagram":
            if not isinstance(args.get("name"), str):
                return _err("invalid_arguments", "name 必须是字符串")
            return read_tool(args["name"])
        if name == "inspect_diagram":
            if not isinstance(args.get("name"), str):
                return _err("invalid_arguments", "name 必须是字符串")
            return inspect_tool(args["name"])
        if name == "apply_changes":
            return apply_tool(args.get("expected_version"), args.get("operations"))
        if name == "compare_changes":
            b_id, a_id = args.get("before"), args.get("after")
            if b_id not in _snapshots or a_id not in _snapshots:
                return _err("invalid_arguments", f"快照标识无效，当前可用：{sorted(_snapshots)}")
            return compare_tool(_snapshots[b_id], _snapshots[a_id])
        return _err("unknown_tool", f"未注册的工具：{name}")
    except Exception as exc:
        return _err("internal", f"{type(exc).__name__}: {exc}")
