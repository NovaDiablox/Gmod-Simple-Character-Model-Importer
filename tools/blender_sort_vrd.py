#!/usr/bin/env python3
"""Step 11 Blender automation: infer and export VRD skirt/dress helpers."""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import re
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


ROOT = Path(__file__).resolve().parents[1]
MAX_PREVIEW_TRIANGLES = 500000
HELPER_MESH_NAMES = {"smd_bone_vis"}
EXCLUDED_INFERENCE_OBJECTS = {"physics"}
VRD_FRAMES = [0, 10, 20, 30]
VRD_WEIGHT_FRAMES = [10, 20, 30]
DEFAULT_VRD_INTENSITY_MULTIPLIERS = {"10": 1.0, "20": 0.75, "30": 0.42}
DRIVER_BONES = {"ValveBiped.Bip01_L_Thigh", "ValveBiped.Bip01_R_Thigh"}
ESSENTIAL_BONE_PREFIXES = ("ValveBiped.",)
ESSENTIAL_BONES = {"ZArmTwist_L", "ZArmTwist_R", "ZHandTwist_L", "ZHandTwist_R", "Eye_L", "Eye_R"}
AUTO_VRD_ESSENTIAL_ROOTS = {
    "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_Spine",
    "ValveBiped.Bip01_Spine1",
    "ValveBiped.Bip01_Spine2",
    "ValveBiped.Bip01_Spine4",
}
LOWER_GARMENT_HINTS = (
    "skirt",
    "dress",
    "robe",
    "cloth",
    "coat",
    "apron",
    "mantle",
    "cape",
    "sleeve",
    "shangyi",
    "xia",
    "qun",
    "hem",
    "tail",
    "裙",
    "衣",
    "裳",
    "摆",
    "下摆",
    "上衣",
    "外套",
    "披",
)
EXCLUDED_NAME_HINTS = (
    "hair",
    "face",
    "eye",
    "brow",
    "mouth",
    "tongue",
    "weapon",
    "gun",
    "sword",
    "finger",
    "hand",
    "toe",
    "breast",
    "chest",
    "ear",
    "horn",
    "tailbone",
)


def log(message: str) -> None:
    print(f"[Step11 VRD] {message}", flush=True)


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


def clear_startup_scene() -> None:
    ensure_object_mode()
    for obj in list(bpy.context.scene.objects):
        obj.select_set(True)
    bpy.ops.object.delete()


def natural_key(value: object) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(value))]


def safe_fragment(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_").lower()
    return text or "item"


def v3(value: Vector) -> list[float]:
    return [round(float(value.x), 6), round(float(value.y), 6), round(float(value.z), 6)]


def normalize_intensity_multipliers(raw: object) -> dict[str, float]:
    source = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULT_VRD_INTENSITY_MULTIPLIERS)
    for frame in (10, 20, 30):
        key = str(frame)
        try:
            value = float(source.get(key, out[key]))  # type: ignore[union-attr]
        except Exception:
            value = out[key]
        out[key] = max(0.0, min(2.0, value))
    return out


def frame_intensity_multiplier(multipliers: dict[str, float], frame: int) -> float:
    if frame == 0:
        return 0.0
    return max(0.0, min(2.0, float(multipliers.get(str(frame), DEFAULT_VRD_INTENSITY_MULTIPLIERS.get(str(frame), 1.0)))))


def input_smd_files(input_dir: Path) -> list[Path]:
    files = sorted([path for path in input_dir.glob("*.smd") if path.is_file()], key=lambda item: natural_key(item.name))
    if not files:
        raise RuntimeError(f"No top-level SMD files were found in {input_dir}")
    body = [path for path in files if path.name.lower() == "body.smd"]
    return body + [path for path in files if path not in body] if body else files


def enable_source_tools() -> bool:
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_valvesource")
    except Exception:
        try:
            import io_scene_valvesource  # type: ignore

            io_scene_valvesource.register()
        except Exception as exc:
            log(f"Blender Source Tools could not be enabled: {exc}")
            return False
    try:
        bpy.ops.import_scene.smd.get_rna_type()
    except Exception as exc:
        log(f"Blender Source Tools SMD importer is unavailable: {exc}")
        return False
    return True


def enable_l4d2_tools() -> bool:
    try:
        bpy.ops.preferences.addon_enable(module="Blender_L4D2_Character_Tools")
    except Exception:
        addon_root = bpy.utils.user_resource("SCRIPTS", path="addons", create=False)
        if addon_root and str(addon_root) not in sys.path:
            sys.path.insert(0, str(addon_root))
        try:
            import Blender_L4D2_Character_Tools  # type: ignore

            Blender_L4D2_Character_Tools.register()
        except Exception as exc:
            log(f"L4D2 Character Tools could not be enabled; manual VRD fallback will be used: {exc}")
            return False
    try:
        bpy.ops.vrd.auto_pose.get_rna_type()
        bpy.ops.vrd.export_bones.get_rna_type()
        return hasattr(bpy.context.scene, "project_items")
    except Exception as exc:
        log(f"L4D2 Character Tools VRD operators are unavailable; manual VRD fallback will be used: {exc}")
        return False


def import_smds(input_dir: Path) -> dict[str, object]:
    smd_files = input_smd_files(input_dir)
    first = smd_files[0]
    log(f"Importing base VRD source SMD: {first.name}")
    bpy.ops.import_scene.smd(filepath=str(first), append="NEW_ARMATURE", upAxis="Z")
    armature = main_armature()
    imported = [first.name]
    for path in smd_files[1:]:
        log(f"Importing additional VRD source SMD: {path.name}")
        set_active_only(armature)
        bpy.ops.import_scene.smd(filepath=str(path), append="VALIDATE", upAxis="Z")
        imported.append(path.name)
    return {"imported_smds": imported, "armature": armature.name}


def main_armature() -> bpy.types.Object:
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature was imported from the SMD files.")
    armatures.sort(key=lambda obj: len(obj.data.bones), reverse=True)
    return armatures[0]


def mesh_objects(include_physics: bool = False) -> list[bpy.types.Object]:
    out = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        name = obj.name.lower()
        if obj.name in HELPER_MESH_NAMES or obj.name.startswith("VTA vertices"):
            continue
        if not include_physics and name in EXCLUDED_INFERENCE_OBJECTS:
            continue
        out.append(obj)
    return sorted(out, key=lambda obj: natural_key(obj.name))


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
            path = str(value.get("base_color_path") or value.get("atlas_path") or "")
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
    seed = sum((offset + 1) * ord(char) for offset, char in enumerate(uid)) + index * 53
    hue = (seed % 360) / 360.0
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.42, 0.88)
    return [round(red, 4), round(green, 4), round(blue, 4), 1.0]


