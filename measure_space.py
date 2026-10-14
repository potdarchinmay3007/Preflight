"""Token cost of policy retrieval per agent: all policy docs vs chunks returned.

Run from the project folder: python bench_context.py
"""
import rag
import server

AGENTS = [
    "lookalike_prospecting",
    "website_visitor_outreach",
    "champion_reactivation",
    "conference_followup",
]

# Settings read from rag.py. Any name that doesn't exist there prints as "?".
CONFIG = ["TOKEN_METHOD", "CHUNK_WORDS", "CHUNK_OVERLAP", "TOP_K"]

# Keys expected in the policy_context dict returned by rag.search_policy.
KEYS = ("tokens_all_policy_docs", "tokens_returned", "chunks_returned")


def main():
    print(" | ".join(f"{name}: {getattr(rag, name, '?')}" for name in CONFIG))
    print()

    for agent in AGENTS:
        ctx = server.simulate_agent_run(agent).get("policy_context")

        if not ctx:
            print(f"{agent}: no issues found, no policy context retrieved")
            continue

        total, used, chunks = (ctx.get(k) for k in KEYS)
        if None in (total, used, chunks):
            print(f"{agent}: unexpected keys, got {sorted(ctx)}")
            continue

        saved = 100 * (1 - used / total) if total else 0
        print(f"{agent}: all docs {total} -> returned {used} "
              f"({chunks} chunks, {saved:.0f}% fewer tokens)")


if __name__ == "__main__":
    main()
