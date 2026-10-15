"""Native adapters: CadQuery/Open CASCADE, Gmsh and CalculiX; mm/N/MPa."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

import cadquery as cq
import gmsh
import meshio
import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mesh(step, output, length, size=5):
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.option.setNumber('General.NumThreads', 1)
        gmsh.model.add('gongzheng')
        gmsh.model.occ.importShapes(str(step))
        gmsh.model.occ.synchronize()
        for name, x in [('CLAMP', 0), ('LOAD', length)]:
            tags = []
            for _, tag in gmsh.model.getEntities(2):
                b = gmsh.model.getBoundingBox(2, tag)
                if abs(b[0] - x) < 1e-4 and abs(b[3] - x) < 1e-4:
                    tags.append(tag)
            if not tags:
                raise ValueError('Missing boundary: ' + name)
            g = gmsh.model.addPhysicalGroup(2, tags)
            gmsh.model.setPhysicalName(2, g, name)
        g = gmsh.model.addPhysicalGroup(3, [tag for _, tag in gmsh.model.getEntities(3)])
        gmsh.model.setPhysicalName(3, g, 'BODY')
        gmsh.option.setNumber('Mesh.MeshSizeMin', size / 2)
        gmsh.option.setNumber('Mesh.MeshSizeMax', size)
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(2)
        gmsh.model.mesh.optimize('HighOrder')
        gmsh.write(str(output))
    finally:
        gmsh.finalize()


def make_deck(mesh_path, output, force, E=70000, nu=.3):
    m = meshio.read(str(mesh_path))
    p = m.points[:, :3]
    tet = m.cells_dict['tetra10']
    tri = m.cells_dict['triangle6']
    tags = m.cell_data_dict['gmsh:physical']['triangle6']
    fixed = np.unique(tri[tags == m.field_data['CLAMP'][0]])
    load = tri[tags == m.field_data['LOAD'][0]]
    # Consistent nodal load for planar quadratic faces: zero at corners, A/3 at midsides.
    xyz = p[load[:, :3]]
    area = np.linalg.norm(np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0]), axis=1) / 2
    weights = np.zeros(len(p))
    for i in (3, 4, 5):
        np.add.at(weights, load[:, i], area / (3 * area.sum()))
    lines = ['*HEADING', 'Gongzheng Lab linear elastic demo, mm N MPa', '*NODE']
    lines += [f'{i + 1},' + ','.join(f'{v:.12g}' for v in row) for i, row in enumerate(p)]
    lines += ['*ELEMENT,TYPE=C3D10,ELSET=BODY']
    lines += [f'{i + 1},' + ','.join(str(int(v) + 1) for v in row) for i, row in enumerate(tet)]
    lines += ['*NSET,NSET=ALLN,GENERATE', f'1,{len(p)},1', '*NSET,NSET=FIX']
    lines += [','.join(str(int(v) + 1) for v in fixed[i:i + 16]) for i in range(0, len(fixed), 16)]
    lines += ['*MATERIAL,NAME=AL', '*ELASTIC', f'{E},{nu}', '*SOLID SECTION,ELSET=BODY,MATERIAL=AL', '*BOUNDARY', 'FIX,1,3', '*STEP', '*STATIC', '*CLOAD']
    for i in np.flatnonzero(weights):
        for j, value in enumerate(force):
            if value:
                lines.append(f'{i + 1},{j + 1},{weights[i] * value:.12g}')
    lines += ['*NODE PRINT,NSET=ALLN', 'U', '*NODE FILE', 'U', '*END STEP']
    Path(output).write_text('\n'.join(lines) + '\n')
    return weights


def run_solver(deck, weights):
    deck = Path(deck)
    proc = subprocess.run(['ccx', '-i', deck.stem], cwd=deck.parent,
                          capture_output=True, text=True, timeout=240)
    log = proc.stdout + '\n' + proc.stderr
    deck.with_suffix('.log').write_text(log)
    if proc.returncode or '*ERROR' in log or 'nonpositive jacobian' in log.lower():
        raise RuntimeError('CalculiX failed; inspect native log')
    text = deck.with_suffix('.dat').read_text()
    section = re.split(r'displacements\s*\(vx,vy,vz\)', text, flags=re.I)[-1]
    rows = {}
    for line in section.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0].isdigit():
            rows[int(parts[0]) - 1] = [float(v.replace('D', 'E')) for v in parts[1:]]
    if len(rows) != len(weights):
        raise RuntimeError('Incomplete native displacement table')
    u = np.array([rows[i] for i in range(len(weights))])
    if not np.isfinite(u).all():
        raise RuntimeError('Nonfinite displacement')
    return {'tip_mean_mm': (weights @ u).tolist(), 'max_displacement_mm': float(np.linalg.norm(u, axis=1).max()), 'nodes': len(u)}, u


def deck_force(path):
    force = np.zeros(3)
    active = False
    for line in Path(path).read_text().splitlines():
        if line.startswith('*'):
            active = line.upper().startswith('*CLOAD')
        elif active and line.strip():
            parts = line.split(',')
            force[int(parts[1]) - 1] += float(parts[2])
    return force.tolist()


def deck_signature(path):
    """Normalize the supported adapter deck; extra/unsupported cards fail closed.

    This is intentionally not a general CalculiX input interpreter. Comments,
    whitespace, numeric spelling and keyword option order do not affect it.
    """
    blocks = []
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('**'):
            continue
        if line.startswith('*'):
            key = [s.strip().upper() for s in line.split(',')]
            blocks.append([tuple([key[0]] + sorted(key[1:])), []])
        elif blocks and blocks[-1][0][0] != '*HEADING':
            tokens = []
            for token in line.split(','):
                token = token.strip().upper()
                try:
                    token = format(float(token.replace('D', 'E')), '.9g')
                except ValueError:
                    pass
                tokens.append(token)
            blocks[-1][1].append(tuple(tokens))
    return [(key, sorted(rows)) for key, rows in blocks]


def shape_data(shape):
    v, f = shape.tessellate(.35, .3)
    b = shape.BoundingBox()
    return {'points': [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in v],
            'triangles': f, 'volume_mm3': shape.Volume(),
            'bbox_mm': [b.xmin, b.ymin, b.zmin, b.xmax, b.ymax, b.zmax]}


def run_pipeline(p, force, out, size=5):
    from gongzheng.model import build
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    s = build(p)
    cq.exporters.export(s, str(out / 'part.step'))
    reopened = cq.importers.importStep(str(out / 'part.step')).val()
    if not reopened.isValid():
        raise ValueError('STEP reopen invalid')
    mesh(out / 'part.step', out / 'mesh.msh', p['length_mm'], size)
    w = make_deck(out / 'mesh.msh', out / 'analysis.inp', force)
    result, u = run_solver(out / 'analysis.inp', w)
    result['mesh_sha256'] = digest(out / 'mesh.msh')
    result['deck_sha256'] = digest(out / 'analysis.inp')
    (out / 'result.json').write_text(json.dumps(result, indent=2))
    display = shape_data(reopened)
    m = meshio.read(str(out / 'mesh.msh'))
    display['fea'] = {'points': np.round(m.points[:, :3], 6).tolist(), 'u': np.round(u, 9).tolist(),
                      'triangles': m.cells_dict['triangle6'][:, :3].tolist()}
    (out / 'view.json').write_text(json.dumps(display, separators=(',', ':')))
    return result
