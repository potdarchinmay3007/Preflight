# Preflight

An MCP server that checks an automated sales or marketing agent before it is allowed to email prospects or edit a CRM. It tests whether the agent's trigger signal is worth acting on, shows what the agent would do and what could collide, and records who approved the launch and why.

Status: working prototype on synthetic data. It is not connected to any CRM or agent platform.

## Questions a business will ask

| Question | Answer |
|---|---|
| What problem does it solve? | Agents that send email and write to a CRM take actions that are hard to undo. Preflight gives a team three checks to run first: does the signal work, what will the agent touch, and who signed off. |
| Who uses it? | A RevOps analyst or developer, through an MCP client such as Claude Desktop or Cursor. |
| What does it need to run? | Python 3.12 (recommended), the packages in `requirements.txt` (`mcp`, `tiktoken`, `chromadb`), and an MCP client. No paid service or API key. |
| What does it cost? | Nothing beyond your own compute and whichever AI client you use. The embedding model runs locally and is downloaded once. |
| What data does it need? | Accounts (suppression flag, last contact date, CRM status), signal events with outcome dates, agent definitions, and policy documents in Markdown. Today these are synthetic JSON files in `data/` and `policy/`. |
| Does our data leave our machine? | The server itself makes no network calls except the one-time model download. However, tool results are returned to the AI client, and that client sends them to its model provider. Account data in a result is therefore visible to that provider. Check this against your data policy. |
| Does it connect to our CRM? | No. A real deployment needs a data adapter that exports your accounts and events into the formats above. None has been built. |
| Can it block a launch? | No. It advises and records. It is not wired to any agent platform, and the "human approves" rule is a convention, not an enforced control. |
| Who supports it? | It is a single-developer prototype with no support commitment. |
| Under what license? | No license has been selected. This must be settled before any commercial use. |

## What it does

| Tool | Purpose |
|---|---|
| `backtest_signal(signal, window_days=30)` | Hit rate, no-signal baseline, lift, 95% range and a KEEP, DROP or UNSURE verdict. Counts only events old enough for the outcome to be known. Needs 30 or more events per group. |
| `simulate_agent_run(agent_id, account_ids?)` | Dry run. Reports blockers (suppressed account, contacted within 7 days) and warnings (possible duplicate company, overwrite of a customer record), plus the policy passages that apply, found by vector search. |
| `decide_launch(run_id, decision, reason)` | Records approve or reject with a required reason. Approval is refused while blockers remain. Writes `data/audit_log.jsonl`. |

The server also offers one resource (`policy://guardrails`) and one prompt (`launch_review`). Which issues count as blockers is a single setting, `BLOCKING` in `logic.py`.

## How it is built

`logic.py` holds the checks and has no MCP code. `rag.py` splits the policy files into 120-word chunks (20 overlap), stores them in ChromaDB with cosine distance, and returns the best chunk for each kind of problem found. `server.py` registers the tools and calls the other two. About 370 lines in total.

## Testing and metrics

Measured on the development sandbox (Linux, Python 3.12.3, 240 accounts, 6,400 events, 60 runs, all synthetic).

| Check | Result |
|---|---|
| Unit tests for `logic.py` | 12 of 12 pass |
| Backtest versus planted ground truth | The data plants lifts of 3.0, 2.0, 1.5 and 0.5. The backtest finds 2.98, 2.07, 1.33 and 0.44 (absolute error 0.02, 0.07, 0.17, 0.06). Verdicts: KEEP, KEEP, KEEP, DROP. |
| Verdict stability across windows (7, 14, 30, 60, 90 days) | Three signals never change verdict. `champion_moves` is UNSURE at 7 and 14 days and KEEP from 30 days, so its KEEP is marginal. |
| Duplicate detection | Finds both planted duplicate pairs among 240 accounts, with no false pairs. |
| Rule checks against independent counts | A dry run over all 240 accounts flags 11 suppressed (11 in the data), 14 recently contacted (14 in the data) and 70 customer overwrites (70 customers in the data). |
| Approval gate over all 60 runs | 50 runs have blockers and 10 do not. Approval was refused or recorded correctly in 60 of 60. |
| Speed (excludes policy search) | `backtest_signal` 0.7 ms. Dry run on 25 accounts about 92 ms. Dry run on all 240 accounts about 927 ms. |
| Retrieval accuracy (does the top chunk come from the right policy file?) | Not yet measured. Run `python eval_retrieval.py` after `python rag.py`. |
| Token saving from policy search | Not yet measured for the vector version. Run `python measure_space.py`. |
| Tests that need ChromaDB (`tests/test_rag.py`) | Written, not yet run against the real vector database. |
| Behaviour in AI clients | Earlier version with the same checks, run once each on Claude Desktop (Sonnet 5.5), Cursor with Claude Fable 5 and Cursor with Grok 4.5. All three reported the correct numbers. Their judgement differed on `champion_reactivation`: one flagged the customer overwrites as a policy problem, one listed the rule without applying it, and one recommended launching. |

What these numbers do not show: accuracy on real data, false-positive rates on a real CRM, behaviour under load, concurrent use, or any security testing. The speed figure matters for scale, because the duplicate check compares every account with every other, so time grows roughly with the square of the account count.

## Risks and limitations

- All data is synthetic, so no verdict says anything about real signals.
- Lift is a simple rate comparison, not a causal estimate, and the KEEP rule compares the signal's range with the baseline point estimate.
- Customer-record overwrites are warnings by default, so a dry run can say "safe to launch" while the policy text forbids the write. Add `"overwrite"` to `BLOCKING` to make them blockers.
- The server cannot tell whether a person or a model supplied an approval, and the audit log is a plain file that is not tamper-evident.
- HTTP mode has no authentication. Do not expose it beyond a network you trust.
- Run ids (`R000` to `R059`) are not returned by `simulate_agent_run`, so a client cannot discover them.
- Duplicate matching is string-based. Vector retrieval quality is unmeasured (see above).
- Dependencies are a version range with no lockfile.

## What a pilot would take

1. Export real accounts and signal events into the file formats in `data/`, or write an adapter.
2. Replace the mock policy files with real ones and re-run `python rag.py`.
3. Set the thresholds to your rules: the 7-day contact gap, the 30-event minimum and the `BLOCKING` set.
4. Backtest your own signals and compare the verdicts with what your team already believes.
5. Add authentication before any shared deployment, and decide who may call `decide_launch`.

## Setup

Windows PowerShell, from the project folder (on macOS or Linux use `.venv/bin/python`):

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\python.exe rag.py
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe test_client.py
```

`pip` works too: `python -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -r requirements.txt`. To connect Claude Desktop or Cursor, add this entry to the client's MCP configuration with your absolute paths, then restart the client fully:

```json
{
  "mcpServers": {
    "preflight": {
      "command": "C:\\path\\to\\project\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\project\\server.py"]
    }
  }
}
```

## Project structure

```
server.py            MCP tools, resource, prompt, start-up
logic.py             backtest, dry-run checks, approval rule
rag.py               policy search with ChromaDB; `python rag.py` builds the index
data_gen.py          generates the synthetic data in data/ (seeded)
test_client.py       end-to-end check over real MCP stdio
measure_space.py     policy tokens per agent: all documents versus returned
eval_retrieval.py    checks that each question returns the right policy file
tests/               unit tests for logic.py and rag.py
data/  policy/       synthetic data and mock policy documents
```

## License

No license file is included and a license has not yet been selected.
