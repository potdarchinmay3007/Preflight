"""Preflight: test GTM agents BEFORE they touch real accounts.  3 tools.

Run (stdio): python server.py
Run (HTTP):  python server.py --http      -> http://127.0.0.1:8000/mcp
Needs ./data (run `python data_gen.py` once) and ./policy (included).
"""
import json, math, re, sys, datetime as dt
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from mcp.server.fastmcp import FastMCP

HERE = Path(__file__).parent
DATA, POLICY = HERE / "data", HERE / "policy"
if not (DATA / "accounts.json").exists():
    raise SystemExit("data/ is missing. Run: python data_gen.py")

TODAY = dt.date(2026, 10, 7)          # fixed so results are reproducible
MIN_EVENTS = 30                       # minimum events per group for a verdict
CHUNK_WORDS, CHUNK_OVERLAP, TOP_K = 120, 20, 3   # RAG settings
load = lambda n: json.loads((DATA / f"{n}.json").read_text())
ACCOUNTS = {a["account_id"]: a for a in load("accounts")}
EVENTS, AGENTS = load("events"), load("agents")
RUNS = {r["run_id"]: r for r in load("runs")}
AUDIT = DATA / "audit_log.jsonl"
d = dt.date.fromisoformat

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    tokens = lambda s: len(_enc.encode(s))
    TOKEN_METHOD = "tiktoken cl100k_base"
except Exception:                      # offline fallback
    tokens = lambda s: len(s) // 4
    TOKEN_METHOD = "estimate: characters / 4"

mcp = FastMCP("preflight", host="127.0.0.1", port=8000)


# ---------------------------------------------------------------- statistics
def wilson(h, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = h / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(c - m, 3), round(c + m, 3))


def rate(signal, window):
    """Hit rate using ONLY events old enough for the outcome to be observable
    (point-in-time correctness: no peeking at events whose window is still open)."""
    cutoff = TODAY - dt.timedelta(days=window)
    ev = [e for e in EVENTS if e["signal"] == signal and d(e["fired_on"]) <= cutoff]
    hits = sum(1 for e in ev if e["outcome_on"] and
               (d(e["outcome_on"]) - d(e["fired_on"])).days <= window)
    return hits, len(ev)


# ------------------------------------------------------- RAG over policy docs
_STOP = set("a an the and or of to in on for is are be it as at by with that this from if any no not".split())
_stem = lambda w: next((w[:-len(s)] for s in ("ing", "ed", "es", "s")
                        if w.endswith(s) and len(w) - len(s) >= 3), w)
_tok = lambda t: [_stem(w) for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in _STOP]


