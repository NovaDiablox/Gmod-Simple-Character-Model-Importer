#!/usr/bin/env python3
"""Blender-side step 5 material sorting, cleanup, and merge helper."""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import re
import sys
import time
import zlib
from array import array
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import bpy


DEFAULT_LIMIT = 32
SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
UNSAFE_CHARS_PATTERN = re.compile(r"[^A-Za-z0-9_]+")
SHADOW_NO_BASE_HINTS = ("shadow", "eyeshadow")
BASE_IMAGE_NODE_NAMES = (
    "mmd_base_tex",
    "base color",
    "base_color",
    "basecolor",
    "diffuse",
    "albedo",
    "image texture",
    "mtoon1basecolortexture.image",
)
FALLBACK_BASE_TEXTURE_SIZE = 512
STACKED_FACE_OFFSET = 0.0001
STACKED_FACE_CENTROID_TOLERANCE = 2.5e-5
STACKED_FACE_RELATIVE_TOLERANCE = 0.01
STACKED_FACE_NORMAL_DOT = 0.999
STACKED_FACE_SCORE_THRESHOLD = 0.85
STACKED_FACE_SMALL_GROUP_EXACT_THRESHOLD = 8
MATERIAL_UID_PATTERN = re.compile(r"^mci_mat_\d+_([A-Za-z0-9_]+)$")
STACKED_LAYER_WORDS = {
    "inside",
    "outside",
    "inner",
    "outer",
    "interior",
    "exterior",
}
TEXTURE_ALPHA_ZERO_THRESHOLD = 1.0e-6
SUBSET_COMBINE_COVERAGE_THRESHOLD = 0.95
IMAGE_ALPHA_STATS_CACHE: dict[str, dict[str, object]] = {}


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("scan", "apply-initial", "merge"), required=True)
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--scan-json", type=Path)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--merge-plan-json", type=Path)
    parser.add_argument("--output-blend", type=Path)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--materials-json", type=Path)
    parser.add_argument("--materials-npy", type=Path)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    return parser.parse_args(argv)


def ensure_object_mode() -> None:
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type == "MESH" and getattr(obj, "data", None) and obj.data.materials]


def v3(value: Iterable[float]) -> list[float]:
    vector = list(value)
    return [round(float(vector[0]), 6), round(float(vector[1]), 6), round(float(vector[2]), 6)]


def v4(value: Iterable[float]) -> list[float]:
    vector = list(value)
    out = [float(vector[index]) if index < len(vector) else 1.0 for index in range(4)]
    return [round(max(0.0, min(1.0, item)), 6) for item in out]


def natural_key(name: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", name.lower())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def stripped_safe_name(name: str) -> str:
    name = name.replace(".001", "")
    cleaned = UNSAFE_CHARS_PATTERN.sub("", name)
    cleaned = cleaned.strip("_")
    if cleaned and cleaned[0].isdigit():
        cleaned = "mat_" + cleaned
    return cleaned


def unique_safe_names(names: list[str], prefix: str = "mat") -> dict[str, str]:
    out: dict[str, str] = {}
    used: set[str] = set()
    for index, original in enumerate(names, start=1):
        candidate = stripped_safe_name(original)
        if not candidate or candidate in used:
            candidate = f"{prefix}_{index:03d}"
        while candidate in used:
            candidate = f"{prefix}_{index:03d}_{len(used) + 1:02d}"
        used.add(candidate)
        out[original] = candidate
    return out


def is_safe_name(name: str) -> bool:
    return bool(SAFE_NAME_PATTERN.fullmatch(name))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"JSON file must contain an object: {path}")
    return data


def write_solid_rgba_png(path: Path, width: int, height: int, color: tuple[int, int, int, int]) -> None:
    """Write a small RGBA PNG without relying on Pillow inside Blender's Python."""

    path.parent.mkdir(parents=True, exist_ok=True)
    row = bytes(color) * width
    raw = b"".join(b"\x00" + row for _ in range(height))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind)
        crc = zlib.crc32(payload, crc)
        return len(payload).to_bytes(4, "big") + kind + payload + (crc & 0xFFFFFFFF).to_bytes(4, "big")

    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08"  # bit depth
        + b"\x06"  # RGBA
        + b"\x00"  # compression
        + b"\x00"  # filter
        + b"\x00"  # interlace
    )
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def resolve_image_path(image: bpy.types.Image) -> tuple[str, str, str]:
    if getattr(image, "packed_file", None):
        key = f"packed://{image.name}"
        return "", image.name, key
    raw = str(getattr(image, "filepath", "") or "")
    if not raw:
        key = f"image://{image.name}"
        return "", image.name, key
    try:
        resolved = bpy.path.abspath(raw)
    except Exception:
        resolved = raw
    path = str(Path(resolved).resolve()) if resolved else ""
    filename = Path(path or raw).name
    key = str(Path(path).as_posix()).lower() if path else f"image://{image.name.lower()}"
    return path, filename, key


def texture_key_for_path(path: Path) -> str:
    return str(path.resolve().as_posix()).lower()


def image_from_node(node: bpy.types.Node | None) -> bpy.types.Image | None:
    if node is None:
        return None
    image = getattr(node, "image", None)
    return image if image is not None else None


def upstream_images(socket: bpy.types.NodeSocket, seen: set[str] | None = None) -> list[bpy.types.Image]:
    seen = seen or set()
    images: list[bpy.types.Image] = []
    for link in socket.links:
        source = link.from_node
        key = str(source.as_pointer())
        if key in seen:
            continue
        seen.add(key)
        image = image_from_node(source)
        if image is not None:
            images.append(image)
        for input_socket in getattr(source, "inputs", []):
            images.extend(upstream_images(input_socket, seen))
    return images


def first_node_image_by_name(mat: bpy.types.Material) -> bpy.types.Image | None:
    if not mat.node_tree:
        return None
    for wanted in BASE_IMAGE_NODE_NAMES:
        for node in mat.node_tree.nodes:
            label = f"{node.name} {getattr(node, 'label', '')}".strip().lower()
            if wanted in label:
                image = image_from_node(node)
                if image is not None:
                    return image
    return None


def first_linked_base_image(mat: bpy.types.Material) -> bpy.types.Image | None:
    if not mat.node_tree:
        return None
    for node in mat.node_tree.nodes:
        node_name = f"{node.name} {getattr(node, 'label', '')} {getattr(node, 'bl_idname', '')}".lower()
        if "mmd_shader" in node_name or "principled" in node_name or "bsdf" in node_name:
            preferred_inputs = []
            for input_socket in node.inputs:
                socket_name = input_socket.name.lower()
                if any(hint in socket_name for hint in ("base", "diffuse", "color", "texture")):
                    preferred_inputs.append(input_socket)
            for input_socket in preferred_inputs + list(node.inputs):
                images = upstream_images(input_socket)
                if images:
                    return images[0]
    return None


def first_any_image(mat: bpy.types.Material) -> bpy.types.Image | None:
    if not mat.node_tree:
        return None
    for node in mat.node_tree.nodes:
        image = image_from_node(node)
        if image is not None:
            return image
    return None


def image_alpha_stats(image: bpy.types.Image) -> dict[str, object]:
    width = int(image.size[0]) if len(image.size) > 0 else 0
    height = int(image.size[1]) if len(image.size) > 1 else 0
    total = max(0, width * height)
    cache_key = f"{image.as_pointer()}:{image.name}:{width}x{height}"
    cached = IMAGE_ALPHA_STATS_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)
    stats: dict[str, object] = {
        "base_alpha_zero_pixels": 0,
        "base_alpha_total_pixels": total,
        "base_alpha_zero_ratio": 0.0,
    }
    if total <= 0:
        IMAGE_ALPHA_STATS_CACHE[cache_key] = dict(stats)
        return stats
    try:
        pixels = array("f", [0.0]) * (total * 4)
        image.pixels.foreach_get(pixels)
        zero_pixels = sum(1 for offset in range(3, len(pixels), 4) if pixels[offset] <= TEXTURE_ALPHA_ZERO_THRESHOLD)
        stats["base_alpha_zero_pixels"] = int(zero_pixels)
        stats["base_alpha_zero_ratio"] = round(float(zero_pixels) / max(1, total), 8)
    except Exception as exc:
        stats["base_alpha_stats_error"] = str(exc)
    IMAGE_ALPHA_STATS_CACHE[cache_key] = dict(stats)
    return stats


def resolve_base_texture(mat: bpy.types.Material) -> dict[str, object]:
    image = first_node_image_by_name(mat) or first_linked_base_image(mat) or first_any_image(mat)
    if image is not None:
        path, filename, key = resolve_image_path(image)
        return {
            "has_base_texture": True,
            "base_color_path": path,
            "base_color_file": filename,
            "base_color_key": key,
            "image_name": image.name,
            "packed": bool(getattr(image, "packed_file", None)),
            **image_alpha_stats(image),
        }
    diffuse = v4(getattr(mat, "diffuse_color", (0.8, 0.8, 0.8, 1.0)))
    zero_pixels = 1 if diffuse[3] <= TEXTURE_ALPHA_ZERO_THRESHOLD else 0
    return {
        "has_base_texture": False,
        "base_color_path": "",
        "base_color_file": "",
        "base_color_key": "color:" + ",".join(f"{value:.4f}" for value in diffuse),
        "image_name": "",
        "packed": False,
        "base_alpha_zero_pixels": zero_pixels,
        "base_alpha_total_pixels": 1,
        "base_alpha_zero_ratio": float(zero_pixels),
    }


