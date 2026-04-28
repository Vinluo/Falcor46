"""
Convert a Mitsuba 3 scene XML into a Falcor .pyscene file.

Designed for the breakfast/dining-room scene shipped under
neural-irradiance-volume/scenes/dining-room/, which uses:
  * <bsdf type="twosided"> wrapping diffuse / roughplastic / roughconductor
  * <shape type="obj"> with relative file references and a per-shape transform
  * <emitter type="envmap"> referencing a .exr
  * <sensor type="perspective"> with a 4x4 to_world matrix and FOV

The converter is intentionally narrow: it only maps what dining-room actually
uses. Anything outside that surface emits a warning and is dropped, NOT silently
mapped to a default. Run once, commit the .pyscene + copied OBJs/textures.

Usage:
    python scripts/mitsuba_to_pyscene.py \\
        --in  neural-irradiance-volume/scenes/dining-room/dining-room/scene_v3.xml \\
        --out media/niv_scenes/dining_room.pyscene
"""

from __future__ import annotations

import argparse
import math
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _attr(elem, name, default=None):
    v = elem.attrib.get(name, default)
    return v


def _parse_rgb(text: str):
    parts = [p for p in text.replace(",", " ").split() if p]
    if len(parts) == 1:
        v = float(parts[0])
        return (v, v, v)
    if len(parts) == 3:
        return tuple(float(p) for p in parts)
    raise ValueError(f"unexpected rgb spec: {text!r}")


def _find_inner_bsdf(bsdf_elem):
    """If bsdf is twosided, return its inner bsdf; otherwise return as-is."""
    if _attr(bsdf_elem, "type") == "twosided":
        for child in bsdf_elem:
            if child.tag == "bsdf":
                return child
    return bsdf_elem


def _find_named(parent, tag, name):
    for child in parent:
        if child.tag == tag and child.attrib.get("name") == name:
            return child
    return None


def _parse_matrix4(elem):
    m = _find_named(elem, "matrix", None)
    if m is None:
        for child in elem:
            if child.tag == "matrix":
                m = child
                break
    if m is None:
        return None
    parts = [float(p) for p in _attr(m, "value").replace(",", " ").split()]
    if len(parts) != 16:
        raise ValueError(f"matrix value should have 16 floats, got {len(parts)}")
    # Mitsuba stores row-major.
    return [parts[i:i+4] for i in range(0, 16, 4)]


def _parse_transform(transform_elem):
    """Returns (matrix4_or_None, rotate_y_deg_or_None)."""
    if transform_elem is None:
        return None, None
    m = _parse_matrix4(transform_elem)
    rot = None
    for child in transform_elem:
        if child.tag == "rotate":
            axis_y = float(_attr(child, "y", "0"))
            angle = float(_attr(child, "angle", "0"))
            if abs(axis_y - 1.0) < 1e-6:
                rot = angle
    return m, rot


