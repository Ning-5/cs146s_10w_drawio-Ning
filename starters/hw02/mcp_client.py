"""通过 stdio 连接服务器，发现并调用学生实现的读取与检查工具，并与进程内直接调用对比。"""
import asyncio
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.tool_result import require_success


async def main():
    server = str(Path(__file__).with_name("mcp_server.py"))
    async with stdio_client(StdioServerParameters(command=sys.executable, args=[server])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert {"read_diagram", "inspect_diagram"} <= names, names
            for t in listed.tools:
                print("desc:", t.name, "->", (t.description or "")[:48])
            plan = {"read_diagram": "", "inspect_diagram": "流程 A"}
            mcp_results = {}
            for name, arg in plan.items():
                result = await session.call_tool(name, {"name": arg})
                print(name, result.model_dump_json())
                require_success(result)
                mcp_results[name] = json.loads(result.content[0].text)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hw02"))
    import tools
    inproc = {"read_diagram": tools.read_tool(""), "inspect_diagram": tools.inspect_tool("流程 A")}
    for name, payload in inproc.items():
        same = json.dumps(payload, sort_keys=True, ensure_ascii=False) == json.dumps(mcp_results[name], sort_keys=True, ensure_ascii=False)
        print(f"compare {name}:", "IDENTICAL" if same else "DIFFERS")
        if not same:
            print("  inproc:", json.dumps(payload, ensure_ascii=False))
            print("  mcp   :", json.dumps(mcp_results[name], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
