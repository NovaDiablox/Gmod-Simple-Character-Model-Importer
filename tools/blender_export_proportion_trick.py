#!/usr/bin/env python3
"""Step 9 Blender automation: raw SMD export and proportion trick."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
PROPORTION_ROOT = ROOT / "reference" / "proportion_trick_script-main_new" / "Proportion_Trick"
PROPORTION_TEMPLATE = PROPORTION_ROOT / "proportion_trick_4.5.10.blend"
PROPORTION_TEXT_BLOCK = "Proportion Trick Full"
HELPER_MESH_NAMES = {"smd_bone_vis"}
PROTECTED_EXTRA_BONES = {"ZArmTwist_L", "ZArmTwist_R", "ZHandTwist_L", "ZHandTwist_R", "Eye_L", "Eye_R"}
PHYSICS_MERGE_DISTANCE = 1.0
NONESSENTIAL_EXPORT_ROLL_OFFSET_RADIANS = math.pi
EXPECTED_PROPORTION_ANIMS = {
    Path("anims/proportions.smd"),
    Path("anims/reference_female.smd"),
    Path("anims/reference_male.smd"),
}


def log(message: str) -> None:
    print(f"[Step9 Proportion] {message}", flush=True)


def hidden_subprocess_kwargs() -> dict[str, object]:
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }


def is_essential_bone(name: str) -> bool:
    return name.startswith("ValveBiped") or name in PROTECTED_EXTRA_BONES


def normalize_roll_radians(value: float) -> float:
    while value <= -math.pi:
        value += math.tau
    while value > math.pi:
        value -= math.tau
    return value


def clean_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_object_mode() -> None:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def set_active_only(obj: bpy.types.Object) -> None:
    ensure_object_mode()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def unhide_object(obj: bpy.types.Object) -> None:
    obj.hide_set(False)
    obj.hide_viewport = False
    for collection in obj.users_collection:
        collection.hide_viewport = False


def iter_layer_collections(layer_collection):
    yield layer_collection
    for child in layer_collection.children:
        yield from iter_layer_collections(child)


def unhide_all_export_objects() -> None:
    for collection in bpy.data.collections:
        collection.hide_viewport = False
    try:
        for layer_collection in iter_layer_collections(bpy.context.view_layer.layer_collection):
            layer_collection.exclude = False
            layer_collection.hide_viewport = False
    except Exception as exc:
        log(f"View-layer collection visibility repair warning: {exc}")
    for obj in bpy.context.scene.objects:
        obj.hide_set(False)
        obj.hide_viewport = False
    bpy.context.view_layer.update()


def enable_source_tools() -> bool:
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_valvesource")
    except Exception:
        blender_root = Path(bpy.app.binary_path).resolve().parent
        addon_dirs = [
            blender_root / "4.5" / "scripts" / "addons",
        ]
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
        bpy.ops.export_scene.smd.get_rna_type()
        bpy.ops.import_scene.smd.get_rna_type()
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


def main_armature() -> bpy.types.Object:
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature found in the collision-sorted blend.")
    armatures.sort(key=lambda obj: len(obj.data.bones), reverse=True)
    return armatures[0]


def visible_export_meshes() -> list[bpy.types.Object]:
    meshes = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if obj.name in HELPER_MESH_NAMES or obj.name.startswith("VTA vertices"):
            continue
        meshes.append(obj)
    meshes.sort(key=lambda obj: obj.name.lower())
    return meshes


def find_named_mesh(name: str) -> bpy.types.Object | None:
    exact = bpy.data.objects.get(name)
    if exact is not None and exact.type == "MESH":
        return exact
    wanted = name.casefold()
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name.split(".")[0].casefold() == wanted:
            return obj
    return None


def fix_face_basis_stacking(threshold: float = 1.0e-6, move_step: float = 7.5e-6) -> dict[str, object]:
    face = find_named_mesh("Face")
    if face is None:
        return {"face_object": "", "moved_vertex_count": 0, "duplicate_cluster_count": 0, "warnings": ["Face object not found."]}

    mesh = face.data
    key_blocks = list(mesh.shape_keys.key_blocks) if mesh.shape_keys else []
    basis = mesh.shape_keys.key_blocks.get("Basis") if mesh.shape_keys else None
    if basis is None and key_blocks:
        basis = key_blocks[0]

    def vertex_co(index: int) -> Vector:
        if basis is not None:
            return basis.data[index].co.copy()
        return mesh.vertices[index].co.copy()

    buckets: dict[tuple[int, int, int], list[int]] = {}
    for vertex in mesh.vertices:
        co = vertex_co(vertex.index)
        key = (round(co.x / threshold), round(co.y / threshold), round(co.z / threshold))
        buckets.setdefault(key, []).append(vertex.index)

    moved = 0
    clusters: list[dict[str, object]] = []
    max_movement = 0.0
    for indices in buckets.values():
        if len(indices) < 2:
            continue
        indices = sorted(indices)
        cluster_record = {"kept_vertex": indices[0], "moved_vertices": []}
        for order, vertex_index in enumerate(indices[1:], start=1):
            angle = order * 2.399963229728653
            radius = move_step * (1.0 + 0.35 * (order % 5))
            delta = Vector((math.cos(angle) * radius, math.sin(angle) * radius, move_step * 0.25 * ((order % 3) - 1)))
            if key_blocks:
                for key_block in key_blocks:
                    key_block.data[vertex_index].co += delta
            else:
                mesh.vertices[vertex_index].co += delta
            moved += 1
            max_movement = max(max_movement, float(delta.length))
            cluster_record["moved_vertices"].append({"index": vertex_index, "offset": [delta.x, delta.y, delta.z]})
        clusters.append(cluster_record)

    if moved:
        mesh.update()
    log(f"Face Basis stacking check moved {moved} duplicate vertex/vertices across {len(clusters)} cluster(s).")
    return {
        "face_object": face.name,
        "threshold": threshold,
        "move_step": move_step,
        "moved_vertex_count": moved,
        "duplicate_cluster_count": len(clusters),
        "max_movement": max_movement,
        "clusters": clusters[:200],
    }


def prepare_armature_for_raw_export(armature: bpy.types.Object) -> dict[str, object]:
    log(f"Preparing armature for raw Source export: {armature.name}")
    unhide_object(armature)
    set_active_only(armature)
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = armature.data.edit_bones
    for bone in edit_bones:
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
    before_connected = sum(1 for bone in edit_bones if bone.use_connect)
    try:
        bpy.ops.armature.parent_clear(type="DISCONNECT")
    except Exception as exc:
        log(f"Armature DISCONNECT operator warning: {exc}")
        for bone in edit_bones:
            bone.use_connect = False
    after_connected = sum(1 for bone in edit_bones if bone.use_connect)

    pelvis = edit_bones.get("ValveBiped.Bip01_Pelvis")
    if pelvis is None:
        bpy.ops.object.mode_set(mode="OBJECT")
        raise RuntimeError('Required pelvis bone "ValveBiped.Bip01_Pelvis" was not found.')
    pelvis_direction = pelvis.tail - pelvis.head
    if pelvis_direction.length < 1.0e-6:
        pelvis_direction = Vector((0.0, 0.0, 1.0))
    pelvis_direction.normalize()
    rotated_direction = Matrix.Rotation(math.radians(90.0), 4, "X") @ pelvis_direction
    if rotated_direction.length < 1.0e-6:
        rotated_direction = Vector((0.0, -1.0, 0.0))
    rotated_direction.normalize()
    target_nonessential_roll = normalize_roll_radians(float(pelvis.roll) + NONESSENTIAL_EXPORT_ROLL_OFFSET_RADIANS)

    modified: list[str] = []
    protected: list[str] = []
    for bone in edit_bones:
        if is_essential_bone(bone.name):
            protected.append(bone.name)
            continue
        length = max(float((bone.tail - bone.head).length), 0.001)
        bone.tail = bone.head + rotated_direction * length
        try:
            bone.roll = target_nonessential_roll
        except Exception:
            pass
        modified.append(bone.name)
    bpy.ops.object.mode_set(mode="OBJECT")
    log(
        f"Protected {len(protected)} essential bone(s); aligned/rotated {len(modified)} non-essential bone(s) "
        f"with roll {math.degrees(target_nonessential_roll):.3f} degrees."
    )
    return {
        "armature": armature.name,
        "connected_bones_before": before_connected,
        "connected_bones_after": after_connected,
        "protected_bones": len(protected),
        "modified_nonessential_bones": len(modified),
        "nonessential_roll_offset_degrees": round(math.degrees(NONESSENTIAL_EXPORT_ROLL_OFFSET_RADIANS), 6),
        "target_nonessential_roll_degrees": round(math.degrees(target_nonessential_roll), 6),
        "modified_bone_names": modified[:500],
    }


def vertex_group_weight(vertex: bpy.types.MeshVertex, group_index: int) -> float:
    for group in vertex.groups:
        if group.group == group_index:
            return float(group.weight)
    return 0.0


def remove_zero_weight_nonessential_bones(armature: bpy.types.Object, threshold: float = 1.0e-6) -> dict[str, object]:
    meshes = visible_export_meshes()
    bone_names = [bone.name for bone in armature.data.bones]
    weighted_bones: set[str] = set()
    scanned_groups = 0

    log(f"Checking {len(bone_names)} bone(s) for zero-weight non-essential cleanup across {len(meshes)} exported mesh(es).")
    for obj in meshes:
        mesh = obj.data
        for vertex_group in obj.vertex_groups:
            if vertex_group.name in weighted_bones:
                continue
            scanned_groups += 1
            group_index = vertex_group.index
            if any(vertex_group_weight(vertex, group_index) > threshold for vertex in mesh.vertices):
                weighted_bones.add(vertex_group.name)

    to_remove = [
        name
        for name in bone_names
        if not is_essential_bone(name) and name not in weighted_bones
    ]
    remove_set = set(to_remove)
    parent_before = {bone.name: bone.parent.name if bone.parent else None for bone in armature.data.bones}

    def surviving_parent_name(name: str) -> str | None:
        parent_name = parent_before.get(name)
        visited: set[str] = set()
        while parent_name and parent_name in remove_set and parent_name not in visited:
            visited.add(parent_name)
            parent_name = parent_before.get(parent_name)
        return parent_name if parent_name and parent_name in bone_names and parent_name not in remove_set else None

    reparented: list[dict[str, object]] = []
    if to_remove:
        set_active_only(armature)
        bpy.ops.object.mode_set(mode="EDIT")
        edit_bones = armature.data.edit_bones
        for name in to_remove:
            bone = edit_bones.get(name)
            if bone is None:
                continue
            new_parent = edit_bones.get(surviving_parent_name(name) or "")
            children = [child for child in edit_bones if child.parent == bone]
            for child in children:
                old_use_connect = bool(child.use_connect)
                child.parent = new_parent
                child.use_connect = False
                reparented.append(
                    {
                        "child": child.name,
                        "removed_parent": name,
                        "new_parent": new_parent.name if new_parent else "",
                        "was_connected": old_use_connect,
                    }
                )
            edit_bones.remove(bone)
        bpy.ops.object.mode_set(mode="OBJECT")

        removed_groups = 0
        for obj in meshes:
            for name in to_remove:
                group = obj.vertex_groups.get(name)
                if group is not None:
                    obj.vertex_groups.remove(group)
                    removed_groups += 1
    else:
        removed_groups = 0

    log(
        f"Zero-weight cleanup removed {len(to_remove)} non-essential bone(s), "
        f"reparented {len(reparented)} child bone link(s), and removed {removed_groups} empty vertex group(s)."
    )
    return {
        "enabled": True,
        "threshold": threshold,
        "exported_mesh_count": len(meshes),
        "scanned_bone_count": len(bone_names),
        "scanned_vertex_group_count": scanned_groups,
        "weighted_bone_count": len(weighted_bones),
        "removed_bone_count": len(to_remove),
        "removed_vertex_group_count": removed_groups,
        "reparented_child_count": len(reparented),
        "removed_bones": to_remove[:1000],
        "reparented_children": reparented[:1000],
        "protected_essential_bone_count": sum(1 for name in bone_names if is_essential_bone(name)),
    }


def enforce_single_physics_group(obj: bpy.types.Object, group_name: str, threshold: float = 0.001) -> int:
    group = obj.vertex_groups.get(group_name)
    if group is None:
        return 0
    group_by_index = {vertex_group.index: vertex_group for vertex_group in obj.vertex_groups}
    repaired = 0
    mesh = obj.data
    for vertex in mesh.vertices:
        if vertex_group_weight(vertex, group.index) <= threshold:
            continue
        for assignment in list(vertex.groups):
            if assignment.group in group_by_index and assignment.group != group.index:
                other_group = group_by_index[assignment.group]
                other_group.remove([vertex.index])
                repaired += 1
        group.add([vertex.index], 1.0, "REPLACE")
    return repaired


def simplify_physics_for_source_compile(distance: float = PHYSICS_MERGE_DISTANCE) -> dict[str, object]:
    physics = find_named_mesh("Physics")
    if physics is None:
        return {
            "physics_object": "",
            "merge_distance": distance,
            "processed_groups": [],
            "warnings": ["Physics object not found; no collision simplification was applied."],
        }

    log(f"Simplifying Physics collision mesh per bone with merge distance {distance:.3f} meter(s).")
    set_active_only(physics)
    mesh = physics.data
    before_total = len(mesh.vertices)
    processed_groups: list[dict[str, object]] = []
    total_removed = 0
    total_repaired = 0

    for vertex_group in list(physics.vertex_groups):
        ensure_object_mode()
        mesh.update()
        selected_vertices = [
            vertex.index
            for vertex in mesh.vertices
            if vertex_group_weight(vertex, vertex_group.index) > 0.001
        ]
        if len(selected_vertices) < 2:
            continue

        group_before_total = len(mesh.vertices)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        selected_vertex_set = set(selected_vertices)
        for vertex in mesh.vertices:
            vertex.select = vertex.index in selected_vertex_set
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            result = bpy.ops.mesh.remove_doubles(threshold=distance)
        except Exception as exc:
            bpy.ops.object.mode_set(mode="OBJECT")
            processed_groups.append(
                {
                    "bone": vertex_group.name,
                    "selected_vertices": len(selected_vertices),
                    "removed_vertices": 0,
                    "warning": f"merge-by-distance failed: {exc}",
                }
            )
            log(f"Physics simplification warning for {vertex_group.name}: {exc}")
            continue
        bpy.ops.object.mode_set(mode="OBJECT")
        mesh.update()

        group_after_total = len(mesh.vertices)
        removed = max(0, group_before_total - group_after_total)
        repaired = enforce_single_physics_group(physics, vertex_group.name)
        total_removed += removed
        total_repaired += repaired
        processed_groups.append(
            {
                "bone": vertex_group.name,
                "selected_vertices_before": len(selected_vertices),
                "mesh_vertices_before": group_before_total,
                "mesh_vertices_after": group_after_total,
                "removed_vertices": removed,
                "weight_repairs": repaired,
                "operator_result": sorted(result) if isinstance(result, set) else str(result),
            }
        )
        log(
            f"Physics merge {vertex_group.name}: selected {len(selected_vertices)} vertex/vertices, "
            f"removed {removed}."
        )

    ensure_object_mode()
    set_active_only(physics)
    mesh.update()
    after_total = len(mesh.vertices)
    log(f"Physics simplification removed {total_removed} vertex/vertices total ({before_total} -> {after_total}).")
    return {
        "physics_object": physics.name,
        "merge_distance": distance,
        "vertices_before": before_total,
        "vertices_after": after_total,
        "removed_vertices": max(0, before_total - after_total),
        "processed_group_count": len(processed_groups),
        "processed_groups": processed_groups,
        "weight_repairs": total_repaired,
    }


def configure_source_export(export_dir: Path, processed: bool = False) -> None:
    if not enable_source_tools():
        raise RuntimeError("Blender Source Tools is required for Step 9 export.")
    scene = bpy.context.scene
    scene.vs.export_format = "SMD"
    scene.vs.smd_format = "SOURCE"
    scene.vs.qc_compile = False
    scene.vs.export_path = str(export_dir.resolve())

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
                if processed:
                    obj.vs.export = obj.name in {"proportions", "reference_male", "reference_female"}
                    obj.vs.subdir = "anims"
                    if hasattr(obj.data, "vs"):
                        obj.data.vs.action_selection = "CURRENT"
                else:
                    obj.vs.export = False
                    obj.vs.subdir = "."
            else:
                obj.vs.export = False
        except Exception:
            pass
    source_tools_state_update()


def export_source_files(export_dir: Path, processed: bool = False) -> list[Path]:
    clean_directory(export_dir)
    configure_source_export(export_dir, processed=processed)
    log(f"Exporting {'final' if processed else 'raw'} Source files to {export_dir}")
    result = bpy.ops.export_scene.smd(export_scene=True)
    if result != {"FINISHED"}:
        raise RuntimeError(f"Source export failed: {result}")
    exported = sorted(path for path in export_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".smd", ".vta"})
    if not exported:
        raise RuntimeError(f"Source export did not write any SMD/VTA files under {export_dir}")
    log(f"Exported {len(exported)} Source file(s).")
    return exported


def raw_smds(raw_dir: Path) -> list[Path]:
    return sorted(raw_dir.glob("*.smd"), key=lambda path: path.name.lower())


def select_primary_raw_smd(raw_dir: Path) -> Path:
    smd_paths = raw_smds(raw_dir)
    if not smd_paths:
        raise RuntimeError(f"Raw export did not write any top-level SMD files under {raw_dir}")
    for smd_path in smd_paths:
        if smd_path.name.casefold() == "face.smd":
            return smd_path
    return smd_paths[0]


def import_raw_smds(raw_dir: Path) -> dict[str, object]:
    primary_smd = select_primary_raw_smd(raw_dir)
    log(f"Importing primary raw SMD first: {primary_smd}")
    bpy.ops.import_scene.smd(filepath=str(primary_smd), append="NEW_ARMATURE", upAxis="Z")
    imported_armatures = [
        obj
        for obj in bpy.data.objects
        if obj.type == "ARMATURE" and obj.name not in {"proportions", "reference_female", "reference_male"}
    ]
    if not imported_armatures:
        raise RuntimeError(f"Primary raw SMD import did not create an imported model armature: {primary_smd.name}")
    gg = imported_armatures[0]
    gg.name = "gg"
    gg.data.name = "gg"

    imported_smds = [primary_smd.name]
    for smd_path in raw_smds(raw_dir):
        if smd_path == primary_smd:
            continue
        log(f"Importing raw SMD with VALIDATE: {smd_path.name}")
        set_active_only(gg)
        bpy.ops.import_scene.smd(filepath=str(smd_path), append="VALIDATE", upAxis="Z")
        imported_smds.append(smd_path.name)
    return {"armature": gg.name, "primary_smd": primary_smd.name, "imported_smds": imported_smds}


def import_raw_vtas(raw_dir: Path) -> list[dict[str, object]]:
    raw_vtas = sorted(raw_dir.glob("*.vta"), key=lambda path: path.name.lower())
    if not raw_vtas:
        log("No raw VTA files were exported; skipping VTA import into the proportion workspace.")
        return []
    log(
        "Skipping raw VTA import into Blender; "
        f"{len(raw_vtas)} raw VTA file(s) will be copied into the final proportion export."
    )
    return [
        {
            "file": path.name,
            "target": path.stem,
            "imported": False,
            "skipped": True,
            "copy_to_final": True,
            "reason": "raw VTA is not needed for the proportion trick; final export uses the copied raw VTA",
        }
        for path in raw_vtas
    ]


def run_proportion_text_block() -> None:
    text = bpy.data.texts.get(PROPORTION_TEXT_BLOCK)
    if text is None:
        raise RuntimeError(f'Text block "{PROPORTION_TEXT_BLOCK}" was not found in the proportion template.')
    log(f"Running {PROPORTION_TEXT_BLOCK}.")
    exec(text.as_string(), {"__name__": "__main__"})


def verify_processed_scene() -> dict[str, object]:
    prop = bpy.data.objects.get("proportions")
    if prop is None or prop.type != "ARMATURE":
        raise RuntimeError('Processed scene is missing armature "proportions".')
    if not enable_source_tools():
        raise RuntimeError("Blender Source Tools is unavailable while verifying the processed scene.")
    bad_modifiers: list[str] = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.name in HELPER_MESH_NAMES or obj.name.startswith("VTA vertices"):
            continue
        armature_mod = next((mod for mod in obj.modifiers if mod.type == "ARMATURE"), None)
        if armature_mod is None or armature_mod.object != prop:
            bad_modifiers.append(obj.name)
    if bad_modifiers:
        raise RuntimeError("Meshes not retargeted to proportions: " + ", ".join(bad_modifiers[:30]))

    remaining_constraints = [
        f"{pose_bone.name}:{constraint.name}"
        for pose_bone in prop.pose.bones
        for constraint in pose_bone.constraints
        if constraint.name.startswith("PT_")
    ]
    if remaining_constraints:
        raise RuntimeError("PT constraints were not cleared: " + ", ".join(remaining_constraints[:30]))

    scene = bpy.context.scene
    source_settings = {
        "export_format": str(getattr(scene.vs, "export_format", "")),
        "smd_format": str(getattr(scene.vs, "smd_format", "")),
        "qc_compile": bool(getattr(scene.vs, "qc_compile", True)),
        "export_path": str(getattr(scene.vs, "export_path", "")),
    }
    if source_settings["export_format"] != "SMD" or source_settings["smd_format"] != "SOURCE" or source_settings["qc_compile"]:
        raise RuntimeError(f"Processed scene has invalid Source Tools export settings: {source_settings}")

    shape_counts = {
        obj.name: len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.name not in HELPER_MESH_NAMES and not obj.name.startswith("VTA vertices")
    }
    return {
        "proportions_bone_count": len(prop.data.bones),
        "bad_modifier_count": len(bad_modifiers),
        "pt_constraint_count": len(remaining_constraints),
        "source_tools_settings": source_settings,
        "shape_key_counts": shape_counts,
    }


def validate_final_export(raw_dir: Path, final_dir: Path) -> dict[str, object]:
    exported = sorted(path for path in final_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".smd", ".vta"})
    if not exported:
        raise RuntimeError(f"Final proportion export did not write any SMD/VTA files under {final_dir}")
    raw_top_level_smds = {path.name for path in raw_dir.glob("*.smd")}
    final_top_level_smds = {path.name for path in final_dir.glob("*.smd")}
    missing_top_level = sorted(raw_top_level_smds - final_top_level_smds)
    if missing_top_level:
        raise RuntimeError("Final proportion export missed top-level SMD file(s): " + ", ".join(missing_top_level))
    raw_top_level_vtas = {path.name for path in raw_dir.glob("*.vta")}
    final_top_level_vtas = {path.name for path in final_dir.glob("*.vta")}
    missing_vtas = sorted(raw_top_level_vtas - final_top_level_vtas)
    if missing_vtas:
        raise RuntimeError("Final proportion export missed raw VTA file(s): " + ", ".join(missing_vtas))
    missing_anims = sorted(str(path) for path in EXPECTED_PROPORTION_ANIMS if not (final_dir / path).exists())
    if missing_anims:
        raise RuntimeError("Final proportion export missed required animation SMD file(s): " + ", ".join(missing_anims))
    return {
        "file_count": len(exported),
        "top_level_smd_count": len(final_top_level_smds),
        "top_level_vta_count": len(final_top_level_vtas),
        "animation_smds": sorted(str(path) for path in EXPECTED_PROPORTION_ANIMS),
        "missing_top_level_smds": [],
        "missing_top_level_vtas": [],
        "missing_animation_smds": [],
    }


def write_fresh_session_verifier(script_path: Path, export_dir: Path, report_path: Path) -> None:
    script_path.write_text(
        f"""