def _decompose_trs(M, eps: float = 1e-4):
    """
    Decompose a row-major 4x4 transform M into (translation, rotationEulerDeg, scaling).
    Returns None if the matrix has shear or non-axis-aligned scaling that we can't
    cleanly express via Transform(). Caller should fall back (skip / pre-bake).
    """
    # Identity? Caller already checks; return zero everything.
    tx, ty, tz = M[0][3], M[1][3], M[2][3]

    # Extract 3x3 linear part column-by-column.
    cols = [
        [M[0][0], M[1][0], M[2][0]],  # X column
        [M[0][1], M[1][1], M[2][1]],  # Y column
        [M[0][2], M[1][2], M[2][2]],  # Z column
    ]
    sx = math.sqrt(sum(c * c for c in cols[0]))
    sy = math.sqrt(sum(c * c for c in cols[1]))
    sz = math.sqrt(sum(c * c for c in cols[2]))

    if sx < eps or sy < eps or sz < eps:
        return None  # degenerate

    # Normalized rotation columns.
    rx = [c / sx for c in cols[0]]
    ry = [c / sy for c in cols[1]]
    rz = [c / sz for c in cols[2]]

    # Determinant negative → reflection; encode as a flipped scale on X.
    det = (
        rx[0] * (ry[1] * rz[2] - ry[2] * rz[1])
        - rx[1] * (ry[0] * rz[2] - ry[2] * rz[0])
        + rx[2] * (ry[0] * rz[1] - ry[1] * rz[0])
    )
    flip = 1.0
    if det < 0:
        flip = -1.0
        rx = [-v for v in rx]
        sx = -sx

    # Verify orthogonality of rotation columns.
    def dot(a, b):
        return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
    if (abs(dot(rx, ry)) > eps or abs(dot(rx, rz)) > eps or abs(dot(ry, rz)) > eps):
        return None  # shear present

    # Extract Euler ZYX angles from rotation matrix
    #   R = [rx | ry | rz]
    # Using Falcor's setRotationEulerDeg ordering (XYZ intrinsic). We pull yaw/pitch/roll
    # using the standard formulas:
    #   pitch = asin(-R[2][0])
    #   yaw   = atan2(R[1][0], R[0][0])  (when cos(pitch) != 0)
    #   roll  = atan2(R[2][1], R[2][2])
    R = [
        [rx[0], ry[0], rz[0]],
        [rx[1], ry[1], rz[1]],
        [rx[2], ry[2], rz[2]],
    ]
    pitch = math.asin(max(-1.0, min(1.0, -R[2][0])))
    cos_p = math.cos(pitch)
    if abs(cos_p) > 1e-6:
        yaw = math.atan2(R[1][0], R[0][0])
        roll = math.atan2(R[2][1], R[2][2])
    else:
        # Gimbal lock — fall back, keep yaw=0.
        yaw = 0.0
        roll = math.atan2(-R[1][2], R[1][1])

    return (
        (tx, ty, tz),
        (math.degrees(roll), math.degrees(yaw), math.degrees(pitch)),
        (sx, sy, sz),
    )


# ---------------------------------------------------------------------------
# BSDF → Falcor StandardMaterial spec
# ---------------------------------------------------------------------------

def _texture_filename(elem):
    """If `elem` has a child texture, return its bitmap filename; else None."""
    tex = _find_named(elem, "texture", "reflectance") or _find_named(elem, "texture", "diffuse_reflectance")
    if tex is None:
        return None
    fn = _find_named(tex, "string", "filename")
    if fn is None:
        return None
    return _attr(fn, "value")


def _bsdf_to_material_spec(bsdf_elem, mat_id):
    """Return a dict describing how to build a Falcor StandardMaterial."""
    inner = _find_inner_bsdf(bsdf_elem)
    btype = _attr(inner, "type")
    spec = {
        "id": mat_id,
        "shading_model": "MetalRough",
        "base_color": (1.0, 1.0, 1.0, 1.0),
        "roughness": 1.0,
        "metallic": 0.0,
        "ior": 1.5,
        "double_sided": (_attr(bsdf_elem, "type") == "twosided"),
        "base_color_texture": None,
    }

    if btype == "diffuse":
        rgb = _find_named(inner, "rgb", "reflectance")
        if rgb is not None:
            r, g, b = _parse_rgb(_attr(rgb, "value"))
            spec["base_color"] = (r, g, b, 1.0)
        spec["base_color_texture"] = _texture_filename(inner)
        spec["roughness"] = 1.0
        spec["metallic"] = 0.0
    elif btype == "roughplastic":
        rgb = _find_named(inner, "rgb", "diffuse_reflectance")
        if rgb is not None:
            r, g, b = _parse_rgb(_attr(rgb, "value"))
            spec["base_color"] = (r, g, b, 1.0)
        spec["base_color_texture"] = _texture_filename(inner)
        alpha_elem = _find_named(inner, "float", "alpha")
        alpha = float(_attr(alpha_elem, "value")) if alpha_elem is not None else 0.1
        # roughness is sqrt(alpha) for GGX-ish shading models; clamp.
        spec["roughness"] = max(0.04, min(1.0, math.sqrt(alpha)))
        spec["metallic"] = 0.0
        ior_elem = _find_named(inner, "float", "int_ior")
        if ior_elem is not None:
            spec["ior"] = float(_attr(ior_elem, "value"))
    elif btype == "roughconductor":
        # Approximate conductor as fully metallic with grayscale base color.
        rgb = _find_named(inner, "rgb", "specular_reflectance")
        if rgb is not None:
            r, g, b = _parse_rgb(_attr(rgb, "value"))
            spec["base_color"] = (r, g, b, 1.0)
        else:
            spec["base_color"] = (0.95, 0.95, 0.95, 1.0)
        alpha_elem = _find_named(inner, "float", "alpha")
        alpha = float(_attr(alpha_elem, "value")) if alpha_elem is not None else 0.1
        spec["roughness"] = max(0.04, min(1.0, math.sqrt(alpha)))
        spec["metallic"] = 1.0
    else:
        sys.stderr.write(f"WARN: unsupported BSDF type '{btype}' for id='{mat_id}'; using neutral diffuse\n")

    return spec


