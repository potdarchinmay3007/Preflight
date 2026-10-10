"""Prints token counts (all policy docs vs chunks returned) for each agent. For the README."""
import server
print("tokenizer:", server.TOKEN_METHOD, "| chunk words:", server.CHUNK_WORDS,
      "| overlap:", server.CHUNK_OVERLAP, "| top-k:", server.TOP_K)
for ag in server.AGENTS:
    c = server.simulate_agent_run(ag).get("policy_context")
    if c:
        print(f"{ag}: all docs {c['tokens_all_policy_docs']} -> returned {c['tokens_returned']} "
              f"({c['chunks_returned']} chunks)")