import json
import shutil
import sys
from pathlib import Path

import bpy

EXPORT_DIR = Path({str(export_dir)!r})
REPORT_PATH = Path({str(report_path)!r})
PROPORTION_ROOT = Path({str(PROPORTION_ROOT)!r})
HELPER_MESH_NAMES = {sorted(HELPER_MESH_NAMES)!r}
EXPECTED_ANIMS = {sorted(str(path) for path in EXPECTED_PROPORTION_ANIMS)!r}


def enable_source_tools():
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_valvesource")
        bpy.ops.export_scene.smd.get_rna_type()
        return
    except Exception:
        pass
    addon_dirs = [
        Path(bpy.app.binary_path).resolve().parent / "4.5" / "scripts" / "addons",
    ]
    user_dir = bpy.utils.user_resource("SCRIPTS", path="addons", create=False)
    if user_dir:
        addon_dirs.append(Path(user_dir))
    for addon_dir in addon_dirs:
        if addon_dir.exists() and str(addon_dir) not in sys.path:
            sys.path.insert(0, str(addon_dir))
    import io_scene_valvesource
    io_scene_valvesource.register()
    bpy.ops.export_scene.smd.get_rna_type()


def configure_export():
    scene = bpy.context.scene
    scene.vs.export_format = "SMD"
    scene.vs.smd_format = "SOURCE"
    scene.vs.qc_compile = False
    scene.vs.export_path = str(EXPORT_DIR)
    for collection in bpy.data.collections:
        try:
            collection.hide_viewport = False
            collection.vs.mute = True
        except Exception:
            pass
    for obj in scene.objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        try:
            if obj.type == "MESH":
                obj.vs.export = obj.name not in HELPER_MESH_NAMES and not obj.name.startswith("VTA vertices")
                obj.vs.subdir = "."
            elif obj.type == "ARMATURE":
                obj.vs.export = obj.name in {{"proportions", "reference_male", "reference_female"}}
                obj.vs.subdir = "anims"
                if hasattr(obj.data, "vs"):
                    obj.data.vs.action_selection = "CURRENT"
            else:
                obj.vs.export = False
        except Exception:
            pass


