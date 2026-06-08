#!/usr/bin/env python3
"""Quick smoke test for JAK1 RA question in pipeline mode."""
import json
import urllib.request

BASE = "http://localhost:8000"

def req(method, path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=180) as resp:
        return resp.status, json.loads(resp.read().decode())

login_status, login = req("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})
token = login["access_token"]
_, agents = req("GET", "/api/agents", token=token)

query = "What evidence in our indexed documents supports JAK1 as a target in rheumatoid arthritis, and what are the main risks or gaps?"
targets = [
    "ADMET Prediction",
    "Target Validation",
    "Pathway Insight",
    "Literature Miner",
]

for name in targets:
    match = [a for a in agents if name in a["name"]]
    if not match:
        print(f"MISSING AGENT: {name}")
        continue
    agent = match[0]
    try:
        status, run = req(
            "POST",
            f"/api/agents/{agent['id']}/run",
            token=token,
            body={
                "input_data": {
                    "query": query,
                    "task_type": "target_validation" if "Target" in name else ("literature" if "Literature" in name else ("pathway" if "Pathway" in name else "molecular")),
                    "top_k": 8,
                },
                "context": "pipeline test",
            },
        )
        o = run.get("output_json") or {}
        keys = list(o.keys())[:12]
        ans = (o.get("answer") or o.get("summary") or "")[:120]
        print(f"\n=== {name} HTTP {status} ===")
        print(f"  mode={o.get('mode')} status={run.get('status')}")
        print(f"  keys={keys}")
        print(f"  answer/summary preview: {ans!r}")
    except Exception as exc:
        print(f"\n=== {name} FAILED ===")
        print(f"  {exc}")
