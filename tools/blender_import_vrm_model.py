#!/usr/bin/env python3
"""Blender-side step 1 VRM import helper."""

from __future__ import annotations

import argparse
import functools
import json
import math
import re
import shutil
import struct
import sys
import time
from pathlib import Path

import bpy
from mathutils import Matrix

print = functools.partial(print, flush=True)


VRM_REQUIRED_HUMANOID_BONES = (
    "hips",
    "spine",
    "head",
    "leftUpperArm",
    "leftLowerArm",
    "leftHand",
    "leftUpperLeg",
    "leftLowerLeg",
    "leftFoot",
    "rightUpperArm",
    "rightLowerArm",
    "rightHand",
    "rightUpperLeg",
    "rightLowerLeg",
    "rightFoot",
)

# Humanoid slot -> CATS standard bone name expected by cats_manual.convert_to_valve.
HUMANOID_TO_CATS_COMMON = {
    "hips": "Hips",
    "spine": "Spine",
    "chest": "Chest",
    "upperChest": "Upper Chest",
    "neck": "Neck",
    "head": "Head",
    "leftEye": "Eye_L",
    "rightEye": "Eye_R",
    "leftShoulder": "Left shoulder",
    "leftUpperArm": "Left arm",
    "leftLowerArm": "Left elbow",
    "leftHand": "Left wrist",
    "rightShoulder": "Right shoulder",
    "rightUpperArm": "Right arm",
    "rightLowerArm": "Right elbow",
    "rightHand": "Right wrist",
    "leftUpperLeg": "Left leg",
    "leftLowerLeg": "Left knee",
    "leftFoot": "Left ankle",
    "leftToes": "Left toe",
    "rightUpperLeg": "Right leg",
    "rightLowerLeg": "Right knee",
    "rightFoot": "Right ankle",
    "rightToes": "Right toe",
}

FINGER_SLOT_NAMES = {
    "Thumb": ("Thumb0_{side}", "Thumb1_{side}", "Thumb2_{side}"),
    "Index": ("IndexFinger1_{side}", "IndexFinger2_{side}", "IndexFinger3_{side}"),
    "Middle": ("MiddleFinger1_{side}", "MiddleFinger2_{side}", "MiddleFinger3_{side}"),
    "Ring": ("RingFinger1_{side}", "RingFinger2_{side}", "RingFinger3_{side}"),
    "Little": ("LittleFinger1_{side}", "LittleFinger2_{side}", "LittleFinger3_{side}"),
}


