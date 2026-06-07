#!/usr/bin/env python3
"""Step 10 Blender automation: sort c_arms SMD files."""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import shutil
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHT_THRESHOLD = 0.12
MAX_PREVIEW_TRIANGLES = 500000
HELPER_MESH_NAMES = {"smd_bone_vis"}
EXCLUDED_IMPORT_NAMES = {"physics.smd"}
FOREARM_ROOTS = {"ValveBiped.Bip01_R_Forearm", "ValveBiped.Bip01_L_Forearm"}


def log(message: str) -> None:
    print(f"[Step10 CArms] {message}", flush=True)


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_object_mode() -> None:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def set_active_only(obj: bpy.types.Object) -> None:
    ensure_object_mode()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def prepare_output_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in list(path.iterdir()):
        if child.name == "blender_sort_carms.log":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def clear_startup_scene() -> None:
    ensure_object_mode()
    for obj in list(bpy.context.scene.objects):
        obj.select_set(True)
    bpy.ops.object.delete()


def enable_source_tools() -> bool:
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_valvesource")
    except Exception:
        blender_root = Path(bpy.app.binary_path).resolve().parent
        addon_dirs = [blender_root / "4.5" / "scripts" / "addons"]
        user_addon_dir = bpy.utils.user_resource("SCRIPTS", path="addons", create=False)
        if user_addon_dir:
            addon_dirs.append(Path(user_addon_dir))
        for addon_dir in addon_dirs:
            if addon_dir.exists() and str(addon_dir) not in sys.path:
                sys.path.insert(0, str(addon_dir))
        try:
            import io_scene_valvesource  # type: ignore

            io_scene_valvesource.register()
        except Exception as exc:
            log(f"Blender Source Tools could not be enabled: {exc}")
            return False
    try:
        bpy.ops.import_scene.smd.get_rna_type()
        bpy.ops.export_scene.smd.get_rna_type()
    except Exception as exc:
        log(f"Blender Source Tools operators are unavailable: {exc}")
        return False
    return True


def source_tools_state_update() -> None:
    try:
        from io_scene_valvesource.utils import State  # type: ignore

        State.update_scene(bpy.context.scene)
    except Exception as exc:
        log(f"Source Tools export list refresh warning: {exc}")


def v3(value: Vector) -> list[float]:
    return [round(float(value.x), 6), round(float(value.y), 6), round(float(value.z), 6)]


def natural_key(value: object) -> list[object]:
    import re

    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(value))]


def safe_fragment(value: str) -> str:
    import re

    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_").lower()
    return text or "item"


def input_smd_files(input_dir: Path) -> list[Path]:
    files = []
    for path in sorted(input_dir.glob("*.smd"), key=lambda item: natural_key(item.name)):
        if path.name.lower() in EXCLUDED_IMPORT_NAMES:
            continue
        files.append(path)
    if not files:
        raise RuntimeError(f"No top-level SMD files were found in {input_dir}")
    body = [path for path in files if path.name.lower() == "body.smd"]
    if body:
        return body + [path for path in files if path not in body]
    return files


def import_smds(input_dir: Path) -> dict[str, object]:
    smd_files = input_smd_files(input_dir)
    first = smd_files[0]
    log(f"Importing base c_arms source SMD: {first.name}")
    bpy.ops.import_scene.smd(filepath=str(first), append="NEW_ARMATURE", upAxis="Z")
    armatures = [
        obj
        for obj in bpy.data.objects
        if obj.type == "ARMATURE" and obj.name not in {"proportions", "reference_female", "reference_male"}
    ]
    if not armatures:
        armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError(f"{first.name} did not import an armature.")
    armature = armatures[0]
    imported = [first.name]
    for path in smd_files[1:]:
        log(f"Importing additional c_arms source SMD: {path.name}")
        set_active_only(armature)
        bpy.ops.import_scene.smd(filepath=str(path), append="VALIDATE", upAxis="Z")
        imported.append(path.name)
    return {"armature": armature.name, "imported_smds": imported, "skipped_smds": sorted(EXCLUDED_IMPORT_NAMES)}


def main_armature() -> bpy.types.Object:
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature was imported from the SMD files.")
    armatures.sort(key=lambda obj: len(obj.data.bones), reverse=True)
    return armatures[0]


def child_bone_names(armature: bpy.types.Object, roots: set[str]) -> set[str]:
    bones = armature.data.bones
    out = set()
    for root in roots:
        if root in bones:
            out.add(root)
    for bone in bones:
        parent = bone.parent
        while parent is not None:
            if parent.name in roots:
                out.add(bone.name)
                break
            parent = parent.parent
    return out


