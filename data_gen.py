"""Generate synthetic GTM data with PLANTED ground truth.

Planted lifts (multiplier on a 8% base meeting rate):
  first_gtm_hire      3.0x   (strong)
  pricing_page_visits 2.0x   (good)
  champion_moves      1.5x   (mild)
  conference_attendee 0.5x   (worse than random, a trap)
The server must rediscover these numbers from raw events.
"""
import json, random, datetime as dt
from pathlib import Path

random.seed(7)
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)
TODAY = dt.date(2026, 10, 7)
BASE = 0.08
LIFT = {"first_gtm_hire": 3.0, "pricing_page_visits": 2.0,
        "champion_moves": 1.5, "conference_attendee": 0.5}
MAX_OUTCOME_DAYS = 30

first = ["Orbit","Nimbus","Kestrel","Lumen","Vertex","Harbor","Quill","Ember","Tidal","Cobalt",
         "Aurora","Fathom","Juniper","Mosaic","Zephyr","Onyx","Basalt","Cedar","Delta","Echo",
         "Falcon","Granite","Helix","Indigo","Jasper","Krypton","Lattice","Meridian","Nova","Opal",
         "Pioneer","Quasar","Relay","Summit","Talon","Umbra","Vector","Willow","Xenon","Yonder"]
last = ["Labs","Systems","Data","Cloud","Robotics","Analytics","Networks","Software"]
combos = [f"{f} {l}" for f in first for l in last]
random.shuffle(combos)
accounts = []
for i in range(240):
    accounts.append({
        "account_id": f"A{i:03d}", "name": combos[i],
        "owner": random.choice(["maya", "carl", "sam"]),
        "last_contacted": str(TODAY - dt.timedelta(days=random.randint(1, 90))),
        "suppressed": random.random() < 0.04,
        "crm_fields": {"status": random.choice(["prospect", "customer", "churned"]),
                       "icp_fit": random.randint(30, 95)},
    })
# planted duplicates under different spellings
accounts[40]["name"] = accounts[5]["name"].upper() + ", Inc."   # same company, different spelling
accounts[41]["name"] = accounts[9]["name"] + " Corp"

events = []
eid = 0
def add(sig, p):
    global eid
    a = random.choice(accounts)
    fired = TODAY - dt.timedelta(days=random.randint(1, 300))
    hit = random.random() < p
    outcome = str(fired + dt.timedelta(days=random.randint(3, MAX_OUTCOME_DAYS))) if hit else None
    # drop outcomes that would be in the future relative to TODAY
    if outcome and dt.date.fromisoformat(outcome) > TODAY:
        outcome = None
    events.append({"event_id": f"E{eid}", "signal": sig, "account_id": a["account_id"],
                   "fired_on": str(fired), "outcome_on": outcome})
    eid += 1
for sig, lift in LIFT.items():
    for _ in range(600):
        add(sig, min(0.95, BASE * lift))
for _ in range(4000):          # control group: no signal
    add("control", BASE)

agents = {
    "lookalike_prospecting": {"signal": "first_gtm_hire", "actions": ["email", "crm_update"]},
    "website_visitor_outreach": {"signal": "pricing_page_visits", "actions": ["email"]},
    "champion_reactivation": {"signal": "champion_moves", "actions": ["email", "crm_update"]},
    "conference_followup": {"signal": "conference_attendee", "actions": ["email"]},
}

# agent runs (id, agent, accounts) - used by decide_launch
runs = []
for r in range(60):
    ag = random.choice(list(agents))
    runs.append({"run_id": f"R{r:03d}", "agent": ag,
                 "account_ids": random.sample([a["account_id"] for a in accounts], 12)})

for name, obj in [("accounts", accounts), ("events", events), ("agents", agents), ("runs", runs)]:
    (OUT / f"{name}.json").write_text(json.dumps(obj))
print("generated", {k: len(v) for k, v in
      [("accounts", accounts), ("events", events), ("runs", runs)]})