def humanoid_to_cats_map(vrm_version: str) -> dict[str, str]:
    mapping = dict(HUMANOID_TO_CATS_COMMON)
    is_vrm1 = vrm_version.startswith("1")
    for side_slot, side in (("left", "L"), ("right", "R")):
        for finger, targets in FINGER_SLOT_NAMES.items():
            if finger == "Thumb":
                # VRM 1.0 renamed the thumb chain to metacarpal/proximal/distal.
                if is_vrm1:
                    segments = ("ThumbMetacarpal", "ThumbProximal", "ThumbDistal")
                else:
                    segments = ("ThumbProximal", "ThumbIntermediate", "ThumbDistal")
            else:
                segments = (f"{finger}Proximal", f"{finger}Intermediate", f"{finger}Distal")
            for segment, target in zip(segments, targets):
                mapping[f"{side_slot}{segment}"] = target.format(side=side)
    return mapping


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vrm", type=Path, required=True)
    parser.add_argument("--output-blend", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--textures-dir", type=Path, default=None)
    return parser.parse_args(argv)


def operator_keywords(operator, desired: dict[str, object]) -> dict[str, object]:
    try:
        props = {prop.identifier for prop in operator.get_rna_type().properties}
    except Exception:
        return desired
    return {key: value for key, value in desired.items() if key in props}


def call_operator(operator, **desired):
    kwargs = operator_keywords(operator, desired)
    try:
        result = operator(**kwargs)
    except Exception as exc:
        raise RuntimeError(f"{operator.idname()} failed with arguments {sorted(kwargs)}: {exc}") from exc
    if isinstance(result, set) and "CANCELLED" in result:
        raise RuntimeError(f"{operator.idname()} was cancelled by Blender")
    return result


def read_glb_json(path: Path) -> dict:
    with path.open("rb") as handle:
        header = handle.read(12)
        if len(header) < 12 or header[:4] != b"glTF":
            raise ValueError(f"not a GLB/VRM file: invalid magic in {path}")
        while True:
            chunk_header = handle.read(8)
            if len(chunk_header) < 8:
                break
            chunk_length, chunk_type = struct.unpack("<I4s", chunk_header)
            chunk_data = handle.read(chunk_length)
            if len(chunk_data) < chunk_length:
                raise ValueError(f"truncated GLB chunk in {path}")
            if chunk_type == b"JSON":
                return json.loads(chunk_data.decode("utf-8"))
    raise ValueError(f"no JSON chunk found in GLB/VRM file: {path}")


def vrm_extension_info(gltf: dict) -> tuple[str, dict, dict[str, int]]:
    extensions = gltf.get("extensions") or {}
    vrm1 = extensions.get("VRMC_vrm")
    if isinstance(vrm1, dict):
        bone_map: dict[str, int] = {}
        human_bones = (vrm1.get("humanoid") or {}).get("humanBones") or {}
        if isinstance(human_bones, dict):
            for slot, info in human_bones.items():
                node = info.get("node") if isinstance(info, dict) else None
                if isinstance(node, int):
                    bone_map[str(slot)] = node
        return str(vrm1.get("specVersion") or "1.0"), vrm1, bone_map
    vrm0 = extensions.get("VRM")
    if isinstance(vrm0, dict):
        bone_map = {}
        entries = (vrm0.get("humanoid") or {}).get("humanBones") or []
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and isinstance(entry.get("node"), int) and entry.get("bone"):
                    bone_map.setdefault(str(entry["bone"]), entry["node"])
        return str(vrm0.get("specVersion") or "0.0"), vrm0, bone_map
    return "", {}, {}


def clear_scene() -> None:
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def setup_scene() -> None:
    scene = bpy.context.scene
    with context_suppressed():
        scene.render.engine = "CYCLES"
        scene.cycles.device = "GPU"
    scene.render.film_transparent = True
    scene.render.resolution_x = 2000
    scene.render.resolution_y = 2000
    world = bpy.data.worlds.get("World")
    if world and world.node_tree:
        background = world.node_tree.nodes.get("Background")
        if background:
            background.inputs[0].default_value = (1, 1, 1, 1)


class context_suppressed:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return exc_type is not None


def ensure_object_mode() -> None:
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")


def select_only(objects: list[bpy.types.Object], active: bpy.types.Object | None = None) -> None:
    ensure_object_mode()
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active or (objects[0] if objects else None)


def armature_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type == "MESH"]


def import_vrm(vrm_path: Path) -> None:
    print(f"Importing VRM with the bundled glTF importer: {vrm_path}")
    try:
        call_operator(bpy.ops.import_scene.gltf, filepath=str(vrm_path))
    except RuntimeError as exc:
        print(f"Direct .vrm import failed ({exc}); retrying through a temporary .glb copy.")
        temp_glb = vrm_path.with_suffix(".import_temp.glb")
        shutil.copyfile(vrm_path, temp_glb)
        try:
            call_operator(bpy.ops.import_scene.gltf, filepath=str(temp_glb))
        finally:
            try:
                temp_glb.unlink()
            except OSError:
                pass
    print(f"Imported VRM: {vrm_path}")


def validate_imported_scene(vrm_path: Path) -> None:
    imported_meshes = mesh_objects()
    imported_armatures = armature_objects()
    vertex_count = sum(len(obj.data.vertices) for obj in imported_meshes)
    if not imported_armatures or not imported_meshes or vertex_count == 0:
        raise RuntimeError(
            f"glTF import produced no usable model from {vrm_path}: "
            f"{len(imported_armatures)} armature(s), {len(imported_meshes)} mesh object(s), {vertex_count} vertices. "
            "The VRM file may be corrupt or unsupported."
        )


