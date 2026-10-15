"""Integration regressions: execute CAD, meshing and the native solver."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from gongzheng.examples import BASE, REQ, SCENES, write
from gongzheng.native import digest, run_pipeline
from gongzheng.proposal import apply_proposal
from gongzheng.repair import repair
from gongzheng.verify import verify

ROOT = Path(__file__).resolve().parents[1]

class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def fixture(self, name):
        target = self.work / 'input'
        shutil.copytree(ROOT / 'examples' / name, target)
        return target

    def test_six_designed_cases(self):
        for name, _, failure in SCENES:
            with self.subTest(case=name):
                r = verify(ROOT / 'examples' / name, self.work / name)
                failed = {c['id'] for c in r['checks'] if c['status']=='fail'}
                if name == 'normal':
                    self.assertEqual(r['decision'], 'accept')
                else:
                    self.assertEqual(r['decision'], 'reject')
                    self.assertIn(failure, failed)

    def test_recipe_repairs_five_failures_without_changing_requirements(self):
        for name, _, _ in SCENES[1:]:
            with self.subTest(case=name):
                out = self.work / name
                self.assertEqual(repair(ROOT/'examples'/name, out)['decision'], 'accept')
                self.assertEqual(digest(out/'candidate/requirements.json'), digest(ROOT/'examples'/name/'requirements.json'))

    def test_material_tampering_with_recomputed_hash_is_detected(self):
        p = self.fixture('normal')
        deck = p/'analysis.inp'
        deck.write_text(deck.read_text().replace('70000,0.3', '700000,0.3'))
        result=json.loads((p/'result.json').read_text())
        # Even a forged matching lineage hash must not authorize different physics.
        result['deck_sha256']=digest(deck)
        write(p/'result.json', result)
        r=verify(p,self.work/'check')
        check=next(c for c in r['checks'] if c['id']=='result')
        self.assertEqual(check['status'],'fail')
        self.assertFalse(check['observed']['adapter_deck_matches_mesh_and_requirements'])

    def test_step_changed_while_parameters_unchanged(self):
        p=self.fixture('normal')
        shutil.copyfile(ROOT/'examples/clearance/part.step',p/'part.step')
        r=verify(p,self.work/'check')
        self.assertEqual(next(c for c in r['checks'] if c['id']=='source_step')['status'],'fail')

    def test_equivalent_comments_are_accepted(self):
        p=self.fixture('normal')
        d=p/'analysis.inp';d.write_text('** audit comment\n'+d.read_text())
        result=json.loads((p/'result.json').read_text());result['deck_sha256']=digest(d);write(p/'result.json',result)
        self.assertEqual(verify(p,self.work/'check')['decision'],'accept')

    def test_public_clearance_boundary(self):
        for height, expected in [(4.5,'accept'),(4.51,'reject')]:
            p=self.work/str(height);p.mkdir()
            params={**BASE,'boss_height_mm':height}
            result=run_pipeline(params,REQ['analysis']['force_N_global'],p)
            write(p/'parameters.json',params);write(p/'requirements.json',REQ)
            write(p/'report.json',{'max_displacement_mm':result['max_displacement_mm']})
            self.assertEqual(verify(p,self.work/f'check-{height}')['decision'],expected)

    def test_missing_media_is_tool_error_not_engineering_rejection(self):
        p=self.fixture('normal');(p/'part.step').unlink()
        with self.assertRaises(Exception):
            verify(p,self.work/'check')
        self.assertFalse((self.work/'check/acceptance.json').exists())

    def test_model_proposal_cannot_replace_requirements(self):
        p=self.fixture('variant')
        proposal=self.work/'proposal.json'
        write(proposal,{'schema':'gongzheng.proposal.v1','parameters':{**BASE,'requirements':{}}})
        with self.assertRaises(ValueError):
            apply_proposal(p,proposal,self.work/'run')

    def test_model_proposal_uses_unchanged_trusted_requirements(self):
        p=self.fixture('variant');proposal=self.work/'proposal.json'
        write(proposal,{'schema':'gongzheng.proposal.v1','parameters':BASE,'rationale_zh':'恢复参数关系'})
        r=apply_proposal(p,proposal,self.work/'run')
        self.assertEqual(r['decision'],'accept')
        self.assertEqual(r['requirements_sha256'],digest(p/'requirements.json'))

if __name__=='__main__':
    unittest.main(verbosity=2)