def mesh_objects() -> list[bpy.types.Object]:
    return sorted(
        [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name not in HELPER_MESH_NAMES and not obj.name.startswith("VTA vertices")],
        key=lambda obj: natural_key(obj.name),
    )


def vertex_keep_mask(obj: bpy.types.Object, target_bones: set[str], threshold: float) -> tuple[list[bool], int]:
    target_indices = {
        group.index
        for group in obj.vertex_groups
        if group.name in target_bones
    }
    weighted: list[bool] = []
    for vertex in obj.data.vertices:
        matched = False
        for ref in vertex.groups:
            if ref.group in target_indices and float(ref.weight) > threshold:
                matched = True
                break
        weighted.append(matched)
    keep = list(weighted)
    # Keep complete triangles around every qualifying weighted vertex. Deleting only
    # below-threshold vertices can otherwise leave no complete c_arms faces.
    for poly in obj.data.polygons:
        if any(weighted[int(vertex_index)] for vertex_index in poly.vertices):
            for vertex_index in poly.vertices:
                keep[int(vertex_index)] = True
    return keep, sum(1 for value in weighted if value)


def prune_mesh_to_carms(obj: bpy.types.Object, target_bones: set[str], threshold: float) -> dict[str, object]:
    before_vertices = len(obj.data.vertices)
    before_faces = len(obj.data.polygons)
    keep, weighted_vertices_before_expand = vertex_keep_mask(obj, target_bones, threshold)
    kept_vertices_before_delete = sum(1 for value in keep if value)
    log(
        f"{obj.name}: {weighted_vertices_before_expand:,} vertices exceed c_arms weight threshold; "
        f"{kept_vertices_before_delete:,} vertices kept after triangle expansion."
    )
    if weighted_vertices_before_expand <= 0:
        return {
            "object": obj.name,
            "removed": True,
            "before_vertices": before_vertices,
            "before_faces": before_faces,
            "after_vertices": 0,
            "after_faces": 0,
            "kept_weighted_vertices": weighted_vertices_before_expand,
            "kept_expanded_vertices": 0,
            "reason": "no vertices exceeded the c_arms weight threshold",
        }

    set_active_only(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    for vertex in bm.verts:
        vertex.select_set(not keep[vertex.index])
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.delete(type="VERT")
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.data.update()

    after_vertices = len(obj.data.vertices)
    after_faces = len(obj.data.polygons)
    removed = after_vertices <= 0 or after_faces <= 0
    return {
        "object": obj.name,
        "removed": removed,
        "before_vertices": before_vertices,
        "before_faces": before_faces,
        "after_vertices": after_vertices,
        "after_faces": after_faces,
        "kept_weighted_vertices": weighted_vertices_before_expand,
        "kept_expanded_vertices": kept_vertices_before_delete,
        "reason": "empty after deleting non-c_arms vertices" if removed else "",
    }


def prune_all_meshes(target_bones: set[str], threshold: float) -> list[dict[str, object]]:
    reports = []
    for obj in list(mesh_objects()):
        report = prune_mesh_to_carms(obj, target_bones, threshold)
        reports.append(report)
        if report.get("removed"):
            log(f"Removing empty c_arms bodygroup: {obj.name}")
            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            log(
                f"Kept {obj.name}: {int(report.get('after_vertices', 0)):,} vertices, "
                f"{int(report.get('after_faces', 0)):,} faces."
            )
    if not mesh_objects():
        raise RuntimeError("No c_arms bodygroup retained any faces after weight filtering.")
    return reports


def material_texture_map(input_dir: Path) -> dict[str, str]:
    workspace_root = input_dir.parent.parent if input_dir.parent.name == "9_export_proportion_trick" else input_dir.parent
    material_json = workspace_root / "5_sort_materials" / "materials.json"
    if not material_json.exists():
        return {}
    try:
        data = json.loads(material_json.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, str] = {}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            path = str(value.get("base_color_path") or "")
            if path and Path(path).exists():
                for key_name in ("material_name", "proposed_name", "final_name", "combined_material", "name"):
                    name = str(value.get(key_name) or "")
                    if name:
                        out.setdefault(name.casefold(), path)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return out


def material_texture_path(mat: bpy.types.Material | None, texture_by_name: dict[str, str]) -> str:
    if mat is None:
        return ""
    mapped = texture_by_name.get(mat.name.casefold())
    if mapped:
        return mapped
    if mat.node_tree is None:
        return ""
    for node in mat.node_tree.nodes:
        if getattr(node, "type", "") == "TEX_IMAGE" and getattr(node, "image", None) is not None:
            image = node.image
            if image.packed_file:
                return ""
            path = bpy.path.abspath(image.filepath or "")
            if path and Path(path).exists():
                return path
    return ""


def preview_color(uid: str, index: int) -> list[float]:
    seed = sum((offset + 1) * ord(char) for offset, char in enumerate(uid)) + index * 41
    hue = (seed % 360) / 360.0
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.42, 0.88)
    return [round(red, 4), round(green, 4), round(blue, 4), 1.0]