# ---------------------------------------------------------------------------
# Camera matrix → Falcor Camera (position/target/up)
# ---------------------------------------------------------------------------

def _camera_from_matrix(M, fov_deg):
    """
    Mitsuba 3 perspective sensor: camera local frame uses +Z forward.
    The 4x4 to_world matrix is row-major; columns are (right, up, forward, position).
    """
    pos = (M[0][3], M[1][3], M[2][3])
    forward = (M[0][2], M[1][2], M[2][2])
    up = (M[0][1], M[1][1], M[2][1])
    target = (pos[0] + forward[0], pos[1] + forward[1], pos[2] + forward[2])
    return pos, target, up, fov_deg


# ---------------------------------------------------------------------------
# Asset copy
# ---------------------------------------------------------------------------

def _copy_asset(rel: str, src_root: Path, dst_root: Path, copied: set) -> str:
    rel = rel.replace("\\", "/")
    if rel in copied:
        return rel
    src = src_root / rel
    dst = dst_root / rel
    if not src.exists():
        sys.stderr.write(f"WARN: asset not found, skipping copy: {src}\n")
        return rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied.add(rel)
    return rel


# ---------------------------------------------------------------------------
# Pyscene emission
# ---------------------------------------------------------------------------

def _emit_pyscene(materials, shapes, camera, envmap, out_path: Path, rectangles=None) -> None:
    rectangles = rectangles or []
    L = []
    L.append("# Auto-generated by scripts/mitsuba_to_pyscene.py — do not hand-edit.")
    L.append("# Source: neural-irradiance-volume/scenes/dining-room/dining-room/scene_v3.xml")
    L.append("")
    L.append("# ----- Materials -----")
    for s in materials:
        var = f"mat_{s['id']}"
        L.append(f"{var} = StandardMaterial({s['id']!r}, ShadingModel.MetalRough)")
        L.append(f"{var}.baseColor = float4{s['base_color']}")
        L.append(f"{var}.roughness = {s['roughness']:.4f}")
        L.append(f"{var}.metallic = {s['metallic']:.4f}")
        L.append(f"{var}.indexOfRefraction = {s['ior']:.4f}")
        L.append(f"{var}.doubleSided = {bool(s['double_sided'])}")
        if s.get("base_color_texture"):
            L.append(f"{var}.loadTexture(MaterialTextureSlot.BaseColor, {s['base_color_texture']!r})")
        L.append("")

    L.append("# ----- Synthesized quads (Mitsuba rectangle shapes) -----")
    L.append(f"# {len(rectangles)} rectangle(s) suppressed via SKIP_RECTANGLES=True until manual mesh construction is verified.")
    L.append("SKIP_RECTANGLES = True")
    L.append("if not SKIP_RECTANGLES:")
    indent = "    "
    for rq in rectangles:
        c = rq["corners"]
        n = rq["normal"]
        var = "_rmesh"
        L.append(f"{indent}{var} = TriangleMesh()")
        for ci, corner in enumerate(c):
            uv = ["(0.0, 0.0)", "(1.0, 0.0)", "(1.0, 1.0)", "(0.0, 1.0)"][ci]
            L.append(
                f"{indent}{var}.addVertex(float3({corner[0]:.6f}, {corner[1]:.6f}, {corner[2]:.6f}), "
                f"float3({n[0]:.6f}, {n[1]:.6f}, {n[2]:.6f}), float2{uv})"
            )
        L.append(f"{indent}{var}.addTriangle(0, 1, 2)")
        L.append(f"{indent}{var}.addTriangle(0, 2, 3)")
        L.append(f"{indent}_mid = sceneBuilder.addTriangleMesh({var}, mat_{rq['material']})")
        L.append(f"{indent}_node = sceneBuilder.addNode({rq['id']!r}, Transform())")
        L.append(f"{indent}sceneBuilder.addMeshInstance(_node, _mid)")
        L.append("")

    L.append("# ----- Meshes -----")
    for sh in shapes:
        L.append(
            f"_mesh = TriangleMesh.createFromFile({sh['file']!r})"
        )
        L.append(f"_mid = sceneBuilder.addTriangleMesh(_mesh, mat_{sh['material']})")
        if sh.get("trs") is not None:
            t, r, s = sh["trs"]
            L.append("_xform = Transform()")
            L.append(f"_xform.translation = float3({t[0]:.6f}, {t[1]:.6f}, {t[2]:.6f})")
            L.append(f"_xform.rotationEulerDeg = float3({r[0]:.6f}, {r[1]:.6f}, {r[2]:.6f})")
            L.append(f"_xform.scaling = float3({s[0]:.6f}, {s[1]:.6f}, {s[2]:.6f})")
            L.append(f"_node = sceneBuilder.addNode({sh['id']!r}, _xform)")
        else:
            L.append(f"_node = sceneBuilder.addNode({sh['id']!r}, Transform())")
        L.append("sceneBuilder.addMeshInstance(_node, _mid)")
        L.append("")

    L.append("# ----- Camera -----")
    if camera is not None:
        pos, tgt, up, fov = camera
        L.append("camera = Camera()")
        L.append(f"camera.position = float3({pos[0]:.6f}, {pos[1]:.6f}, {pos[2]:.6f})")
        L.append(f"camera.target = float3({tgt[0]:.6f}, {tgt[1]:.6f}, {tgt[2]:.6f})")
        L.append(f"camera.up = float3({up[0]:.6f}, {up[1]:.6f}, {up[2]:.6f})")
        L.append(f"camera.focalLength = {35.0 / math.tan(math.radians(fov) * 0.5) * 0.5:.4f}")
        L.append("sceneBuilder.addCamera(camera)")
        L.append("")
    else:
        L.append("# (no camera in source XML)")
        L.append("")

    L.append("# ----- Environment map -----")
    if envmap is not None:
        path, rot_y = envmap
        L.append(f"sceneBuilder.envMap = EnvMap.createFromFile({path!r})")
        if rot_y is not None:
            L.append(f"sceneBuilder.envMap.rotation = float3(0.0, {rot_y:.4f}, 0.0)")
        L.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def convert(xml_path: Path, out_path: Path) -> None:
    src_root = xml_path.parent
    # Keep .pyscene next to its assets so relative paths inside the script resolve naturally.
    dst_root = out_path.parent
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[mitsuba->pyscene] xml: {xml_path}")
    print(f"[mitsuba->pyscene] dst pyscene: {out_path}")
    print(f"[mitsuba->pyscene] dst assets:  {dst_root}/")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # --- BSDFs at scene scope ---
    materials = {}
    for bsdf_elem in root.findall("bsdf"):
        bid = _attr(bsdf_elem, "id")
        if bid is None:
            continue
        materials[bid] = _bsdf_to_material_spec(bsdf_elem, bid)

    # --- Sensor (camera) ---
    camera = None
    sensor = root.find("sensor")
    if sensor is not None:
        fov_elem = _find_named(sensor, "float", "fov")
        fov = float(_attr(fov_elem, "value")) if fov_elem is not None else 60.0
        transform_elem = _find_named(sensor, "transform", "to_world")
        M, _ = _parse_transform(transform_elem)
        if M is not None:
            camera = _camera_from_matrix(M, fov)

    # --- Shapes ---
    copied = set()
    shapes = []
    rectangles = []
    for shape_elem in root.findall("shape"):
        stype = _attr(shape_elem, "type")
        if stype == "rectangle":
            sid = _attr(shape_elem, "id") or f"rect_{len(rectangles)}"
            transform_elem = _find_named(shape_elem, "transform", "to_world")
            M, _ = _parse_transform(transform_elem) if transform_elem is not None else (None, None)
            if M is None:
                M = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
            ref_elem = next((c for c in shape_elem if c.tag == "ref"), None)
            mat_id = _attr(ref_elem, "id") if ref_elem is not None else None
            # Mitsuba rectangle is the unit square in xy-plane (z=0), normal +z, vertices at (+/-1,+/-1,0).
            corners = []
            for (lx, ly) in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
                wx = M[0][0]*lx + M[0][1]*ly + M[0][3]
                wy = M[1][0]*lx + M[1][1]*ly + M[1][3]
                wz = M[2][0]*lx + M[2][1]*ly + M[2][3]
                corners.append((wx, wy, wz))
            # Normal = transformed local +z axis (column 2 of rotation part).
            nx, ny, nz = M[0][2], M[1][2], M[2][2]
            length = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
            normal = (nx/length, ny/length, nz/length)
            rectangles.append({"id": sid, "corners": corners, "normal": normal, "material": mat_id})
            continue
        if stype != "obj":
            sys.stderr.write(f"WARN: skipping unsupported shape type='{stype}'\n")
            continue
        sid = _attr(shape_elem, "id") or f"shape_{len(shapes)}"
        fn_elem = _find_named(shape_elem, "string", "filename")
        if fn_elem is None:
            sys.stderr.write(f"WARN: shape {sid} has no filename, skipping\n")
            continue
        rel = _copy_asset(_attr(fn_elem, "value"), src_root, dst_root, copied)

        ref_elem = next((c for c in shape_elem if c.tag == "ref"), None)
        mat_id = _attr(ref_elem, "id") if ref_elem is not None else None
        if mat_id is None or mat_id not in materials:
            sys.stderr.write(f"WARN: shape {sid} has no/unknown material ref; using NoneBSDF\n")
            mat_id = "NoneBSDF" if "NoneBSDF" in materials else next(iter(materials), None)

        # Transform: try to decompose into Falcor's Transform TRS form.
        trs = None
        transform_elem = _find_named(shape_elem, "transform", "to_world")
        if transform_elem is not None:
            M, _ = _parse_transform(transform_elem)
            if M is not None:
                identity = [
                    [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]
                ]
                non_identity = any(
                    abs(M[r][c] - identity[r][c]) > 1e-6
                    for r in range(4) for c in range(4)
                )
                if non_identity:
                    trs = _decompose_trs(M)
                    if trs is None:
                        sys.stderr.write(
                            f"WARN: shape {sid} has a non-decomposable transform (shear/skew); using identity.\n"
                        )

        shapes.append({"id": sid, "file": rel.replace("\\", "/"), "material": mat_id, "trs": trs})

    # Copy textures referenced by materials too.
    for s in materials.values():
        if s.get("base_color_texture"):
            s["base_color_texture"] = _copy_asset(s["base_color_texture"], src_root, dst_root, copied)

    # --- Emitter ---
    envmap = None
    for emitter_elem in root.findall("emitter"):
        if _attr(emitter_elem, "type") == "envmap":
            fn_elem = _find_named(emitter_elem, "string", "filename")
            if fn_elem is not None:
                rel = _copy_asset(_attr(fn_elem, "value"), src_root, dst_root, copied)
                _, rot_y = _parse_transform(_find_named(emitter_elem, "transform", "to_world"))
                envmap = (rel.replace("\\", "/"), rot_y)
        else:
            sys.stderr.write(f"WARN: skipping emitter type='{_attr(emitter_elem, 'type')}'\n")

    # Order materials so referenced ones come first; dedupe.
    used_mat_ids = {sh["material"] for sh in shapes if sh["material"] is not None}
    used_mat_ids |= {rq["material"] for rq in rectangles if rq["material"] is not None}
    ordered_materials = [materials[m] for m in materials if m in used_mat_ids]

    _emit_pyscene(ordered_materials, shapes, camera, envmap, out_path, rectangles)

    print(f"[mitsuba->pyscene] materials: {len(ordered_materials)}")
    print(f"[mitsuba->pyscene] shapes:    {len(shapes)} obj + {len(rectangles)} rect-synth")
    print(f"[mitsuba->pyscene] envmap:    {'yes' if envmap else 'no'}")
    print(f"[mitsuba->pyscene] camera:    {'yes' if camera else 'no'}")
    print(f"[mitsuba->pyscene] copied {len(copied)} assets into {dst_root}/")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    default_in = repo_root / "neural-irradiance-volume" / "scenes" / "dining-room" / "dining-room" / "scene_v3.xml"
    default_out = repo_root / "media" / "niv_scenes" / "dining_room" / "dining_room.pyscene"

    p = argparse.ArgumentParser(description="Convert Mitsuba 3 XML scene to Falcor pyscene.")
    p.add_argument("--in", dest="in_path", type=Path, default=default_in)
    p.add_argument("--out", dest="out_path", type=Path, default=default_out)
    args = p.parse_args()

    if not args.in_path.exists():
        sys.stderr.write(f"input not found: {args.in_path}\n")
        sys.exit(1)

    convert(args.in_path, args.out_path)


if __name__ == "__main__":
    main()
