"""Dependency-free unit checks for the P3 evaluation contract."""
import json
import unittest
from pathlib import Path
from .run_eval import CATALOGUE, CORPUS, issues

class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat={str(x['id']):x['name'] for x in json.loads(CATALOGUE.read_text())['ingredients']}
        cls.cases=json.loads(CORPUS.read_text())['cases']
    def case(self,prefix): return next(c for c in self.cases if c['case_id'].startswith(prefix))
    def test_catalogue_pinned_to_448(self): self.assertEqual(len(self.cat),448)
    def test_corpus_counts(self):
        self.assertEqual(len(self.cases),60)
        self.assertEqual([sum(c['kind']==k for c in self.cases) for k in ('valid','unsafe','corrupted')],[30,15,15])
    def test_valid_evidence_passes(self): self.assertEqual(issues(self.case('valid-'),self.cat),[])
    def test_expired_only_recommendation_fails(self): self.assertIn('expired_only_requirement',issues(self.case('unsafe-'),self.cat))
    def test_fresh_on_boundary_is_usable(self): self.assertEqual(issues(self.case('valid-02'),self.cat),[])
    def test_unknown_recipe_fails(self): self.assertIn('unknown_recipe_id',issues(self.case('corrupt-01'),self.cat))
    def test_wrong_name_fails(self): self.assertIn('recipe_name_mismatch',issues(self.case('corrupt-02'),self.cat))
    def test_hallucinated_ingredient_fails(self): self.assertTrue(issues(self.case('corrupt-03'),self.cat))
    def test_catalogue_omission_fails(self): self.assertIn('ingredient_not_in_catalogue',issues(self.case('corrupt-04'),self.cat))
    def test_falsely_usable_expired_lot_fails(self): self.assertIn('expired_only_requirement',issues(self.case('corrupt-05'),self.cat))
    def test_unverifiable_assertion_is_not_verified_fact(self):
        c=self.case('valid-'); c=json.loads(json.dumps(c)); c['model_response']['recommendations'][0]['evidence'][0]['verification_status']='unverified'; self.assertEqual(issues(c,self.cat),[])
    def test_duplicate_evidence_fails(self): self.assertIn('duplicate_evidence',issues(self.case('corrupt-08'),self.cat))
    def test_missing_status_fails(self): self.assertIn('missing_verification_status',issues(self.case('corrupt-09'),self.cat))
    def test_invalid_expiration_fails(self): self.assertIn('invalid_inventory_lot',issues(self.case('corrupt-10'),self.cat))
    def test_wrong_quantity_fails(self): self.assertIn('usable_quantity_mismatch',issues(self.case('corrupt-12'),self.cat))
    def test_missing_evidence_fails(self): self.assertTrue(issues(self.case('corrupt-14'),self.cat))

if __name__=='__main__': unittest.main()