def collect_preview(texture_by_name: dict[str, str], max_triangles: int = MAX_PREVIEW_TRIANGLES) -> dict[str, object]:
    objects = mesh_objects()
    total_triangles = sum(max(0, len(poly.vertices) - 2) for obj in objects for poly in obj.data.polygons)
    stride = max(1, math.ceil(total_triangles / max_triangles)) if total_triangles else 1
    triangles: list[dict[str, object]] = []
    materials_by_uid: dict[str, dict[str, object]] = {}
    points: list[list[float]] = []
    triangle_index = 0
    for object_index, obj in enumerate(objects, start=1):
        uv_layer = obj.data.uv_layers.active
        for poly in obj.data.polygons:
            mat = obj.data.materials[int(poly.material_index)] if 0 <= int(poly.material_index) < len(obj.data.materials) else None
            mat_name = mat.name if mat is not None else "No_Material"
            material_uid = f"{safe_fragment(obj.name)}__{int(poly.material_index):03d}_{safe_fragment(mat_name)}"
            texture_path = material_texture_path(mat, texture_by_name)
            if material_uid not in materials_by_uid:
                materials_by_uid[material_uid] = {
                    "uid": material_uid,
                    "material_name": f"{obj.name} / {mat_name}",
                    "proposed_name": mat_name,
                    "bodygroup": obj.name,
                    "keep": True,
                    "preview_color": preview_color(material_uid, object_index),
                    "base_color_path": texture_path,
                    "base_color_file": Path(texture_path).name if texture_path else "",
                    "alpha": 1.0,
                }
            verts = list(poly.vertices)
            loops = list(poly.loop_indices)
            if len(verts) < 3:
                continue
            for offset in range(1, len(verts) - 1):
                if triangle_index % stride == 0:
                    vertex_indices = [verts[0], verts[offset], verts[offset + 1]]
                    loop_indices = [loops[0], loops[offset], loops[offset + 1]]
                    coords = [v3(obj.matrix_world @ obj.data.vertices[index].co) for index in vertex_indices]
                    uvs: list[list[float]] = []
                    for loop_index in loop_indices:
                        if uv_layer is not None and 0 <= loop_index < len(uv_layer.data):
                            uv = uv_layer.data[loop_index].uv
                            uvs.append([round(float(uv.x), 6), round(float(uv.y), 6)])
                        else:
                            uvs.append([0.0, 0.0])
                    points.extend(coords)
                    triangles.append(
                        {
                            "points": coords,
                            "uvs": uvs,
                            "material_uid": material_uid,
                            "texture_path": texture_path,
                            "object_name": obj.name,
                        }
                    )
                triangle_index += 1
    mins = [min(point[index] for point in points) for index in range(3)] if points else [0.0, 0.0, 0.0]
    maxs = [max(point[index] for point in points) for index in range(3)] if points else [1.0, 1.0, 1.0]
    return {
        "materials": sorted(materials_by_uid.values(), key=lambda item: natural_key(item.get("uid", ""))),
        "material_count": len(materials_by_uid),
        "model_preview": {
            "triangles": triangles,
            "source_triangle_count": total_triangles,
            "sampled_triangle_count": len(triangles),
            "sample_stride": stride,
            "mins": mins,
            "maxs": maxs,
        },
    }


def configure_source_export(output_dir: Path) -> None:
    if not enable_source_tools():
        raise RuntimeError("Blender Source Tools is required for Step 10 export.")
    scene = bpy.context.scene
    scene.vs.export_format = "SMD"
    scene.vs.smd_format = "SOURCE"
    scene.vs.qc_compile = False
    scene.vs.export_path = str(output_dir.resolve())
    for collection in bpy.data.collections:
        try:
            collection.vs.mute = True
        except Exception:
            pass
    for obj in scene.objects:
        try:
            if obj.type == "MESH":
                obj.vs.export = obj.name not in HELPER_MESH_NAMES and not obj.name.startswith("VTA vertices")
                obj.vs.subdir = "."
            elif obj.type == "ARMATURE":
                obj.vs.export = False
                obj.vs.subdir = "."
            else:
                obj.vs.export = False
        except Exception:
            pass
    source_tools_state_update()