def collect_preview(
    input_dir: Path,
    max_triangles: int = MAX_PREVIEW_TRIANGLES,
    frame: int | None = None,
    evaluated: bool = False,
) -> dict[str, object]:
    if frame is not None:
        bpy.context.scene.frame_set(int(frame))
    texture_by_name = material_texture_map(input_dir)
    objects = mesh_objects(include_physics=False)
    total_triangles = sum(max(0, len(poly.vertices) - 2) for obj in objects for poly in obj.data.polygons)
    stride = max(1, math.ceil(total_triangles / max_triangles)) if total_triangles else 1
    triangles: list[dict[str, object]] = []
    materials_by_uid: dict[str, dict[str, object]] = {}
    points: list[list[float]] = []
    triangle_index = 0
    depsgraph = bpy.context.evaluated_depsgraph_get() if evaluated else None
    if depsgraph is not None:
        depsgraph.update()
    for object_index, obj in enumerate(objects, start=1):
        eval_obj = obj
        mesh = obj.data
        temp_mesh = False
        if depsgraph is not None:
            eval_obj = obj.evaluated_get(depsgraph)
            try:
                mesh = eval_obj.to_mesh()
                temp_mesh = True
            except Exception:
                mesh = obj.data
                eval_obj = obj
                temp_mesh = False
        try:
            uv_layer = mesh.uv_layers.active
            material_slots = obj.data.materials
            for poly in mesh.polygons:
                mat = material_slots[int(poly.material_index)] if 0 <= int(poly.material_index) < len(material_slots) else None
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
                        coords = [v3(eval_obj.matrix_world @ mesh.vertices[index].co) for index in vertex_indices]
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
        finally:
            if temp_mesh:
                eval_obj.to_mesh_clear()
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


def is_essential_bone(name: str) -> bool:
    return name.startswith(ESSENTIAL_BONE_PREFIXES) or name in ESSENTIAL_BONES


def closest_essential_parent_name(bone: bpy.types.Bone | None) -> str:
    parent = bone.parent if bone else None
    while parent:
        if is_essential_bone(parent.name):
            return parent.name
        parent = parent.parent
    return ""


def direct_parent_name(bone: bpy.types.Bone | None) -> str:
    return bone.parent.name if bone and bone.parent else ""


def default_vrd_root_status(bone: bpy.types.Bone) -> tuple[bool, str, str, str]:
    direct_parent = direct_parent_name(bone)
    essential_parent = closest_essential_parent_name(bone)
    if not direct_parent:
        return True, "", "", ""
    if not direct_parent.startswith("ValveBiped."):
        return (
            False,
            essential_parent,
            direct_parent,
            f"Disabled by default: direct parent is {direct_parent}; automatic VRD only enables bones directly parented to a ValveBiped pelvis/spine bone.",
        )
    if direct_parent in AUTO_VRD_ESSENTIAL_ROOTS:
        return True, essential_parent or direct_parent, direct_parent, ""
    return (
        False,
        essential_parent or direct_parent,
        direct_parent,
        f"Disabled by default: direct parent is {direct_parent}; automatic VRD only enables direct pelvis/spine-root garment chains.",
    )


def normalized_name(name: str) -> str:
    return re.sub(r"[\s_\-\.]+", "", name).casefold()


def bone_head(armature: bpy.types.Object, name: str) -> Vector | None:
    bone = armature.data.bones.get(name)
    if not bone:
        return None
    return armature.matrix_world @ bone.head_local


def bone_tail(armature: bpy.types.Object, name: str) -> Vector | None:
    bone = armature.data.bones.get(name)
    if not bone:
        return None
    return armature.matrix_world @ bone.tail_local


def preserve_imported_armature_report(armature: bpy.types.Object) -> dict[str, object]:
    bone_count = len(armature.data.bones) if armature and armature.type == "ARMATURE" else 0
    return {
        "mode": "preserve_imported_step9_armature",
        "bone_count": bone_count,
        "updated_bones": [],
        "warnings": [],
    }


def axis_or_default(vector: Vector, fallback: Vector) -> Vector:
    if vector.length <= 1e-6:
        return fallback.normalized()
    return vector.normalized()


def landmark_axes(armature: bpy.types.Object) -> dict[str, object]:
    pelvis = bone_head(armature, "ValveBiped.Bip01_Pelvis") or Vector((0, 0, 0))
    left_thigh = bone_head(armature, "ValveBiped.Bip01_L_Thigh") or (pelvis + Vector((1, 0, -1)))
    right_thigh = bone_head(armature, "ValveBiped.Bip01_R_Thigh") or (pelvis + Vector((-1, 0, -1)))
    head = bone_head(armature, "ValveBiped.Bip01_Head1") or bone_head(armature, "ValveBiped.Bip01_Spine4") or (pelvis + Vector((0, 0, 10)))
    left_foot = bone_head(armature, "ValveBiped.Bip01_L_Foot") or (left_thigh - Vector((0, 0, 10)))
    right_foot = bone_head(armature, "ValveBiped.Bip01_R_Foot") or (right_thigh - Vector((0, 0, 10)))
    side_axis = axis_or_default(left_thigh - right_thigh, Vector((1, 0, 0)))
    up_axis = axis_or_default(head - pelvis, Vector((0, 0, 1)))
    forward_axis = axis_or_default(side_axis.cross(up_axis), Vector((0, 1, 0)))
    leg_len = max(0.001, ((left_thigh - left_foot).length + (right_thigh - right_foot).length) * 0.5)
    body_height = max(0.001, (head - pelvis).length)
    return {
        "pelvis": pelvis,
        "left_thigh": left_thigh,
        "right_thigh": right_thigh,
        "side_axis": side_axis,
        "up_axis": up_axis,
        "forward_axis": forward_axis,
        "leg_len": leg_len,
        "body_height": body_height,
        "center_threshold": max(0.35, (left_thigh - right_thigh).length * 0.28),
    }


def vertex_group_indices(obj: bpy.types.Object) -> dict[str, int]:
    return {group.name: group.index for group in obj.vertex_groups}


def weight_for_vertex(vertex: bpy.types.MeshVertex, group_index: int) -> float:
    for ref in vertex.groups:
        if ref.group == group_index:
            return float(ref.weight)
    return 0.0


def collect_bone_weight_stats(bone_name: str) -> dict[str, object]:
    coords: list[Vector] = []
    objects: set[str] = set()
    material_uids: set[str] = set()
    weighted_count = 0
    source_faces = 0
    for obj in mesh_objects(include_physics=False):
        indices = vertex_group_indices(obj)
        group_index = indices.get(bone_name)
        if group_index is None:
            continue
        weighted_vertices = {
            int(vertex.index)
            for vertex in obj.data.vertices
            if weight_for_vertex(vertex, group_index) > 0.001
        }
        if not weighted_vertices:
            continue
        objects.add(obj.name)
        weighted_count += len(weighted_vertices)
        coords.extend(obj.matrix_world @ obj.data.vertices[index].co for index in weighted_vertices)
        for poly in obj.data.polygons:
            if any(int(index) in weighted_vertices for index in poly.vertices):
                mat = obj.data.materials[int(poly.material_index)] if 0 <= int(poly.material_index) < len(obj.data.materials) else None
                mat_name = mat.name if mat else "No_Material"
                material_uids.add(f"{safe_fragment(obj.name)}__{int(poly.material_index):03d}_{safe_fragment(mat_name)}")
                source_faces += 1
    if not coords:
        return {"bone": bone_name, "weighted_vertices": 0, "source_objects": [], "material_uids": [], "source_faces": 0}
    mins = Vector((min(coord.x for coord in coords), min(coord.y for coord in coords), min(coord.z for coord in coords)))
    maxs = Vector((max(coord.x for coord in coords), max(coord.y for coord in coords), max(coord.z for coord in coords)))
    centroid = sum(coords, Vector((0, 0, 0))) / len(coords)
    return {
        "bone": bone_name,
        "weighted_vertices": weighted_count,
        "source_objects": sorted(objects, key=natural_key),
        "material_uids": sorted(material_uids, key=natural_key),
        "source_faces": source_faces,
        "centroid": centroid,
        "mins": mins,
        "maxs": maxs,
    }


