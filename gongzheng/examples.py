"""Self-authored simulation fixtures, separate from private challenge assets."""
import copy
import json
import shutil
from pathlib import Path

from gongzheng.native import run_pipeline
from gongzheng.verify import verify

BASE = {'length_mm': 72, 'width_mm': 24, 'height_mm': 10, 'boss_height_mm': 4}
REQ = {'assembly': {'envelope_z_mm': 15, 'min_clearance_mm': .5},
       'variants': {'widths_mm': [24, 32, 40], 'hole_y_width_ratio': .2},
       'analysis': {'force_N_global': [0, 0, -100], 'frame': 'CAD global XYZ; X length, Y width, Z thickness; clamp X=0, traction X=length', 'max_displacement_mm': .25}}
SCENES = [('normal', '正常交付', 'all'), ('clearance', '装配接口越界', 'assembly'),
          ('variant', '默认正确、变型失效', 'variants'), ('stale-mesh', '旧网格沿用', 'mesh_geometry'),
          ('load-sign', '求解完成、载荷反向', 'load'), ('report', '报告数值与重算失配', 'report')]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def generate(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    normal = root / 'normal'
    normal.mkdir(exist_ok=True)
    result = run_pipeline(BASE, REQ['analysis']['force_N_global'], normal)
    write(normal / 'parameters.json', BASE)
    write(normal / 'requirements.json', REQ)
    write(normal / 'report.json', {'max_displacement_mm': result['max_displacement_mm']})
    for name, title, failure in SCENES[1:]:
        target = root / name
        shutil.copytree(normal, target, dirs_exist_ok=True)
        p = copy.deepcopy(BASE)
        if name == 'clearance':
            p['boss_height_mm'] = 8
        if name == 'variant':
            p['hole_y_override_mm'] = 4.8
        if name == 'stale-mesh':
            p['width_mm'] = 32
        if name in ('clearance', 'variant', 'stale-mesh'):
            from gongzheng.model import build
            import cadquery as cq
            if name != 'stale-mesh':
                r = run_pipeline(p, REQ['analysis']['force_N_global'], target)
                write(target / 'report.json', {'max_displacement_mm': r['max_displacement_mm']})
            else:
                cq.exporters.export(build(p), str(target / 'part.step'))
        if name == 'load-sign':
            r = run_pipeline(p, [0, 0, 100], target)
            write(target / 'report.json', {'max_displacement_mm': r['max_displacement_mm']})
        if name == 'report':
            write(target / 'report.json', {'max_displacement_mm': result['max_displacement_mm'] * .25})
        write(target / 'parameters.json', p)
    write(root / 'catalog.json', [{'id': n, 'title': t, 'description': '自行生成的合成工程示例'} for n, t, _ in SCENES])
    print('Generated', len(SCENES), 'fixtures')


def regression(root, out):
    root, out = Path(root), Path(out)
    rows = []
    for name, title, failure in SCENES:
        result = verify(root / name, out / name)
        failed = [c['id'] for c in result['checks'] if c['status'] == 'fail']
        expected = result['decision'] == ('accept' if name == 'normal' else 'reject')
        expected = expected and (not failed if name == 'normal' else failure in failed)
        rows.append({'id': name, 'title': title, 'decision': result['decision'], 'failed_checks': failed,
                     'expected_outcome': expected, 'duration_s': result['duration_s']})
        print(name, result['decision'], failed, flush=True)
    write(out / 'regression.json', {'scope': 'six designed synthetic regression fixtures, not a population estimate', 'rows': rows, 'all_expected': all(r['expected_outcome'] for r in rows)})
    if not all(r['expected_outcome'] for r in rows):
        raise AssertionError('Fixture regression failed')
