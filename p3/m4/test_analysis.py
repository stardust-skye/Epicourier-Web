"""Synthetic smoke checks for M4 tally validation; these are not study data."""
import csv, tempfile, unittest
from pathlib import Path
from .analysis import REQUIRED, run

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'tally.csv'
        with self.path.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=sorted(REQUIRED)); w.writeheader()
            recipe_ids=[101,102,103,104,105,106,107,109,111,112]
            for condition in ('A','B'):
                for i in range(1,11):
                    w.writerow({'participant_code':'DRYRUN-1','condition':condition,'scenario_id':f'S{i:02}','order_group':'AB','scenario_position':i,'selected_recipe_id':recipe_ids[i-1],'identified_ingredients':'[]','identified_expired_ingredients':'[]','decision_time_seconds':'10','confidence_1_to_5':'3'})
    def tearDown(self): self.tmp.cleanup()
    def test_complete_pair_analyzes_and_reports_denominators(self):
        r=run(self.path); self.assertEqual(r['participants_completed'],1); self.assertEqual(r['trials_completed'],20); self.assertEqual(r['missing_trials'],[]); self.assertEqual(r['conditions']['A']['unsafe_denominator'],10)
    def test_missing_trials_are_preserved(self):
        with self.path.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
        rows.pop()
        with self.path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=sorted(REQUIRED)); w.writeheader(); w.writerows(rows)
        r=run(self.path); self.assertEqual(len(r['missing_trials']),1); self.assertEqual(r['trials_completed'],19)
    def test_unknown_scenario_is_rejected(self):
        with self.path.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
        rows[0]['scenario_id']='NOPE'
        with self.path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=sorted(REQUIRED)); w.writeheader(); w.writerows(rows)
        with self.assertRaisesRegex(ValueError,'unknown scenario'): run(self.path)

if __name__=='__main__': unittest.main()