def score_bone_candidate(armature: bpy.types.Object, bone: bpy.types.Bone, stats: dict[str, object], axes: dict[str, object]) -> tuple[float, str, list[str]]:
    warnings: list[str] = []
    name = bone.name
    norm = normalized_name(name)
    weighted_vertices = int(stats.get("weighted_vertices", 0) or 0)
    if weighted_vertices <= 0:
        return 0.0, "none", ["Bone has no weighted render vertices."]
    hint_score = 0.0
    if any(hint.casefold() in name.casefold() or hint.casefold() in norm for hint in LOWER_GARMENT_HINTS):
        hint_score = 0.45
    if any(hint in norm for hint in EXCLUDED_NAME_HINTS):
        hint_score -= 0.35
    centroid = stats.get("centroid")
    if not isinstance(centroid, Vector):
        return 0.0, "none", ["No weighted centroid."]
    pelvis = axes["pelvis"]
    side_axis = axes["side_axis"]
    up_axis = axes["up_axis"]
    center_threshold = float(axes["center_threshold"])
    leg_len = float(axes["leg_len"])
    assert isinstance(pelvis, Vector) and isinstance(side_axis, Vector) and isinstance(up_axis, Vector)
    relative = centroid - pelvis
    height = float(relative.dot(up_axis))
    side_distance = float(relative.dot(side_axis))
    lower_region_score = 0.0
    if -0.82 * leg_len <= height <= 0.22 * leg_len:
        lower_region_score = 0.28
    elif -1.15 * leg_len <= height <= 0.35 * leg_len:
        lower_region_score = 0.16
        warnings.append("Bone is near but outside the preferred lower garment height band.")
    else:
        warnings.append("Bone weighted vertices are outside the lower garment height band.")
    geometry_score = 0.0
    mins = stats.get("mins")
    maxs = stats.get("maxs")
    if isinstance(mins, Vector) and isinstance(maxs, Vector):
        corners = bounds_corners(mins, maxs)
        height_min, height_max = projected_range(corners, pelvis, up_axis)
        side_min, side_max = projected_range(corners, pelvis, side_axis)
        lower_overlap = height_max >= -1.02 * leg_len and height_min <= 0.32 * leg_len
        near_hip_width = side_min <= center_threshold * 2.35 and side_max >= -center_threshold * 2.35
        side_panel = abs(side_distance) >= center_threshold * 0.55 and abs(side_distance) <= center_threshold * 2.45
        center_panel = abs(side_distance) <= center_threshold * 1.20
        if lower_overlap and near_hip_width and (side_panel or center_panel):
            geometry_score = 0.14
        if lower_overlap and side_panel:
            geometry_score = max(geometry_score, 0.18)
    parent = bone.parent.name if bone.parent else ""
    hierarchy_score = 0.0
    if parent == "ValveBiped.Bip01_Pelvis" or parent == "ValveBiped.Bip01_Spine" or not parent:
        hierarchy_score = 0.18
    elif parent in armature.data.bones and not is_essential_bone(parent):
        hierarchy_score = 0.08
    size_score = min(0.12, math.log10(max(10, weighted_vertices)) * 0.045)
    confidence = max(0.0, min(0.98, 0.08 + hint_score + lower_region_score + geometry_score + hierarchy_score + size_score))
    if confidence < 0.55:
        side = "none"
    elif abs(side_distance) <= center_threshold:
        side = "center"
    elif side_distance > 0:
        side = "left"
    else:
        side = "right"
    return confidence, side, warnings


def infer_vrd_rows(armature: bpy.types.Object) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    axes = landmark_axes(armature)
    raw_candidates: list[dict[str, object]] = []
    for bone in armature.data.bones:
        if is_essential_bone(bone.name):
            continue
        stats = collect_bone_weight_stats(bone.name)
        confidence, side, warnings = score_bone_candidate(armature, bone, stats, axes)
        if confidence < 0.50:
            continue
        default_enabled, essential_parent, direct_parent, root_warning = default_vrd_root_status(bone)
        if root_warning:
            warnings = list(warnings) + [root_warning]
        entry = {
            "bone": bone.name,
            "parent": bone.parent.name if bone.parent else "",
            "essential_parent": essential_parent,
            "direct_parent": direct_parent,
            "default_enabled": default_enabled,
            "confidence": round(confidence, 3),
            "side": side,
            "weighted_vertices": int(stats.get("weighted_vertices", 0) or 0),
            "source_faces": int(stats.get("source_faces", 0) or 0),
            "source_objects": stats.get("source_objects", []),
            "material_uids": stats.get("material_uids", []),
            "centroid": v3(stats["centroid"]) if isinstance(stats.get("centroid"), Vector) else [0.0, 0.0, 0.0],
            "bounds": {
                "mins": v3(stats["mins"]) if isinstance(stats.get("mins"), Vector) else [0.0, 0.0, 0.0],
                "maxs": v3(stats["maxs"]) if isinstance(stats.get("maxs"), Vector) else [0.0, 0.0, 0.0],
            },
            "warnings": warnings,
        }
        raw_candidates.append(entry)

    def candidate_depth(entry: dict[str, object]) -> int:
        depth = 0
        bone = armature.data.bones.get(str(entry.get("bone") or ""))
        while bone and bone.parent:
            depth += 1
            bone = bone.parent
        return depth

    def selected_nonessential_ancestor(entry: dict[str, object], selected_names: set[str]) -> str:
        bone = armature.data.bones.get(str(entry.get("bone") or ""))
        parent = bone.parent if bone else None
        while parent:
            if is_essential_bone(parent.name):
                return ""
            if parent.name in selected_names:
                return parent.name
            parent = parent.parent
        return ""

    filtered: list[dict[str, object]] = []
    selected_names: set[str] = set()
    suppressed_descendants: list[dict[str, object]] = []
    for entry in sorted(raw_candidates, key=lambda item: (candidate_depth(item), -float(item["confidence"]), natural_key(item["bone"]))):
        ancestor = selected_nonessential_ancestor(entry, selected_names)
        if ancestor:
            skipped = dict(entry)
            skipped["suppressed_by"] = ancestor
            suppressed_descendants.append(skipped)
            continue
        filtered.append(entry)
        selected_names.add(str(entry["bone"]))

    rows: list[dict[str, object]] = []
    for index, candidate in enumerate(sorted(filtered, key=lambda item: natural_key(item["bone"])), start=1):
        side = str(candidate.get("side") or "center")
        drivers = []
        if side == "left":
            drivers = ["ValveBiped.Bip01_L_Thigh"]
        elif side == "right":
            drivers = ["ValveBiped.Bip01_R_Thigh"]
        else:
            drivers = ["ValveBiped.Bip01_L_Thigh", "ValveBiped.Bip01_R_Thigh"]
        for driver in drivers:
            confidence = float(candidate.get("confidence", 0.0) or 0.0)
            enabled = bool(candidate.get("default_enabled", True)) and confidence >= 0.78
            row = {
                "uid": f"vrd_{len(rows) + 1:03d}_{safe_fragment(candidate['bone'])}_{'l' if driver.endswith('_L_Thigh') else 'r'}",
                "enabled": enabled,
                "procedural_bone": candidate["bone"],
                "driver_bone": driver,
                "angle": 90.0,
                "side": side if len(drivers) == 1 else "center",
                "essential_parent": candidate.get("essential_parent", ""),
                "direct_parent": candidate.get("direct_parent", ""),
                "confidence": round(confidence, 3),
                "weighted_vertices": candidate.get("weighted_vertices", 0),
                "source_faces": candidate.get("source_faces", 0),
                "source_objects": candidate.get("source_objects", []),
                "material_uids": candidate.get("material_uids", []),
                "centroid": candidate.get("centroid", [0.0, 0.0, 0.0]),
                "bounds": candidate.get("bounds", {}),
                "warnings": list(candidate.get("warnings", [])),
            }
            if not enabled:
                if not bool(candidate.get("default_enabled", True)):
                    row["warnings"].append("Candidate is visible for review but disabled because it is not directly parented to an eligible ValveBiped pelvis/spine bone.")
                else:
                    row["warnings"].append("Medium-confidence VRD candidate; review before enabling.")
            rows.append(row)
    sync_vrd_row_frame_weights(armature, rows, axes)
    analysis_summary = {
        "candidate_count": len(filtered),
        "raw_candidate_count": len(raw_candidates),
        "suppressed_descendant_count": len(suppressed_descendants),
        "suppressed_descendants": [
            {
                "bone": item.get("bone"),
                "parent": item.get("parent"),
                "essential_parent": item.get("essential_parent"),
                "direct_parent": item.get("direct_parent"),
                "suppressed_by": item.get("suppressed_by"),
                "confidence": item.get("confidence"),
            }
            for item in sorted(suppressed_descendants, key=lambda item: natural_key(item.get("bone", "")))
        ],
        "enabled_row_count": sum(1 for row in rows if row.get("enabled")),
        "axes": {
            "pelvis": v3(axes["pelvis"]),
            "left_thigh": v3(axes["left_thigh"]),
            "right_thigh": v3(axes["right_thigh"]),
        },
    }
    return rows, filtered, analysis_summary