def export_carms(output_dir: Path) -> list[Path]:
    configure_source_export(output_dir)
    log(f"Exporting c_arms SMD files to {output_dir}")
    result = bpy.ops.export_scene.smd(export_scene=True)
    if result != {"FINISHED"}:
        raise RuntimeError(f"Source export failed: {result}")
    files = sorted(path for path in output_dir.glob("*.smd") if path.is_file())
    if not files:
        raise RuntimeError(f"No c_arms SMD files were exported under {output_dir}")
    return files


def copy_anims(input_dir: Path, output_dir: Path) -> list[Path]:
    source = input_dir / "anims"
    target = output_dir / "anims"
    if not source.exists():
        return []
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    copied = sorted(path for path in target.rglob("*.smd") if path.is_file())
    log(f"Copied {len(copied)} animation SMD file(s) to {target}.")
    return copied


def file_inventory(output_dir: Path, exported: list[Path], copied_anims: list[Path], object_reports: list[dict[str, object]]) -> list[dict[str, object]]:
    by_stem = {str(report.get("object") or ""): report for report in object_reports if not report.get("removed")}
    files: list[dict[str, object]] = []
    for path in exported:
        report = by_stem.get(path.stem, {})
        files.append(
            {
                "name": path.name,
                "relative_path": str(path.relative_to(output_dir)),
                "path": str(path),
                "type": "SMD",
                "size": path.stat().st_size,
                "source_stage": "c_arms_export",
                "vertices": int(report.get("after_vertices", 0) or 0),
                "faces": int(report.get("after_faces", 0) or 0),
                "warnings": "",
            }
        )
    for path in copied_anims:
        files.append(
            {
                "name": path.name,
                "relative_path": str(path.relative_to(output_dir)),
                "path": str(path),
                "type": "SMD",
                "size": path.stat().st_size,
                "source_stage": "copied_anim",
                "vertices": 0,
                "faces": 0,
                "warnings": "",
            }
        )
    return files


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workspace-blend", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--files-json", type=Path, required=True)
    parser.add_argument("--weight-threshold", type=float, default=DEFAULT_WEIGHT_THRESHOLD)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, object]:
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    workspace_blend = args.workspace_blend.resolve()
    report_json = args.report_json.resolve()
    files_json = args.files_json.resolve()
    threshold = float(args.weight_threshold)
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
    if threshold <= 0.0:
        raise RuntimeError("Weight threshold must be positive.")

    log(f"Opening a clean Blender scene for c_arms import from {input_dir}")
    clear_startup_scene()
    if not enable_source_tools():
        raise RuntimeError("Blender Source Tools is required for Step 10.")
    prepare_output_directory(output_dir)
    import_report = import_smds(input_dir)
    armature = main_armature()
    target_bones = child_bone_names(armature, FOREARM_ROOTS)
    missing_roots = sorted(root for root in FOREARM_ROOTS if root not in target_bones)
    if missing_roots:
        raise RuntimeError("Required forearm bone(s) missing from imported armature: " + ", ".join(missing_roots))
    log(f"c_arms target bone set contains {len(target_bones)} forearm/hand/finger bone(s).")
    object_reports = prune_all_meshes(target_bones, threshold)
    texture_by_name = material_texture_map(input_dir)
    preview = collect_preview(texture_by_name)

    workspace_blend.parent.mkdir(parents=True, exist_ok=True)
    log(f"Saving c_arms workspace blend: {workspace_blend}")
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace_blend))

    exported = export_carms(output_dir)
    copied_anims = copy_anims(input_dir, output_dir)
    files = file_inventory(output_dir, exported, copied_anims, object_reports)
    files_json.parent.mkdir(parents=True, exist_ok=True)
    files_json.write_text(json.dumps({"files": files}, ensure_ascii=False, indent=2), encoding="utf-8")

    kept_reports = [report for report in object_reports if not report.get("removed")]
    report = {
        "version": 1,
        "kind": "sort_c_arms",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "workspace_blend": str(workspace_blend),
        "weight_threshold": threshold,
        "forearm_roots": sorted(FOREARM_ROOTS),
        "target_bones": sorted(target_bones, key=natural_key),
        "import": import_report,
        "bodygroups": object_reports,
        "kept_bodygroup_count": len(kept_reports),
        "removed_bodygroup_count": len(object_reports) - len(kept_reports),
        "exported_file_count": len(exported),
        "copied_anim_count": len(copied_anims),
        **preview,
        "files": files,
        "validation": {
            "ok": bool(exported) and bool(kept_reports),
            "errors": [],
            "warnings": [],
        },
    }
    write_json(report_json, report)
    log(f"Wrote c_arms report: {report_json}")
    log(f"Wrote c_arms file list: {files_json}")
    return report


def main(argv: list[str] | None = None) -> int:
    run(parse_args(argv))
    return 0


if __name__ == "__main__":
    args_after_dash = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    raise SystemExit(main(args_after_dash))
