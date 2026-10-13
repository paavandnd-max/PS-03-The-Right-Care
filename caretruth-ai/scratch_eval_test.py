import json
import sys
from pathlib import Path

# Add caretruth-ai to path
caretruth_path = Path(r"c:\Users\Paavan Sharma\antigravity-team-workspace\caretruth-ai")
sys.path.insert(0, str(caretruth_path))

from fastapi.testclient import TestClient
import api

client = TestClient(api.app)

probe_file = Path(r"c:\Users\Paavan Sharma\antigravity-team-workspace\reference\participant_eval_kit\participant_eval_kit\samples\ps03_practice_probes.jsonl")

results = []
with open(probe_file, encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        probe = json.loads(line)
        pid = probe["probe_id"]
        inp = probe["input"]
        resp = client.post("/solve", json=inp)
        assert resp.status_code == 200, f"Error {resp.status_code}: {resp.text}"
        out = resp.json()
        results.append(out)
        print(f"=== PROBE: {pid} ===")
        print(f"Abstain: {out.get('abstain')} | Reason: {out.get('abstain_reason')}")
        print(f"Desert flags: {out.get('desert_flags')}")
        facs = out.get("facilities", [])
        print(f"Facilities count: {len(facs)}")
        for i, fac in enumerate(facs[:3]):
            print(f"  #{i+1}: {fac['facility_name']} (PIN {fac['facility_pin']})")
            print(f"      verdict={fac['verdict']} | score={fac['trust_score']} | dist={fac['distance_km']} km")
            for cit in fac.get("citations", []):
                print(f"      cit [{cit['source_field']}]: {cit['span']}")
        print()