def verify_scene():
    prop = bpy.data.objects.get("proportions")
    if prop is None or prop.type != "ARMATURE":
        raise RuntimeError('Processed scene is missing armature "proportions".')
    constraints = [
        f"{{pose_bone.name}}:{{constraint.name}}"
        for pose_bone in prop.pose.bones
        for constraint in pose_bone.constraints
        if constraint.name.startswith("PT_")
    ]
    if constraints:
        raise RuntimeError("PT constraints remain after reopening: " + ", ".join(constraints[:30]))
    bad_modifiers = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.name in HELPER_MESH_NAMES or obj.name.startswith("VTA vertices"):
            continue
        armature_mod = next((mod for mod in obj.modifiers if mod.type == "ARMATURE"), None)
        if armature_mod is None or armature_mod.object != prop:
            bad_modifiers.append(obj.name)
    if bad_modifiers:
        raise RuntimeError("Meshes not retargeted to proportions after reopening: " + ", ".join(bad_modifiers[:30]))
    return {{"proportions_bone_count": len(prop.data.bones), "mesh_count": len([obj for obj in bpy.context.scene.objects if obj.type == "MESH"])}}


enable_source_tools()
verification = verify_scene()
if EXPORT_DIR.exists():
    shutil.rmtree(EXPORT_DIR)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
