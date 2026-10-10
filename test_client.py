"""End-to-end check: talk to server.py over real MCP stdio, like a host would."""
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def call(s, name, args):
    res = await s.call_tool(name, args)
    return json.loads(res.content[0].text)

async def main():
    params = StdioServerParameters(command=sys.executable, args=["server.py"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print("TOOLS:", [t.name for t in (await s.list_tools()).tools])
            print("RESOURCES:", [str(x.uri) for x in (await s.list_resources()).resources])
            print("PROMPTS:", [p.name for p in (await s.list_prompts()).prompts])
            b = await call(s, "backtest_signal", {"signal": "conference_attendee"})
            print("BACKTEST:", b["verdict"], "lift", b["lift"], "range", b["range_95"])
            sim = await call(s, "simulate_agent_run", {"agent_id": "conference_followup"})
            pc = sim.get("policy_context", {})
            print("SIMULATE: blockers", sim["blockers"], "warnings", sim["warnings"],
                  "| policy chunks", pc.get("chunks_returned"),
                  "| tokens", pc.get("tokens_all_policy_docs"), "->", pc.get("tokens_returned"),
                  f"({pc.get('token_method')})")
            print("APPROVE R003:", (await call(s, "decide_launch",
                  {"run_id": "R003", "decision": "approve", "reason": "test"}))["status"])
asyncio.run(main())