def main_armature() -> bpy.types.Object:
    candidates = armature_objects()
    if not candidates:
        raise RuntimeError("No armature found after VRM import.")
    return max(candidates, key=lambda obj: len(obj.data.bones))


def remove_bone_shape_helpers() -> list[str]:
    """Remove display-only custom shape objects the glTF importer assigns to pose bones."""

    shape_objects: set[bpy.types.Object] = set()
    for armature in armature_objects():
        for pose_bone in armature.pose.bones:
            if pose_bone.custom_shape is not None:
                shape_objects.add(pose_bone.custom_shape)
                pose_bone.custom_shape = None
    removed: list[str] = []
    for obj in shape_objects:
        if obj.type == "MESH" and not any(modifier.type == "ARMATURE" for modifier in obj.modifiers):
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    if removed:
        print(f"Removed {len(removed)} bone display shape helper objects: {', '.join(removed)}")
    return removed


def remove_childless_root_empties() -> list[str]:
    removed: list[str] = []
    for obj in list(bpy.data.objects):
        if obj.type == "EMPTY" and obj.parent is None and not obj.children:
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    if removed:
        print(f"Removed {len(removed)} childless root empties: {', '.join(removed)}")
    return removed


def make_single_user() -> None:
    print("Making imported objects and object data single-user.")
    select_only(list(bpy.data.objects))
    call_operator(bpy.ops.object.make_single_user, object=True, obdata=True)


def normalize_scene_orientation(vrm_version: str) -> bool:
    """Parent meshes under the armature and bake object transforms.

    VRM 0.x models face -Z in glTF space and therefore +Y after the Blender glTF
    import; the MMD pipeline expects models facing -Y, so VRM 0.x scenes are
    rotated 180 degrees around Z before the transforms are applied.
    """

    rotate = not vrm_version.startswith("1")
    armature = main_armature()
    meshes = mesh_objects()
    ensure_object_mode()

    parented = [obj for obj in meshes if obj.parent is not None]
    if parented:
        select_only(parented, parented[0])
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.context.view_layer.update()

    if rotate:
        print("Rotating VRM 0.x scene 180 degrees around Z so the model faces -Y like MMD imports.")
        rotation = Matrix.Rotation(math.pi, 4, "Z")
        for obj in [armature] + meshes:
            if obj.parent is None:
                obj.matrix_world = rotation @ obj.matrix_world
        bpy.context.view_layer.update()

    select_only([armature] + meshes, armature)
    call_operator(bpy.ops.object.transform_apply, location=True, rotation=True, scale=True)

    if meshes:
        select_only(meshes + [armature], armature)
        call_operator(bpy.ops.object.parent_set, type="OBJECT", keep_transform=True)
    ensure_object_mode()
    return rotate


def rename_humanoid_bones(
    armature: bpy.types.Object,
    bone_map: dict[str, int],
    gltf: dict,
    vrm_version: str,
) -> tuple[int, list[str]]:
    """Rename humanoid bones to the CATS standard names convert_to_valve expects.

    Renaming armature bones in object mode also renames the matching vertex
    groups on meshes deformed by this armature, so weights stay intact.
    """

    warnings: list[str] = []
    nodes = gltf.get("nodes") or []
    node_names = [str(node.get("name") or "") for node in nodes]
    name_usage: dict[str, int] = {}
    for name in node_names:
        if name:
            name_usage[name] = name_usage.get(name, 0) + 1

    mapping = humanoid_to_cats_map(vrm_version)
    bones = armature.data.bones
    renamed = 0
    for slot, target in mapping.items():
        node_index = bone_map.get(slot)
        if node_index is None:
            continue
        if not (0 <= node_index < len(node_names)):
            warnings.append(f"humanoid slot {slot} points at invalid node index {node_index}; skipped")
            continue
        node_name = node_names[node_index]
        if not node_name:
            warnings.append(f"humanoid slot {slot} points at unnamed node {node_index}; skipped")
            continue
        if name_usage.get(node_name, 0) > 1:
            warnings.append(f"humanoid slot {slot} node name {node_name!r} is duplicated in the VRM; skipped")
            continue
        bone = bones.get(node_name)
        if bone is None:
            warnings.append(f"humanoid slot {slot}: no bone named {node_name!r} on the imported armature; skipped")
            continue
        if bone.name == target:
            renamed += 1
            continue
        squatter = bones.get(target)
        if squatter is not None and squatter != bone:
            print(f"Renaming non-humanoid bone {target!r} to {target + '.vrmold'!r} to free the name.")
            squatter.name = f"{target}.vrmold"
        bone.name = target
        renamed += 1
    print(f"Renamed {renamed} humanoid bones to CATS standard names ({len(warnings)} skipped).")
    for warning in warnings:
        print(f"Warning: {warning}")
    return renamed, warnings


