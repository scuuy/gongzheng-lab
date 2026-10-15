"""Trusted example adapter. Submitted project data is JSON, never executable code."""
import cadquery as cq


def build(p):
    length, width, height = (float(p[k]) for k in ('length_mm', 'width_mm', 'height_mm'))
    if not (40 <= length <= 120 and 16 <= width <= 48 and 6 <= height <= 20):
        raise ValueError('Geometry outside supported demonstration range')
    y = float(p.get('hole_y_override_mm', .2 * width))
    if abs(y) + 3 >= width / 2:
        raise ValueError('Hole intersects outside edge')
    body = cq.Workplane('XY').box(length, width, height, centered=(False, True, False))
    hole = cq.Workplane('XY').center(.7 * length, y).circle(3).extrude(height)
    body = body.cut(hole)
    boss = float(p.get('boss_height_mm', 4))
    if not 0 <= boss <= 12:
        raise ValueError('Unsupported interface height')
    if boss:
        stud = cq.Workplane('XY').center(.82 * length, -width / 4).circle(3).extrude(boss).translate((0, 0, height))
        body = body.union(stud)
    return body.val()