configure_export()
result = bpy.ops.export_scene.smd(export_scene=True)
if result != {{"FINISHED"}}:
    raise RuntimeError(f"Fresh-session Source export failed: {{result}}")
files = sorted(path for path in EXPORT_DIR.rglob("*") if path.is_file() and path.suffix.lower() in {{".smd", ".vta"}})
missing_anims = [name for name in EXPECTED_ANIMS if not (EXPORT_DIR / name).exists()]
if missing_anims:
    raise RuntimeError("Fresh-session export missed required animation SMD file(s): " + ", ".join(missing_anims))
REPORT_PATH.write_text(json.dumps({{
    "ok": True,
    "export_dir": str(EXPORT_DIR),
    "file_count": len(files),
    "verification": verification,
    "files": [str(path.relative_to(EXPORT_DIR)) for path in files],
}}, ensure_ascii=False, indent=2), encoding="utf-8")
print("Fresh-session Step 9 verification passed.")
""".lstrip(),
        encoding="utf-8",
    )


def run_fresh_session_verification(processed_blend: Path, workspace_dir: Path) -> dict[str, object]:
    verify_dir = workspace_dir / "fresh_session_verify_export"
    verify_script = workspace_dir / "fresh_session_verify_processed.py"
    verify_report = workspace_dir / "fresh_session_verify_report.json"
    verify_log = workspace_dir / "fresh_session_verify.log"
    write_fresh_session_verifier(verify_script, verify_dir, verify_report)
    command = [
        bpy.app.binary_path,
        "--factory-startup",
        "--background",
        str(processed_blend),
        "--python",
        str(verify_script),
    ]
    log("Running fresh-session processed blend verification.")
    completed = subprocess.run(
        command,
        cwd=str(PROPORTION_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        **hidden_subprocess_kwargs(),
    )
    verify_log.write_text(completed.stdout or "", encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"Fresh-session processed blend verification failed; see {verify_log}")
    if not verify_report.exists():
        raise RuntimeError(f"Fresh-session processed blend verification did not write {verify_report}")
    report = json.loads(verify_report.read_text(encoding="utf-8"))
    report["log"] = str(verify_log)
    report["script"] = str(verify_script)
    return report


def replace_final_vtas(raw_dir: Path, final_dir: Path) -> list[dict[str, object]]:
    log("Copying raw VTA files into the final proportion export.")
    actions: list[dict[str, object]] = []
    raw_vtas = {
        path.name: path
        for path in sorted(raw_dir.glob("*.vta"), key=lambda path: path.name.lower())
    }
    keep_names = set(raw_vtas)
    for vta_path in sorted(final_dir.rglob("*.vta"), key=lambda path: path.name.lower()):
        if vta_path.name not in keep_names:
            vta_path.unlink()
            actions.append({"file": vta_path.name, "action": "deleted", "reason": "no matching raw VTA was exported"})

    for name in sorted(keep_names):
        raw = raw_vtas[name]
        final = final_dir / name
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(raw, final)
        actions.append({"file": name, "action": "raw_vta_copied", "raw_path": str(raw), "final_path": str(final)})
    if not keep_names:
        actions.append({"file": "", "action": "none", "warning": "no raw VTA files were exported"})
    return actions


def file_inventory(final_dir: Path, vta_actions: list[dict[str, object]]) -> list[dict[str, object]]:
    stage_by_name = {
        str(action.get("file")): str(action.get("action"))
        for action in vta_actions
        if str(action.get("action")) in {"raw_vta_copied", "raw_vta_replaced", "kept_final"}
    }
    warning_by_name = {
        str(action.get("file")): str(action.get("warning") or "")
        for action in vta_actions
        if str(action.get("warning") or "")
    }
    files: list[dict[str, object]] = []
    for path in sorted(final_dir.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower().lstrip(".")
        if suffix not in {"smd", "vta", "qc"}:
            continue
        files.append(
            {
                "name": path.name,
                "relative_path": str(path.relative_to(final_dir)),
                "path": str(path),
                "type": suffix.upper(),
                "size": path.stat().st_size,
                "source_stage": "raw_vta_copied" if stage_by_name.get(path.name) in {"raw_vta_copied", "raw_vta_replaced"} else "proportion",
                "warnings": warning_by_name.get(path.name, ""),
            }
        )
    return files


def run(args: argparse.Namespace) -> dict[str, object]:
    input_blend = Path(args.input_blend).resolve()
    raw_dir = Path(args.raw_dir).resolve()
    workspace_dir = Path(args.workspace_dir).resolve()
    final_dir = Path(args.final_dir).resolve()
    pre_blend = Path(args.pre_blend).resolve()
    processed_blend = Path(args.processed_blend).resolve()
    report_json = Path(args.report_json).resolve()
    files_json = Path(args.files_json).resolve()

    if not input_blend.exists():
        raise FileNotFoundError(input_blend)
    if not PROPORTION_TEMPLATE.exists():
        raise FileNotFoundError(PROPORTION_TEMPLATE)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    log(f"Opening collision-sorted blend: {input_blend}")
    bpy.ops.wm.open_mainfile(filepath=str(input_blend))
    unhide_all_export_objects()
    armature = main_armature()

    log("Pre-processing Face Basis vertices and armature export orientation.")
    face_report = fix_face_basis_stacking()
    if getattr(args, "remove_zero_weight_bones", False):
        zero_weight_bone_report = remove_zero_weight_nonessential_bones(armature)
    else:
        log("Zero-weight non-essential bone cleanup is disabled for this Step 9 run.")
        zero_weight_bone_report = {"enabled": False, "removed_bone_count": 0, "removed_bones": []}
    armature_report = prepare_armature_for_raw_export(armature)
    physics_simplification_report = simplify_physics_for_source_compile()

    log(f"Saving prepared pre-proportion blend: {pre_blend}")
    pre_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(pre_blend))

    raw_files = export_source_files(raw_dir, processed=False)
    raw_top_level_smds = raw_smds(raw_dir)
    if not raw_top_level_smds:
        raise RuntimeError(f"Raw export did not write any top-level SMD files under {raw_dir}")

    log(f"Opening proportion trick template: {PROPORTION_TEMPLATE}")
    bpy.ops.wm.open_mainfile(filepath=str(PROPORTION_TEMPLATE))
    log("Repairing proportion template collection and object visibility.")
    unhide_all_export_objects()
    if not enable_source_tools():
        raise RuntimeError("Blender Source Tools is required inside the proportion template.")
    import_report = import_raw_smds(raw_dir)
    vta_import_report = import_raw_vtas(raw_dir)

    log(f"Saving imported proportion workspace: {processed_blend}")
    processed_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(processed_blend))

    run_proportion_text_block()
    processed_verification = verify_processed_scene()

    final_files_before_vta = export_source_files(final_dir, processed=True)
    log(f"Saving proportion processed blend: {processed_blend}")
    bpy.ops.wm.save_as_mainfile(filepath=str(processed_blend))
    fresh_session_verification = run_fresh_session_verification(processed_blend, workspace_dir)

    vta_actions = replace_final_vtas(raw_dir, final_dir)
    files = file_inventory(final_dir, vta_actions)
    final_export_validation = validate_final_export(raw_dir, final_dir)
    files_json.parent.mkdir(parents=True, exist_ok=True)
    files_json.write_text(json.dumps({"files": files}, ensure_ascii=False, indent=2), encoding="utf-8")

    if not any(file.get("type") == "SMD" for file in files):
        raise RuntimeError("Final proportion export did not produce any SMD files.")

    report = {
        "input_blend": str(input_blend),
        "proportion_package": str(PROPORTION_ROOT),
        "proportion_template": str(PROPORTION_TEMPLATE),
        "proportion_text_block": PROPORTION_TEXT_BLOCK,
        "pre_blend": str(pre_blend),
        "processed_blend": str(processed_blend),
        "raw_dir": str(raw_dir),
        "workspace_dir": str(workspace_dir),
        "final_dir": str(final_dir),
        "face_basis_stacking": face_report,
        "zero_weight_bone_cleanup": zero_weight_bone_report,
        "armature_preparation": armature_report,
        "physics_simplification": physics_simplification_report,
        "raw_export": {
            "file_count": len(raw_files),
            "files": [str(path.relative_to(raw_dir)) for path in raw_files],
        },
        "proportion_import": import_report,
        "vta_import": vta_import_report,
        "processed_scene_verification": processed_verification,
        "fresh_session_verification": fresh_session_verification,
        "final_export_before_vta_replacement": {
            "file_count": len(final_files_before_vta),
            "files": [str(path.relative_to(final_dir)) for path in final_files_before_vta],
        },
        "final_export_validation": final_export_validation,
        "vta_replacement": vta_actions,
        "final_files": files,
        "validation": {"ok": True, "errors": [], "warnings": []},
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Wrote proportion export report: {report_json}")
    log(f"Wrote proportion export file list: {files_json}")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-blend", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--workspace-dir", required=True)
    parser.add_argument("--final-dir", required=True)
    parser.add_argument("--pre-blend", required=True)
    parser.add_argument("--processed-blend", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--files-json", required=True)
    parser.add_argument("--remove-zero-weight-bones", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    run(parse_args(argv))
    return 0


if __name__ == "__main__":
    args_after_dash = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    raise SystemExit(main(args_after_dash))