def create_standard_vrd_action(armature: bpy.types.Object, prefer_addon: bool) -> tuple[bool, str]:
    set_active_only(armature)
    if prefer_addon and bpy.app.background:
        log("Skipping L4D2 auto_pose in background mode; using equivalent manual VRD pose.")
        prefer_addon = False
    if prefer_addon:
        try:
            log("Generating standard VRD action with L4D2 Character Tools.")
            result = bpy.ops.vrd.auto_pose()
            if result == {"FINISHED"} and bpy.data.actions.get("VRD"):
                armature.animation_data_create()
                armature.animation_data.action = bpy.data.actions["VRD"]
                return True, ""
        except Exception as exc:
            log(f"L4D2 auto_pose failed; using manual VRD pose fallback: {exc}")
    log("Generating standard VRD action with manual fallback.")
    bpy.context.scene.frame_set(0)
    ensure_object_mode()
    set_active_only(armature)
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
    base_pose = {
        pose_bone.name: {
            "location": pose_bone.location.copy(),
            "rotation": pose_bone.rotation_quaternion.copy(),
        }
        for pose_bone in armature.pose.bones
    }
    action = bpy.data.actions.get("VRD")
    if action:
        bpy.data.actions.remove(action)
    action = bpy.data.actions.new(name="VRD")
    action.use_fake_user = True
    armature.animation_data_create()
    armature.animation_data.action = action
    # These are relative thigh driver poses. Do not zero the imported pose;
    # Source SMD imports may carry an A-pose as pose channels over a different
    # edit/rest armature. Resetting to identity turns the preview/output arms
    # into the malformed T-pose seen in Blender.
    rotations = {
        10: {
            "ValveBiped.Bip01_L_Thigh": (0.707107, 0, 0, -0.707107),
            "ValveBiped.Bip01_R_Thigh": (0.707107, 0, 0, -0.707107),
        },
        20: {
            "ValveBiped.Bip01_L_Thigh": (0.683013, -0.183013, -0.183013, -0.683013),
            "ValveBiped.Bip01_R_Thigh": (0.683013, 0.183013, 0.183013, -0.683013),
        },
        30: {
            "ValveBiped.Bip01_L_Thigh": (0.965926, -1.74183e-08, -0.258819, -2.91367e-09),
            "ValveBiped.Bip01_R_Thigh": (0.965926, 2.37505e-08, 0.258819, -1.17871e-08),
        },
    }
    for frame in VRD_FRAMES:
        bpy.context.scene.frame_set(frame)
        for pose_bone in armature.pose.bones:
            base = base_pose.get(pose_bone.name)
            if not base:
                continue
            pose_bone.location = base["location"].copy()
            pose_bone.rotation_quaternion = base["rotation"].copy()
        for name, quat in rotations.get(frame, {}).items():
            pose_bone = armature.pose.bones.get(name)
            if pose_bone:
                base = base_pose.get(name, {})
                base_rotation = base.get("rotation", Quaternion())
                pose_bone.rotation_quaternion = base_rotation @ Quaternion(quat)
        for pose_bone in armature.pose.bones:
            pose_bone.keyframe_insert(data_path="location", frame=frame)
            pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    return False, ""


def key_all_bones_at_vrd_frames(armature: bpy.types.Object) -> None:
    log("Keying every pose bone at frames 0, 10, 20, and 30.")
    set_active_only(armature)
    for frame in VRD_FRAMES:
        bpy.context.scene.frame_set(frame)
        for pose_bone in armature.pose.bones:
            pose_bone.keyframe_insert(data_path="location", frame=frame)
            if pose_bone.rotation_mode == "QUATERNION":
                pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            else:
                pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame)


def row_side_sign(row: dict[str, object]) -> float:
    driver = str(row.get("driver_bone") or "")
    if "L_Thigh" in driver:
        return 1.0
    if "R_Thigh" in driver:
        return -1.0
    return 0.0


def vector_from_json(value: object) -> Vector | None:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return Vector((float(value[0]), float(value[1]), float(value[2])))
        except Exception:
            return None
    return None


def row_centroid(armature: bpy.types.Object, row: dict[str, object]) -> Vector | None:
    centroid = vector_from_json(row.get("centroid"))
    if centroid is not None:
        return centroid
    stats = collect_bone_weight_stats(str(row.get("procedural_bone") or ""))
    candidate = stats.get("centroid")
    if isinstance(candidate, Vector):
        return candidate
    bone_name = str(row.get("procedural_bone") or "")
    head = bone_head(armature, bone_name)
    tail = bone_tail(armature, bone_name)
    if head is not None and tail is not None:
        return (head + tail) * 0.5
    return None


def row_bounds(armature: bpy.types.Object, row: dict[str, object]) -> tuple[Vector, Vector] | None:
    raw_bounds = row.get("bounds")
    if isinstance(raw_bounds, dict):
        mins = vector_from_json(raw_bounds.get("mins"))
        maxs = vector_from_json(raw_bounds.get("maxs"))
        if mins is not None and maxs is not None and (maxs - mins).length > 1e-6:
            return mins, maxs
    stats = collect_bone_weight_stats(str(row.get("procedural_bone") or ""))
    mins = stats.get("mins")
    maxs = stats.get("maxs")
    if isinstance(mins, Vector) and isinstance(maxs, Vector) and (maxs - mins).length > 1e-6:
        return mins, maxs
    centroid = row_centroid(armature, row)
    if centroid is None:
        return None
    return centroid, centroid


