"""Acceptance uses public requirements and fresh native calculations, no hidden answer."""
import json
import math
import time
from pathlib import Path

import cadquery as cq
import meshio
import numpy as np

from gongzheng.model import build
from gongzheng.native import digest, deck_force, deck_signature, make_deck, run_pipeline, shape_data


def verify(project, out, requirements=None):
    start = time.monotonic()
    project, out = Path(project), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    p = json.loads((project / 'parameters.json').read_text())
    # In agent evaluations, pass a separate trusted requirements path.
    req_path = Path(requirements) if requirements else project / 'requirements.json'
    req = json.loads(req_path.read_text())
    checks = []

    def record(key, label, ok, observed, expected, files):
        checks.append({'id': key, 'label': label, 'status': 'pass' if ok else 'fail',
                       'observed': observed, 'expected': expected, 'files': files})

    current = build(p)
    submitted = cq.importers.importStep(str(project / 'part.step')).val()
    delta = current.cut(submitted).Volume() + submitted.cut(current).Volume()
    record('source_step', '参数源与交付 STEP 一致', delta < .001 and submitted.isValid(),
           {'symmetric_difference_mm3': delta}, {'maximum_mm3': .001}, ['parameters.json', 'part.step'])
    bb = submitted.BoundingBox()
    margin = req['assembly']['envelope_z_mm'] - bb.zmax
    record('assembly', '装配净空', margin >= req['assembly']['min_clearance_mm'] - 1e-6,
           {'clearance_mm': margin}, req['assembly'], ['part.step', 'requirements.json'])
    variants = []
    for width in req['variants']['widths_mm']:
        q = {**p, 'width_mm': width}
        solid = build(q)
        centers = []
        for face in solid.Faces():
            if face.geomType() == 'CYLINDER':
                c = face.Center()
                if abs(c.x - .7 * p['length_mm']) < .01:
                    centers.append(c.y)
        y = centers[0] if centers else None
        target = width * req['variants']['hole_y_width_ratio']
        ok = y is not None and abs(y - target) < .01
        variants.append({'width_mm': width, 'measured_hole_y_mm': y, 'required_hole_y_mm': target, 'pass': ok})
        cq.exporters.export(solid, str(out / f'variant-{width}.step'))
    record('variants', '承诺变型范围内的孔位关系', all(v['pass'] for v in variants), variants,
           req['variants'], ['parameters.json', 'requirements.json'])
    mesh = meshio.read(str(project / 'mesh.msh'))
    points = mesh.points[:, :3]
    box = np.array([*points.min(0), *points.max(0)])
    target_box = np.array([bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax])
    tet = mesh.cells_dict['tetra10'][:, :4]
    x = points[tet]
    volumes = np.abs(np.linalg.det(x[:, 1:] - x[:, :1])) / 6
    volume = float(volumes.sum())
    gap = float(np.max(np.abs(box - target_box)))
    relative_volume = abs(volume - submitted.Volume()) / submitted.Volume()
    # Necessary coarse consistency gate; not a general mesh/CAD equivalence proof.
    record('mesh_geometry', '网格与当前几何的包络及体积一致', gap < .01 and relative_volume < .04,
           {'bbox_error_mm': gap, 'volume_relative_error': relative_volume},
           {'bbox_tolerance_mm': .01, 'volume_tolerance': .04, 'scope': 'coarse geometry gate'}, ['part.step', 'mesh.msh'])
    force = deck_force(project / 'analysis.inp')
    intended = req['analysis']['force_N_global']
    record('load', '求解输入的总载荷符合公开工况', np.linalg.norm(np.array(force) - intended) < 1e-6,
           {'total_force_N_global': force}, {'force_N_global': intended, 'frame': 'CAD global XYZ'}, ['analysis.inp', 'requirements.json'])
    rebuilt = run_pipeline(p, intended, out / 'replay')
    old = json.loads((project / 'result.json').read_text())
    # Re-run the submitted native deck as a distinct path; do not trust report numbers.
    from gongzheng.native import run_solver
    import shutil
    deck = out / 'submitted.inp'
    shutil.copyfile(project / 'analysis.inp', deck)
    # Uniform mean is not used for gate; maximum displacement has no weighting dependence.
    actual, _ = run_solver(deck, np.ones(len(points)) / len(points))
    error = abs(actual['max_displacement_mm'] - old['max_displacement_mm'])
    lineage = old.get('mesh_sha256') == digest(project / 'mesh.msh') and old.get('deck_sha256') == digest(project / 'analysis.inp')
    expected_deck = out / 'expected-from-submitted-mesh.inp'
    make_deck(project / 'mesh.msh', expected_deck, intended)
    deck_matches = deck_signature(expected_deck) == deck_signature(project / 'analysis.inp')
    record('result', '求解输入符合网格工况且结果可重现', error < 1e-6 and lineage and deck_matches,
           {'max_u_error_mm': error, 'hash_lineage_matches': lineage, 'adapter_deck_matches_mesh_and_requirements': deck_matches},
           {'max_u_tolerance_mm': 1e-6, 'lineage_required': True, 'deck_scope': 'supported linear elastic adapter; nodes/elements/material/constraints/loads'}, ['analysis.inp', 'mesh.msh', 'result.json'])
    report = json.loads((project / 'report.json').read_text())
    deviation = abs(report['max_displacement_mm'] - rebuilt['max_displacement_mm'])
    record('report', '报告与公开工况的独立重算一致', deviation < .001,
           {'reported_mm': report['max_displacement_mm'], 'replayed_mm': rebuilt['max_displacement_mm'], 'difference_mm': deviation},
           {'maximum_difference_mm': .001}, ['report.json', 'requirements.json', 'replay/result.json'])
    limit = req['analysis']['max_displacement_mm']
    record('response', '指定工况的位移限值', rebuilt['max_displacement_mm'] <= limit,
           {'max_displacement_mm': rebuilt['max_displacement_mm']}, {'maximum_mm': limit}, ['replay/result.json', 'requirements.json'])
    payload = {'schema': 'gongzheng.acceptance.v1', 'project': project.name,
               'decision': 'accept' if all(c['status'] == 'pass' for c in checks) else 'reject',
               'checks': checks, 'passed': sum(c['status'] == 'pass' for c in checks), 'total': len(checks),
               'duration_s': round(time.monotonic() - start, 3),
               'scope': 'synthetic fixture; linear elastic; no safety certification',
               'requirements_sha256': digest(req_path),
               'lineage': {f.name: digest(f) for f in project.iterdir() if f.is_file() and f.suffix in ('.json', '.step', '.msh', '.inp')},
               'geometry': shape_data(submitted), 'replay_result': rebuilt}
    (out / 'acceptance.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    return payload