def ensure_upper_chest(armature: bpy.types.Object) -> bool:
    """Create a zero-weight Upper Chest bone when the VRM humanoid has none.

    CATS converts 'Upper Chest' to ValveBiped.Bip01_Spine2 and protects it from
    zero-weight bone cleanup, so the Source spine chain Spine/Spine1/Spine2 is
    complete after step 2. Mirrors the chest creation CATS Fix Model uses.
    """

    bones = armature.data.bones
    if bones.get("Upper Chest") is not None or bones.get("Chest") is None:
        return False
    print("Creating a zero-weight 'Upper Chest' bone to complete the Source spine chain.")
    select_only([armature], armature)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        edit_bones = armature.data.edit_bones
        chest = edit_bones.get("Chest")
        if chest is None:
            return False
        neck = edit_bones.get("Neck")
        chest_top = neck.head.copy() if neck is not None else chest.tail.copy()
        former_children = list(chest.children)
        upper_chest = edit_bones.new("Upper Chest")
        upper_chest.head = chest.head + (chest_top - chest.head) / 2
        upper_chest.tail = chest_top
        if (upper_chest.tail - upper_chest.head).length < 1e-5:
            upper_chest.tail.z = upper_chest.head.z + 0.05
        upper_chest.parent = chest
        chest.tail = upper_chest.head
        for child in former_children:
            child.parent = upper_chest
    finally:
        ensure_object_mode()
    return True


def safe_image_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._-")
    return cleaned[:48] or "image"