def assign_base_texture(mat: bpy.types.Material, texture_path: Path) -> None:
    image = bpy.data.images.load(str(texture_path), check_existing=True)
    image.name = Path(texture_path).name
    mat.use_nodes = True
    node_tree = mat.node_tree
    if node_tree is None:
        return
    nodes = node_tree.nodes
    image_node = nodes.new(type="ShaderNodeTexImage")
    image_node.name = "mmd_base_tex"
    image_node.label = "mmd_base_tex"
    image_node.image = image
    shader = None
    for node in nodes:
        node_name = f"{node.name} {getattr(node, 'label', '')} {getattr(node, 'bl_idname', '')}".lower()
        if "principled" in node_name or "bsdf" in node_name or "mmd_shader" in node_name:
            shader = node
            break
    if shader is None:
        shader = nodes.new(type="ShaderNodeBsdfPrincipled")
        output = next((node for node in nodes if node.bl_idname == "ShaderNodeOutputMaterial"), None)
        if output is not None:
            try:
                node_tree.links.new(shader.outputs[0], output.inputs[0])
            except Exception:
                pass
    target_socket = None
    if shader is not None:
        for socket in shader.inputs:
            name = socket.name.lower()
            if "base" in name and "color" in name:
                target_socket = socket
                break
        if target_socket is None:
            target_socket = shader.inputs.get("Base Color") if hasattr(shader.inputs, "get") else None
    if target_socket is not None:
        try:
            node_tree.links.new(image_node.outputs["Color"], target_socket)
        except Exception:
            pass


def filter_resolved_base_texture_warnings(raw_warnings: object) -> list[str]:
    if not isinstance(raw_warnings, list):
        return []
    filtered: list[str] = []
    for warning in raw_warnings:
        text = str(warning)
        lowered = text.lower()
        if "no base-color image was found" in lowered:
            continue
        if "base-color fallback" in lowered:
            continue
        if "defaulting to removed" in lowered:
            continue
        filtered.append(text)
    return filtered


def apply_manual_base_textures(entries: list[dict[str, object]]) -> dict[str, object]:
    assigned: list[dict[str, object]] = []
    warnings: list[str] = []
    for index, entry in enumerate(entries, start=1):
        if not bool(entry.get("keep", True)) or not bool(entry.get("manual_base_texture")):
            continue
        uid = str(entry.get("uid") or f"mat_{index:03d}")
        material_name = str(entry.get("material_name") or "")
        raw_path = str(entry.get("base_color_path") or "").strip()
        if not raw_path:
            warnings.append(f"{uid}: manual base-color texture was requested but no path was provided.")
            entry["has_base_texture"] = False
            continue
        texture_path = Path(raw_path)
        if not texture_path.exists():
            warnings.append(f"{uid}: manual base-color texture was not found: {texture_path}")
            entry["has_base_texture"] = False
            continue
        mat = bpy.data.materials.get(material_name)
        if mat is None:
            warnings.append(f"{uid}: material was not found for manual base-color texture assignment: {material_name}")
            continue
        resolved_path = texture_path.resolve()
        try:
            assign_base_texture(mat, resolved_path)
        except Exception as exc:
            warnings.append(f"{uid}: failed to assign manual base-color texture {resolved_path}: {exc}")
            entry["has_base_texture"] = False
            continue
        entry["has_base_texture"] = True
        entry["base_color_path"] = str(resolved_path)
        entry["base_color_file"] = resolved_path.name
        entry["base_color_key"] = texture_key_for_path(resolved_path)
        entry["image_name"] = resolved_path.name
        entry["packed"] = False
        entry["warnings"] = filter_resolved_base_texture_warnings(entry.get("warnings", []))
        assigned.append(
            {
                "uid": uid,
                "material_name": material_name,
                "path": str(resolved_path),
            }
        )
    return {"assigned": assigned, "count": len(assigned), "warnings": warnings}


def ensure_fallback_base_textures(entries: list[dict[str, object]], output_dir: Path) -> dict[str, object]:
    generated: list[dict[str, object]] = []
    used_filenames: set[str] = set()
    texture_dir = output_dir / "generated_base_textures"
    for index, entry in enumerate(entries, start=1):
        if not bool(entry.get("keep", True)) or bool(entry.get("has_base_texture")):
            continue
        uid = str(entry.get("uid") or f"mat_{index:03d}")
        material_name = str(entry.get("material_name") or "")
        mat = bpy.data.materials.get(material_name)
        if mat is None:
            continue
        base_name = stripped_safe_name(str(entry.get("proposed_name") or material_name or uid)) or f"mat_{index:03d}"
        filename = f"{base_name}_base_white.png"
        suffix = 2
        while filename.lower() in used_filenames:
            filename = f"{base_name}_base_white_{suffix:02d}.png"
            suffix += 1
        used_filenames.add(filename.lower())
        texture_path = texture_dir / filename
        write_solid_rgba_png(texture_path, FALLBACK_BASE_TEXTURE_SIZE, FALLBACK_BASE_TEXTURE_SIZE, (255, 255, 255, 255))
        assign_base_texture(mat, texture_path)
        entry["has_base_texture"] = True
        entry["base_color_path"] = str(texture_path.resolve())
        entry["base_color_file"] = texture_path.name
        entry["base_color_key"] = texture_key_for_path(texture_path)
        entry["image_name"] = texture_path.name
        entry["packed"] = False
        warnings = filter_resolved_base_texture_warnings(entry.get("warnings", []))
        warnings.append("Generated 512x512 white base-color fallback because the kept material had no resolved base texture.")
        entry["warnings"] = warnings
        generated.append({"uid": uid, "material_name": material_name, "path": str(texture_path), "size": FALLBACK_BASE_TEXTURE_SIZE})
    return {"generated": generated, "count": len(generated), "directory": str(texture_dir) if generated else ""}


def material_alpha(mat: bpy.types.Material) -> float:
    values: list[float] = []
    try:
        values.append(float(mat.diffuse_color[3]))
    except Exception:
        pass
    if mat.node_tree:
        for node in mat.node_tree.nodes:
            node_name = f"{node.name} {getattr(node, 'label', '')} {getattr(node, 'bl_idname', '')}".lower()
            if "mmd_shader" in node_name and len(node.inputs) > 12:
                try:
                    values.append(float(node.inputs[12].default_value))
                except Exception:
                    pass
            if "principled" in node_name or "bsdf" in node_name:
                socket = node.inputs.get("Alpha") if hasattr(node.inputs, "get") else None
                if socket is not None:
                    try:
                        values.append(float(socket.default_value))
                    except Exception:
                        pass
    if not values:
        return 1.0
    return round(max(0.0, min(1.0, min(values))), 6)


def entry_alpha(entry: dict[str, object], default: float = 1.0) -> float:
    value = entry.get("alpha", default)
    if value in (None, ""):
        return float(default)
    return float(value)


def material_uid(index: int, name: str) -> str:
    slug = stripped_safe_name(name).lower()
    if not slug:
        slug = "material"
    return f"mci_mat_{index:03d}_{slug[:36]}"


