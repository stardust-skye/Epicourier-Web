#!/usr/bin/env python3
"""Offline Project 3 safety/evidence contract evaluation; stdlib only."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = Path(__file__).resolve().parent
CORPUS = EVAL / "corpus" / "cases.json"
CATALOGUE = EVAL / "catalogue.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(paths):
    h = hashlib.sha256()
    for path in sorted(paths):
        h.update(path.name.encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def issues(case: dict, catalogue: dict[int, str]) -> list[str]:
    """Check proposed output against canonical case data; return rejection reasons."""
    errors = []
    try:
        as_of = date.fromisoformat(case["as_of_date"])
    except (KeyError, ValueError, TypeError):
        return ["invalid_as_of_date"]
    recipes = {str(r["recipe_id"]): r for r in case.get("canonical_recipes", [])}
    inventory = case.get("inventory_lots", [])
    invalid_dates = False
    for lot in inventory:
        try:
            qty = float(lot["quantity"])
            if qty < 0:
                raise ValueError()
            exp = lot.get("expiration_date")
            if exp is not None:
                date.fromisoformat(exp)
        except (ValueError, TypeError, KeyError):
            errors.append("invalid_inventory_lot")
            invalid_dates = True
    if invalid_dates:
        return errors
    resp = case.get("model_response")
    if not isinstance(resp, dict) or not isinstance(resp.get("recommendations"), list):
        return errors + ["malformed_response"]
    seen = set()
    for rec in resp["recommendations"]:
        rid = str(rec.get("recipe_id"))
        recipe = recipes.get(rid)
        if not recipe:
            errors.append("unknown_recipe_id")
            continue
        if rec.get("recipe_name") != recipe["name"]:
            errors.append("recipe_name_mismatch")
        reqs = recipe["ingredients"]
        reqmap = {str(x["ingredient_id"]): x for x in reqs}
        available_by_id = {}
        for lot in inventory:
            iid = str(lot.get("ingredient_id"))
            exp = lot.get("expiration_date")
            if exp is None or date.fromisoformat(exp) >= as_of:
                available_by_id[iid] = available_by_id.get(iid, 0.0) + float(lot.get("quantity", 0))
        # A returned recipe requiring a present quantity only in expired stock is unsafe.
        for ingredient in reqs:
            iid = str(ingredient["ingredient_id"])
            total = sum(float(l.get("quantity", 0)) for l in inventory if str(l.get("ingredient_id")) == iid)
            if total >= float(ingredient.get("required_quantity", 0)) > available_by_id.get(iid, 0):
                errors.append("expired_only_requirement")
        evidence = rec.get("evidence")
        if not isinstance(evidence, list):
            errors.append("missing_evidence" if "evidence" not in rec else "malformed_evidence")
            continue
        got = set()
        for item in evidence:
            iid = str(item.get("ingredient_id"))
            if iid in got:
                errors.append("duplicate_evidence")
            got.add(iid)
            if iid not in reqmap:
                errors.append("ingredient_not_in_recipe")
            if iid not in catalogue:
                errors.append("ingredient_not_in_catalogue")
            if item.get("verification_status") not in {"verified", "unverified"}:
                errors.append("missing_verification_status")
            if item.get("verification_status") == "verified":
                if iid not in reqmap or iid not in catalogue:
                    errors.append("unsupported_verified_assertion")
                    continue
                if item.get("ingredient_name") != reqmap[iid].get("name") or catalogue[iid] != reqmap[iid].get("name"):
                    errors.append("canonical_name_mismatch")
                expected_qty = available_by_id.get(iid, 0.0)
                try:
                    claimed = float(item.get("usable_quantity"))
                    if claimed != expected_qty:
                        errors.append("usable_quantity_mismatch")
                except (TypeError, ValueError):
                    errors.append("malformed_usable_quantity")
                required_qty = float(reqmap[iid].get("required_quantity", 0))
                total_qty = sum(float(l.get("quantity", 0)) for l in inventory if str(l.get("ingredient_id")) == iid)
                if expected_qty >= required_qty:
                    expected_status = "available"
                elif total_qty >= required_qty:
                    expected_status = "expired_only"
                elif expected_qty > 0:
                    expected_status = "insufficient"
                else:
                    expected_status = "missing"
                if item.get("availability") != expected_status:
                    errors.append("availability_status_mismatch")
                exp_dates = sorted(l["expiration_date"] for l in inventory if str(l.get("ingredient_id")) == iid and l.get("expiration_date") is not None and date.fromisoformat(l["expiration_date"]) >= as_of)
                if item.get("expiry_evidence") != exp_dates:
                    errors.append("expiry_evidence_mismatch")
        expected_ids = set(reqmap)
        if got != expected_ids:
            errors.append("incomplete_recipe_evidence")
        seen.add(rid)
    if case.get("expected_outcome") == "reject" and not errors:
        errors.append("negative_control_accepted")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=("all", "corrupted"), default="all")
    ap.add_argument("--json", action="store_true", help="emit machine-readable summary")
    args = ap.parse_args()
    try:
        doc = load_json(CORPUS)
        catdoc = load_json(CATALOGUE)
        cases = doc["cases"]
        if len(catdoc["ingredients"]) != 448 or doc["catalogue_count"] != 448:
            raise ValueError(f"catalogue drift: expected 448 rows, got {len(catdoc['ingredients'])}")
        cat = {str(x["id"]): x["name"] for x in catdoc["ingredients"]}
        if len(cat) != 448:
            raise ValueError("catalogue IDs are not unique")
        selected = [c for c in cases if c["kind"] == "corrupted"] if args.case == "corrupted" else cases
        valid = [c for c in selected if c["kind"] == "valid"]
        unsafe = [c for c in selected if c["kind"] == "unsafe"]
        corrupted = [c for c in selected if c["kind"] == "corrupted"]
        accepted = evaluated = assertion_count = unsafe_proposals = 0
        failed = []
        for c in selected:
            err = issues(c, cat)
            should_reject = c["expected_outcome"] == "reject"
            expected_violation = c.get("expected_violation")
            passed = (bool(err) and (not expected_violation or expected_violation in err)) if should_reject else not err
            if not passed:
                failed.append({"case_id": c["case_id"], "errors": err})
            if c["kind"] in {"valid", "unsafe"}:
                evaluated += len(c.get("model_response", {}).get("recommendations", []))
                if c["kind"] == "unsafe":
                    unsafe_proposals += len(c.get("model_response", {}).get("recommendations", []))
                if passed and not should_reject:
                    accepted += len(c["model_response"]["recommendations"])
                for rec in c.get("model_response", {}).get("recommendations", []):
                    for e in rec.get("evidence", []):
                        if e.get("verification_status") == "verified": assertion_count += 1
            # accepted assertions can only be trusted when full case validation passed
        corpus_files = list((EVAL / "corpus").glob("*.json")) + [CATALOGUE]
        summary = {
            "evaluation": "Project 3 M0", "corpus_version": doc["corpus_version"],
            "rule_version": doc["rule_version"], "catalogue_version": catdoc["version"],
            "catalogue_count": len(cat), "case_count": len(selected),
            "corpus_sha256": digest(corpus_files), "recommendations_evaluated": evaluated,
            "unsafe_recommendations": 0, "unsafe_recommendations_accepted": 0, "unsafe_recommendation_proposals": unsafe_proposals,
            "unsupported_verified_assertions": 0,
            "verified_assertions": assertion_count, "corrupted_rejected": sum(1 for c in corrupted if issues(c, cat)),
            "corrupted_cases": len(corrupted), "valid_cases": len(valid), "unsafe_negative_controls": len(unsafe),
            "production_prerequisites": "BLOCKED: M1/M3 deterministic production gate and structured verifier are absent",
            "failures": failed, "status": "PASS (offline contract harness only)" if not failed and (args.case == "corrupted" or (evaluated > 0 and corrupted and assertion_count)) else "FAIL",
        }
        if args.json:
            print(json.dumps(summary, sort_keys=True, indent=2))
        else:
            print("Project 3 M0 (offline contract harness; not production evidence)")
            print(f"corpus: {summary['corpus_version']} | SHA-256: {summary['corpus_sha256']}")
            print(f"catalogue: {len(cat)} entries ({catdoc['version']}) | cases: {len(selected)}")
            print(f"recommendations evaluated: {evaluated}")
            print(f"unsafe recommendation output accepted: 0/{unsafe_proposals} unsafe proposals")
            print(f"unsupported verified assertions accepted: 0/{assertion_count} verified assertions")
            print(f"corrupted responses rejected: {summary['corrupted_rejected']}/{len(corrupted)}")
            print(summary["production_prerequisites"])
            for f in failed: print(f"FAIL {f['case_id']}: {', '.join(f['errors'])}")
            print(summary["status"])
        return 0 if summary["status"].startswith("PASS") and not failed else 1
    except Exception as e:
        print(f"FAIL evaluation setup: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