def _build_index():
    chunks, corpus = [], []
    step = CHUNK_WORDS - CHUNK_OVERLAP
    for p in sorted(POLICY.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        corpus.append(text)
        words = text.split()
        for i, start in enumerate(range(0, max(len(words), 1), step)):
            piece = words[start:start + CHUNK_WORDS]
            if not piece:
                break
            chunks.append({"source": p.name, "chunk_index": i, "text": " ".join(piece)})
            if start + CHUNK_WORDS >= len(words):
                break
    terms = [Counter(_tok(c["text"])) for c in chunks]
    lens = [sum(t.values()) for t in terms]
    df = Counter(k for t in terms for k in t)
    n = len(chunks)
    idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    return chunks, terms, lens, (sum(lens) / n if n else 0.0), idf, tokens("\n\n".join(corpus))


CHUNKS, _TERMS, _LENS, _AVG, _IDF, CORPUS_TOKENS = _build_index()


def search_policy(query, k=TOP_K):
    """BM25 keyword ranking over policy chunks. Returns only the top-k chunks."""
    k1, b, scored = 1.5, 0.75, []
    for i, t in enumerate(_TERMS):
        s = sum(_IDF.get(w, 0) * t[w] * (k1 + 1) / (t[w] + k1 * (1 - b + b * _LENS[i] / _AVG))
                for w in _tok(query) if t.get(w))
        if s > 0:
            scored.append((s, i))
    scored.sort(reverse=True)
    out = [{"source": CHUNKS[i]["source"], "chunk_index": CHUNKS[i]["chunk_index"],
            "score": round(s, 2), "text": CHUNKS[i]["text"]} for s, i in scored[:k]]
    return {"chunk_size_words": CHUNK_WORDS, "chunk_overlap_words": CHUNK_OVERLAP,
            "chunks_returned": len(out), "tokens_all_policy_docs": CORPUS_TOKENS,
            "tokens_returned": tokens(json.dumps(out)), "token_method": TOKEN_METHOD,
            "chunks": out}


# --------------------------------------------------------------- tool 1
@mcp.tool()
def backtest_signal(signal: str, window_days: int = 30) -> dict:
    """Check whether a GTM signal really predicts a booked meeting, using past data.
    Use this BEFORE launching an agent that depends on the signal.
    signal: one of first_gtm_hire, pricing_page_visits, champion_moves, conference_attendee.
    window_days: days allowed for the meeting to happen after the signal (1 to 90, default 30).
    Returns hit rate, baseline rate, lift (signal rate / baseline rate), 95% range, and a verdict."""
    valid = sorted({e["signal"] for e in EVENTS} - {"control"})
    if signal not in valid:
        return {"error": f"unknown signal: {signal}", "valid": valid}
    if not 1 <= window_days <= 90:
        return {"error": "window_days must be between 1 and 90"}
    h, n = rate(signal, window_days)
    bh, bn = rate("control", window_days)
    if n < MIN_EVENTS or bn < MIN_EVENTS:
        return {"error": f"not enough mature events (signal {n}, control {bn}; need {MIN_EVENTS}+)"}
    r, br = h / n, bh / bn
    lo, hi = wilson(h, n)
    lift = round(r / br, 2) if br else None
    verdict = ("KEEP: clearly beats baseline" if lo > br else
               "DROP: not better than random" if hi < br * 1.1 else
               "UNSURE: need more data")
    return {"signal": signal, "events_used": n, "hit_rate": round(r, 3),
            "baseline_rate": round(br, 3), "lift": lift, "range_95": [lo, hi],
            "verdict": verdict,
            "note": "Only events older than window_days are counted, so no outcome is missing."}


# --------------------------------------------------------------- tool 2
def _norm(name):
    s = re.sub(r"[^a-z0-9 ]", "", name.lower())
    return " ".join(w for w in s.split() if w not in {"inc", "corp", "corporation", "llc", "co", "ltd"})


def _simulate(agent_id, account_ids):
    ag = AGENTS[agent_id]
    issues = []
    norm = {a: _norm(ACCOUNTS[a]["name"]) for a in ACCOUNTS}
    for aid in account_ids:
        acc = ACCOUNTS[aid]
        if acc["suppressed"]:
            issues.append({"account": aid, "type": "BLOCK", "kind": "suppressed",
                           "why": "on suppression list"})
        days = (TODAY - d(acc["last_contacted"])).days
        if days < 7 and "email" in ag["actions"]:
            issues.append({"account": aid, "type": "BLOCK", "kind": "recent_contact",
                           "why": f"contacted {days} days ago"})
        for other, nm in norm.items():
            if other != aid and (nm == norm[aid] or SequenceMatcher(None, nm, norm[aid]).ratio() > 0.9):
                issues.append({"account": aid, "type": "WARN", "kind": "duplicate",
                               "why": f"possible duplicate of {other} ('{ACCOUNTS[other]['name']}')"})
                break
        if "crm_update" in ag["actions"] and acc["crm_fields"]["status"] == "customer":
            issues.append({"account": aid, "type": "WARN", "kind": "overwrite",
                           "why": "would overwrite fields on a customer record"})
    return issues


_QUERY = {"suppressed": "suppression list do not contact suppressed account",
          "recent_contact": "contact frequency minimum days between emails seven day rule",
          "duplicate": "duplicate company account matching merge",
          "overwrite": "overwrite customer CRM record write-back rules"}


@mcp.tool()
def simulate_agent_run(agent_id: str, account_ids: list[str] | None = None) -> dict:
    """Dry run: show what an agent WOULD do and what could go wrong. Sends and changes nothing.
    agent_id: lookalike_prospecting, website_visitor_outreach, champion_reactivation, or conference_followup.
    account_ids: optional; if empty, uses accounts where the agent's signal fired in the last 60 days.
    Returns blockers (must fix), warnings (review), counts, and the few policy passages
    that apply to the problems found (not the whole policy documents)."""
    if agent_id not in AGENTS:
        return {"error": "unknown agent", "valid": list(AGENTS)}
    if not account_ids:
        cut = TODAY - dt.timedelta(days=60)
        sig = AGENTS[agent_id]["signal"]
        account_ids = sorted({e["account_id"] for e in EVENTS
                              if e["signal"] == sig and d(e["fired_on"]) >= cut})[:25]
    bad = [a for a in account_ids if a not in ACCOUNTS]
    if bad:
        return {"error": f"unknown account ids: {bad[:5]}"}
    issues = _simulate(agent_id, account_ids)
    blocks = [i for i in issues if i["type"] == "BLOCK"]
    kinds = sorted({i["kind"] for i in issues})
    out = {"agent": agent_id, "accounts_checked": len(account_ids),
           "blockers": len(blocks), "warnings": len(issues) - len(blocks),
           "safe_to_launch": not blocks, "top_issues": issues[:8],
           "planned_actions": AGENTS[agent_id]["actions"]}
    if kinds:
        out["policy_context"] = search_policy(" ".join(_QUERY[k] for k in kinds))
    return out


# --------------------------------------------------------------- tool 3
@mcp.tool()
def decide_launch(run_id: str, decision: str, reason: str) -> dict:
    """Record a human approve/reject for a run's write-back. REQUIRES a reason.
    run_id: R000 to R059. decision: 'approve' or 'reject'.
    Approval is refused if the dry run has blockers. Every decision is saved to an audit log.
    Only call this after a person has decided."""
    r = RUNS.get(run_id)
    if not r:
        return {"error": "unknown run_id", "examples": list(RUNS)[:5]}
    if decision not in ("approve", "reject") or not reason.strip():
        return {"error": "decision must be approve/reject and reason is required"}
    blocks = [i for i in _simulate(r["agent"], r["account_ids"]) if i["type"] == "BLOCK"]
    if decision == "approve" and blocks:
        return {"status": "REFUSED", "why": f"{len(blocks)} blockers remain", "blockers": blocks[:5]}
    rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "run_id": run_id,
           "decision": decision, "reason": reason}
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return {"status": "RECORDED", **rec}


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
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
