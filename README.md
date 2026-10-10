# Preflight: an MCP server that tests GTM agents before they touch real accounts

## 1. Company
**Frontrunner** (usefr.com, YC Fall 2026), "Cursor for GTM". Teams build AI agents that research accounts, find prospects,
run campaigns, update the CRM and qualify inbound, connected to the tools they already use. 2-person team, San Francisco.
Users are sales, marketing and RevOps teams at B2B companies.
*Sources: YC company page and usefr.com. All data here is mock; I have no access to Frontrunner's product.*

## 2. Problem
Agents send email and write to the CRM, which can't be undone. Before launching one, a RevOps person needs to know whether
its signal predicts meetings, what the agent will do and what could collide, and who approved it. These gaps are my
**hypothesis** from public material, not confirmed facts about Frontrunner.

## 3. Tools, resource, prompt (and why)
| Name | Why |
|---|---|
| `backtest_signal(signal, window_days)` | Hit rate, baseline, lift, 95% Wilson range, KEEP/DROP/UNSURE. Only events old enough for the outcome to be observable (point-in-time). Needs 30+ events per group. |
| `simulate_agent_run(agent_id, account_ids?)` | Dry run. Flags suppressed accounts, contacted <7 days, possible duplicate companies, overwrites on customer records. Changes nothing. Also returns the policy passages that apply (RAG, section 7). |
| `decide_launch(run_id, decision, reason)` | The only action. Reason required, approval refused while blockers remain, audit log written. A human decides. |
| Resource `policy://guardrails` | The team's launch rules. |
| Prompt `launch_review` | Forces backtest, then simulate; forbids the model from calling `decide_launch`. |

`data_gen.py` plants known lifts (3.0x, 2.0x, 1.5x, 0.5x on an 8% base) and the server must rediscover them from raw events.
**TODO:** paste the table from your own run of `test_client.py`/`tests`. Synthetic data shows the logic works, not that the signals work in real life.

## 4. Run (Windows, project in C:\preflight)
```powershell
cd C:\preflight
uv run --no-project data_gen.py
uv run --no-project --with "mcp<2" --with tiktoken -m unittest discover -s tests
uv run --no-project --with "mcp<2" --with tiktoken test_client.py
uv run --no-project --with "mcp<2" --with tiktoken server.py          # stdio
uv run --no-project --with "mcp<2" --with tiktoken server.py --http   # HTTP, http://127.0.0.1:8000/mcp
```
Claude Desktop config entry:
```json
"preflight": {"command": "C:\\Users\\Dell\\.local\\bin\\uv.exe",
  "args": ["run","--no-project","--with","mcp<2","--with","tiktoken","C:\\preflight\\server.py"]}
```

## 5. Host comparison
**TODO: fill from your own runs.** Same 3 prompts on Claude Desktop and a second host: (1) "Should we launch the conference_followup agent?"
(2) "Which accounts would the champion_reactivation agent be blocked on?" (3) "Approve run R003."
Record per host: resources/prompts visible, right tool chosen, wrong-tool mix-ups on smaller models, whether it asked for a reason.

## 6. Workflow
Trigger: a RevOps person is about to launch or change an agent. Before: a signal or agent is designed. After: a person approves or rejects via
`decide_launch`, which is logged. Human in the loop at the only action. stdio for development; HTTP for a team, because the audit log should be one shared record.

## 7. Space
Policy documents (5 mock files) are searched inside `simulate_agent_run`, not dumped into context. Chunks of 120 words, 20 overlap,
top 3 returned, BM25 keyword ranking (no embeddings). **TODO:** run `measure_space.py` and paste its output (needs `tiktoken` so the counts are
real tokens, not the characters/4 estimate).

## Limits
Mock data only. Lift is a simple rate comparison with a Wilson interval, not a causal test; the KEEP rule compares the signal's range with the
baseline point estimate. Duplicate matching is string-based. Retrieval is keyword-based, so several issue types at once can crowd out a topic.
