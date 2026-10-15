"""Demonstration repair recipe derived only from public requirements.
Not an autonomous AI repair. Every proposal requires an explicit invocation.
"""
import json
import shutil
from pathlib import Path

from gongzheng.native import run_pipeline
from gongzheng.verify import verify


def repair(project, out):
    project, out = Path(project), Path(out)
    candidate = out / 'candidate'
    if candidate.exists():
        raise ValueError('Repair output already exists; select a fresh run directory')
    shutil.copytree(project, candidate)
    p = json.loads((candidate / 'parameters.json').read_text())
    req = json.loads((candidate / 'requirements.json').read_text())
    before = dict(p)
    p.pop('hole_y_override_mm', None)
    ceiling = req['assembly']['envelope_z_mm'] - req['assembly']['min_clearance_mm'] - p['height_mm']
    p['boss_height_mm'] = min(p.get('boss_height_mm', 0), ceiling)
    (candidate / 'parameters.json').write_text(json.dumps(p, indent=2))
    result = run_pipeline(p, req['analysis']['force_N_global'], candidate)
    (candidate / 'report.json').write_text(json.dumps({'max_displacement_mm': result['max_displacement_mm']}, indent=2))
    (out / 'proposal.json').write_text(json.dumps({'method': 'explicit deterministic demo recipe; not AI inference',
        'requirements_changed': False, 'parameters_before': before, 'parameters_after': p,
        'regenerated': ['part.step', 'mesh.msh', 'analysis.inp', 'result.json', 'report.json']}, indent=2))
    return verify(candidate, out / 'verification')
