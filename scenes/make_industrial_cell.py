"""
make_industrial_cell.py
====================================================================
Parametric generator for a Sionna RT INDUSTRIAL cell (Mitsuba 3 XML).

New project direction (2026-07-21): device-free worker PRESENCE +
COARSE COUNT + COARSE ZONE in an occluded industrial hazard cell,
from static CSI snapshots.  This scene is the static environment for
that task (Stage 2 direction).  The old domestic 5x5 room lives in
stage1/scenes/make_indoor_scene.py.

NOTE (2026-07-21): This is the FIRST generic industrial-cell design.
It was superseded by scene_builder.ipynb (the robot-cell scene), but
is KEPT as a foundation / fallback -- do not delete.

What this emits (self-contained, no mesh dir):
  industrial_cell/industrial_cell_occluded.xml
        full cell  -- central machine present (occludes hazard zone)
  industrial_cell/industrial_cell_los.xml
        same cell  -- central machine REMOVED (line-of-sight control)
  industrial_cell/industrial_cell.json
        sidecar: room dims, materials, objects, HAZARD ZONE,
        worker-placement region, suggested TX / AP positions.

Run:  python make_industrial_cell.py
====================================================================
"""

import json
from pathlib import Path

# --------------------------------------------------------------------
# Scene parameters  (metres; +z up, floor surface z=0, bay centred at
# the origin so x in [-X/2, X/2], y in [-Y/2, Y/2])
# --------------------------------------------------------------------

SCENE_NAME = "industrial_cell"

# Machine bay interior (clear inner space)
ROOM_X, ROOM_Y, ROOM_Z = 10.0, 7.0, 4.0
WALL_T = 0.15                 # wall / floor / ceiling thickness (industrial)

# Sionna maps these "type" strings to ITU radio materials.
# Valid: concrete, brick, plasterboard, wood, glass, metal,
#        ceiling_board, floorboard, very_dry_ground, ...
MAT_WALL    = "concrete"      # floor + 4 walls
MAT_CEILING = "metal"         # metal roof deck (industrial)
MAT_MACHINE = "metal"
MAT_CABINET = "metal"
MAT_RACKING = "metal"

# --------------------------------------------------------------------
# Objects.  Each: name, (size_x, size_y, size_z), (cx, cy, cz), material,
#                 removable_for_LOS
# --------------------------------------------------------------------

# Central machine = base + tower (built tall so it truly occludes).
MACHINE = [
    ("Machine_base",  (1.2, 1.2, 1.0), ( 0.0,  0.0, 0.50), MAT_MACHINE, True),
    ("Machine_tower", (0.5, 0.5, 1.3), ( 0.0,  0.0, 1.65), MAT_MACHINE, True),
]

# Surrounding equipment (kept in BOTH variants).
EQUIPMENT = [
    # Control cabinet against the east wall.
    ("Cabinet", (0.8, 1.5, 2.0), ( 4.45, -1.50, 1.00), MAT_CABINET, False),
    # Tall storage racking against the north wall.
    ("Racking", (2.5, 0.6, 2.5), (-2.50,  3.05, 1.25), MAT_RACKING, False),
]

OBJECTS = MACHINE + EQUIPMENT

# --------------------------------------------------------------------
# Hazard zone (labelling region -- a floor rectangle around the machine)
# --------------------------------------------------------------------

HAZARD_ZONE = {          # a worker footprint inside this square -> "in zone"
    "type": "rect",
    "x_min": -1.5, "x_max": 1.5,
    "y_min": -1.5, "y_max": 1.5,
}

# Worker placement region: floor inset from the walls, minus object
# footprints (+ clearance).
WORKER_INSET = 0.5       # keep workers this far off the walls
OBJ_CLEARANCE = 0.3      # keep workers this far from object footprints

# --------------------------------------------------------------------
# Suggested TX / AP layout (written to sidecar; not into the XML).
# --------------------------------------------------------------------

TX_HEIGHT = 2.8
SUGGESTED_TX = [
    ("iot_0", (-4.5, -3.0, TX_HEIGHT)),
    ("iot_1", ( 4.5, -3.0, TX_HEIGHT)),
    ("iot_2", (-4.5,  3.0, TX_HEIGHT)),
    ("iot_3", ( 4.5,  3.0, TX_HEIGHT)),
]
SUGGESTED_AP = {
    "pos": (-4.85, 0.0, 2.5),   # west wall, mid-height
    "n_ant": 4,                 # M=4 antenna array at this point
}


# --------------------------------------------------------------------
# Room shell (6 solid slabs; ceiling can differ in material)
# --------------------------------------------------------------------

def _room_boxes():
    hx, hy, hz = ROOM_X / 2, ROOM_Y / 2, ROOM_Z / 2
    t = WALL_T
    return [
        ("Floor",   (ROOM_X, ROOM_Y, t), (0.0, 0.0, -t / 2),            MAT_WALL),
        ("Ceiling", (ROOM_X, ROOM_Y, t), (0.0, 0.0, ROOM_Z + t / 2),    MAT_CEILING),
        ("Wall_N",  (ROOM_X, t, ROOM_Z), (0.0,  hy + t / 2, hz),        MAT_WALL),
        ("Wall_S",  (ROOM_X, t, ROOM_Z), (0.0, -hy - t / 2, hz),        MAT_WALL),
        ("Wall_E",  (t, ROOM_Y, ROOM_Z), ( hx + t / 2, 0.0, hz),        MAT_WALL),
        ("Wall_W",  (t, ROOM_Y, ROOM_Z), (-hx - t / 2, 0.0, hz),        MAT_WALL),
    ]


