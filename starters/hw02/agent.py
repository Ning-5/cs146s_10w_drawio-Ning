"""在 run_agent 中实现 Agent 控制循环；测试时可传入预设模型响应。"""
import os
from pathlib import Path
from typing import Callable
from tools import TOOLS, dispatch

MAX_TURNS = 8
MAX_TOOL_CALLS = 12


def local_model(messages: list[dict], tools: list[dict]) -> dict:
    from dotenv import load_dotenv
    from ollama import Client
    load_dotenv(Path(__file__).with_name(".env"))
    client = Client(host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"), timeout=120)
    return client.chat(model=os.getenv("OLLAMA_MODEL", "qwen3:4b-q4_K_M"), messages=messages, tools=tools).message.model_dump()


def run_agent(request: str, model: Callable = local_model) -> dict:
    from tools import reset_snapshots
    import json as _json

    reset_snapshots()  # 每次 run_agent 隔离快照表

    system = (
        "你是 drawio 图表修复助手。只能通过提供的工具读取和修改文件。"
        "修改前必须先 read_diagram 获取最新 version；"
        "完成所有修改后，用 inspect_diagram 复查问题数，再给出最终回答。"
    )
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": request},
    ]

    events: list[dict] = []
    turns = 0
    tool_calls_used = 0
    last_tool_result: dict | None = None
    apply_failed = False


    for _ in range(MAX_TURNS):
        turns += 1
        try:
            reply = model(messages, TOOLS)
        except Exception as exc:
            events.append({"type": "model_error", "error": f"{type(exc).__name__}: {exc}"})
            return {"answer": "模型服务不可用，任务已停止。",
                    "stop_reason": "model_error",
                    "events": events, "turns": turns, "tool_calls": tool_calls_used}
        messages.append(reply)                   # 保存 assistant 消息（含 tool_calls）

        calls = reply.get("tool_calls") or []
        if not calls:
            # 模型不再调工具：给出文字回答
            content = (reply.get("content") or "").strip()
            if apply_failed:
                # 复查未通过：最后一步工具失败，不算完成
                events.append({"type": "final_unverified", "content": content})
                return {"answer": content, "stop_reason": "unverified",
                        "events": events, "turns": turns, "tool_calls": tool_calls_used}
            events.append({"type": "final", "content": content})
            return {"answer": content, "stop_reason": "completed",
                    "events": events, "turns": turns, "tool_calls": tool_calls_used}

        # 按顺序处理每个工具调用
        for call in calls:
            if tool_calls_used >= MAX_TOOL_CALLS:
                events.append({"type": "limit", "kind": "max_tool_calls"})
                return {"answer": "工具调用次数已达上限，任务中止。",
                        "stop_reason": "max_tool_calls",
                        "events": events, "turns": turns, "tool_calls": tool_calls_used}
            fn = call["function"]["name"]
            raw_args = call["function"].get("arguments") or {}
            # Ollama 有时把 arguments 给成 JSON 字符串
            args = _json.loads(raw_args) if isinstance(raw_args, str) else raw_args

            result = dispatch(fn, args)          # ← 每次调用工具记一次
            tool_calls_used += 1
            last_tool_result = result
            if fn == "apply_changes" and args.get("operations"):
                apply_failed = not result["ok"]

            events.append({"type": "tool_call", "name": fn,
                           "args": args,
                           "ok": result["ok"],
                           "error": result["error"]})

            # 工具返回消息必须带 tool_call_id，模型才能把结果对上调用
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id"),
                "name": fn,
                "content": _json.dumps(result, ensure_ascii=False),
            })

    events.append({"type": "limit", "kind": "max_turns"})
    return {"answer": "已达到最大轮数限制，未能完成任务。",
            "stop_reason": "max_turns",
            "events": events, "turns": turns, "tool_calls": tool_calls_used}


if __name__ == "__main__":
    import json
    request = input("请输入任务: ").strip()
    if not request:
        raise SystemExit("任务不能为空")
    print(json.dumps(run_agent(request), ensure_ascii=False, indent=2))