def bounds_corners(mins: Vector, maxs: Vector) -> list[Vector]:
    return [
        Vector((x, y, z))
        for x in (mins.x, maxs.x)
        for y in (mins.y, maxs.y)
        for z in (mins.z, maxs.z)
    ]


def projected_range(points: list[Vector], origin: Vector, axis: Vector) -> tuple[float, float]:
    values = [float((point - origin).dot(axis)) for point in points]
    return (min(values), max(values)) if values else (0.0, 0.0)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    if abs(edge1 - edge0) <= 1e-8:
        return 1.0 if value >= edge1 else 0.0
    t = clamp01((value - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def row_frame_response(armature: bpy.types.Object, row: dict[str, object], frame: int, axes: dict[str, object]) -> float:
    if frame == 0:
        return 0.0
    centroid = row_centroid(armature, row)
    if centroid is None:
        return 1.0
    driver = str(row.get("driver_bone") or "")
    thigh = bone_head(armature, driver) or axes.get("pelvis")
    side_axis = axes.get("side_axis")
    forward_axis = axes.get("forward_axis")
    leg_len = float(axes.get("leg_len", 1.0) or 1.0)
    if not isinstance(thigh, Vector) or not isinstance(side_axis, Vector) or not isinstance(forward_axis, Vector):
        return 1.0
    rel = centroid - thigh
    side_sign = row_side_sign(row)
    front = float(rel.dot(forward_axis))
    side = float(rel.dot(side_axis)) * side_sign
    bounds = row_bounds(armature, row)
    if bounds is not None:
        corners = bounds_corners(bounds[0], bounds[1])
        front_min, front_max = projected_range(corners, thigh, forward_axis)
        raw_side_min, raw_side_max = projected_range(corners, thigh, side_axis)
        side_min = raw_side_min * side_sign
        side_max = raw_side_max * side_sign
        if side_min > side_max:
            side_min, side_max = side_max, side_min
    else:
        front_min = front_max = front
        side_min = side_max = side
    center_threshold = float(axes.get("center_threshold", leg_len * 0.12) or (leg_len * 0.12))
    front_scale = max(0.35, leg_len * 0.18)
    # Lateral VRD response should be based on hip/thigh spacing, not full leg
    # length. Long Source-scale legs make side skirt panels look deceptively
    # "near zero" if this threshold is tied to knee/foot distance.
    side_scale = max(0.35, min(leg_len * 0.16, center_threshold * 0.85))
    if frame == 10:
        # Forward thigh pose. Only cloth in front of the thigh is a strong collision risk.
        return smoothstep(-front_scale * 0.22, front_scale * 0.90, max(front, front_max * 0.92))
    if frame == 20:
        # Forward plus diagonal/outward pose. A side skirt panel can collide at
        # frame 20 even when its centroid is not in front of the thigh, so use
        # the weighted bounds and let same-side cloth lift independently.
        front_response = smoothstep(-front_scale * 0.28, front_scale * 0.92, max(front, front_max * 0.92))
        side_response = smoothstep(-side_scale * 0.18, side_scale * 0.82, max(side, side_max * 0.92))
        side_overlap = smoothstep(-side_scale * 0.92, side_scale * 0.28, side_max)
        diagonal_response = clamp01(max(front_response, side_response * 0.88, (front_response * 0.58 + side_response * 0.62)))
        if side_response > 0.36 and side_overlap > 0.30:
            diagonal_response = max(diagonal_response, 0.64 + 0.36 * side_response)
        return clamp01(diagonal_response)
    if frame == 30:
        # Side/global-Y pose. Back cloth is still a collision risk, but side
        # cloth must also react when it sits outward from the driver thigh.
        # This intentionally uses geometry relative to the thigh, not names:
        # front-center skirt panels remain quiet, while left/right side panels
        # such as SideSleeves follow the corresponding thigh.
        back_response = smoothstep(-front_scale * 0.20, front_scale, max(-front, -front_min * 0.92))
        side_sweep_response = smoothstep(side_scale * 0.02, side_scale * 1.15, max(side, side_max * 0.92))
        return clamp01(max(back_response, side_sweep_response))
    return 1.0


def normalize_frame_weight_overrides(raw: object) -> dict[str, float | None]:
    source = raw if isinstance(raw, dict) else {}
    out: dict[str, float | None] = {}
    for frame in VRD_WEIGHT_FRAMES:
        key = str(frame)
        value = source.get(key)  # type: ignore[union-attr]
        if value is None or str(value).strip() == "":
            out[key] = None
            continue
        try:
            out[key] = clamp01(float(value))
        except Exception:
            out[key] = None
    return out


def automatic_row_frame_weights(armature: bpy.types.Object, row: dict[str, object], axes: dict[str, object] | None = None) -> dict[str, float]:
    resolved_axes = axes or landmark_axes(armature)
    return {str(frame): round(clamp01(row_frame_response(armature, row, frame, resolved_axes)), 6) for frame in VRD_WEIGHT_FRAMES}


def sync_vrd_row_frame_weights(
    armature: bpy.types.Object,
    rows: list[dict[str, object]],
    axes: dict[str, object] | None = None,
) -> None:
    resolved_axes = axes or landmark_axes(armature)
    for row in rows:
        row["auto_frame_weights"] = automatic_row_frame_weights(armature, row, resolved_axes)
        row["frame_weight_overrides"] = normalize_frame_weight_overrides(row.get("frame_weight_overrides"))


def effective_row_frame_weight(armature: bpy.types.Object, row: dict[str, object], frame: int, axes: dict[str, object]) -> float:
    if frame == 0:
        return 0.0
    overrides = normalize_frame_weight_overrides(row.get("frame_weight_overrides"))
    override = overrides.get(str(frame))
    if override is not None:
        return override
    return clamp01(row_frame_response(armature, row, frame, axes))


def global_vrd_delta_matrix(angle_degrees: float, side_sign: float, frame: int, response: float = 1.0) -> Matrix:
    """Return the VRD procedural rotation in global coordinates.

    The L4D2 VRD authoring pose describes the driver thigh rotations in global
    axes. Procedural skirt/dress bones must follow those same global axes.
    Writing these rotations directly to pose_bone.rotation_quaternion is wrong
    because that property is local to the bone.
    """
    angle = math.radians(float(angle_degrees or 90.0))
    response = max(0.0, min(2.0, float(response)))
    if response <= 1e-5:
        return Matrix.Identity(4)
    if frame == 10:
        return Matrix.Rotation(-angle * response, 4, "X")
    if frame == 20:
        x_rot = Matrix.Rotation(-min(math.radians(108.0), angle * 1.12) * response, 4, "X")
        z_rot = Matrix.Rotation(float(side_sign) * angle * 0.5 * response, 4, "Z")
        return z_rot @ x_rot
    if frame == 30:
        y_angle = math.radians(55.0) * (float(angle_degrees or 90.0) / 90.0)
        return Matrix.Rotation(-float(side_sign) * y_angle * response, 4, "Y")
    return Matrix.Identity(4)


def set_pose_bone_global_delta(
    armature: bpy.types.Object,
    pose_bone: bpy.types.PoseBone,
    base_matrix: Matrix,
    global_delta: Matrix,
) -> None:
    base_world = armature.matrix_world @ base_matrix
    pivot_world = base_world.translation
    desired_world = Matrix.Translation(pivot_world) @ global_delta @ Matrix.Translation(-pivot_world) @ base_world
    pose_bone.matrix = armature.matrix_world.inverted_safe() @ desired_world


def apply_procedural_rows_to_action(
    armature: bpy.types.Object,
    rows: list[dict[str, object]],
    intensity_multipliers: dict[str, float] | None = None,
) -> None:
    enabled_rows = [row for row in rows if row.get("enabled", True)]
    if not enabled_rows:
        log("No enabled VRD rows; standard driver pose action will be saved without procedural cloth keys.")
        return
    multipliers = normalize_intensity_multipliers(intensity_multipliers)
    log(
        "Applying procedural VRD cloth rotations for "
        f"{len(enabled_rows)} row(s) with frame multipliers "
        f"10={multipliers['10']:.2f}, 20={multipliers['20']:.2f}, 30={multipliers['30']:.2f}."
    )
    axes = landmark_axes(armature)
    set_active_only(armature)
    bpy.ops.object.mode_set(mode="POSE")
    rows_by_bone: dict[str, list[dict[str, object]]] = {}
    for row in enabled_rows:
        name = str(row.get("procedural_bone") or "")
        if name:
            rows_by_bone.setdefault(name, []).append(row)
    rest_matrices: dict[str, Matrix] = {}
    bpy.context.scene.frame_set(0)
    for name in rows_by_bone:
        pose_bone = armature.pose.bones.get(name)
        if not pose_bone:
            continue
        pose_bone.rotation_mode = "QUATERNION"
        rest_matrices[name] = pose_bone.matrix.copy()
    for frame in VRD_FRAMES:
        frame_multiplier = frame_intensity_multiplier(multipliers, frame)
        bpy.context.scene.frame_set(frame)
        for name, bone_rows in rows_by_bone.items():
            pose_bone = armature.pose.bones.get(name)
            if not pose_bone:
                continue
            pose_bone.rotation_mode = "QUATERNION"
            base = rest_matrices.get(name)
            if base is None:
                continue
            weighted_rows: list[tuple[dict[str, object], float, float]] = []
            for row in bone_rows:
                response = effective_row_frame_weight(armature, row, frame, axes)
                if response <= 1e-5:
                    continue
                weighted_rows.append((row, response, row_side_sign(row)))
            if not weighted_rows:
                set_pose_bone_global_delta(armature, pose_bone, base, Matrix.Identity(4))
            else:
                max_response = max(response for _row, response, _sign in weighted_rows)
                angle = sum(float(row.get("angle", 90.0) or 90.0) * response for row, response, _sign in weighted_rows) / max(
                    1e-6, sum(response for _row, response, _sign in weighted_rows)
                )
                side_numerator = sum(sign * response for _row, response, sign in weighted_rows)
                side_denominator = sum(response for _row, response, _sign in weighted_rows)
                side_sign = 0.0 if abs(side_numerator) <= 1e-6 else max(-1.0, min(1.0, side_numerator / max(1e-6, side_denominator)))
                set_pose_bone_global_delta(
                    armature,
                    pose_bone,
                    base,
                    global_vrd_delta_matrix(angle, side_sign, frame, max_response * frame_multiplier),
                )
            pose_bone.keyframe_insert(data_path="rotation_quaternion")
            pose_bone.keyframe_insert(data_path="location")
    bpy.ops.object.mode_set(mode="OBJECT")


def pose_line_triangles(armature: bpy.types.Object, rows: list[dict[str, object]], frame: int) -> list[dict[str, object]]:
    bpy.context.scene.frame_set(frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    arm_eval = armature.evaluated_get(depsgraph)
    triangles: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    colors = {
        "ValveBiped.Bip01_L_Thigh": [0.25, 0.95, 0.45, 0.95],
        "ValveBiped.Bip01_R_Thigh": [1.0, 0.42, 0.28, 0.95],
    }

    def add_bone_line(uid: str, bone_name: str, color: list[float]) -> None:
        pose_bone = arm_eval.pose.bones.get(bone_name)
        if not pose_bone:
            return
        head = arm_eval.matrix_world @ pose_bone.head
        tail = arm_eval.matrix_world @ pose_bone.tail
        if (head - tail).length <= 1e-6:
            tail = head + Vector((0.0, 0.0, 0.1))
        triangles.append(
            {
                "uid": uid,
                "bone": bone_name,
                "points": [v3(head), v3(tail), v3(tail)],
                "color": color,
            }
        )

    for bone_name, color in colors.items():
        add_bone_line(f"driver_{bone_name}", bone_name, color)
    for row in rows:
        if not row.get("enabled", True):
            continue
        proc = str(row.get("procedural_bone") or "")
        if not proc:
            continue
        key = (str(row.get("uid") or proc), proc)
        if key in seen:
            continue
        seen.add(key)
        add_bone_line(str(row.get("uid") or proc), proc, [1.0, 0.76, 0.08, 1.0])
    return triangles


def collect_vrd_frame_previews(input_dir: Path) -> tuple[dict[str, dict[str, object]], dict[str, object], list[dict[str, object]], int]:
    frame_previews: dict[str, dict[str, object]] = {}
    base_preview: dict[str, object] | None = None
    materials: list[dict[str, object]] = []
    material_count = 0
    for frame in VRD_FRAMES:
        frame_preview = collect_preview(input_dir, frame=frame, evaluated=True)
        if base_preview is None:
            base_preview = frame_preview
            materials = list(frame_preview.get("materials", [])) if isinstance(frame_preview.get("materials"), list) else []
            material_count = int(frame_preview.get("material_count", 0) or 0)
        frame_previews[str(frame)] = {"model_preview": frame_preview.get("model_preview", {})}
    return frame_previews, base_preview or collect_preview(input_dir), materials, material_count


def collect_bone_preview(armature: bpy.types.Object | None) -> dict[str, object]:
    if armature is None:
        return {"bones": []}
    bones: list[dict[str, object]] = []
    matrix = armature.matrix_world
    for bone in armature.data.bones:
        head = matrix @ bone.head_local
        tail = matrix @ bone.tail_local
        bones.append(
            {
                "uid": bone.name,
                "name": bone.name,
                "parent": bone.parent.name if bone.parent else "",
                "head": v3(head),
                "tail": v3(tail),
            }
        )
    return {"bones": bones}


def build_vrd_preview(
    armature: bpy.types.Object,
    rows: list[dict[str, object]],
    input_dir: Path,
    driver_frame_previews: dict[str, dict[str, object]] | None = None,
    driver_overlays: dict[str, dict[str, object]] | None = None,
    intensity_multipliers: dict[str, float] | None = None,
) -> dict[str, object]:
    log("Building animated VRD preview meshes for frames 0, 10, 20, and 30.")
    frame_previews, preview, materials, material_count = collect_vrd_frame_previews(input_dir)
    overlays = {str(frame): {"triangles": pose_line_triangles(armature, rows, frame)} for frame in VRD_FRAMES}
    return {
        "version": 1,
        "intensity_multipliers": normalize_intensity_multipliers(intensity_multipliers),
        "materials": materials,
        "material_count": material_count,
        "model_preview": preview.get("model_preview", {}),
        "bone_preview": collect_bone_preview(armature),
        "frame_previews": frame_previews,
        "driver_frame_previews": driver_frame_previews or {},
        "frames": overlays,
        "driver_frames": driver_overlays or {},
        "frame_ticks": VRD_FRAMES,
        "rows": rows,
    }


def create_vrd_project(armature: bpy.types.Object, rows: list[dict[str, object]], vrd_path: Path) -> bool:
    if not hasattr(bpy.context.scene, "project_items"):
        return False
    scene = bpy.context.scene
    scene.project_items.clear()
    project = scene.project_items.add()
    project.name = "VRD Project 1"
    try:
        project.animation_name = "VRD"
    except Exception:
        pass
    scene.active_project_index = 0
    for row in rows:
        if not row.get("enabled", True):
            continue
        cxbone = project.bone_set.cxbone_list.add()
        cxbone.name = str(row.get("procedural_bone") or "")
        cxbone.angle = float(row.get("angle", 90.0) or 90.0)
        qdbone = project.bone_set.qdbone_list.add()
        qdbone.name = str(row.get("driver_bone") or "")
    scene.export_all = False
    scene.export_default = True
    scene.export_nekomdl = False
    scene.vrd_export_path = str(vrd_path)
    set_active_only(armature)
    return True


def get_transforms(pose_bone: bpy.types.PoseBone, transform_type: str) -> str:
    if pose_bone.parent:
        matrix = pose_bone.parent.matrix.inverted_safe() @ pose_bone.matrix
    else:
        matrix = pose_bone.matrix
    if transform_type == "ROTATION":
        values = [math.degrees(value) for value in matrix.to_euler()]
    else:
        values = list(matrix.to_translation().xyz)
    return " ".join(str(round(float(value), 6)) for value in values)


def manual_export_vrd(armature: bpy.types.Object, rows: list[dict[str, object]], vrd_path: Path) -> str:
    content = "// VRD Project 1\n"
    enabled_rows = [row for row in rows if row.get("enabled", True)]
    for index, row in enumerate(enabled_rows):
        proc = str(row.get("procedural_bone") or "")
        driver = str(row.get("driver_bone") or "")
        if proc not in armature.data.bones or driver not in armature.data.bones:
            continue
        proc_parent = armature.data.bones[proc].parent.name if armature.data.bones[proc].parent else "Bip01_Pelvis"
        driver_parent = armature.data.bones[driver].parent.name if armature.data.bones[driver].parent else "Bip01_Pelvis"
        proc_parent = proc_parent.replace("ValveBiped.", "")
        driver_parent = driver_parent.replace("ValveBiped.", "")
        driver_short = driver.replace("ValveBiped.", "")
        content += f"<helper> {proc} {proc_parent} {driver_parent} {driver_short}\n"
        bpy.context.scene.frame_set(0)
        basepos = get_transforms(armature.pose.bones[proc], "TRANSLATION")
        content += f"<basepos> {basepos}\n"
        base_values = [float(value) for value in basepos.split()]
        for frame in VRD_FRAMES:
            bpy.context.scene.frame_set(frame)
            qd_rotation = get_transforms(armature.pose.bones[driver], "ROTATION")
            cx_rotation = get_transforms(armature.pose.bones[proc], "ROTATION")
            frame_translation = get_transforms(armature.pose.bones[proc], "TRANSLATION")
            frame_values = [float(value) for value in frame_translation.split()]
            translation = [str(round(frame_values[idx] - base_values[idx], 6)) for idx in range(3)]
            content += f"<trigger> {float(row.get('angle', 90.0) or 90.0):.1f} {qd_rotation} {cx_rotation} {' '.join(translation)}\n"
        if index < len(enabled_rows) - 1:
            content += "\n"
    vrd_path.parent.mkdir(parents=True, exist_ok=True)
    vrd_path.write_text(content, encoding="utf-8")
    return content


def export_vrd(armature: bpy.types.Object, rows: list[dict[str, object]], vrd_path: Path, addon_available: bool) -> tuple[str, bool]:
    vrd_path.parent.mkdir(parents=True, exist_ok=True)
    if addon_available and create_vrd_project(armature, rows, vrd_path):
        try:
            log(f"Exporting StudioMDL VRD with L4D2 Character Tools: {vrd_path}")
            result = bpy.ops.vrd.export_bones(action="DEFAULT_EXPORT_FILE")
            if result == {"FINISHED"} and vrd_path.exists():
                return vrd_path.read_text(encoding="utf-8", errors="replace"), True
        except Exception as exc:
            log(f"L4D2 VRD export failed; using manual fallback: {exc}")
    log(f"Exporting StudioMDL VRD with manual fallback: {vrd_path}")
    return manual_export_vrd(armature, rows, vrd_path), False


def validate_plan(armature: bpy.types.Object, rows: list[dict[str, object]]) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    for required in sorted(DRIVER_BONES):
        if required not in armature.data.bones:
            errors.append(f"Missing required driver bone: {required}")
    enabled = [row for row in rows if row.get("enabled", True)]
    if not enabled:
        warnings.append("No enabled VRD rows; export will not contain skirt/dress helpers.")
    for row in enabled:
        proc = str(row.get("procedural_bone") or "")
        driver = str(row.get("driver_bone") or "")
        if proc not in armature.data.bones:
            errors.append(f"Enabled row references missing procedural bone: {proc}")
        if driver not in armature.data.bones:
            errors.append(f"Enabled row references missing driver bone: {driver}")
        if driver not in DRIVER_BONES:
            errors.append(f"Driver bone must be left or right thigh: {driver}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def count_vrd_helpers(content: str) -> tuple[int, int]:
    helpers = 0
    triggers = 0
    for line in content.splitlines():
        if line.startswith("<helper>"):
            helpers += 1
        elif line.startswith("<trigger>"):
            triggers += 1
    return helpers, triggers


def load_plan(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid VRD plan: {path}")
    return data


def run_analyze(args: argparse.Namespace) -> dict[str, object]:
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    log(f"Opening a clean Blender scene for VRD import from {input_dir}")
    clear_startup_scene()
    if not enable_source_tools():
        raise RuntimeError("Blender Source Tools is required for Step 11.")
    addon_available = enable_l4d2_tools()
    import_report = import_smds(input_dir)
    armature = main_armature()
    arm_display_alignment = preserve_imported_armature_report(armature)
    auto_pose_used, pose_warning = create_standard_vrd_action(armature, addon_available)
    rows, candidates, summary = infer_vrd_rows(armature)
    validation = validate_plan(armature, rows)
    if pose_warning:
        validation["warnings"].append(pose_warning)
    intensity_multipliers = normalize_intensity_multipliers({})
    driver_frame_previews, _driver_preview, _driver_materials, _driver_material_count = collect_vrd_frame_previews(input_dir)
    driver_overlays = {str(frame): {"triangles": pose_line_triangles(armature, rows, frame)} for frame in VRD_FRAMES}
    apply_procedural_rows_to_action(armature, rows, intensity_multipliers)
    key_all_bones_at_vrd_frames(armature)
    preview = build_vrd_preview(armature, rows, input_dir, driver_frame_previews, driver_overlays, intensity_multipliers)
    workspace_blend = args.workspace_blend.resolve()
    log(f"Saving VRD analysis workspace blend: {workspace_blend}")
    workspace_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace_blend))
    plan = {
        "version": 1,
        "kind": "sort_vrd",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "action_name": "VRD",
        "intensity_multipliers": intensity_multipliers,
        "rows": rows,
        "warnings": validation.get("warnings", []),
    }
    analysis = {
        "version": 1,
        "kind": "sort_vrd",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "workspace_blend": str(workspace_blend),
        "import": import_report,
        "arm_display_alignment": arm_display_alignment,
        "addon_available": addon_available,
        "auto_pose_used": auto_pose_used,
        "candidate_summary": summary,
        "intensity_multipliers": intensity_multipliers,
        "candidates": candidates,
        "validation": validation,
        **{key: preview[key] for key in ("materials", "material_count", "model_preview", "bone_preview")},
    }
    write_json(args.analysis_json.resolve(), analysis)
    write_json(args.plan_json.resolve(), plan)
    write_json(args.preview_json.resolve(), preview)
    log(f"Wrote VRD analysis: {args.analysis_json.resolve()}")
    log(f"Wrote VRD plan: {args.plan_json.resolve()}")
    log(f"Wrote VRD preview: {args.preview_json.resolve()}")
    return analysis


def run_apply(args: argparse.Namespace) -> dict[str, object]:
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = load_plan(args.plan_json.resolve())
    rows = [row for row in plan.get("rows", []) if isinstance(row, dict)] if isinstance(plan.get("rows"), list) else []
    intensity_multipliers = normalize_intensity_multipliers(plan.get("intensity_multipliers"))
    plan["intensity_multipliers"] = intensity_multipliers
    log(f"Opening a clean Blender scene for VRD export from {input_dir}")
    clear_startup_scene()
    if not enable_source_tools():
        raise RuntimeError("Blender Source Tools is required for Step 11.")
    addon_available = enable_l4d2_tools()
    import_report = import_smds(input_dir)
    armature = main_armature()
    arm_display_alignment = preserve_imported_armature_report(armature)
    auto_pose_used, pose_warning = create_standard_vrd_action(armature, addon_available)
    sync_vrd_row_frame_weights(armature, rows)
    plan["rows"] = rows
    write_json(args.plan_json.resolve(), plan)
    validation = validate_plan(armature, rows)
    if validation["errors"]:
        raise RuntimeError("VRD plan validation failed: " + "; ".join(str(error) for error in validation["errors"]))
    driver_frame_previews, _driver_preview, _driver_materials, _driver_material_count = collect_vrd_frame_previews(input_dir)
    driver_overlays = {str(frame): {"triangles": pose_line_triangles(armature, rows, frame)} for frame in VRD_FRAMES}
    apply_procedural_rows_to_action(armature, rows, intensity_multipliers)
    key_all_bones_at_vrd_frames(armature)
    preview = build_vrd_preview(armature, rows, input_dir, driver_frame_previews, driver_overlays, intensity_multipliers)
    workspace_blend = args.workspace_blend.resolve()
    log(f"Saving VRD workspace blend: {workspace_blend}")
    workspace_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace_blend))
    vrd_content, addon_export_used = export_vrd(armature, rows, args.vrd_path.resolve(), addon_available)
    helper_count, trigger_count = count_vrd_helpers(vrd_content)
    if helper_count <= 0 and any(row.get("enabled", True) for row in rows):
        raise RuntimeError("VRD export completed but no <helper> blocks were written.")
    if trigger_count != helper_count * 4:
        validation["warnings"].append(f"Expected four triggers per helper; found {trigger_count} triggers for {helper_count} helpers.")
    if pose_warning:
        validation["warnings"].append(pose_warning)
    report = {
        "version": 1,
        "kind": "sort_vrd",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "workspace_blend": str(workspace_blend),
        "vrd_path": str(args.vrd_path.resolve()),
        "import": import_report,
        "arm_display_alignment": arm_display_alignment,
        "addon_available": addon_available,
        "auto_pose_used": auto_pose_used,
        "addon_export_used": addon_export_used,
        "intensity_multipliers": intensity_multipliers,
        "enabled_row_count": sum(1 for row in rows if row.get("enabled", True)),
        "helper_count": helper_count,
        "trigger_count": trigger_count,
        "rows": rows,
        "validation": validation,
        **{key: preview[key] for key in ("materials", "material_count", "model_preview", "bone_preview")},
        "frames": preview.get("frames", {}),
    }
    write_json(args.preview_json.resolve(), preview)
    write_json(args.report_json.resolve(), report)
    log(f"Wrote VRD file: {args.vrd_path.resolve()}")
    log(f"Wrote VRD report: {args.report_json.resolve()}")
    return report


def run_preview(args: argparse.Namespace) -> dict[str, object]:
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = load_plan(args.plan_json.resolve())
    rows = [row for row in plan.get("rows", []) if isinstance(row, dict)] if isinstance(plan.get("rows"), list) else []
    intensity_multipliers = normalize_intensity_multipliers(plan.get("intensity_multipliers"))
    plan["intensity_multipliers"] = intensity_multipliers
    log(f"Opening a clean Blender scene for VRD preview from {input_dir}")
    clear_startup_scene()
    if not enable_source_tools():
        raise RuntimeError("Blender Source Tools is required for Step 11.")
    addon_available = enable_l4d2_tools()
    import_report = import_smds(input_dir)
    armature = main_armature()
    arm_display_alignment = preserve_imported_armature_report(armature)
    auto_pose_used, pose_warning = create_standard_vrd_action(armature, addon_available)
    sync_vrd_row_frame_weights(armature, rows)
    plan["rows"] = rows
    validation = validate_plan(armature, rows)
    if pose_warning:
        validation["warnings"].append(pose_warning)
    write_json(args.plan_json.resolve(), plan)
    if validation["errors"]:
        raise RuntimeError("VRD preview validation failed: " + "; ".join(str(error) for error in validation["errors"]))
    driver_frame_previews, _driver_preview, _driver_materials, _driver_material_count = collect_vrd_frame_previews(input_dir)
    driver_overlays = {str(frame): {"triangles": pose_line_triangles(armature, rows, frame)} for frame in VRD_FRAMES}
    apply_procedural_rows_to_action(armature, rows, intensity_multipliers)
    key_all_bones_at_vrd_frames(armature)
    preview = build_vrd_preview(armature, rows, input_dir, driver_frame_previews, driver_overlays, intensity_multipliers)
    report = {
        "version": 1,
        "kind": "sort_vrd_preview",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "import": import_report,
        "arm_display_alignment": arm_display_alignment,
        "addon_available": addon_available,
        "auto_pose_used": auto_pose_used,
        "intensity_multipliers": intensity_multipliers,
        "enabled_row_count": sum(1 for row in rows if row.get("enabled", True)),
        "rows": rows,
        "validation": validation,
        **{key: preview[key] for key in ("materials", "material_count", "model_preview", "bone_preview")},
        "frames": preview.get("frames", {}),
    }
    write_json(args.preview_json.resolve(), preview)
    write_json(args.report_json.resolve(), report)
    log(f"Wrote VRD preview: {args.preview_json.resolve()}")
    return preview


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["analyze", "apply", "preview"], required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workspace-blend", type=Path, required=True)
    parser.add_argument("--analysis-json", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--preview-json", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--vrd-path", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "analyze":
        run_analyze(args)
    elif args.mode == "preview":
        run_preview(args)
    else:
        run_apply(args)
    return 0


if __name__ == "__main__":
    args_after_dash = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    raise SystemExit(main(args_after_dash))
