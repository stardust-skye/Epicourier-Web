#!/usr/bin/env python3
"""Analyze anonymized M4 trial tallies; standard library only."""
import argparse, csv, json, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = {"participant_code","condition","scenario_id","order_group","scenario_position","selected_recipe_id","identified_ingredients","identified_expired_ingredients","decision_time_seconds","confidence_1_to_5"}

def run(input_path):
    scenarios_doc=json.loads((HERE/"scenarios.json").read_text(encoding="utf-8")); scenarios={x["scenario_id"]:x for x in scenarios_doc["scenarios"]}
    provenance=set()
    with open(input_path,encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames): raise ValueError(f"missing columns: {sorted(REQUIRED-set(reader.fieldnames or []))}")
        rows=list(reader)
    if not rows: raise ValueError("no trial rows")
    seen=set(); scored=[]
    for n,r in enumerate(rows,2):
        if r.get("data_provenance"): provenance.add(r["data_provenance"])
        if not r["participant_code"]: raise ValueError(f"row {n}: participant_code is empty")
        if r["condition"] not in {"A","B"}: raise ValueError(f"row {n}: invalid condition")
        if r["order_group"] not in {"AB","BA"}: raise ValueError(f"row {n}: invalid order_group")
        if r["scenario_id"] not in scenarios: raise ValueError(f"row {n}: unknown scenario")
        key=(r["participant_code"],r["condition"],r["scenario_id"])
        if key in seen: raise ValueError(f"row {n}: duplicate participant/condition/scenario")
        seen.add(key); s=scenarios[r["scenario_id"]]
        try:
            rid=int(r["selected_recipe_id"]); pos=int(r["scenario_position"]); sec=float(r["decision_time_seconds"]); conf=int(r["confidence_1_to_5"])
            claims=json.loads(r["identified_ingredients"]); expired=json.loads(r["identified_expired_ingredients"])
            if sec<0 or not 1<=conf<=5 or pos<1 or not isinstance(claims,list) or not isinstance(expired,list): raise ValueError()
        except Exception as e: raise ValueError(f"row {n}: malformed trial values") from e
        allowed={int(x["recipe_id"]) for x in s["canonical_recipes"]}
        if rid not in allowed: raise ValueError(f"row {n}: selected recipe is not in scenario ground truth")
        claim_ids=[int(x) for x in claims]; exp_ids=[int(x) for x in expired]
        correct=sum(x in s["ground_truth_available_ingredients"] for x in claim_ids)+sum(x in s["ground_truth_expired_ingredients"] for x in exp_ids)
        scored.append({"participant":r["participant_code"],"condition":r["condition"],"scenario":r["scenario_id"],"unsafe":rid in s["unsafe_recipe_ids"] or rid not in s["safe_recipe_ids"],"correct":correct,"claims":len(claim_ids)+len(exp_ids),"seconds":sec,"confidence":conf})
    enrolled={r['participant'] for r in scored}; missing=[{"participant_code":p,"condition":c,"scenario_id":sid} for p in sorted(enrolled) for c in ('A','B') for sid in sorted(scenarios) if (p,c,sid) not in seen]
    out={"data_provenance":sorted(provenance) if provenance else ["unspecified"],"participants_enrolled":len(enrolled),"participants_completed":sum(1 for p in enrolled if all((p,c,sid) in seen for c in ('A','B') for sid in scenarios)),"trials_completed":len(scored),"trials_planned":len(enrolled)*len(scenarios)*2,"missing_trials":missing,"conditions":{},"paired_differences":{}}
    for c in ('A','B'):
        a=[x for x in scored if x['condition']==c]; times=[x['seconds'] for x in a]; conf=[x['confidence'] for x in a]; correct=sum(x['correct'] for x in a)
        out['conditions'][c]={"unsafe_selections":sum(x['unsafe'] for x in a),"unsafe_denominator":len(a),"ingredient_claims_correct":correct,"ingredient_claims_denominator":sum(x['claims'] for x in a),"decision_time_mean_seconds":statistics.mean(times) if times else None,"decision_time_median_seconds":statistics.median(times) if times else None,"confidence_mean":statistics.mean(conf) if conf else None,"confidence_median":statistics.median(conf) if conf else None}
    by={}
    for x in scored: by.setdefault(x['participant'],{})[x['condition']]=by.setdefault(x['participant'],{}).get(x['condition'],[])+[x]
    pairs=[]
    for p,v in sorted(by.items()):
        if 'A' in v and 'B' in v:
            pairs.append({"participant_code":p,"unsafe_rate_B_minus_A":sum(x['unsafe'] for x in v['B'])/len(v['B'])-sum(x['unsafe'] for x in v['A'])/len(v['A']),"time_mean_B_minus_A":statistics.mean(x['seconds'] for x in v['B'])-statistics.mean(x['seconds'] for x in v['A']),"confidence_mean_B_minus_A":statistics.mean(x['confidence'] for x in v['B'])-statistics.mean(x['confidence'] for x in v['A'])})
    out['paired_differences']=pairs; out['limitations']="Descriptive convenience-sample analysis only; missing planned trials remain visible in the denominator."
    return out

def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',required=True); p.add_argument('--json',action='store_true'); args=p.parse_args()
    try:
        out=run(Path(args.input)); print(json.dumps(out,indent=2,sort_keys=True)); return 0
    except Exception as e: print(f"FAIL: {e}",file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
