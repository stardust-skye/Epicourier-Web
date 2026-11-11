# Project 3 M0: offline safety and evidence contract

Run from the repository root with `py -3 p3/eval/run_eval.py`; use `--json` for machine readable output and `--case corrupted` to run the harness negative controls alone. The runner uses Python's standard library only and makes no network, Gemini, or Supabase calls.

The frozen corpus has 30 plausible outputs, 15 expired-only proposals, and 15 corrupted responses. Its hand-authored expected outcomes are independent of the validator. The ingredient snapshot is derived from `backend/dataset/ingredients-supabase.csv`; the expected catalogue size is pinned to 448. Corpus/catalogue SHA-256 is printed for reproduction.

**Interpretation:** PASS means this offline verifier accepted all declared valid examples, rejected unsafe/corrupt proposals, and met the fixture assertions. It does not show that the live recommendation endpoint invokes this verifier. The current inherited recommender has no deterministic expiry gate or structured canonical evidence; therefore production M0 threshold claims remain blocked pending M1/M3. The evaluator is an evaluation contract and synthetic harness, not a production implementation.

`baseline/legacy-characteristics.json` documents the inherited boundary; `py -3 p3/eval/baseline/run_baseline.py` applies that legacy shape-only boundary to the frozen unsafe proposals with mock responses. It demonstrates the absence of a deterministic gate, not a live-model failure rate. No Gemini calls are part of CI. Run the inherited receipt-v1 M0 separately: `py -3 p2/eval/run_eval.py` and `py -3 p2/eval/run_eval.py --case corrupted`.