# --------------------------------------------------------------------
# XML emission
# --------------------------------------------------------------------

def _bsdf_xml(mat_type):
    return (
        f'    <bsdf type="itu-radio-material" id="mat-{mat_type}">\n'
        f'        <string name="type" value="{mat_type}"/>\n'
        f'    </bsdf>\n'
    )


def _cube_xml(name, size, center, mat_type):
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    cx, cy, cz = center
    return (
        f'    <shape type="cube" id="{name}">\n'
        f'        <transform name="to_world">\n'
        f'            <scale x="{hx:.4f}" y="{hy:.4f}" z="{hz:.4f}"/>\n'
        f'            <translate x="{cx:.4f}" y="{cy:.4f}" z="{cz:.4f}"/>\n'
        f'        </transform>\n'
        f'        <ref id="mat-{mat_type}"/>\n'
        f'    </shape>\n'
    )


def build_scene_xml(include_occluder):
    boxes = [(n, s, c, m) for (n, s, c, m) in _room_boxes()]
    for (n, s, c, m, removable) in OBJECTS:
        if removable and not include_occluder:
            continue
        boxes.append((n, s, c, m))

    used_materials = sorted({mat for (_, _, _, mat) in boxes})

    parts = ['<scene version="3.0.0">\n']
    parts.append('    <integrator type="path"/>\n\n')
    for mat in used_materials:
        parts.append(_bsdf_xml(mat))
    parts.append('\n')
    for (name, size, center, mat) in boxes:
        parts.append(_cube_xml(name, size, center, mat))
    parts.append('</scene>\n')
    return "".join(parts)


# --------------------------------------------------------------------
# Sidecar (geometry contract for the data-generation script)
# --------------------------------------------------------------------

def _footprint(size, center, clearance):
    hx, hy = size[0] / 2 + clearance, size[1] / 2 + clearance
    cx, cy = center[0], center[1]
    return {"x_min": cx - hx, "x_max": cx + hx,
            "y_min": cy - hy, "y_max": cy + hy}


def build_sidecar():
    exclusions = [
        {"name": n, **_footprint(s, c, OBJ_CLEARANCE)}
        for (n, s, c, m, _removable) in OBJECTS
    ]
    return {
        "scene_name": SCENE_NAME,
        "units": "metres; +z up; floor z=0; bay centred at origin",
        "room": {"x": ROOM_X, "y": ROOM_Y, "z": ROOM_Z, "wall_t": WALL_T},
        "materials": {
            "wall": MAT_WALL, "ceiling": MAT_CEILING,
            "machine": MAT_MACHINE, "cabinet": MAT_CABINET,
            "racking": MAT_RACKING,
        },
        "objects": [
            {"name": n, "size": list(s), "center": list(c),
             "material": m, "removable_for_los": removable}
            for (n, s, c, m, removable) in OBJECTS
        ],
        "occluder_objects": [n for (n, _, _, _, r) in OBJECTS if r],
        "hazard_zone": HAZARD_ZONE,
        "worker_region": {
            "type": "rect_with_exclusions",
            "x_min": -ROOM_X / 2 + WORKER_INSET,
            "x_max":  ROOM_X / 2 - WORKER_INSET,
            "y_min": -ROOM_Y / 2 + WORKER_INSET,
            "y_max":  ROOM_Y / 2 - WORKER_INSET,
            "exclusions": exclusions,
        },
        "suggested_tx": [
            {"name": n, "pos": list(p)} for (n, p) in SUGGESTED_TX
        ],
        "suggested_ap": {"pos": list(SUGGESTED_AP["pos"]),
                         "n_ant": SUGGESTED_AP["n_ant"]},
        "variants": {
            "occluded": f"{SCENE_NAME}_occluded.xml",
            "los": f"{SCENE_NAME}_los.xml",
        },
    }


# --------------------------------------------------------------------

def main():
    out_dir = Path(__file__).parent / SCENE_NAME
    out_dir.mkdir(parents=True, exist_ok=True)

    occ_path = out_dir / f"{SCENE_NAME}_occluded.xml"
    los_path = out_dir / f"{SCENE_NAME}_los.xml"
    json_path = out_dir / f"{SCENE_NAME}.json"

    occ_path.write_text(build_scene_xml(include_occluder=True), encoding="utf-8")
    los_path.write_text(build_scene_xml(include_occluder=False), encoding="utf-8")
    json_path.write_text(json.dumps(build_sidecar(), indent=2), encoding="utf-8")

    n_equip = len(EQUIPMENT)
    n_machine = len(MACHINE)
    print(f"Wrote {occ_path}")
    print(f"Wrote {los_path}")
    print(f"Wrote {json_path}")
    print(f"  bay interior : {ROOM_X} x {ROOM_Y} x {ROOM_Z} m")
    print(f"  shell        : 6 slabs ({MAT_WALL} walls/floor, {MAT_CEILING} ceiling)")
    print(f"  occluded xml : 6 shell + {n_machine} machine + {n_equip} equipment")
    print(f"  los xml      : 6 shell + {n_equip} equipment (machine removed)")


if __name__ == "__main__":
    main()