def image_extension(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    return ""


def unpack_images(textures_dir: Path) -> tuple[int, list[str]]:
    warnings: list[str] = []
    packed_images = [image for image in bpy.data.images if image.packed_file is not None]
    if not packed_images:
        print("No packed images found to unpack.")
        return 0, warnings
    textures_dir.mkdir(parents=True, exist_ok=True)
    print(f"Unpacking {len(packed_images)} embedded images into {textures_dir}")
    used_names: set[str] = set()
    unpacked = 0
    for index, image in enumerate(packed_images, start=1):
        base_name = f"tex_{index:03d}_{safe_image_name(image.name)}"
        while base_name.lower() in used_names:
            base_name += "_x"
        used_names.add(base_name.lower())
        try:
            data = bytes(image.packed_file.data) if image.packed_file.data else b""
            extension = image_extension(data)
            if data and extension:
                # Write the embedded bytes directly; unpack(WRITE_ORIGINAL) would
                # write to the original packed path instead of the textures dir.
                target = textures_dir / f"{base_name}{extension}"
                target.write_bytes(data)
                image.filepath_raw = str(target)
                image.unpack(method="REMOVE")
            else:
                target = textures_dir / f"{base_name}.png"
                image.filepath_raw = str(target)
                image.file_format = "PNG"
                image.save()
            if not target.exists():
                raise RuntimeError(f"image file was not written: {target}")
            unpacked += 1
        except Exception as exc:
            warnings.append(f"could not unpack image {image.name!r}: {exc}")
            print(f"Warning: could not unpack image {image.name!r}: {exc}")
    print(f"Unpacked {unpacked} images to disk.")
    return unpacked, warnings


def build_report(
    vrm_path: Path,
    output_blend: Path,
    elapsed: float,
    vrm_version: str,
    humanoid_bones_renamed: int,
    rotated_for_vrm0: bool,
    upper_chest_created: bool,
    textures_dir: Path,
    unpacked_image_count: int,
    warnings: list[str],
) -> dict[str, object]:
    meshes = mesh_objects()
    armatures = armature_objects()
    material_names = {
        material.name
        for obj in meshes
        for material in getattr(obj.data, "materials", [])
        if material is not None
    }
    shapekey_count = 0
    for mesh in bpy.data.meshes:
        if mesh.shape_keys:
            shapekey_count += max(0, len(mesh.shape_keys.key_blocks) - 1)

    return {
        "pmx_path": str(vrm_path),
        "vrm_path": str(vrm_path),
        "format": "vrm",
        "vrm_version": vrm_version,
        "humanoid_bones_renamed": humanoid_bones_renamed,
        "rotated_for_vrm0": rotated_for_vrm0,
        "upper_chest_created": upper_chest_created,
        "textures_dir": str(textures_dir),
        "unpacked_image_count": unpacked_image_count,
        "warnings": warnings,
        "output_blend": str(output_blend),
        "elapsed_seconds": round(elapsed, 3),
        "object_count": len(bpy.data.objects),
        "mesh_object_count": len(meshes),
        "mesh_data_count": len(bpy.data.meshes),
        "vertex_count": sum(len(obj.data.vertices) for obj in meshes),
        "material_count": len(material_names),
        "image_count": len([image for image in bpy.data.images if image.filepath or image.packed_file]),
        "armature_count": len(armatures),
        "armature_bone_count": sum(len(obj.data.bones) for obj in armatures),
        "shapekey_count": shapekey_count,
        "objects": [
            {
                "name": obj.name,
                "type": obj.type,
                "vertices": len(obj.data.vertices) if obj.type == "MESH" else 0,
                "bones": len(obj.data.bones) if obj.type == "ARMATURE" else 0,
            }
            for obj in bpy.data.objects
        ],
    }


def main() -> int:
    args = parse_args()
    if not args.vrm.exists():
        raise FileNotFoundError(args.vrm)

    started = time.monotonic()
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    textures_dir = args.textures_dir or (args.vrm.parent / "vrm_textures")

    print("Starting MMD Character Importer Blender step 1 (VRM).")
    gltf = read_glb_json(args.vrm)
    vrm_version, _vrm_extension, bone_map = vrm_extension_info(gltf)
    if not bone_map:
        print("Warning: no VRM humanoid bone mapping was found; bones will keep their original names.")
    else:
        missing_slots = [slot for slot in VRM_REQUIRED_HUMANOID_BONES if slot not in bone_map]
        if missing_slots:
            print("Warning: VRM humanoid mapping is missing required bones: " + ", ".join(missing_slots))
    print(f"Detected VRM specification version: {vrm_version or 'unknown'}")

    clear_scene()
    setup_scene()
    import_vrm(args.vrm)
    validate_imported_scene(args.vrm)
    remove_bone_shape_helpers()
    remove_childless_root_empties()
    make_single_user()
    rotated = normalize_scene_orientation(vrm_version)
    renamed, warnings = rename_humanoid_bones(main_armature(), bone_map, gltf, vrm_version)
    upper_chest_created = ensure_upper_chest(main_armature())
    unpacked, unpack_warnings = unpack_images(textures_dir)
    warnings.extend(unpack_warnings)
    print(f"Saving blend file: {args.output_blend}")
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend))
    report = build_report(
        args.vrm,
        args.output_blend,
        time.monotonic() - started,
        vrm_version,
        renamed,
        rotated,
        upper_chest_created,
        textures_dir,
        unpacked,
        warnings,
    )
    args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote import report: {args.report_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
