"""Preflight: an MCP server that checks a GTM agent BEFORE it touches real accounts.

The tools here are thin. The checks live in logic.py and the policy search in rag.py.

Run over stdio:  python server.py
Run over HTTP:   python server.py --http      (set PREFLIGHT_HOST and PREFLIGHT_PORT to change the address)
"""
import os
import sys

from mcp.server.fastmcp import FastMCP

import logic
import rag

mcp = FastMCP(
    "preflight",
    host=os.environ.get("PREFLIGHT_HOST", "127.0.0.1"),
    port=int(os.environ.get("PREFLIGHT_PORT", "8000")),
)

# One question per kind of problem. The best policy chunk for each question is returned.
POLICY_QUESTION = {
    "suppressed": "What is the rule for accounts on the suppression list?",
    "recent_contact": "How many days must pass between contacts with the same account?",
    "duplicate": "What must an agent do when a company may already exist under a similar name?",
    "overwrite": "May an agent overwrite fields on a customer record in the CRM?",
}


@mcp.tool()
def backtest_signal(signal: str, window_days: int = 30) -> dict:
    """Check whether a GTM signal really predicts a booked meeting, using past data.
    Use this BEFORE launching an agent that depends on the signal.
    signal: one of first_gtm_hire, pricing_page_visits, champion_moves, conference_attendee.
    window_days: days allowed for the meeting to happen after the signal (1 to 90, default 30).
    Returns hit rate, baseline rate, lift (signal rate / baseline rate), 95% range, and a verdict."""
    return logic.backtest(signal, window_days)


@mcp.tool()
def simulate_agent_run(agent_id: str, account_ids: list[str] | None = None) -> dict:
    """Dry run: show what an agent WOULD do and what could go wrong. Sends and changes nothing.
    agent_id: lookalike_prospecting, website_visitor_outreach, champion_reactivation, or conference_followup.
    account_ids: optional; if empty, uses accounts where the agent's signal fired in the last 60 days.
    Returns blockers (must fix), warnings (review), counts, and the policy passages that apply
    to the problems found (not the whole policy documents)."""
    result = logic.dry_run(agent_id, account_ids)
    if result.get("issue_kinds"):
        result["policy_context"] = rag.search_policy([POLICY_QUESTION[k] for k in result["issue_kinds"]])
    return result


@mcp.tool()
def decide_launch(run_id: str, decision: str, reason: str) -> dict:
    """Record a human approve/reject for a run's write-back. REQUIRES a reason.
    run_id: R000 to R059. decision: 'approve' or 'reject'.
    Approval is refused if the dry run has blockers. Every decision is saved to an audit log.
    Only call this after a person has decided."""
    return logic.record_decision(run_id, decision, reason)


@mcp.resource("policy://guardrails")
def guardrails() -> str:
    """Launch rules the team agreed on."""
    return ("1. Backtest every signal; drop any whose lift range includes baseline.\n"
            "2. Never email a suppressed account or one contacted in the last 7 days.\n"
            "3. A human gives a written reason for every approval.\n")


@mcp.prompt()
def launch_review(agent_id: str) -> str:
    """Checklist prompt for reviewing an agent before launch."""
    return (f"Review agent '{agent_id}' before launch. First call backtest_signal for its signal, "
            f"then simulate_agent_run. Read policy://guardrails. Recommend approve or reject with "
            f"reasons. Do not call decide_launch; a human decides.")


if __name__ == "__main__":
    mcp.run(transport="streamable-http" if "--http" in sys.argv else "stdio")
