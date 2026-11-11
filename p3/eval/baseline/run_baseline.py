#!/usr/bin/env python3
"""Offline mock comparison against the inherited RecommendedRecipe boundary.

This intentionally models shape validation only. It does not call Gemini and does
not claim to reproduce how a particular live model responds to a prompt.
"""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CORPUS=HERE.parent/'corpus'/'cases.json'

def main():
    doc=json.loads(CORPUS.read_text(encoding='utf-8'))
    proposals=[c for c in doc['cases'] if c['kind']=='unsafe']
    accepted=0
    for c in proposals:
        rec=c['model_response']['recommendations'][0]
        # Fields mirror the legacy Pydantic shape; no evidence/safety semantics exist.
        legacy={'recipe_id':rec['recipe_id'],'recipe_name':rec['recipe_name'],'match_score':80,
                'ingredients_available':[],'ingredients_missing':[],'expiring_ingredients_used':[],
                'reason':'Mock inherited prompt response.'}
        if set(legacy)=={'recipe_id','recipe_name','match_score','ingredients_available','ingredients_missing','expiring_ingredients_used','reason'}:
            accepted+=1
    print('Inherited prompt-only mock baseline (not a live-model estimate)')
    print(f'unsafe expired-only proposals accepted by legacy response shape: {accepted}/{len(proposals)}')
    print('deterministic expiry gate: absent')
    print('canonical evidence field: absent')
    print('Gemini calls: 0')
    return 0

if __name__=='__main__': raise SystemExit(main())