def preview_color(index: int, mat: bpy.types.Material, texture: dict[str, object]) -> list[float]:
    diffuse = v4(getattr(mat, "diffuse_color", (0.8, 0.8, 0.8, 1.0)))
    max_rgb = max(diffuse[:3])
    min_rgb = min(diffuse[:3])
    saturation = max_rgb - min_rgb
    if saturation > 0.12 and max_rgb > 0.18:
        return [diffuse[0], diffuse[1], diffuse[2], max(0.35, diffuse[3])]
    seed = f"{texture.get('base_color_key') or mat.name}:{index}"
    value = sum((offset + 1) * ord(char) for offset, char in enumerate(seed))
    hue = (value % 360) / 360.0
    sat = 0.50 + ((value // 11) % 25) / 100.0
    val = 0.72 + ((value // 31) % 18) / 100.0
    red, green, blue = colorsys.hsv_to_rgb(hue, sat, min(0.92, val))
    return [round(red, 6), round(green, 6), round(blue, 6), max(0.35, diffuse[3])]


def material_slots_by_uid(entries: list[dict[str, object]]) -> dict[tuple[str, int], str]:
    out: dict[tuple[str, int], str] = {}
    for entry in entries:
        uid = str(entry.get("uid") or "")
        refs = entry.get("slot_refs", [])
        if not uid or not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            obj_name = str(ref.get("object") or "")
            slot_index = int(ref.get("slot_index", -1))
            if obj_name and slot_index >= 0:
                out[(obj_name, slot_index)] = uid
    return out


def collect_material_entries() -> tuple[list[dict[str, object]], dict[str, object]]:
    material_order: list[bpy.types.Material] = []
    material_seen: set[str] = set()
    slot_refs: dict[str, list[dict[str, object]]] = defaultdict(list)
    assigned_vertices: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    assigned_faces: dict[str, int] = defaultdict(int)

    for obj in mesh_objects():
        for slot_index, mat in enumerate(obj.data.materials):
            if mat is None:
                continue
            if mat.name not in material_seen:
                material_seen.add(mat.name)
                material_order.append(mat)
            slot_refs[mat.name].append({"object": obj.name, "slot_index": slot_index})
        for poly in obj.data.polygons:
            if poly.material_index < 0 or poly.material_index >= len(obj.data.materials):
                continue
            mat = obj.data.materials[poly.material_index]
            if mat is None:
                continue
            assigned_faces[mat.name] += 1
            assigned_vertices[mat.name][obj.name].update(int(index) for index in poly.vertices)

    safe_names = unique_safe_names([mat.name for mat in material_order], "mat")
    entries: list[dict[str, object]] = []
    for index, mat in enumerate(material_order, start=1):
        uid = material_uid(index, mat.name)
        texture = resolve_base_texture(mat)
        alpha = material_alpha(mat)
        diffuse = v4(getattr(mat, "diffuse_color", (0.8, 0.8, 0.8, 1.0)))
        color = preview_color(index, mat, texture)
        warnings: list[str] = []
        has_texture = bool(texture.get("has_base_texture"))
        normalized = mat.name.lower()
        no_base_shadow = (not has_texture) and any(hint in normalized for hint in SHADOW_NO_BASE_HINTS)
        alpha_removed = alpha < 0.5
        if not has_texture:
            warnings.append("No base-color image was found.")
        if no_base_shadow:
            warnings.append("Shadow-like material with no base texture; defaulting to removed.")
        if alpha < 0.999:
            warnings.append(f"Material alpha is {alpha:.3f}.")
        if alpha_removed:
            warnings.append("Material alpha is below 0.500; defaulting to removed.")
        vertex_count = sum(len(vertices) for vertices in assigned_vertices.get(mat.name, {}).values())
        entries.append(
            {
                "uid": uid,
                "material_name": mat.name,
                "proposed_name": safe_names.get(mat.name, f"mat_{index:03d}"),
                "keep": not no_base_shadow and not alpha_removed,
                "slot_refs": slot_refs.get(mat.name, []),
                "object_names": sorted({str(ref["object"]) for ref in slot_refs.get(mat.name, [])}),
                "vertex_count": vertex_count,
                "face_count": int(assigned_faces.get(mat.name, 0)),
                "alpha": alpha,
                "diffuse": diffuse,
                "swatch": color,
                "preview_color": color,
                "warnings": warnings,
                **texture,
            }
        )
    summary = {
        "mesh_object_count": len(mesh_objects()),
        "material_count": len(entries),
        "assigned_face_count": sum(int(entry.get("face_count", 0)) for entry in entries),
        "assigned_vertex_count": sum(int(entry.get("vertex_count", 0)) for entry in entries),
        "alpha_material_count": sum(1 for entry in entries if entry_alpha(entry) < 0.999),
        "no_base_texture_count": sum(1 for entry in entries if not entry.get("has_base_texture")),
    }
    return entries, summary


def collect_material_preview(entries: list[dict[str, object]], max_triangles: int = 500000) -> dict[str, object]:
    uid_by_slot = material_slots_by_uid(entries)
    total_triangles = 0
    for obj in mesh_objects():
        for poly in obj.data.polygons:
            total_triangles += max(0, len(poly.vertices) - 2)
    stride = max(1, math.ceil(total_triangles / max(1, max_triangles)))
    triangles: list[dict[str, object]] = []
    triangle_index = 0
    entry_by_uid = {str(entry["uid"]): entry for entry in entries}
    points: list[list[float]] = []
    for obj in mesh_objects():
        matrix = obj.matrix_world
        uv_layer = obj.data.uv_layers.active
        for poly in obj.data.polygons:
            uid = uid_by_slot.get((obj.name, int(poly.material_index)), "")
            entry = entry_by_uid.get(uid, {})
            verts = list(poly.vertices)
            loops = list(poly.loop_indices)
            if len(verts) < 3:
                continue
            for offset in range(1, len(verts) - 1):
                if triangle_index % stride == 0:
                    loop_indices = [loops[0], loops[offset], loops[offset + 1]]
                    uvs = []
                    for loop_index in loop_indices:
                        if uv_layer is not None and 0 <= loop_index < len(uv_layer.data):
                            uv = uv_layer.data[loop_index].uv
                            uvs.append([round(float(uv.x), 6), round(float(uv.y), 6)])
                        else:
                            uvs.append([0.0, 0.0])
                    coords = [
                        v3(matrix @ obj.data.vertices[verts[0]].co),
                        v3(matrix @ obj.data.vertices[verts[offset]].co),
                        v3(matrix @ obj.data.vertices[verts[offset + 1]].co),
                    ]
                    points.extend(coords)
                    triangles.append(
                        {
                            "points": coords,
                            "uvs": uvs,
                            "material_uid": uid,
                            "color": entry.get("preview_color") or entry.get("swatch") or [0.8, 0.8, 0.8, 1.0],
                            "texture_path": entry.get("base_color_path", ""),
                            "alpha": entry.get("alpha", 1.0),
                        }
                    )
                triangle_index += 1
    if points:
        mins = [min(point[index] for point in points) for index in range(3)]
        maxs = [max(point[index] for point in points) for index in range(3)]
    else:
        mins = [0.0, 0.0, 0.0]
        maxs = [1.0, 1.0, 1.0]
    return {
        "triangles": triangles,
        "source_triangle_count": total_triangles,
        "sampled_triangle_count": len(triangles),
        "sample_stride": stride,
        "mins": mins,
        "maxs": maxs,
    }


def entry_base_zero_alpha_pixels(entry: dict[str, object]) -> int:
    value = entry.get("base_alpha_zero_pixels", 0)
    try:
        return int(value)
    except Exception:
        return 0


def vertex_sets_by_object_uid(entries: list[dict[str, object]]) -> dict[str, dict[str, set[int]]]:
    uid_by_slot = material_slots_by_uid(entries)
    out: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for obj in mesh_objects():
        for poly in obj.data.polygons:
            uid = uid_by_slot.get((obj.name, int(poly.material_index)))
            if uid:
                out[obj.name][uid].update(int(index) for index in poly.vertices)
    return out


def subset_combine_operations(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    entry_by_uid = {str(entry.get("uid") or ""): entry for entry in entries}
    vertices_by_object = vertex_sets_by_object_uid(entries)
    operations: list[dict[str, object]] = []
    claimed_by_object: dict[str, set[str]] = defaultdict(set)
    for obj_name, vertices_by_uid in vertices_by_object.items():
        kept_vertices_by_uid = {
            uid: vertices
            for uid, vertices in vertices_by_uid.items()
            if vertices and bool(entry_by_uid.get(uid, {}).get("keep", True))
        }
        candidates: list[dict[str, object]] = []
        for container_uid, container_vertices in kept_vertices_by_uid.items():
            member_uids = [
                uid
                for uid, vertices in kept_vertices_by_uid.items()
                if uid == container_uid or vertices.issubset(container_vertices)
            ]
            if len(member_uids) < 2:
                continue
            union_vertices: set[int] = set()
            for uid in member_uids:
                if uid == container_uid:
                    continue
                union_vertices.update(kept_vertices_by_uid[uid])
            coverage = len(union_vertices) / max(1, len(container_vertices))
            if coverage < SUBSET_COMBINE_COVERAGE_THRESHOLD:
                continue
            target_uid = min(
                member_uids,
                key=lambda uid: (
                    entry_base_zero_alpha_pixels(entry_by_uid.get(uid, {})),
                    -len(kept_vertices_by_uid.get(uid, set())),
                    natural_key(str(entry_by_uid.get(uid, {}).get("material_name") or uid)),
                ),
            )
            candidates.append(
                {
                    "object": obj_name,
                    "container_uid": container_uid,
                    "target_uid": target_uid,
                    "member_uids": sorted(member_uids, key=natural_key),
                    "coverage": coverage,
                    "container_vertex_count": len(container_vertices),
                    "target_vertex_count": len(kept_vertices_by_uid.get(target_uid, set())),
                }
            )
        candidates.sort(
            key=lambda item: (
                -len(item["member_uids"]),
                -float(item["coverage"]),
                -int(item["container_vertex_count"]),
                natural_key(str(entry_by_uid.get(str(item["target_uid"]), {}).get("material_name") or item["target_uid"])),
            )
        )
        for candidate in candidates:
            member_uids = [str(uid) for uid in candidate["member_uids"]]
            if any(uid in claimed_by_object[obj_name] for uid in member_uids):
                continue
            target_uid = str(candidate["target_uid"])
            target_entry = entry_by_uid.get(target_uid, {})
            for uid in member_uids:
                entry = entry_by_uid.get(uid)
                if entry is None:
                    continue
                entry["combine_target_uid"] = target_uid
                if uid == target_uid:
                    continue
                operations.append(
                    {
                        "source_uid": uid,
                        "target_uid": target_uid,
                        "reason": "source material vertices are covered by a sibling subset cluster; selected target by base texture zero-alpha pixels, then vertex count",
                        "enabled": True,
                        "object": obj_name,
                        "container_uid": candidate["container_uid"],
                        "cluster_uids": member_uids,
                        "coverage": round(float(candidate["coverage"]), 6),
                        "source_vertex_count": len(kept_vertices_by_uid.get(uid, set())),
                        "target_vertex_count": len(kept_vertices_by_uid.get(target_uid, set())),
                        "source_base_alpha_zero_pixels": entry_base_zero_alpha_pixels(entry),
                        "target_base_alpha_zero_pixels": entry_base_zero_alpha_pixels(target_entry),
                    }
                )
            claimed_by_object[obj_name].update(member_uids)
    return operations


def build_initial_plan(input_blend: Path, entries: list[dict[str, object]], limit: int) -> dict[str, object]:
    first_by_key: dict[str, str] = {}
    operations: list[dict[str, object]] = []
    for entry in entries:
        uid = str(entry.get("uid") or "")
        key = str(entry.get("base_color_key") or "")
        if not bool(entry.get("keep", True)):
            entry["combine_target_uid"] = uid
            continue
        if key and key in first_by_key:
            entry["combine_target_uid"] = first_by_key[key]
            operations.append(
                {
                    "source_uid": uid,
                    "target_uid": first_by_key[key],
                    "reason": "same resolved base-color texture",
                    "enabled": True,
                }
            )
        else:
            first_by_key[key] = uid
            entry["combine_target_uid"] = uid
    subset_operations = subset_combine_operations(entries)
    subset_cluster_uids = {
        str(uid)
        for operation in subset_operations
        for uid in operation.get("cluster_uids", [])
    }
    if subset_cluster_uids:
        operations = [operation for operation in operations if str(operation.get("source_uid") or "") not in subset_cluster_uids]
    operations.extend(subset_operations)
    return {
        "version": 1,
        "kind": "sort_materials_initial",
        "input_blend": str(input_blend),
        "material_limit": int(limit),
        "materials": entries,
        "combine_operations": operations,
        "warnings": [],
    }


def analyze_current_file(input_blend: Path, limit: int) -> tuple[dict[str, object], dict[str, object]]:
    entries, summary = collect_material_entries()
    preview = collect_material_preview(entries)
    analysis = {
        "version": 1,
        "kind": "sort_materials",
        "input_blend": str(input_blend),
        **summary,
        "materials": entries,
        "model_preview": preview,
    }
    plan = build_initial_plan(input_blend, entries, limit)
    return analysis, plan


def mark_remaining_materials_as_kept(analysis: dict[str, object]) -> dict[str, object]:
    """Post-cleanup scans must not reapply scan-time removal defaults.

    At this point unchecked material geometry has already been deleted from the
    scene, so every material still present is part of the active user plan even
    when its Blender alpha is below the scan default threshold.
    """

    materials = analysis.get("materials", [])
    if not isinstance(materials, list):
        return analysis
    for entry in materials:
        if not isinstance(entry, dict):
            continue
        entry["keep"] = True
        warnings = entry.get("warnings", [])
        if isinstance(warnings, list):
            filtered = [
                warning
                for warning in warnings
                if "defaulting to removed" not in str(warning).lower()
                and "alpha is below 0.500" not in str(warning).lower()
            ]
            alpha = entry_alpha(entry)
            if alpha < 0.5:
                filtered.append("Low-alpha material is kept because it remains after the active material plan was applied.")
            entry["warnings"] = filtered
    return analysis


def entries_from_plan(plan: dict[str, object]) -> list[dict[str, object]]:
    raw = plan.get("materials", [])
    if not isinstance(raw, list):
        raise RuntimeError("Material plan JSON is missing a materials list.")
    entries = [entry for entry in raw if isinstance(entry, dict)]
    if not entries:
        raise RuntimeError("Material plan has no material entries.")
    return entries


def validate_material_names(entries: list[dict[str, object]], key: str = "proposed_name") -> None:
    seen: set[str] = set()
    errors: list[str] = []
    for entry in entries:
        if not bool(entry.get("keep", True)):
            continue
        name = str(entry.get(key) or "").strip()
        uid = str(entry.get("uid") or "")
        if not is_safe_name(name):
            errors.append(f"{uid}: unsafe material name {name!r}")
        if name in seen:
            errors.append(f"{uid}: duplicate material name {name!r}")
        seen.add(name)
    if errors:
        raise RuntimeError("Material naming validation failed:\n" + "\n".join(errors))


def normalize_combine_targets(entries: list[dict[str, object]]) -> None:
    kept = {str(entry.get("uid") or "") for entry in entries if bool(entry.get("keep", True))}
    for entry in entries:
        uid = str(entry.get("uid") or "")
        if not uid:
            continue
        target = str(entry.get("combine_target_uid") or uid)
        if uid not in kept or target not in kept:
            entry["combine_target_uid"] = uid


def duplicate_material_vertex_group_suppressions(entries: list[dict[str, object]]) -> dict[tuple[str, str], dict[str, object]]:
    uid_by_slot = material_slots_by_uid(entries)
    entry_by_uid = {str(entry.get("uid") or ""): entry for entry in entries if str(entry.get("uid") or "")}
    suppressions: dict[tuple[str, str], dict[str, object]] = {}
    for obj in mesh_objects():
        vertices_by_uid: dict[str, set[int]] = defaultdict(set)
        face_count_by_uid: dict[str, int] = defaultdict(int)
        for poly in obj.data.polygons:
            uid = uid_by_slot.get((obj.name, int(poly.material_index)))
            if not uid:
                continue
            vertices_by_uid[uid].update(int(index) for index in poly.vertices)
            face_count_by_uid[uid] += 1

        uids_by_vertices: dict[frozenset[int], list[str]] = defaultdict(list)
        for uid, vertices in vertices_by_uid.items():
            if vertices:
                uids_by_vertices[frozenset(vertices)].append(uid)

        for vertex_key, uids in uids_by_vertices.items():
            if len(uids) < 2:
                continue
            kept_uids = [uid for uid in uids if bool(entry_by_uid.get(uid, {}).get("keep", True))]
            removed_uids = [uid for uid in uids if not bool(entry_by_uid.get(uid, {}).get("keep", True))]
            if not kept_uids or not removed_uids:
                continue
            kept_uids.sort(
                key=lambda uid: (
                    -entry_alpha(entry_by_uid.get(uid, {})),
                    -int(face_count_by_uid.get(uid, 0)),
                    natural_key(str(entry_by_uid.get(uid, {}).get("material_name") or uid)),
                )
            )
            keeper_uid = kept_uids[0]
            keeper_entry = entry_by_uid.get(keeper_uid, {})
            for removed_uid in sorted(
                removed_uids,
                key=lambda uid: natural_key(str(entry_by_uid.get(uid, {}).get("material_name") or uid)),
            ):
                removed_entry = entry_by_uid.get(removed_uid, {})
                suppressions[(obj.name, removed_uid)] = {
                    "object": obj.name,
                    "suppressed_uid": removed_uid,
                    "suppressed_material": str(removed_entry.get("material_name") or removed_uid),
                    "suppressed_alpha": entry_alpha(removed_entry),
                    "keeper_uid": keeper_uid,
                    "keeper_material": str(keeper_entry.get("material_name") or keeper_uid),
                    "keeper_alpha": entry_alpha(keeper_entry),
                    "vertex_count": len(vertex_key),
                    "face_count": int(face_count_by_uid.get(removed_uid, 0)),
                    "reason": "unchecked material has the same vertex set as a kept material",
                }
    return suppressions


def create_source_vertex_groups(entries: list[dict[str, object]]) -> dict[str, object]:
    uid_by_slot = material_slots_by_uid(entries)
    suppressions = duplicate_material_vertex_group_suppressions(entries)
    created: list[dict[str, object]] = []
    removed_existing_suppressed: list[dict[str, object]] = []
    for obj in mesh_objects():
        vertices_by_uid: dict[str, set[int]] = defaultdict(set)
        for poly in obj.data.polygons:
            uid = uid_by_slot.get((obj.name, int(poly.material_index)))
            if uid:
                vertices_by_uid[uid].update(int(index) for index in poly.vertices)
        for uid, vertices in vertices_by_uid.items():
            if (obj.name, uid) in suppressions:
                existing = obj.vertex_groups.get(uid)
                if existing:
                    obj.vertex_groups.remove(existing)
                    removed_existing_suppressed.append({"object": obj.name, "vertex_group": uid})
                continue
            if not vertices:
                continue
            group_name = uid
            existing = obj.vertex_groups.get(group_name)
            if existing:
                obj.vertex_groups.remove(existing)
            group = obj.vertex_groups.new(name=group_name)
            group.add(sorted(vertices), 1.0, "REPLACE")
            created.append({"object": obj.name, "vertex_group": group_name, "vertex_count": len(vertices)})
    suppressed = sorted(
        suppressions.values(),
        key=lambda item: (
            natural_key(str(item.get("object") or "")),
            natural_key(str(item.get("suppressed_material") or "")),
        ),
    )
    return {
        "created": created,
        "count": len(created),
        "suppressed_duplicate_groups": suppressed,
        "suppressed_duplicate_group_count": len(suppressed),
        "removed_existing_suppressed_groups": removed_existing_suppressed,
        "removed_existing_suppressed_group_count": len(removed_existing_suppressed),
    }


def delete_unkept_faces(entries: list[dict[str, object]]) -> dict[str, object]:
    import bmesh

    uid_by_slot = material_slots_by_uid(entries)
    keep_by_uid = {str(entry.get("uid") or ""): bool(entry.get("keep", True)) for entry in entries}
    deleted_faces_total = 0
    deleted_vertices_total = 0
    by_object: list[dict[str, object]] = []
    for obj in mesh_objects():
        mesh = obj.data
        delete_indices: set[int] = set()
        for poly in mesh.polygons:
            uid = uid_by_slot.get((obj.name, int(poly.material_index)))
            if uid and not keep_by_uid.get(uid, True):
                delete_indices.add(int(poly.index))
        if not delete_indices:
            continue
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        faces = [face for face in bm.faces if face.index in delete_indices]
        deleted_faces = len(faces)
        bmesh.ops.delete(bm, geom=faces, context="FACES")
        isolated = [vert for vert in bm.verts if not vert.link_faces]
        deleted_vertices = len(isolated)
        if isolated:
            bmesh.ops.delete(bm, geom=isolated, context="VERTS")
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        deleted_faces_total += deleted_faces
        deleted_vertices_total += deleted_vertices
        by_object.append({"object": obj.name, "faces": deleted_faces, "vertices": deleted_vertices})
    return {"faces": deleted_faces_total, "vertices": deleted_vertices_total, "by_object": by_object}


def material_by_uid(entries: list[dict[str, object]]) -> dict[str, bpy.types.Material]:
    out: dict[str, bpy.types.Material] = {}
    for entry in entries:
        uid = str(entry.get("uid") or "")
        name = str(entry.get("material_name") or "")
        mat = bpy.data.materials.get(name)
        if uid and mat is not None:
            out[uid] = mat
    return out


def consolidate_slots(entries: list[dict[str, object]], target_key: str = "combine_target_uid") -> dict[str, object]:
    uid_by_slot = material_slots_by_uid(entries)
    entry_by_uid = {str(entry.get("uid") or ""): entry for entry in entries}
    mat_by_uid = material_by_uid(entries)
    changed_polygons = 0
    removed_slots = 0
    for obj in mesh_objects():
        old_slots = list(obj.data.materials)
        target_mats: list[bpy.types.Material] = []
        target_index_by_uid: dict[str, int] = {}
        poly_targets: dict[int, str] = {}
        for poly in obj.data.polygons:
            uid = uid_by_slot.get((obj.name, int(poly.material_index)))
            if not uid:
                continue
            entry = entry_by_uid.get(uid, {})
            if not bool(entry.get("keep", True)):
                continue
            target_uid = str(entry.get(target_key) or uid)
            target_mat = mat_by_uid.get(target_uid) or mat_by_uid.get(uid)
            if target_mat is None:
                continue
            if target_uid not in target_index_by_uid:
                target_index_by_uid[target_uid] = len(target_mats)
                target_mats.append(target_mat)
            poly_targets[int(poly.index)] = target_uid
        if not target_mats:
            continue
        obj.data.materials.clear()
        for mat in target_mats:
            obj.data.materials.append(mat)
        for poly in obj.data.polygons:
            target_uid = poly_targets.get(int(poly.index))
            if not target_uid:
                continue
            new_index = target_index_by_uid[target_uid]
            if int(poly.material_index) != new_index:
                changed_polygons += 1
            poly.material_index = new_index
        removed_slots += max(0, len(old_slots) - len(target_mats))
    return {"changed_polygons": changed_polygons, "removed_slots": removed_slots}


def rename_target_materials(entries: list[dict[str, object]], target_key: str = "combine_target_uid") -> dict[str, object]:
    mat_by_uid = material_by_uid(entries)
    target_to_name: dict[str, str] = {}
    for entry in entries:
        if not bool(entry.get("keep", True)):
            continue
        uid = str(entry.get("uid") or "")
        target_uid = str(entry.get(target_key) or uid)
        if target_uid not in target_to_name:
            target_entry = next((candidate for candidate in entries if str(candidate.get("uid") or "") == target_uid), entry)
            target_to_name[target_uid] = str(target_entry.get("proposed_name") or target_entry.get("material_name") or target_uid)
    used: set[str] = set()
    renamed: list[dict[str, str]] = []
    for target_uid, name in sorted(target_to_name.items(), key=lambda item: natural_key(item[1])):
        mat = mat_by_uid.get(target_uid)
        if mat is None:
            continue
        candidate = stripped_safe_name(name) or f"mat_{len(used) + 1:03d}"
        while candidate in used:
            candidate = f"{candidate}_{len(used) + 1:02d}"
        used.add(candidate)
        old_name = mat.name
        mat.name = candidate
        renamed.append({"uid": target_uid, "old_name": old_name, "new_name": mat.name})
    return {"renamed": renamed, "count": len(renamed)}


def material_uid_slug(uid: str) -> str:
    match = MATERIAL_UID_PATTERN.fullmatch(uid)
    return match.group(1) if match else ""


def stacked_candidate_groups_by_slug(entries: list[dict[str, object]]) -> dict[str, list[str]]:
    groups_by_slug: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        if not bool(entry.get("keep", True)):
            continue
        uid = str(entry.get("uid") or "")
        slug = material_uid_slug(uid)
        if slug:
            groups_by_slug[slug].add(uid)
    return {
        slug: sorted(groups, key=natural_key)
        for slug, groups in groups_by_slug.items()
        if len(groups) > 1
    }


def stacked_layer_key(slug: str) -> tuple[str, str]:
    """Return (core_slug, layer_word) for inside/outside style material pairs."""

    text = str(slug or "").strip("_").lower()
    if not text:
        return "", ""

    tokens = [token for token in text.split("_") if token]
    if len(tokens) > 1:
        removed = [token for token in tokens if token in STACKED_LAYER_WORDS]
        if removed:
            core_tokens = [token for token in tokens if token not in STACKED_LAYER_WORDS]
            core = "_".join(core_tokens).strip("_")
            if len(core) >= 3:
                return core, removed[0]

    for word in sorted(STACKED_LAYER_WORDS, key=len, reverse=True):
        if text.startswith(word) and len(text) > len(word) + 2:
            return text[len(word) :].strip("_"), word
        if text.endswith(word) and len(text) > len(word) + 2:
            return text[: -len(word)].strip("_"), word
    return "", ""


def stacked_candidate_buckets(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets: list[dict[str, object]] = []
    seen_group_sets: set[tuple[str, ...]] = set()

    for slug, groups in stacked_candidate_groups_by_slug(entries).items():
        group_key = tuple(groups)
        seen_group_sets.add(group_key)
        buckets.append(
            {
                "key": slug,
                "relation": "exact_slug",
                "groups": groups,
                "group_count": len(groups),
            }
        )

    layered_groups: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for entry in entries:
        if not bool(entry.get("keep", True)):
            continue
        uid = str(entry.get("uid") or "")
        slug = material_uid_slug(uid)
        core, layer = stacked_layer_key(slug)
        if core and layer:
            layered_groups[core][layer].add(uid)

    for core, groups_by_layer in sorted(layered_groups.items(), key=lambda item: natural_key(item[0])):
        if len(groups_by_layer) < 2:
            continue
        groups = sorted({uid for layer_groups in groups_by_layer.values() for uid in layer_groups}, key=natural_key)
        if len(groups) < 2:
            continue
        group_key = tuple(groups)
        if group_key in seen_group_sets:
            continue
        seen_group_sets.add(group_key)
        buckets.append(
            {
                "key": core,
                "relation": "layered_slug",
                "layers": sorted(groups_by_layer),
                "groups": groups,
                "group_count": len(groups),
            }
        )

    return buckets


def mesh_vertex_material_groups(obj: bpy.types.Object, allowed_groups: set[str] | None = None) -> dict[int, set[str]]:
    material_group_by_index = {
        group.index: group.name
        for group in obj.vertex_groups
        if group.name.startswith("mci_mat_") and (allowed_groups is None or group.name in allowed_groups)
    }
    out: dict[int, set[str]] = {}
    if not material_group_by_index:
        return out
    for vertex in obj.data.vertices:
        names = {
            material_group_by_index[item.group]
            for item in vertex.groups
            if item.group in material_group_by_index and float(item.weight) > 0.5
        }
        if names:
            out[int(vertex.index)] = names
    return out


def polygon_group_membership(poly: bpy.types.MeshPolygon, groups_by_vertex: dict[int, set[str]]) -> set[str]:
    vertex_sets = [groups_by_vertex.get(int(index), set()) for index in poly.vertices]
    if not vertex_sets:
        return set()
    common = set(vertex_sets[0])
    for names in vertex_sets[1:]:
        common.intersection_update(names)
        if not common:
            break
    return common


def quantized_key(values: Iterable[float], tolerance: float) -> tuple[int, int, int]:
    vector = list(values)
    return (
        int(round(float(vector[0]) / tolerance)),
        int(round(float(vector[1]) / tolerance)),
        int(round(float(vector[2]) / tolerance)),
    )


def neighboring_keys(key: tuple[int, int, int]) -> Iterable[tuple[int, int, int]]:
    x, y, z = key
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                yield (x + dx, y + dy, z + dz)


def face_signature(mesh: bpy.types.Mesh, poly: bpy.types.MeshPolygon) -> dict[str, object]:
    coords = [mesh.vertices[int(index)].co.copy() for index in poly.vertices]
    centroid = sum(coords[1:], coords[0].copy()) / max(1, len(coords))
    edge_lengths = []
    for index, coord in enumerate(coords):
        nxt = coords[(index + 1) % len(coords)]
        edge_lengths.append(float((coord - nxt).length))
    edge_lengths.sort()
    normal = poly.normal.copy()
    if normal.length > 0:
        normal.normalize()
    return {
        "face_index": int(poly.index),
        "vertex_count": len(coords),
        "centroid": centroid,
        "key": quantized_key(centroid, STACKED_FACE_CENTROID_TOLERANCE),
        "area": float(poly.area),
        "edge_lengths": edge_lengths,
        "normal": normal,
    }


def signatures_match(a: dict[str, object], b: dict[str, object]) -> bool:
    if int(a.get("vertex_count", 0) or 0) != int(b.get("vertex_count", 0) or 0):
        return False
    centroid_a = a.get("centroid")
    centroid_b = b.get("centroid")
    if centroid_a is None or centroid_b is None:
        return False
    if float((centroid_a - centroid_b).length) > STACKED_FACE_CENTROID_TOLERANCE:
        return False
    area_a = float(a.get("area", 0.0) or 0.0)
    area_b = float(b.get("area", 0.0) or 0.0)
    scale = max(abs(area_a), abs(area_b), 1.0e-12)
    if abs(area_a - area_b) / scale > STACKED_FACE_RELATIVE_TOLERANCE:
        return False
    edges_a = list(a.get("edge_lengths", []) or [])
    edges_b = list(b.get("edge_lengths", []) or [])
    if len(edges_a) != len(edges_b):
        return False
    for length_a, length_b in zip(edges_a, edges_b):
        edge_scale = max(abs(float(length_a)), abs(float(length_b)), 1.0e-12)
        if abs(float(length_a) - float(length_b)) / edge_scale > STACKED_FACE_RELATIVE_TOLERANCE:
            return False
    normal_a = a.get("normal")
    normal_b = b.get("normal")
    if normal_a is None or normal_b is None:
        return False
    return abs(float(normal_a.dot(normal_b))) >= STACKED_FACE_NORMAL_DOT


def compare_group_signatures(
    signatures_a: list[dict[str, object]],
    signatures_b: list[dict[str, object]],
) -> tuple[float, int]:
    if not signatures_a or not signatures_b:
        return 0.0, 0
    small, large = (signatures_a, signatures_b) if len(signatures_a) <= len(signatures_b) else (signatures_b, signatures_a)
    large_by_key: dict[tuple[int, int, int], list[tuple[int, dict[str, object]]]] = defaultdict(list)
    for index, signature in enumerate(large):
        large_by_key[signature["key"]].append((index, signature))
    matched_large: set[int] = set()
    matched = 0
    for signature in small:
        found_index = None
        for key in neighboring_keys(signature["key"]):
            for large_index, candidate in large_by_key.get(key, []):
                if large_index in matched_large:
                    continue
                if signatures_match(signature, candidate):
                    found_index = large_index
                    break
            if found_index is not None:
                break
        if found_index is not None:
            matched_large.add(found_index)
            matched += 1
    return matched / max(1, min(len(signatures_a), len(signatures_b))), matched


def collect_material_group_face_signatures(
    obj: bpy.types.Object,
    allowed_groups: set[str] | None = None,
) -> dict[str, list[dict[str, object]]]:
    groups_by_vertex = mesh_vertex_material_groups(obj, allowed_groups)
    if not groups_by_vertex:
        return {}
    out: dict[str, list[dict[str, object]]] = defaultdict(list)
    mesh = obj.data
    try:
        mesh.update(calc_edges=True)
    except TypeError:
        mesh.update()
    for poly in mesh.polygons:
        names = polygon_group_membership(poly, groups_by_vertex)
        if not names:
            continue
        signature = face_signature(mesh, poly)
        for name in names:
            out[name].append(signature)
    return dict(out)


def offset_faces_for_object(obj: bpy.types.Object, face_indices: set[int], offset: float) -> dict[str, object]:
    if not face_indices:
        return {"moved_faces": 0, "moved_vertices": 0, "duplicated_vertices": 0}
    import bmesh

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    original_faces = [
        bm.faces[index]
        for index in sorted(face_indices)
        if 0 <= index < len(bm.faces) and bm.faces[index].is_valid
    ]
    normals_by_vertex: dict[int, object] = {}
    moved_faces = 0
    for face in original_faces:
        if not face.is_valid:
            continue
        normal = face.normal.copy()
        if normal.length <= 0:
            continue
        normal.normalize()
        for vertex in face.verts:
            vertex_index = int(vertex.index)
            if vertex_index in normals_by_vertex:
                normals_by_vertex[vertex_index] += normal
            else:
                normals_by_vertex[vertex_index] = normal.copy()
        moved_faces += 1
    moved_vertices = 0
    for vertex_index, normal in normals_by_vertex.items():
        if normal.length <= 0:
            continue
        normal.normalize()
        bm.verts[vertex_index].co += normal * offset
        moved_vertices += 1
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    try:
        mesh.validate(clean_customdata=False)
    except Exception:
        pass
    return {"moved_faces": moved_faces, "moved_vertices": moved_vertices, "duplicated_vertices": 0}


def detect_and_offset_stacked_material_groups(
    entries: list[dict[str, object]],
    offset: float = STACKED_FACE_OFFSET,
) -> dict[str, object]:
    candidate_buckets = stacked_candidate_buckets(entries)
    candidate_groups = {str(group) for bucket in candidate_buckets for group in list(bucket.get("groups", []) or [])}
    candidate_slug_report = [
        {"slug": str(bucket.get("key") or ""), "groups": list(bucket.get("groups", []) or []), "group_count": int(bucket.get("group_count", 0) or 0)}
        for bucket in candidate_buckets
        if str(bucket.get("relation") or "") == "exact_slug"
    ]
    candidate_layer_report = [
        {
            "slug": str(bucket.get("key") or ""),
            "relation": str(bucket.get("relation") or ""),
            "layers": list(bucket.get("layers", []) or []),
            "groups": list(bucket.get("groups", []) or []),
            "group_count": int(bucket.get("group_count", 0) or 0),
        }
        for bucket in candidate_buckets
        if str(bucket.get("relation") or "") == "layered_slug"
    ]
    pairs: list[dict[str, object]] = []
    object_reports: list[dict[str, object]] = []
    warnings: list[str] = []
    total_moved_faces = 0
    total_moved_vertices = 0
    total_duplicated_vertices = 0
    checked_pair_count = 0
    skipped_pair_count = 0
    for obj in mesh_objects():
        signatures_by_group = collect_material_group_face_signatures(obj, candidate_groups)
        faces_to_move: set[int] = set()
        object_pairs: list[dict[str, object]] = []
        object_checked_pair_count = 0
        object_skipped_pair_count = 0
        checked_pairs_for_object: set[tuple[str, str]] = set()
        for bucket in candidate_buckets:
            bucket_key = str(bucket.get("key") or "")
            bucket_relation = str(bucket.get("relation") or "exact_slug")
            group_names_for_bucket = list(bucket.get("groups", []) or [])
            group_names = [str(name) for name in group_names_for_bucket if str(name) in signatures_by_group]
            for left_index, left_name in enumerate(group_names):
                left_signatures = signatures_by_group[left_name]
                if len(left_signatures) < 3:
                    continue
                for right_name in group_names[left_index + 1 :]:
                    pair_key = tuple(sorted((left_name, right_name)))
                    if pair_key in checked_pairs_for_object:
                        continue
                    checked_pairs_for_object.add(pair_key)
                    object_checked_pair_count += 1
                    checked_pair_count += 1
                    right_signatures = signatures_by_group[right_name]
                    min_faces = min(len(left_signatures), len(right_signatures))
                    if min_faces < 3:
                        object_skipped_pair_count += 1
                        skipped_pair_count += 1
                        continue
                    score, matched = compare_group_signatures(left_signatures, right_signatures)
                    if min_faces < STACKED_FACE_SMALL_GROUP_EXACT_THRESHOLD:
                        stacked = score >= 0.999
                    else:
                        stacked = score >= STACKED_FACE_SCORE_THRESHOLD
                    if not stacked:
                        continue
                    pair = {
                        "object": obj.name,
                        "group_a": left_name,
                        "group_b": right_name,
                        "slug": bucket_key,
                        "candidate_relation": bucket_relation,
                        "overlap_score": round(float(score), 6),
                        "matched_faces": int(matched),
                        "group_a_faces": len(left_signatures),
                        "group_b_faces": len(right_signatures),
                    }
                    object_pairs.append(pair)
                    pairs.append(pair)
                    faces_to_move.update(int(signature["face_index"]) for signature in left_signatures)
                    faces_to_move.update(int(signature["face_index"]) for signature in right_signatures)
        if not faces_to_move:
            continue
        try:
            offset_report = offset_faces_for_object(obj, faces_to_move, offset)
            moved_faces = int(offset_report.get("moved_faces", 0) or 0)
            moved_vertices = int(offset_report.get("moved_vertices", 0) or 0)
            duplicated_vertices = int(offset_report.get("duplicated_vertices", 0) or 0)
            total_moved_faces += moved_faces
            total_moved_vertices += moved_vertices
            total_duplicated_vertices += duplicated_vertices
            object_reports.append(
                {
                    "object": obj.name,
                    "stacked_pairs": object_pairs,
                    "checked_pair_count": object_checked_pair_count,
                    "skipped_pair_count": object_skipped_pair_count,
                    "moved_face_count": moved_faces,
                    "moved_vertex_count": moved_vertices,
                    "duplicated_vertex_count": duplicated_vertices,
                }
            )
        except Exception as exc:
            warnings.append(f"{obj.name}: failed to offset stacked material faces: {exc}")
    return {
        "offset": float(offset),
        "candidate_slug_count": len(candidate_slug_report),
        "candidate_slugs": candidate_slug_report,
        "candidate_layer_slug_count": len(candidate_layer_report),
        "candidate_layer_slugs": candidate_layer_report,
        "candidate_bucket_count": len(candidate_buckets),
        "checked_pair_count": checked_pair_count,
        "skipped_pair_count": skipped_pair_count,
        "pair_count": len(pairs),
        "pairs": pairs,
        "objects": object_reports,
        "moved_face_count": total_moved_faces,
        "moved_vertex_count": total_moved_vertices,
        "duplicated_vertex_count": total_duplicated_vertices,
        "warnings": warnings,
    }


def build_merge_plan_from_analysis(
    input_blend: Path,
    analysis: dict[str, object],
    previous_plan: dict[str, object],
    limit: int,
) -> dict[str, object]:
    raw_materials = analysis.get("materials", [])
    materials = [entry for entry in raw_materials if isinstance(entry, dict) and bool(entry.get("keep", True))]
    count = len(materials)
    group_size = max(1, math.ceil(count / max(1, limit))) if count > limit else 1
    merge_entries: list[dict[str, object]] = []
    for index, entry in enumerate(materials, start=1):
        group = ((index - 1) // group_size) + 1
        single = count <= limit
        final_name = str(entry.get("proposed_name") or entry.get("material_name") or f"mat_{index:03d}") if single else f"mat_group_{group:03d}"
        merge_entries.append(
            {
                "uid": entry.get("uid"),
                "material_name": entry.get("material_name"),
                "current_name": entry.get("proposed_name") or entry.get("material_name"),
                "group": group,
                "final_name": stripped_safe_name(final_name) or f"mat_group_{group:03d}",
                "vertex_count": entry.get("vertex_count", 0),
                "face_count": entry.get("face_count", 0),
                "base_color_path": entry.get("base_color_path", ""),
                "base_color_file": entry.get("base_color_file", ""),
                "base_color_key": entry.get("base_color_key", ""),
                "alpha": entry.get("alpha", 1.0),
                "warnings": entry.get("warnings", []),
                "enabled": True,
            }
        )
    return {
        "version": 1,
        "kind": "sort_materials_merge",
        "input_blend": str(input_blend),
        "material_limit": int(limit),
        "initial_material_count": count,
        "estimated_final_material_count": len({int(entry["group"]) for entry in merge_entries}),
        "use_material_combiner": count > limit,
        "source_plan_kind": previous_plan.get("kind"),
        "materials": merge_entries,
        "warnings": [],
    }


def save_material_mapping(
    path_json: Path | None,
    path_npy: Path | None,
    mapping: dict[str, object],
) -> None:
    if path_json:
        write_json(path_json, mapping)
    if path_npy:
        path_npy.parent.mkdir(parents=True, exist_ok=True)
        try:
            import numpy as np

            items = []
            final_materials = mapping.get("final_materials", [])
            if isinstance(final_materials, list):
                for entry in final_materials:
                    if isinstance(entry, dict):
                        items.append((entry.get("final_name", ""), entry.get("base_color_path", "")))
            np.save(str(path_npy.with_suffix("")), np.array(items, dtype=object))
        except Exception as exc:
            path_npy.with_suffix(".npy.warning.txt").write_text(str(exc), encoding="utf-8")


def apply_initial(
    input_blend: Path,
    plan: dict[str, object],
    output_blend: Path,
    report_json: Path,
    merge_plan_json: Path | None,
    materials_json: Path | None,
    materials_npy: Path | None,
    limit: int,
) -> None:
    started = time.monotonic()
    entries = entries_from_plan(plan)
    validate_material_names(entries)
    normalize_combine_targets(entries)
    print("Assigning manually selected base textures")
    manual_textures = apply_manual_base_textures(entries)
    print("Generating white fallback base textures for kept materials with no resolved base image")
    fallback_textures = ensure_fallback_base_textures(entries, output_blend.parent)
    print("Creating source material vertex groups")
    groups_report = create_source_vertex_groups(entries)
    print("Removing geometry assigned to unchecked materials")
    delete_report = delete_unkept_faces(entries)
    print("Combining materials with matching base-color texture keys")
    consolidate_report = consolidate_slots(entries, "combine_target_uid")
    rename_report = rename_target_materials(entries, "combine_target_uid")
    print("Detecting and offsetting stacked material tracking face groups")
    stacked_offsets_report = detect_and_offset_stacked_material_groups(entries)
    after_analysis, _after_plan = analyze_current_file(output_blend, limit)
    mark_remaining_materials_as_kept(after_analysis)
    merge_plan = build_merge_plan_from_analysis(output_blend, after_analysis, plan, limit)
    if merge_plan_json:
        write_json(merge_plan_json, merge_plan)
        print(f"Wrote material merge plan: {merge_plan_json}")
    mapping = {
        "version": 1,
        "stage": "initial",
        "source_blend": str(input_blend),
        "output_blend": str(output_blend),
        "source_materials": entries,
        "final_materials": after_analysis.get("materials", []),
        "source_vertex_groups": groups_report.get("created", []),
        "manual_base_textures": manual_textures.get("assigned", []),
        "generated_fallback_textures": fallback_textures.get("generated", []),
    }
    save_material_mapping(materials_json, materials_npy, mapping)
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    print(f"Saving material-sorted blend file: {output_blend}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    report = {
        "version": 1,
        "kind": "sort_materials_initial_report",
        "input_blend": str(input_blend),
        "output_blend": str(output_blend),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_vertex_groups": groups_report,
        "manual_base_textures": manual_textures,
        "deleted_geometry": delete_report,
        "consolidated_slots": consolidate_report,
        "renamed_materials": rename_report,
        "generated_fallback_textures": fallback_textures,
        "stacked_material_offsets": stacked_offsets_report,
        "after": after_analysis,
        "merge_plan": str(merge_plan_json) if merge_plan_json else "",
    }
    write_json(report_json, report)
    print(f"Wrote material initial report: {report_json}")


def merge_entries_from_plan(plan: dict[str, object]) -> list[dict[str, object]]:
    raw = plan.get("materials", [])
    if not isinstance(raw, list):
        raise RuntimeError("Material merge plan JSON is missing a materials list.")
    entries = [entry for entry in raw if isinstance(entry, dict) and entry.get("enabled", True)]
    if not entries:
        raise RuntimeError("Material merge plan has no enabled materials.")
    return entries


def validate_merge_names(entries: list[dict[str, object]]) -> dict[int, str]:
    final_by_group: dict[int, str] = {}
    for entry in entries:
        group = int(entry.get("group", 0) or 0)
        if group <= 0:
            raise RuntimeError(f"Invalid material merge group: {entry}")
        final = stripped_safe_name(str(entry.get("final_name") or "")) or f"mat_group_{group:03d}"
        if not is_safe_name(final):
            raise RuntimeError(f"Unsafe final material name for group {group}: {final!r}")
        if group in final_by_group and final_by_group[group] != final:
            final = final_by_group[group]
            entry["final_name"] = final
        final_by_group[group] = final
    names = list(final_by_group.values())
    if len(names) != len(set(names)):
        raise RuntimeError("Final material group names contain duplicates.")
    return final_by_group


def material_combiner_available() -> bool:
    try:
        import addon_utils

        candidates = ["material_combiner_addon", "material-combiner-addon-master"]
        for module in addon_utils.modules(refresh=True):
            name = getattr(module, "__name__", "")
            if name and ("material_combiner" in name or "material-combiner" in name):
                candidates.append(name)
        for name in dict.fromkeys(candidates):
            try:
                addon_utils.enable(name, default_set=False, persistent=False)
            except Exception:
                pass
    except Exception:
        pass
    try:
        bpy.ops.smc.refresh_ob_data.get_rna_type()
        bpy.ops.smc.combiner.get_rna_type()
        import PIL  # noqa: F401

        return True
    except Exception:
        return False


def consolidate_merge_groups(entries: list[dict[str, object]], final_by_group: dict[int, str]) -> dict[str, object]:
    # The material combiner add-on remains preferred for atlas generation, but this internal
    # consolidation is deterministic and keeps the workflow usable in background mode.
    uid_to_group = {str(entry.get("uid") or ""): int(entry.get("group", 0) or 0) for entry in entries}
    uid_to_entry = {str(entry.get("uid") or ""): entry for entry in entries}
    uid_by_slot = material_slots_by_uid(
        [
            {
                "uid": entry.get("uid"),
                "slot_refs": [
                    {"object": obj.name, "slot_index": slot_index}
                    for obj in mesh_objects()
                    for slot_index, mat in enumerate(obj.data.materials)
                    if mat is not None and mat.name == str(entry.get("current_name") or entry.get("material_name") or "")
                ],
            }
            for entry in entries
        ]
    )
    target_material_by_group: dict[int, bpy.types.Material] = {}
    for obj in mesh_objects():
        for slot_index, mat in enumerate(obj.data.materials):
            if mat is None:
                continue
            uid = uid_by_slot.get((obj.name, slot_index))
            if not uid:
                for entry in entries:
                    current = str(entry.get("current_name") or entry.get("material_name") or "")
                    if mat.name == current:
                        uid = str(entry.get("uid") or "")
                        break
            group = uid_to_group.get(str(uid or ""), 0)
            if group and group not in target_material_by_group:
                target_material_by_group[group] = mat

    changed_polygons = 0
    removed_slots = 0
    for obj in mesh_objects():
        old_slots = list(obj.data.materials)
        new_mats: list[bpy.types.Material] = []
        group_to_index: dict[int, int] = {}
        poly_groups: dict[int, int] = {}
        for poly in obj.data.polygons:
            mat = old_slots[poly.material_index] if 0 <= poly.material_index < len(old_slots) else None
            if mat is None:
                continue
            uid = ""
            for entry in entries:
                current = str(entry.get("current_name") or entry.get("material_name") or "")
                if mat.name == current:
                    uid = str(entry.get("uid") or "")
                    break
            group = uid_to_group.get(uid, 0)
            if not group:
                continue
            target = target_material_by_group.get(group) or mat
            if group not in group_to_index:
                group_to_index[group] = len(new_mats)
                new_mats.append(target)
            poly_groups[int(poly.index)] = group
        if not new_mats:
            continue
        obj.data.materials.clear()
        for mat in new_mats:
            obj.data.materials.append(mat)
        for poly in obj.data.polygons:
            group = poly_groups.get(int(poly.index))
            if group is None:
                continue
            new_index = group_to_index[group]
            if int(poly.material_index) != new_index:
                changed_polygons += 1
            poly.material_index = new_index
        removed_slots += max(0, len(old_slots) - len(new_mats))

    renamed: list[dict[str, object]] = []
    for group, mat in sorted(target_material_by_group.items()):
        old = mat.name
        mat.name = final_by_group[group]
        renamed.append({"group": group, "old_name": old, "new_name": mat.name})
    return {
        "method": "internal_group_consolidation",
        "changed_polygons": changed_polygons,
        "removed_slots": removed_slots,
        "renamed": renamed,
        "material_combiner_available": material_combiner_available(),
    }


def try_material_combiner_merge(entries: list[dict[str, object]], final_by_group: dict[int, str], output_dir: Path) -> dict[str, object]:
    if not material_combiner_available():
        return {"status": "unavailable", "method": "material_combiner", "reason": "operators or Pillow unavailable"}
    uid_by_name: dict[str, str] = {}
    group_by_uid: dict[str, int] = {}
    for entry in entries:
        uid = str(entry.get("uid") or "")
        if not uid or not entry.get("enabled", True):
            continue
        group_by_uid[uid] = int(entry.get("group", 0) or 0)
        for key in ("current_name", "material_name"):
            name = str(entry.get(key) or "")
            if name:
                uid_by_name[name] = uid
    try:
        ensure_object_mode()
        bpy.ops.object.select_all(action="DESELECT")
        for obj in mesh_objects():
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        bpy.ops.smc.refresh_ob_data()
        scene = bpy.context.scene
        configured = 0
        for item in scene.smc_ob_data:
            item_type = int(getattr(item, "type", -1))
            if item_type == 0:
                item.used = True
                continue
            if item_type != 1 or not getattr(item, "mat", None):
                continue
            uid = uid_by_name.get(item.mat.name, "")
            group = group_by_uid.get(uid, 0)
            item.used = bool(group)
            if group:
                item.layer = group
                configured += 1
        if configured <= 1:
            return {"status": "skipped", "method": "material_combiner", "reason": "not enough configured materials"}
        scene.smc_size = "QUAD"
        scene.smc_gaps = 0
        result = bpy.ops.smc.combiner(directory=str(output_dir))
        if "FINISHED" not in result:
            return {"status": "failed", "method": "material_combiner", "reason": str(result)}
        final_names = list(final_by_group.values())
        used_materials = []
        for obj in mesh_objects():
            for mat in obj.data.materials:
                if mat is not None and mat not in used_materials:
                    used_materials.append(mat)
        if len(used_materials) == len(final_names):
            for mat, name in zip(sorted(used_materials, key=lambda material: material.name), final_names):
                mat.name = name
        return {
            "status": "merged",
            "method": "material_combiner",
            "configured_materials": configured,
            "final_material_count": len(used_materials),
        }
    except Exception as exc:
        return {"status": "failed", "method": "material_combiner", "reason": str(exc)}


def create_final_vertex_groups(final_by_group: dict[int, str]) -> dict[str, object]:
    created: list[dict[str, object]] = []
    final_names = set(final_by_group.values())
    for obj in mesh_objects():
        vertices_by_name: dict[str, set[int]] = defaultdict(set)
        for poly in obj.data.polygons:
            if poly.material_index < 0 or poly.material_index >= len(obj.data.materials):
                continue
            mat = obj.data.materials[poly.material_index]
            if mat is None or mat.name not in final_names:
                continue
            vertices_by_name[mat.name].update(int(index) for index in poly.vertices)
        for final_name, vertices in vertices_by_name.items():
            group_name = "mci_final_" + final_name
            existing = obj.vertex_groups.get(group_name)
            if existing:
                obj.vertex_groups.remove(existing)
            group = obj.vertex_groups.new(name=group_name)
            group.add(sorted(vertices), 1.0, "REPLACE")
            created.append({"object": obj.name, "vertex_group": group_name, "vertex_count": len(vertices)})
    return {"created": created, "count": len(created)}


def validate_after_merge(analysis: dict[str, object], final_by_group: dict[int, str], limit: int, final_groups: dict[str, object]) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    materials = analysis.get("materials", [])
    material_count = len(materials) if isinstance(materials, list) else 0
    if material_count > limit:
        errors.append(f"Final material count {material_count} is above Source target {limit}.")
    names = [str(entry.get("material_name") or "") for entry in materials if isinstance(entry, dict)]
    unsafe = [name for name in names if not is_safe_name(name)]
    if unsafe:
        errors.append("Unsafe final material names: " + ", ".join(unsafe[:16]))
    if len(names) != len(set(names)):
        errors.append("Final material names contain duplicates.")
    created = final_groups.get("created", [])
    created_names = {str(entry.get("vertex_group") or "") for entry in created if isinstance(entry, dict)}
    missing_groups = [name for name in final_by_group.values() if "mci_final_" + name not in created_names]
    if missing_groups:
        errors.append("Missing final material tracking vertex groups: " + ", ".join(missing_groups[:16]))
    for entry in materials if isinstance(materials, list) else []:
        if isinstance(entry, dict) and entry_alpha(entry) < 0.999:
            warnings.append(f"{entry.get('material_name')}: alpha {entry_alpha(entry):.3f}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def apply_merge(
    input_blend: Path,
    plan: dict[str, object],
    output_blend: Path,
    report_json: Path,
    materials_json: Path | None,
    materials_npy: Path | None,
    limit: int,
) -> None:
    started = time.monotonic()
    entries = merge_entries_from_plan(plan)
    final_by_group = validate_merge_names(entries)
    print("Consolidating material merge groups")
    should_try_combiner = bool(plan.get("use_material_combiner")) and len(entries) > limit
    merge_report = try_material_combiner_merge(entries, final_by_group, output_blend.parent) if should_try_combiner else {"status": "skipped", "method": "material_combiner", "reason": "not required"}
    if merge_report.get("status") != "merged":
        fallback_report = consolidate_merge_groups(entries, final_by_group)
        fallback_report["material_combiner_attempt"] = merge_report
        merge_report = fallback_report
    print("Creating final material vertex groups")
    final_groups = create_final_vertex_groups(final_by_group)
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    print(f"Saving material-merged blend file: {output_blend}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    after_analysis, _unused_plan = analyze_current_file(output_blend, limit)
    mark_remaining_materials_as_kept(after_analysis)
    validation = validate_after_merge(after_analysis, final_by_group, limit, final_groups)
    mapping = {
        "version": 1,
        "stage": "merged",
        "source_blend": str(input_blend),
        "output_blend": str(output_blend),
        "merge_groups": entries,
        "final_materials": after_analysis.get("materials", []),
        "final_vertex_groups": final_groups.get("created", []),
        "validation": validation,
    }
    save_material_mapping(materials_json, materials_npy, mapping)
    report = {
        "version": 1,
        "kind": "sort_materials_merge_report",
        "input_blend": str(input_blend),
        "output_blend": str(output_blend),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "merge": merge_report,
        "final_vertex_groups": final_groups,
        "after": after_analysis,
        "validation": validation,
    }
    write_json(report_json, report)
    print(f"Wrote material merge report: {report_json}")
    if not validation.get("ok"):
        raise RuntimeError("Material merge validation failed:\n" + "\n".join(str(error) for error in validation.get("errors", [])))


def main() -> int:
    args = parse_args()
    print("Starting MMD Character Importer Blender step 5")
    print(f"Opening material input blend: {args.input_blend}")
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend))
    ensure_object_mode()

    if args.mode == "scan":
        if not args.scan_json:
            raise RuntimeError("--scan-json is required for scan mode.")
        analysis, plan = analyze_current_file(args.input_blend, args.limit)
        write_json(args.scan_json, analysis)
        write_json(args.plan_json, plan)
        print(f"Wrote material scan: {args.scan_json}")
        print(f"Wrote material plan: {args.plan_json}")
        return 0

    if args.mode == "apply-initial":
        if not args.output_blend or not args.report_json:
            raise RuntimeError("--output-blend and --report-json are required for apply-initial mode.")
        plan = load_json(args.plan_json)
        apply_initial(
            args.input_blend,
            plan,
            args.output_blend,
            args.report_json,
            args.merge_plan_json,
            args.materials_json,
            args.materials_npy,
            args.limit,
        )
        return 0

    if args.mode == "merge":
        if not args.output_blend or not args.report_json:
            raise RuntimeError("--output-blend and --report-json are required for merge mode.")
        plan = load_json(args.plan_json)
        apply_merge(
            args.input_blend,
            plan,
            args.output_blend,
            args.report_json,
            args.materials_json,
            args.materials_npy,
            args.limit,
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
