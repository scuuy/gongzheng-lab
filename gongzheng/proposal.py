"""Model-agnostic JSON proposal boundary. No model-provided code is executed."""
import json
import math
import shutil
from pathlib import Path

from gongzheng.native import run_pipeline
from gongzheng.verify import verify

ALLOWED = {'length_mm', 'width_mm', 'height_mm', 'boss_height_mm', 'hole_y_override_mm'}


def apply_proposal(project, proposal, out):
    project, out = Path(project), Path(out)
    data = json.loads(Path(proposal).read_text())
    if data.get('schema') != 'gongzheng.proposal.v1':
        raise ValueError('Unsupported proposal schema')
    p = data.get('parameters')
    if not isinstance(p, dict) or set(p) - ALLOWED:
        raise ValueError('Proposal may only supply supported geometry parameters')
    for value in p.values():
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Parameters must be finite numbers')
    if not {'length_mm', 'width_mm', 'height_mm'} <= set(p):
        raise ValueError('Missing required dimensions')
    candidate = out / 'candidate'
    if candidate.exists():
        raise ValueError('Output exists; use a fresh run directory')
    shutil.copytree(project, candidate)
    req = json.loads((project / 'requirements.json').read_text())
    (candidate / 'parameters.json').write_text(json.dumps(p, indent=2))
    result = run_pipeline(p, req['analysis']['force_N_global'], candidate)
    (candidate / 'report.json').write_text(json.dumps({'max_displacement_mm': result['max_displacement_mm']}, indent=2))
    shutil.copyfile(proposal, out / 'proposal.json')
    return verify(candidate, out / 'verification', project / 'requirements.json')
