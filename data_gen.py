"""Token cost of policy retrieval per agent: all policy docs vs chunks returned.

Run: python bench_context.py
"""
import rag
import server

AGENTS = [
    "lookalike_prospecting",
    "website_visitor_outreach",
    "champion_reactivation",
    "conference_followup",
]

# These names are assumed to live in rag.py. Adjust if yours differ.
CONFIG = ["TOKEN_METHOD", "CHUNK_WORDS", "CHUNK_OVERLAP", "TOP_K"]


def main():
    print(" | ".join(f"{name}: {getattr(rag, name, '?')}" for name in CONFIG))

    for agent in AGENTS:
        ctx = server.simulate_agent_run(agent).get("policy_context")
        if not ctx:
            print(f"{agent}: no issues found, no policy context retrieved")
            continue
        print(
            f"{agent}: all docs {ctx['tokens_all_policy_docs']} -> "
            f"returned {ctx['tokens_returned']} ({ctx['chunks_returned']} chunks)"
        )


if __name__ == "__main__":
    main()
