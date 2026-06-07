#!/usr/bin/env python3
"""Blender-side step 8 collision mesh generation helper."""

from __future__ import annotations

import argparse
import colorsys
import copy
import hashlib
import json
import math
import os
import platform
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Iterable

import bmesh
import bpy
from mathutils import Vector


SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_]+")
ROOT = Path(__file__).resolve().parents[1]
COACD_ADDON_ZIP = ROOT / "plugins_software" / "coacd_blender_addon_1_0_45.zip"
MAX_PREVIEW_TRIANGLES = 500000
EPSILON = 1e-7
MIN_MULTI_HULL_POINTS = 36
MAX_HULL_SAMPLE_POINTS = 34
HIGH_TRIANGLE_WARNING = 3600
SHRINK_PRESENTATION_OFFSET = 0.12
COACD_MAX_VERTICES = 64
COACD_THRESHOLD = 0.08
COACD_CACHE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MMDCharacterImporter" / "software" / "coacd_wheels"
COACD_RESULT_CACHE_VERSION = 2
EXCLUDED_SOURCE_OBJECT_TOKENS = (
    "physics",
)
ACTIVE_SOURCE_BODYGROUPS: set[str] | None = None
ACTIVE_ADDITIONAL_BONE_SELECTION: list[dict[str, object]] = []
ACTIVE_COACD_QUALITY = "fast_preview"
ACTIVE_RESULT_CACHE_DIR: Path | None = None

COACD_QUALITY_PRESETS = {
    "fast_preview": {
        "label": "Fast Preview",
        "threshold": 0.10,
        "resolution": 420,
        "preprocess_resolution": 28,
        "mcts_nodes": 4,
        "mcts_iterations": 12,
        "mcts_max_depth": 2,
        "max_ch_vertex": 48,
        "face_caps": {"small": 1800, "medium": 3200, "large": 5200},
    },
    "balanced": {
        "label": "Balanced",
        "threshold": 0.08,
        "resolution": 700,
        "preprocess_resolution": 40,
        "mcts_nodes": 6,
        "mcts_iterations": 24,
        "mcts_max_depth": 3,
        "max_ch_vertex": 56,
        "face_caps": {"small": 2800, "medium": 4800, "large": 7200},
    },
    "high_quality": {
        "label": "High Quality",
        "threshold": COACD_THRESHOLD,
        "resolution": 1000,
        "preprocess_resolution": 50,
        "mcts_nodes": 8,
        "mcts_iterations": 40,
        "mcts_max_depth": 3,
        "max_ch_vertex": COACD_MAX_VERTICES,
        "face_caps": {"small": 5000, "medium": 8000, "large": 12000},
    },
}

TARGET_BONES = [
    "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_Spine1",
    "ValveBiped.Bip01_Spine4",
    "ValveBiped.Bip01_R_Clavicle",
    "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_L_Clavicle",
    "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_Head1",
    "ValveBiped.Bip01_R_Thigh",
    "ValveBiped.Bip01_R_Calf",
    "ValveBiped.Bip01_R_Foot",
    "ValveBiped.Bip01_L_Thigh",
    "ValveBiped.Bip01_L_Calf",
    "ValveBiped.Bip01_L_Foot",
]
DEFAULT_TARGET_BONES = list(TARGET_BONES)
MAX_ADDITIONAL_COLLISION_GROUPS = 14
MAX_TOTAL_COLLISION_PARTS = 32

PHYSICS_SETTINGS = {
    "ValveBiped.Bip01_Pelvis": [{"command": "$jointrotdamping", "value": 3, "line": '$jointrotdamping "ValveBiped.Bip01_Pelvis" 3'}],
    "ValveBiped.Bip01_Spine1": [{"command": "$jointmassbias", "value": 8, "line": '$jointmassbias "ValveBiped.Bip01_Spine1" 8'}],
    "ValveBiped.Bip01_Spine4": [{"command": "$jointmassbias", "value": 9, "line": '$jointmassbias "ValveBiped.Bip01_Spine4" 9'}],
    "ValveBiped.Bip01_R_Clavicle": [{"command": "$jointmassbias", "value": 4, "line": '$jointmassbias "ValveBiped.Bip01_R_Clavicle" 4'}],
    "ValveBiped.Bip01_R_UpperArm": [{"command": "$jointmassbias", "value": 5, "line": '$jointmassbias "ValveBiped.Bip01_R_UpperArm" 5'}],
    "ValveBiped.Bip01_L_Clavicle": [{"command": "$jointmassbias", "value": 4, "line": '$jointmassbias "ValveBiped.Bip01_L_Clavicle" 4'}],
    "ValveBiped.Bip01_L_UpperArm": [{"command": "$jointmassbias", "value": 5, "line": '$jointmassbias "ValveBiped.Bip01_L_UpperArm" 5'}],
    "ValveBiped.Bip01_L_Forearm": [{"command": "$jointmassbias", "value": 4, "line": '$jointmassbias "ValveBiped.Bip01_L_Forearm" 4'}],
    "ValveBiped.Bip01_L_Hand": [{"command": "$jointrotdamping", "value": 1, "line": '$jointrotdamping "ValveBiped.Bip01_L_Hand" 1'}],
    "ValveBiped.Bip01_R_Forearm": [{"command": "$jointmassbias", "value": 4, "line": '$jointmassbias "ValveBiped.Bip01_R_Forearm" 4'}],
    "ValveBiped.Bip01_R_Hand": [{"command": "$jointrotdamping", "value": 1, "line": '$jointrotdamping "ValveBiped.Bip01_R_Hand" 1'}],
    "ValveBiped.Bip01_Head1": [{"command": "$jointmassbias", "value": 4, "line": '$jointmassbias "ValveBiped.Bip01_Head1" 4'}],
    "ValveBiped.Bip01_R_Thigh": [{"command": "$jointmassbias", "value": 7, "line": '$jointmassbias "ValveBiped.Bip01_R_Thigh" 7'}],
    "ValveBiped.Bip01_R_Calf": [{"command": "$jointmassbias", "value": 4, "line": '$jointmassbias "ValveBiped.Bip01_R_Calf" 4'}],
    "ValveBiped.Bip01_R_Foot": [{"command": "$jointrotdamping", "value": 9, "line": '$jointrotdamping "ValveBiped.Bip01_R_Foot" 9'}],
    "ValveBiped.Bip01_L_Thigh": [{"command": "$jointmassbias", "value": 7, "line": '$jointmassbias "ValveBiped.Bip01_L_Thigh" 7'}],
    "ValveBiped.Bip01_L_Calf": [{"command": "$jointmassbias", "value": 4, "line": '$jointmassbias "ValveBiped.Bip01_L_Calf" 4'}],
    "ValveBiped.Bip01_L_Foot": [{"command": "$jointrotdamping", "value": 9, "line": '$jointrotdamping "ValveBiped.Bip01_L_Foot" 9'}],
}

DEFAULT_PHYSICS_QC_SETTINGS = {
    "ValveBiped.Bip01_Pelvis": ['$jointrotdamping "{bone}" 3'],
    "ValveBiped.Bip01_Spine1": [
        '$jointmassbias "{bone}" 8',
        '$jointrotdamping "{bone}" 5',
        '$jointconstrain "{bone}" x limit -10 10 0',
        '$jointconstrain "{bone}" y limit -16 16 0',
        '$jointconstrain "{bone}" z limit -19 19 0',
    ],
    "ValveBiped.Bip01_Spine4": [
        '$jointmassbias "{bone}" 9',
        '$jointrotdamping "{bone}" 5',
        '$jointconstrain "{bone}" x limit -10 10 0',
        '$jointconstrain "{bone}" y limit -10 10 0',
        '$jointconstrain "{bone}" z limit -20 20 0',
    ],
    "ValveBiped.Bip01_R_Clavicle": [
        '$jointmassbias "{bone}" 4',
        '$jointrotdamping "{bone}" 6',
        '$jointconstrain "{bone}" x limit -10 10 0',
        '$jointconstrain "{bone}" y limit -5 5 0',
        '$jointconstrain "{bone}" z limit 0 15 0',
    ],
    "ValveBiped.Bip01_L_Clavicle": [
        '$jointmassbias "{bone}" 4',
        '$jointrotdamping "{bone}" 6',
        '$jointconstrain "{bone}" x limit -10 10 0',
        '$jointconstrain "{bone}" y limit -5 5 0',
        '$jointconstrain "{bone}" z limit 0 15 0',
    ],
    "ValveBiped.Bip01_R_UpperArm": [
        '$jointmassbias "{bone}" 5',
        '$jointconstrain "{bone}" x limit -15 20 0',
        '$jointconstrain "{bone}" y limit -40 32 0',
        '$jointconstrain "{bone}" z limit -80 25 0',
    ],
    "ValveBiped.Bip01_L_UpperArm": [
        '$jointmassbias "{bone}" 5',
        '$jointconstrain "{bone}" x limit -15 20 0',
        '$jointconstrain "{bone}" y limit -40 32 0',
        '$jointconstrain "{bone}" z limit -80 25 0',
    ],
    "ValveBiped.Bip01_L_Forearm": [
        '$jointmassbias "{bone}" 4',
        '$jointrotdamping "{bone}" 4',
        '$jointconstrain "{bone}" x limit -40 15 0',
        '$jointconstrain "{bone}" y limit 0 0 0',
        '$jointconstrain "{bone}" z limit -120 10 0',
    ],
    "ValveBiped.Bip01_R_Forearm": [
        '$jointmassbias "{bone}" 4',
        '$jointrotdamping "{bone}" 4',
        '$jointconstrain "{bone}" x limit -40 15 0',
        '$jointconstrain "{bone}" y limit 0 0 0',
        '$jointconstrain "{bone}" z limit -120 10 0',
    ],
    "ValveBiped.Bip01_L_Hand": [
        '$jointrotdamping "{bone}" 1',
        '$jointconstrain "{bone}" x limit -25 25 0',
        '$jointconstrain "{bone}" y limit -35 35 0',
        '$jointconstrain "{bone}" z limit -50 50 0',
    ],
    "ValveBiped.Bip01_R_Hand": [
        '$jointrotdamping "{bone}" 1',
        '$jointconstrain "{bone}" x limit -25 25 0',
        '$jointconstrain "{bone}" y limit -35 35 0',
        '$jointconstrain "{bone}" z limit -50 50 0',
    ],
    "ValveBiped.Bip01_Head1": [
        '$jointmassbias "{bone}" 4',
        '$jointrotdamping "{bone}" 3',
        '$jointconstrain "{bone}" x limit -50 50 0',
        '$jointconstrain "{bone}" y limit -20 20 0',
        '$jointconstrain "{bone}" z limit -26 30 0',
    ],
    "ValveBiped.Bip01_R_Thigh": [
        '$jointmassbias "{bone}" 7',
        '$jointrotdamping "{bone}" 7',
        '$jointconstrain "{bone}" x limit -30 30 0',
        '$jointconstrain "{bone}" y limit -60 30 0',
        '$jointconstrain "{bone}" z limit -100 30 0',
    ],
    "ValveBiped.Bip01_L_Thigh": [
        '$jointmassbias "{bone}" 7',
        '$jointrotdamping "{bone}" 7',
        '$jointconstrain "{bone}" x limit -30 30 0',
        '$jointconstrain "{bone}" y limit -30 60 0',
        '$jointconstrain "{bone}" z limit -100 30 0',
    ],
    "ValveBiped.Bip01_R_Calf": [
        '$jointmassbias "{bone}" 4',
        '$jointrotdamping "{bone}" 5',
        '$jointconstrain "{bone}" x limit -15 15 0',
        '$jointconstrain "{bone}" y limit -5 5 0',
        '$jointconstrain "{bone}" z limit -10 125 0',
    ],
    "ValveBiped.Bip01_L_Calf": [
        '$jointmassbias "{bone}" 4',
        '$jointrotdamping "{bone}" 5',
        '$jointconstrain "{bone}" x limit -15 15 0',
        '$jointconstrain "{bone}" y limit -5 5 0',
        '$jointconstrain "{bone}" z limit -10 125 0',
    ],
    "ValveBiped.Bip01_R_Foot": [
        '$jointrotdamping "{bone}" 9',
        '$jointconstrain "{bone}" x limit -15 15 0',
        '$jointconstrain "{bone}" y limit -15 15 0',
        '$jointconstrain "{bone}" z limit -18 25 0',
    ],
    "ValveBiped.Bip01_L_Foot": [
        '$jointrotdamping "{bone}" 9',
        '$jointconstrain "{bone}" x limit -15 15 0',
        '$jointconstrain "{bone}" y limit -15 15 0',
        '$jointconstrain "{bone}" z limit -18 25 0',
    ],
}

ROTATION_PRESETS = {
    "FS": {
        "label": "Front Skirt or Clothes",
        "lines": [
            '$jointconstrain "{bone}" x limit -80 2 0',
            '$jointconstrain "{bone}" y limit -2 2 0',
            '$jointconstrain "{bone}" z limit -2 2 0',
        ],
    },
    "GS": {
        "label": "Limited All Direction Rotation",
        "lines": [
            '$jointrotdamping "{bone}" 12',
            '$jointconstrain "{bone}" x limit -10 10 3',
            '$jointconstrain "{bone}" y limit -10 10 3',
            '$jointconstrain "{bone}" z limit -10 10 3',
        ],
    },
    "FL": {
        "label": "Front Left Hair",
        "lines": [
            '$jointconstrain "{bone}" x limit -60 10 0',
            '$jointconstrain "{bone}" y limit -10 60 0',
            '$jointconstrain "{bone}" z limit -15 15 0',
        ],
    },
    "FR": {
        "label": "Front Right Hair",
        "lines": [
            '$jointconstrain "{bone}" x limit -60 10 0',
            '$jointconstrain "{bone}" y limit -60 10 0',
            '$jointconstrain "{bone}" z limit -15 15 0',
        ],
    },
    "SR": {
        "label": "Side Right Skirt",
        "lines": [
            '$jointconstrain "{bone}" x limit -2 2 0',
            '$jointconstrain "{bone}" y limit -80 2 0',
            '$jointconstrain "{bone}" z limit -2 2 0',
        ],
    },
    "SL": {
        "label": "Side Left Skirt",
        "lines": [
            '$jointconstrain "{bone}" x limit -2 2 0',
            '$jointconstrain "{bone}" y limit -2 80 0',
            '$jointconstrain "{bone}" z limit -2 2 0',
        ],
    },
    "BS": {
        "label": "Back Skirt",
        "lines": [
            '$jointconstrain "{bone}" x limit -2 80 0',
            '$jointconstrain "{bone}" y limit -2 2 0',
            '$jointconstrain "{bone}" z limit -2 2 0',
        ],
    },
    "BH": {
        "label": "Back Hair or Tail",
        "lines": [
            '$jointconstrain "{bone}" x limit -30 105 0',
            '$jointconstrain "{bone}" y limit -30 30 0',
            '$jointconstrain "{bone}" z limit -15 15 0',
        ],
    },
    "BR": {
        "label": "Back Hair or Tail, Spin Right",
        "lines": [
            '$jointconstrain "{bone}" x limit -30 105 0',
            '$jointconstrain "{bone}" y limit -60 30 0',
            '$jointconstrain "{bone}" z limit -15 15 0',
        ],
    },
    "BL": {
        "label": "Back Hair or Tail, Spin Left",
        "lines": [
            '$jointconstrain "{bone}" x limit -30 105 0',
            '$jointconstrain "{bone}" y limit -30 60 0',
            '$jointconstrain "{bone}" z limit -15 15 0',
        ],
    },
    "GF": {
        "label": "Free Rotation for Hair",
        "lines": [
            '$jointconstrain "{bone}" x limit -100 100 0',
            '$jointconstrain "{bone}" y limit -45 45 0',
            '$jointconstrain "{bone}" z limit -30 30 0',
        ],
    },
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("scan-sources", "scan-bones", "analyze", "apply"), required=True)
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--analysis-json", type=Path)
    parser.add_argument("--plan-json", type=Path)
    parser.add_argument("--sources-json", type=Path)
    parser.add_argument("--bones-json", type=Path)
    parser.add_argument("--source-bodygroups-json", type=Path)
    parser.add_argument("--additional-bones-json", type=Path)
    parser.add_argument("--output-blend", type=Path)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--physics-settings-json", type=Path)
    parser.add_argument("--physics-smd", type=Path)
    parser.add_argument("--quality-preset", choices=tuple(COACD_QUALITY_PRESETS), default="fast_preview")
    parser.add_argument("--coacd-cache-dir", type=Path)
    return parser.parse_args(argv)


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def current_quality_preset() -> dict[str, object]:
    return COACD_QUALITY_PRESETS.get(ACTIVE_COACD_QUALITY, COACD_QUALITY_PRESETS["fast_preview"])


def current_quality_label() -> str:
    return str(current_quality_preset().get("label") or ACTIVE_COACD_QUALITY)


def quality_face_tier(bone_name: str) -> str:
    lower = bone_name.lower()
    if any(token in lower for token in ("hand", "foot", "clavicle")):
        return "small"
    if any(token in lower for token in ("forearm", "calf", "upperarm", "thigh")):
        return "medium"
    return "large"


def coacd_face_cap_for_bone(bone_name: str) -> int:
    preset = current_quality_preset()
    face_caps = preset.get("face_caps", {})
    if not isinstance(face_caps, dict):
        return 5200
    return int(face_caps.get(quality_face_tier(bone_name), face_caps.get("medium", 5200)) or 5200)


def timing_entry(started: float) -> float:
    return round(float(time.monotonic() - started), 4)


def json_cache_key(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8", "replace")
    return hashlib.sha256(encoded).hexdigest()


def v3(value: Vector) -> list[float]:
    return [round(float(value.x), 6), round(float(value.y), 6), round(float(value.z), 6)]


def natural_key(value: object) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(value))]


def safe_fragment(value: str) -> str:
    return SAFE_NAME_RE.sub("_", str(value or "")).strip("_").lower() or "item"


def ensure_object_mode() -> None:
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")


def armature_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]


def mesh_objects(include_physics: bool = False) -> list[bpy.types.Object]:
    objects = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if not include_physics and obj.name == "Physics":
            continue
        objects.append(obj)
    return objects


def set_active_source_bodygroups(source_json: Path | None) -> None:
    global ACTIVE_SOURCE_BODYGROUPS
    ACTIVE_SOURCE_BODYGROUPS = None
    if source_json is None:
        return
    data = json.loads(source_json.read_text(encoding="utf-8"))
    raw_names = data.get("enabled_bodygroups", data.get("bodygroups", [])) if isinstance(data, dict) else []
    if isinstance(raw_names, list):
        ACTIVE_SOURCE_BODYGROUPS = {str(name) for name in raw_names if str(name)}
        log_progress(f"Using {len(ACTIVE_SOURCE_BODYGROUPS):,} user-selected CoACD source bodygroup(s).")


def set_active_additional_bones(selection_json: Path | None) -> None:
    global ACTIVE_ADDITIONAL_BONE_SELECTION
    ACTIVE_ADDITIONAL_BONE_SELECTION = []
    if selection_json is None:
        return
    data = json.loads(selection_json.read_text(encoding="utf-8"))
    raw_groups = data.get("additional_groups", []) if isinstance(data, dict) else []
    if isinstance(raw_groups, list):
        ACTIVE_ADDITIONAL_BONE_SELECTION = [dict(group) for group in raw_groups if isinstance(group, dict)]
    log_progress(f"Using {len(ACTIVE_ADDITIONAL_BONE_SELECTION):,} user-selected additional CoACD bone group(s).")


def source_selection_summary() -> dict[str, object]:
    if ACTIVE_SOURCE_BODYGROUPS is None:
        return {"mode": "all_bodygroups", "enabled_bodygroups": []}
    return {"mode": "explicit_bodygroups", "enabled_bodygroups": sorted(ACTIVE_SOURCE_BODYGROUPS, key=natural_key)}


def rotation_presets_for_json() -> list[dict[str, object]]:
    presets: list[dict[str, object]] = []
    for code in sorted(ROTATION_PRESETS):
        preset = ROTATION_PRESETS[code]
        lines = [str(line).format(bone="{bone}") for line in preset.get("lines", [])]
        presets.append({"code": code, "label": str(preset.get("label") or code), "lines": lines})
    return presets


def qc_templates_to_settings(bone_name: str, templates: Iterable[str]) -> list[dict[str, object]]:
    settings: list[dict[str, object]] = []
    for template in templates:
        line = str(template).format(bone=bone_name)
        command = line.split()[0] if line.split() else ""
        settings.append({"command": command, "line": line})
    return settings


def default_physics_settings_for_bone(bone_name: str) -> list[dict[str, object]]:
    templates = DEFAULT_PHYSICS_QC_SETTINGS.get(bone_name)
    if templates:
        return qc_templates_to_settings(bone_name, templates)
    return [dict(entry) for entry in PHYSICS_SETTINGS.get(bone_name, []) if isinstance(entry, dict)]


def rotation_settings_for_bone(bone_name: str, rotation_type: str) -> list[dict[str, object]]:
    preset = ROTATION_PRESETS.get(str(rotation_type or "").upper())
    if not preset:
        return []
    return qc_templates_to_settings(bone_name, preset.get("lines", []))


def settings_for_target_spec(spec: dict[str, object]) -> list[dict[str, object]]:
    bone_name = str(spec.get("bone") or "")
    if str(spec.get("kind") or "default") == "additional":
        return rotation_settings_for_bone(bone_name, str(spec.get("rotation_type") or ""))
    return default_physics_settings_for_bone(bone_name)


def collision_qc_lines_for_specs(target_specs: list[dict[str, object]]) -> list[str]:
    lines = [
        '$collisionjoints "Physics.smd" \n',
        "{\n",
        "\t$mass 48 \n",
        "\t$inertia 12 \n",
        "\t$damping 0.8 \n",
        "\t$rotdamping 4 \n",
        '\t$rootbone "ValveBiped.Bip01_Pelvis" \n\n',
    ]
    for spec in target_specs:
        bone_name = str(spec.get("bone") or "")
        if not bone_name:
            continue
        settings = settings_for_target_spec(spec)
        for entry in settings:
            line = str(entry.get("line") or "").strip()
            if line:
                lines.append(f"\t{line} \n")
        if settings:
            lines.append("\n")
    lines.extend(
        [
            "}\n\n",
            "$collisiontext\n",
            "{\n",
            "\tanimatedfriction\n\t{\n",
            '\t\tanimfrictionmin\t\t"80.000000"\n',
            '\t\tanimfrictionmax\t\t"600.000000"\n',
            '\t\tanimfrictiontimein\t\t"0.150000"\n',
            '\t\tanimfrictiontimeout\t\t"0.250000"\n',
            '\t\tanimfrictiontimehold\t\t"1.750000"\n',
            "\t}\n",
            "\teditparams\n\t{\n",
            '\t\trootname\t\t"valvebiped.bip01_pelvis"\n',
            '\t\ttotalmass\t\t"50.000000"\n',
            "\t}\n",
            "}\n",
        ]
    )
    return lines


def main_armature() -> bpy.types.Object | None:
    armatures = armature_objects()
    if not armatures:
        return None
    return max(armatures, key=lambda obj: len(obj.data.bones))


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


def scan_collision_bones(input_blend: Path) -> dict[str, object]:
    log_progress(f"Scanning CoACD bones for {input_blend}.")
    armature = main_armature()
    preview = collect_model_preview()
    bone_preview = collect_bone_preview(armature)
    bones: list[dict[str, object]] = []
    default_set = set(DEFAULT_TARGET_BONES)
    if armature is not None:
        for bone in sorted(armature.data.bones, key=lambda item: natural_key(item.name)):
            is_default = bone.name in default_set
            children = sorted((child.name for child in bone.children), key=natural_key)
            warning = "Default ValveBiped collision target; already enabled." if is_default else ""
            head = armature.matrix_world @ bone.head_local
            tail = armature.matrix_world @ bone.tail_local
            bones.append(
                {
                    "uid": bone.name,
                    "name": bone.name,
                    "parent": bone.parent.name if bone.parent else "",
                    "children": children,
                    "head": v3(head),
                    "tail": v3(tail),
                    "is_default_target": is_default,
                    "eligible": not is_default,
                    "warnings": [warning] if warning else [],
                }
            )
    log_progress(f"Found {len(bones):,} armature bone(s) for optional collision groups.")
    return {
        "version": 1,
        "kind": "collision_bones",
        "input_blend": str(input_blend),
        "armature": armature.name if armature else "",
        "default_target_bones": DEFAULT_TARGET_BONES,
        "max_additional_groups": MAX_ADDITIONAL_COLLISION_GROUPS,
        "max_total_collision_parts": MAX_TOTAL_COLLISION_PARTS,
        "bones": bones,
        "bone_preview": bone_preview,
        "rotation_presets": rotation_presets_for_json(),
        "model_preview": preview.get("model_preview", {}),
        "materials": preview.get("materials", []),
        "material_count": preview.get("material_count", 0),
    }


def ordered_direct_chain(armature: bpy.types.Object, raw_names: Iterable[str]) -> tuple[list[str], list[str]]:
    names = [str(name) for name in raw_names if str(name)]
    unique = []
    for name in names:
        if name not in unique:
            unique.append(name)
    selected = set(unique)
    errors: list[str] = []
    for name in unique:
        if name not in armature.data.bones:
            errors.append(f"Additional collision bone does not exist: {name}")
    if errors or not unique:
        return [], errors
    roots = []
    for name in unique:
        bone = armature.data.bones[name]
        if bone.parent is None or bone.parent.name not in selected:
            roots.append(name)
    if len(roots) != 1:
        return [], [f"Additional collision group must form one direct parent-child chain; found {len(roots)} chain roots."]
    ordered = [roots[0]]
    current = armature.data.bones[roots[0]]
    while True:
        selected_children = [child.name for child in current.children if child.name in selected]
        if not selected_children:
            break
        if len(selected_children) > 1:
            return [], [f"Additional collision group branches at {current.name}; choose one direct chain."]
        ordered.append(selected_children[0])
        current = armature.data.bones[selected_children[0]]
    if set(ordered) != selected:
        return [], ["Additional collision group must be a continuous direct parent-child chain."]
    return ordered, []


def resolve_additional_collision_groups(armature: bpy.types.Object | None) -> tuple[list[dict[str, object]], list[str]]:
    if not ACTIVE_ADDITIONAL_BONE_SELECTION:
        return [], []
    if armature is None:
        return [], ["Additional CoACD bones were selected, but the model has no armature."]
    errors: list[str] = []
    merged: dict[int, dict[str, object]] = {}
    for raw in ACTIVE_ADDITIONAL_BONE_SELECTION:
        try:
            group_id = int(raw.get("group", 0) or 0)
        except Exception:
            group_id = 0
        if group_id < 1 or group_id > MAX_ADDITIONAL_COLLISION_GROUPS:
            errors.append(f"Additional collision group must be between 1 and {MAX_ADDITIONAL_COLLISION_GROUPS}: {raw.get('group')}")
            continue
        bones = raw.get("bones", [])
        if isinstance(bones, str):
            bones = [bones]
        if not isinstance(bones, list):
            bones = []
        rotation_type = str(raw.get("rotation_type") or "").upper().strip()
        entry = merged.setdefault(group_id, {"group": group_id, "bones": [], "rotation_type": rotation_type})
        if rotation_type:
            if entry.get("rotation_type") and str(entry.get("rotation_type")) != rotation_type:
                errors.append(f"Additional collision group {group_id} has conflicting rotation types.")
            entry["rotation_type"] = rotation_type
        for bone_name in bones:
            text = str(bone_name or "")
            if text and text not in entry["bones"]:
                entry["bones"].append(text)
    if len(merged) > MAX_ADDITIONAL_COLLISION_GROUPS:
        errors.append(f"At most {MAX_ADDITIONAL_COLLISION_GROUPS} additional collision groups are allowed.")
    default_set = set(DEFAULT_TARGET_BONES)
    used_bones: set[str] = set()
    groups: list[dict[str, object]] = []
    for group_id in sorted(merged):
        raw = merged[group_id]
        bones = [str(name) for name in raw.get("bones", []) if str(name)]
        rotation_type = str(raw.get("rotation_type") or "").upper()
        if not bones:
            errors.append(f"Additional collision group {group_id} has no bones.")
            continue
        if rotation_type not in ROTATION_PRESETS:
            errors.append(f"Additional collision group {group_id} is missing a valid rotation type.")
        for bone_name in bones:
            if bone_name in default_set:
                errors.append(f"Additional collision group {group_id} cannot reuse default target bone {bone_name}.")
            if bone_name in used_bones:
                errors.append(f"Additional collision bone {bone_name} is assigned to more than one group.")
            used_bones.add(bone_name)
        chain, chain_errors = ordered_direct_chain(armature, bones)
        errors.extend(f"Additional collision group {group_id}: {error}" for error in chain_errors)
        if not chain:
            continue
        owner = chain[0]
        groups.append(
            {
                "group": group_id,
                "bone": owner,
                "owner_bone": owner,
                "bones": chain,
                "rotation_type": rotation_type,
                "rotation_label": str(ROTATION_PRESETS.get(rotation_type, {}).get("label") or rotation_type),
                "uid": f"collision_extra_{group_id:02d}_{safe_fragment(owner)}",
            }
        )
    if len(DEFAULT_TARGET_BONES) + len(groups) > MAX_TOTAL_COLLISION_PARTS:
        errors.append(f"Collision generation supports at most {MAX_TOTAL_COLLISION_PARTS} total parts.")
    return groups, sorted(set(errors))


def target_specs_for_armature(armature: bpy.types.Object | None) -> tuple[list[dict[str, object]], list[str], list[dict[str, object]]]:
    additional_groups, errors = resolve_additional_collision_groups(armature)
    specs: list[dict[str, object]] = []
    for index, bone_name in enumerate(DEFAULT_TARGET_BONES, start=1):
        specs.append(
            {
                "bone": bone_name,
                "uid": f"collision_{index:02d}_{safe_fragment(bone_name)}",
                "kind": "default",
                "group_bones": [bone_name],
                "influence_bones": None,
                "collision_group": None,
                "rotation_type": "",
            }
        )
    for group in additional_groups:
        specs.append(
            {
                "bone": str(group.get("owner_bone") or group.get("bone") or ""),
                "uid": str(group.get("uid") or ""),
                "kind": "additional",
                "group_bones": list(group.get("bones", [])) if isinstance(group.get("bones"), list) else [],
                "influence_bones": list(group.get("bones", [])) if isinstance(group.get("bones"), list) else [],
                "collision_group": int(group.get("group", 0) or 0),
                "rotation_type": str(group.get("rotation_type") or ""),
                "rotation_label": str(group.get("rotation_label") or ""),
            }
        )
    return specs, errors, additional_groups


def material_texture_path(mat: bpy.types.Material | None) -> str:
    if mat is None or mat.node_tree is None:
        return ""
    nodes = list(mat.node_tree.nodes)
    preferred = []
    for node in nodes:
        if getattr(node, "type", "") != "TEX_IMAGE" or getattr(node, "image", None) is None:
            continue
        name = f"{node.name} {node.label}".lower()
        score = 0
        if "mmd_base_tex" in name:
            score += 100
        if any(token in name for token in ("base", "diffuse", "albedo", "color")):
            score += 30
        preferred.append((score, node))
    preferred.sort(key=lambda item: item[0], reverse=True)
    for _score, node in preferred:
        image = node.image
        if image is None:
            continue
        if image.packed_file:
            return f"packed:{image.name}"
        path = bpy.path.abspath(image.filepath or "")
        if path:
            return path
    return ""


def preview_color(uid: str, index: int) -> list[float]:
    seed = sum((offset + 1) * ord(char) for offset, char in enumerate(uid)) + index * 37
    hue = (seed % 360) / 360.0
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.46, 0.86)
    return [round(red, 4), round(green, 4), round(blue, 4), 1.0]


def material_for_polygon(obj: bpy.types.Object, poly: bpy.types.MeshPolygon) -> bpy.types.Material | None:
    if 0 <= int(poly.material_index) < len(obj.data.materials):
        return obj.data.materials[int(poly.material_index)]
    return None


def collect_model_preview(max_triangles: int = MAX_PREVIEW_TRIANGLES) -> dict[str, object]:
    objects = sorted(mesh_objects(include_physics=False), key=lambda item: natural_key(item.name))
    total_triangles = sum(max(0, len(poly.vertices) - 2) for obj in objects for poly in obj.data.polygons)
    stride = max(1, math.ceil(total_triangles / max_triangles)) if total_triangles else 1
    triangles: list[dict[str, object]] = []
    materials_by_uid: dict[str, dict[str, object]] = {}
    points: list[list[float]] = []
    triangle_index = 0
    for object_index, obj in enumerate(objects, start=1):
        bodygroup_uid = f"bodygroup_{object_index:03d}_{safe_fragment(obj.name)[:32]}"
        uv_layer = obj.data.uv_layers.active
        for poly in obj.data.polygons:
            material_index = int(poly.material_index)
            mat = material_for_polygon(obj, poly)
            mat_name = mat.name if mat is not None else "No_Material"
            material_uid = f"{bodygroup_uid}__mat_{material_index:03d}_{safe_fragment(mat_name)[:32]}"
            texture_path = material_texture_path(mat)
            if material_uid not in materials_by_uid:
                materials_by_uid[material_uid] = {
                    "uid": material_uid,
                    "bodygroup_uid": bodygroup_uid,
                    "highlight_group": bodygroup_uid,
                    "material_name": f"{obj.name} / {mat_name}",
                    "proposed_name": mat_name,
                    "bodygroup": obj.name,
                    "keep": True,
                    "preview_color": preview_color(material_uid, object_index + material_index + 1),
                    "base_color_path": texture_path if texture_path and not texture_path.startswith("packed:") else "",
                    "base_color_file": Path(texture_path).name if texture_path and not texture_path.startswith("packed:") else texture_path,
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
                            "object_name": obj.name,
                            "bodygroup": obj.name,
                            "polygon_index": int(poly.index),
                            "texture_path": texture_path if texture_path and not texture_path.startswith("packed:") else "",
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


def collect_collision_source_bodygroups(
    armature: bpy.types.Object | None,
    target_specs: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    influence_names: set[str] = set()
    target_influences: dict[str, list[str]] = {}
    if armature is not None:
        target_specs = target_specs or target_specs_for_armature(armature)[0]
        target_influences = {
            str(spec.get("bone") or ""): influence_bones_for_spec(armature, spec)
            for spec in target_specs
            if spec.get("bone")
        }
        for names in target_influences.values():
            influence_names.update(names)
    bodygroups: list[dict[str, object]] = []
    for index, obj in enumerate(sorted(mesh_objects(include_physics=False), key=lambda item: natural_key(item.name)), start=1):
        material_names = []
        for material in obj.data.materials:
            if material is not None and material.name not in material_names:
                material_names.append(material.name)
        face_count = sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons)
        weighted_vertices = 0
        target_hits: set[str] = set()
        if armature is not None and influence_names:
            group_by_index = {group.index: group.name for group in obj.vertex_groups}
            for vertex in obj.data.vertices:
                has_target_weight = False
                for target_name, names in target_influences.items():
                    if vertex_group_weight_any(obj, vertex, names, group_by_index) > 0.0:
                        has_target_weight = True
                        target_hits.add(target_name)
                if has_target_weight:
                    weighted_vertices += 1
        warning = ""
        if weighted_vertices == 0 and armature is not None:
            warning = "No vertices are weighted to Step 8 target bones."
        bodygroups.append(
            {
                "uid": f"source_bodygroup_{index:03d}_{safe_fragment(obj.name)[:40]}",
                "name": obj.name,
                "enabled": True,
                "vertex_count": len(obj.data.vertices),
                "face_count": face_count,
                "material_count": len(material_names),
                "materials": sorted(material_names, key=natural_key),
                "target_weighted_vertex_count": weighted_vertices,
                "target_bones": sorted(target_hits, key=natural_key),
                "warnings": [warning] if warning else [],
            }
        )
    return bodygroups


def scan_source_bodygroups(input_blend: Path) -> dict[str, object]:
    log_progress(f"Scanning CoACD source bodygroups for {input_blend}.")
    armature = main_armature()
    preview = collect_model_preview()
    target_specs, selection_errors, additional_groups = target_specs_for_armature(armature)
    sources = collect_collision_source_bodygroups(armature, target_specs)
    log_progress(f"Found {len(sources):,} available collision source bodygroup(s).")
    return {
        "version": 1,
        "kind": "collision_sources",
        "input_blend": str(input_blend),
        "armature": armature.name if armature else "",
        "default_target_bones": DEFAULT_TARGET_BONES,
        "target_bones": [str(spec.get("bone") or "") for spec in target_specs if spec.get("bone")],
        "additional_collision_groups": additional_groups,
        "additional_collision_errors": selection_errors,
        "source_bodygroups": sources,
        "selected_source_bodygroups": [str(entry.get("name") or "") for entry in sources],
        "selection": {"mode": "all_bodygroups", "enabled_bodygroups": [str(entry.get("name") or "") for entry in sources]},
        "model_preview": preview.get("model_preview", {}),
        "materials": preview.get("materials", []),
        "material_count": preview.get("material_count", 0),
    }


def target_shape_type(bone_name: str) -> str:
    lower = bone_name.lower()
    if any(token in lower for token in ("hand", "foot")):
        return "oriented_box"
    if any(token in lower for token in ("upperarm", "forearm", "thigh", "calf", "clavicle")):
        return "capsule"
    return "ellipsoid"


def default_shrink(bone_name: str) -> float:
    lower = bone_name.lower()
    if "head" in lower:
        base = 0.78
    elif any(token in lower for token in ("spine", "pelvis")):
        base = 0.74
    elif any(token in lower for token in ("hand", "foot", "clavicle")):
        base = 0.70
    else:
        base = 0.72
    return round(base + SHRINK_PRESENTATION_OFFSET, 6)


def orthonormal_basis(axis: Vector) -> tuple[Vector, Vector, Vector]:
    z_axis = axis.normalized() if axis.length > EPSILON else Vector((0.0, 0.0, 1.0))
    ref = Vector((0.0, 0.0, 1.0))
    if abs(z_axis.dot(ref)) > 0.88:
        ref = Vector((1.0, 0.0, 0.0))
    x_axis = ref.cross(z_axis)
    if x_axis.length <= EPSILON:
        x_axis = Vector((1.0, 0.0, 0.0))
    x_axis.normalize()
    y_axis = z_axis.cross(x_axis)
    if y_axis.length <= EPSILON:
        y_axis = Vector((0.0, 1.0, 0.0))
    y_axis.normalize()
    return x_axis, y_axis, z_axis


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return float(ordered[index])


def platform_wheel_tags() -> list[str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return ["win_amd64"]
    if system == "darwin":
        return ["macosx", "arm64" if ("arm" in machine or "aarch64" in machine) else "x86_64"]
    if "linux" in system:
        return ["manylinux", "aarch64" if ("aarch64" in machine or "arm64" in machine) else "x86_64"]
    return []


def installed_coacd_wheels_dirs() -> list[Path]:
    candidates: list[Path] = []
    try:
        for scripts_path in bpy.utils.script_paths("addons"):
            path = Path(scripts_path) / "coacd_blender_addon" / "wheels"
            if path.exists():
                candidates.append(path)
    except Exception:
        pass
    return candidates


def find_matching_coacd_wheel() -> Path | None:
    tags = platform_wheel_tags()
    for wheels_dir in installed_coacd_wheels_dirs():
        wheels = sorted(wheels_dir.glob("coacd_u-*.whl"))
        for wheel in wheels:
            lower = wheel.name.lower()
            if all(tag in lower for tag in tags):
                return wheel
    if not COACD_ADDON_ZIP.exists():
        return None
    try:
        with zipfile.ZipFile(COACD_ADDON_ZIP) as archive:
            members = sorted(name for name in archive.namelist() if name.startswith("coacd_blender_addon/wheels/coacd_u-") and name.endswith(".whl"))
            for member in members:
                lower = member.lower()
                if all(tag in lower for tag in tags):
                    COACD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    destination = COACD_CACHE_DIR / Path(member).name
                    source_info = archive.getinfo(member)
                    if not destination.exists() or destination.stat().st_size != source_info.file_size:
                        with archive.open(member) as source, destination.open("wb") as handle:
                            shutil.copyfileobj(source, handle)
                    return destination
    except Exception:
        return None
    return None


def ensure_coacd_module():
    try:
        import coacd_u as coacd_mod  # type: ignore

        return coacd_mod, "imported"
    except Exception:
        pass
    wheel = find_matching_coacd_wheel()
    if wheel is None:
        return None, "No matching bundled CoACD wheel was found."
    extract_dir = COACD_CACHE_DIR / wheel.stem
    marker = extract_dir / ".complete"
    if not marker.exists():
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(extract_dir)
        marker.write_text("ok", encoding="utf-8")
    if str(extract_dir) not in sys.path:
        sys.path.insert(0, str(extract_dir))
    try:
        import coacd_u as coacd_mod  # type: ignore

        return coacd_mod, f"loaded from {wheel.name}"
    except Exception as exc:
        return None, f"CoACD wheel could not be imported: {exc}"


def coacd_runtime_status() -> dict[str, object]:
    module, source = ensure_coacd_module()
    return {
        "available": module is not None,
        "source": source,
        "module_file": str(getattr(module, "__file__", "")) if module is not None else "",
    }


def bone_points(armature: bpy.types.Object, bone_name: str) -> tuple[Vector, Vector]:
    bone = armature.data.bones[bone_name]
    return bone.head_local.copy(), bone.tail_local.copy()


def bone_span_points(armature: bpy.types.Object, bone_name: str, group_bones: Iterable[str] | None = None) -> tuple[Vector, Vector]:
    names = [str(name) for name in (group_bones or []) if str(name) in armature.data.bones]
    if not names:
        return bone_points(armature, bone_name)
    first = armature.data.bones[names[0]]
    last = armature.data.bones[names[-1]]
    return first.head_local.copy(), last.tail_local.copy()


def is_collision_source_object(obj: bpy.types.Object) -> bool:
    name = safe_fragment(obj.name)
    if any(token in name for token in EXCLUDED_SOURCE_OBJECT_TOKENS):
        return False
    if ACTIVE_SOURCE_BODYGROUPS is None:
        return True
    return obj.name in ACTIVE_SOURCE_BODYGROUPS


def log_progress(message: str) -> None:
    print(f"[Step8 Collision] {message}", flush=True)


def side_token_for_bone(bone_name: str) -> str:
    lower = bone_name.lower()
    if "_l_" in lower or lower.endswith("_l") or ".bip01_l_" in lower:
        return "l"
    if "_r_" in lower or lower.endswith("_r") or ".bip01_r_" in lower:
        return "r"
    return ""


def side_matches(candidate: str, side: str) -> bool:
    if not side:
        return False
    lower = candidate.lower()
    return f"_{side}_" in lower or lower.endswith(f"_{side}") or f".bip01_{side}_" in lower


def collision_influence_bones(armature: bpy.types.Object, bone_name: str) -> list[str]:
    names: list[str] = []

    def add(name: str) -> None:
        if name and name in armature.data.bones and name not in names:
            names.append(name)

    add(bone_name)
    if bone_name == "ValveBiped.Bip01_Spine1":
        add("ValveBiped.Bip01_Spine")
    elif bone_name == "ValveBiped.Bip01_Spine4":
        add("ValveBiped.Bip01_Spine2")
    elif bone_name == "ValveBiped.Bip01_Head1":
        add("ValveBiped.Bip01_Neck1")
        add("Eye_L")
        add("Eye_R")

    side = side_token_for_bone(bone_name)
    lower_bone = bone_name.lower()
    if side and "upperarm" in lower_bone:
        add(f"ZArmTwist_{side.upper()}")
    elif side and "forearm" in lower_bone:
        add(f"ZHandTwist_{side.upper()}")
    elif side and "hand" in lower_bone:
        for bone in armature.data.bones:
            lower = bone.name.lower()
            if side_matches(lower, side) and any(token in lower for token in ("finger", "thumb")):
                add(bone.name)
    elif side and "foot" in lower_bone:
        for bone in armature.data.bones:
            lower = bone.name.lower()
            if side_matches(lower, side) and ("toe" in lower or "ball" in lower):
                add(bone.name)
    return names


def influence_bones_for_spec(armature: bpy.types.Object, spec: dict[str, object]) -> list[str]:
    raw = spec.get("influence_bones")
    if isinstance(raw, list) and raw:
        names = []
        for item in raw:
            name = str(item or "")
            if name and name in armature.data.bones and name not in names:
                names.append(name)
        if names:
            return names
    return collision_influence_bones(armature, str(spec.get("bone") or ""))


def collect_weighted_vertex_cloud(
    armature: bpy.types.Object,
    filtered_sources: bool = True,
    target_specs: list[dict[str, object]] | None = None,
) -> dict[str, list[Vector]]:
    armature_inv = armature.matrix_world.inverted()
    target_specs = target_specs or target_specs_for_armature(armature)[0]
    target_names = [str(spec.get("bone") or "") for spec in target_specs if spec.get("bone")]
    clouds: dict[str, list[Vector]] = {name: [] for name in target_names}
    influence_by_target = {str(spec.get("bone") or ""): influence_bones_for_spec(armature, spec) for spec in target_specs if spec.get("bone")}
    for obj in mesh_objects(include_physics=False):
        if filtered_sources and not is_collision_source_object(obj):
            continue
        group_by_index = {group.index: group.name for group in obj.vertex_groups}
        world = obj.matrix_world
        for vertex in obj.data.vertices:
            coord = armature_inv @ (world @ vertex.co)
            for target_name, influence_names in influence_by_target.items():
                weight = vertex_group_weight_any(obj, vertex, influence_names, group_by_index)
                if weight > 0.0:
                    clouds[target_name].append(coord.copy())
    return clouds


def vertex_group_weight(obj: bpy.types.Object, vertex: bpy.types.MeshVertex, bone_name: str, group_by_index: dict[int, str]) -> float:
    best = 0.0
    for group_ref in vertex.groups:
        if group_by_index.get(group_ref.group) == bone_name:
            best = max(best, float(group_ref.weight))
    return best


def vertex_group_weight_any(obj: bpy.types.Object, vertex: bpy.types.MeshVertex, bone_names: Iterable[str], group_by_index: dict[int, str]) -> float:
    wanted = set(bone_names)
    total = 0.0
    for group_ref in vertex.groups:
        if group_by_index.get(group_ref.group) in wanted:
            total += float(group_ref.weight)
    return total


def weight_threshold_for_bone(
    armature: bpy.types.Object,
    bone_name: str,
    filtered_sources: bool = True,
    influence_bones: list[str] | None = None,
) -> dict[str, object]:
    influence_bones = influence_bones or collision_influence_bones(armature, bone_name)
    weights: list[float] = []
    for obj in mesh_objects(include_physics=False):
        if filtered_sources and not is_collision_source_object(obj):
            continue
        group_by_index = {group.index: group.name for group in obj.vertex_groups}
        for vertex in obj.data.vertices:
            weight = vertex_group_weight_any(obj, vertex, influence_bones, group_by_index)
            if weight > 0.0:
                weights.append(weight)
    if not weights:
        return {
            "mean": 0.0,
            "stdev": 0.0,
            "max": 0.0,
            "threshold": 0.0,
            "weighted_vertex_count": 0.0,
            "influence_bones": influence_bones,
            "threshold_method": "half_max_summed_influence_weight",
        }
    mean = sum(weights) / float(len(weights))
    variance = sum((weight - mean) * (weight - mean) for weight in weights) / float(len(weights))
    stdev = math.sqrt(max(0.0, variance))
    max_weight = max(weights)
    threshold = max_weight * 0.5
    return {
        "mean": round(float(mean), 6),
        "stdev": round(float(stdev), 6),
        "max": round(float(max_weight), 6),
        "threshold": round(float(threshold), 6),
        "weighted_vertex_count": float(len(weights)),
        "influence_bones": influence_bones,
        "threshold_method": "half_max_summed_influence_weight",
    }


def build_collision_source_index(
    armature: bpy.types.Object,
    filtered_sources: bool = True,
    target_specs: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    started = time.monotonic()
    armature_inv = armature.matrix_world.inverted()
    target_specs = target_specs or target_specs_for_armature(armature)[0]
    target_names = [str(spec.get("bone") or "") for spec in target_specs if spec.get("bone")]
    influence_by_target = {
        str(spec.get("bone") or ""): influence_bones_for_spec(armature, spec)
        for spec in target_specs
        if spec.get("bone")
    }
    target_by_group_name: dict[str, list[str]] = {}
    for target_name, influence_names in influence_by_target.items():
        for group_name in influence_names:
            target_by_group_name.setdefault(group_name, []).append(target_name)

    indexed_objects: list[dict[str, object]] = []
    clouds: dict[str, list[Vector]] = {name: [] for name in target_names}
    weight_samples: dict[str, list[float]] = {name: [] for name in target_names}
    all_points: list[Vector] = []
    total_faces = 0

    for obj in mesh_objects(include_physics=False):
        if filtered_sources and not is_collision_source_object(obj):
            continue
        coords = [armature_inv @ (obj.matrix_world @ vertex.co) for vertex in obj.data.vertices]
        all_points.extend(coord.copy() for coord in coords)
        group_by_index = {group.index: group.name for group in obj.vertex_groups}
        target_lists = {target_name: [0.0] * len(obj.data.vertices) for target_name in target_names}
        for vertex in obj.data.vertices:
            vertex_index = int(vertex.index)
            for group_ref in vertex.groups:
                group_name = group_by_index.get(group_ref.group)
                if not group_name:
                    continue
                for target_name in target_by_group_name.get(group_name, []):
                    target_lists[target_name][vertex_index] += float(group_ref.weight)
        for target_name, weights in target_lists.items():
            for vertex_index, weight in enumerate(weights):
                if weight > 0.0:
                    weight_samples[target_name].append(weight)
                    clouds[target_name].append(coords[vertex_index].copy())
        polygons = [[int(index) for index in poly.vertices] for poly in obj.data.polygons if len(poly.vertices) >= 3]
        total_faces += sum(max(0, len(poly) - 2) for poly in polygons)
        indexed_objects.append(
            {
                "name": obj.name,
                "vertex_count": len(obj.data.vertices),
                "face_count": sum(max(0, len(poly) - 2) for poly in polygons),
                "coords": coords,
                "polygons": polygons,
                "weights": target_lists,
            }
        )

    thresholds: dict[str, dict[str, object]] = {}
    for target_name, weights in weight_samples.items():
        influence_bones = influence_by_target.get(target_name, [])
        if not weights:
            thresholds[target_name] = {
                "mean": 0.0,
                "stdev": 0.0,
                "max": 0.0,
                "threshold": 0.0,
                "weighted_vertex_count": 0.0,
                "influence_bones": influence_bones,
                "threshold_method": "half_max_summed_influence_weight",
            }
            continue
        mean = sum(weights) / float(len(weights))
        variance = sum((weight - mean) * (weight - mean) for weight in weights) / float(len(weights))
        max_weight = max(weights)
        thresholds[target_name] = {
            "mean": round(float(mean), 6),
            "stdev": round(float(math.sqrt(max(0.0, variance))), 6),
            "max": round(float(max_weight), 6),
            "threshold": round(float(max_weight * 0.5), 6),
            "weighted_vertex_count": float(len(weights)),
            "influence_bones": influence_bones,
            "threshold_method": "half_max_summed_influence_weight",
        }

    if all_points:
        mins = Vector((min(point.x for point in all_points), min(point.y for point in all_points), min(point.z for point in all_points)))
        maxs = Vector((max(point.x for point in all_points), max(point.y for point in all_points), max(point.z for point in all_points)))
    else:
        mins = Vector((-0.5, -0.5, 0.0))
        maxs = Vector((0.5, 0.5, 1.0))
    log_progress(
        f"Indexed {len(indexed_objects):,} {'selected' if filtered_sources else 'all'} source bodygroup(s): "
        f"{len(all_points):,} vertices, {total_faces:,} triangulated faces in {time.monotonic() - started:.2f}s."
    )
    return {
        "objects": indexed_objects,
        "clouds": clouds,
        "thresholds": thresholds,
        "influence_by_target": influence_by_target,
        "target_bones": target_names,
        "target_specs": target_specs,
        "scene_mins": mins,
        "scene_maxs": maxs,
        "filtered_sources": filtered_sources,
        "object_names": [str(obj.get("name") or "") for obj in indexed_objects],
        "vertex_count": len(all_points),
        "face_count": total_faces,
        "duration": timing_entry(started),
    }


def add_triangle_to_indexed_region(
    region_vertices: list[Vector],
    region_faces: list[tuple[int, int, int]],
    vertex_index_map: dict[tuple[str, int], int],
    object_name: str,
    vertex_indices: list[int],
    coords: list[Vector],
) -> None:
    face_indices: list[int] = []
    for vertex_index in vertex_indices:
        key = (object_name, int(vertex_index))
        existing = vertex_index_map.get(key)
        if existing is None:
            if int(vertex_index) >= len(coords):
                return
            existing = len(region_vertices)
            vertex_index_map[key] = existing
            region_vertices.append(coords[int(vertex_index)].copy())
        face_indices.append(existing)
    if len(face_indices) == 3 and len(set(face_indices)) == 3:
        region_faces.append((face_indices[0], face_indices[1], face_indices[2]))


def collect_bone_region_mesh_from_index(
    source_index: dict[str, object],
    armature: bpy.types.Object,
    bone_name: str,
    fit: dict[str, object] | None = None,
) -> dict[str, object]:
    thresholds = source_index.get("thresholds", {}) if isinstance(source_index.get("thresholds"), dict) else {}
    stats = thresholds.get(bone_name, {}) if isinstance(thresholds.get(bone_name), dict) else {}
    threshold = float(stats.get("threshold", 0.0) or 0.0)
    influence_by_target = source_index.get("influence_by_target", {}) if isinstance(source_index.get("influence_by_target"), dict) else {}
    influence_bones = list(influence_by_target.get(bone_name, collision_influence_bones(armature, bone_name)))
    vertices: list[Vector] = []
    faces: list[tuple[int, int, int]] = []
    vertex_index_map: dict[tuple[str, int], int] = {}
    source_objects: set[str] = set()
    selected_vertex_count = 0
    selected_face_count = 0
    child_face_count = 0
    target_names = source_index.get("target_bones", TARGET_BONES)
    if not isinstance(target_names, list):
        target_names = TARGET_BONES
    child_names = direct_target_children(armature, bone_name, target_names)
    child_stats = {
        child: thresholds.get(child, {})
        for child in child_names
        if isinstance(thresholds.get(child, {}), dict)
    }

    parent_center = fit.get("center") if fit else None
    parent_axis = fit.get("axes", (None, None, None))[2] if fit else None
    parent_t_min = 0.0
    parent_t_max = 0.0
    parent_span = 0.0
    if isinstance(parent_center, Vector) and isinstance(parent_axis, Vector):
        source_points: list[Vector] = []
        for obj_entry in source_index.get("objects", []):
            if not isinstance(obj_entry, dict):
                continue
            coords = obj_entry.get("coords", [])
            weights_by_target = obj_entry.get("weights", {})
            weights = weights_by_target.get(bone_name, []) if isinstance(weights_by_target, dict) else []
            if not isinstance(coords, list) or not isinstance(weights, list):
                continue
            source_points.extend(coords[index].copy() for index, weight in enumerate(weights) if float(weight) >= threshold > 0.0 and index < len(coords))
        if source_points:
            ts = [(point - parent_center).dot(parent_axis) for point in source_points]
            parent_t_min = percentile(ts, 0.04)
            parent_t_max = percentile(ts, 0.96)
            parent_span = max(0.04, parent_t_max - parent_t_min)

    for obj_entry in source_index.get("objects", []):
        if not isinstance(obj_entry, dict):
            continue
        object_name = str(obj_entry.get("name") or "")
        coords = obj_entry.get("coords", [])
        polygons = obj_entry.get("polygons", [])
        weights_by_target = obj_entry.get("weights", {})
        if not isinstance(coords, list) or not isinstance(polygons, list) or not isinstance(weights_by_target, dict):
            continue
        target_weights = weights_by_target.get(bone_name, [])
        if not isinstance(target_weights, list):
            continue
        selected = [float(weight) >= threshold > 0.0 for weight in target_weights]
        selected_vertex_count += sum(1 for flag in selected if flag)
        child_weights_by_name = {
            child: weights_by_target.get(child, [])
            for child in child_names
            if isinstance(weights_by_target.get(child, []), list)
        }
        for poly_vertices_raw in polygons:
            poly_vertices = [int(index) for index in poly_vertices_raw] if isinstance(poly_vertices_raw, list) else []
            if len(poly_vertices) < 3:
                continue
            weights = [float(target_weights[index]) for index in poly_vertices if index < len(target_weights)]
            selected_count = sum(1 for index in poly_vertices if index < len(selected) and selected[index])
            include = selected_count >= 2 or (max(weights) if weights else 0.0) >= max(0.20, threshold)
            include_child = False
            if not include and isinstance(parent_center, Vector) and isinstance(parent_axis, Vector) and parent_span > 0.0:
                current_overlap = (max(weights) if weights else 0.0) >= max(0.02, threshold * 0.20)
                valid_coords = [coords[index] for index in poly_vertices if index < len(coords)]
                if valid_coords:
                    centroid = sum((point for point in valid_coords), Vector((0.0, 0.0, 0.0))) / float(len(valid_coords))
                    t = (centroid - parent_center).dot(parent_axis)
                    in_joint_span = parent_t_max - parent_span * 0.12 <= t <= parent_t_max + parent_span * 0.14
                    if current_overlap and in_joint_span:
                        for child, child_weights in child_weights_by_name.items():
                            child_threshold = float(child_stats.get(child, {}).get("threshold", 0.0) or 0.0)
                            child_poly_weights = [float(child_weights[index]) for index in poly_vertices if index < len(child_weights)]
                            if child_threshold > 0.0 and child_poly_weights and max(child_poly_weights) >= max(0.08, child_threshold):
                                include_child = True
                                break
            if not include and not include_child:
                continue
            source_objects.add(object_name)
            if include_child:
                child_face_count += 1
            else:
                selected_face_count += 1
            for offset in range(1, len(poly_vertices) - 1):
                add_triangle_to_indexed_region(
                    vertices,
                    faces,
                    vertex_index_map,
                    object_name,
                    [poly_vertices[0], poly_vertices[offset], poly_vertices[offset + 1]],
                    coords,
                )

    return {
        "vertices": vertices,
        "faces": faces,
        "points": vertices,
        "stats": stats,
        "child_stats": child_stats,
        "influence_bones": influence_bones,
        "source_objects": sorted(source_objects, key=natural_key),
        "selected_vertex_count": selected_vertex_count,
        "selected_face_count": selected_face_count,
        "child_face_count": child_face_count,
        "method": "indexed_merged_bodygroups_weight_region",
    }


def add_triangle_to_region(
    region_vertices: list[Vector],
    region_faces: list[tuple[int, int, int]],
    vertex_index_map: dict[tuple[str, int], int],
    obj: bpy.types.Object,
    vertex_indices: list[int],
    armature_inv,
) -> None:
    face_indices: list[int] = []
    for vertex_index in vertex_indices:
        key = (obj.name, int(vertex_index))
        existing = vertex_index_map.get(key)
        if existing is None:
            existing = len(region_vertices)
            vertex_index_map[key] = existing
            region_vertices.append(armature_inv @ (obj.matrix_world @ obj.data.vertices[int(vertex_index)].co))
        face_indices.append(existing)
    if len(face_indices) == 3 and len(set(face_indices)) == 3:
        region_faces.append((face_indices[0], face_indices[1], face_indices[2]))


def collect_bone_region_mesh(
    armature: bpy.types.Object,
    bone_name: str,
    fit: dict[str, object] | None = None,
    filtered_sources: bool = True,
) -> dict[str, object]:
    armature_inv = armature.matrix_world.inverted()
    influence_bones = collision_influence_bones(armature, bone_name)
    stats = weight_threshold_for_bone(armature, bone_name, filtered_sources=filtered_sources, influence_bones=influence_bones)
    threshold = float(stats.get("threshold", 0.0) or 0.0)
    vertices: list[Vector] = []
    faces: list[tuple[int, int, int]] = []
    vertex_index_map: dict[tuple[str, int], int] = {}
    source_objects: set[str] = set()
    selected_vertex_count = 0
    selected_face_count = 0
    child_face_count = 0
    child_names = direct_target_children(armature, bone_name)
    child_influence_bones = {child: collision_influence_bones(armature, child) for child in child_names}
    child_stats = {
        child: weight_threshold_for_bone(armature, child, filtered_sources=filtered_sources, influence_bones=child_influence_bones[child])
        for child in child_names
    }

    parent_center = fit.get("center") if fit else None
    parent_axis = fit.get("axes", (None, None, None))[2] if fit else None
    parent_t_min = 0.0
    parent_t_max = 0.0
    parent_span = 0.0
    if isinstance(parent_center, Vector) and isinstance(parent_axis, Vector):
        source_points = []
        for obj in mesh_objects(include_physics=False):
            if filtered_sources and not is_collision_source_object(obj):
                continue
            group_by_index = {group.index: group.name for group in obj.vertex_groups}
            for vertex in obj.data.vertices:
                if vertex_group_weight_any(obj, vertex, influence_bones, group_by_index) >= threshold > 0.0:
                    source_points.append(armature_inv @ (obj.matrix_world @ vertex.co))
        if source_points:
            ts = [(point - parent_center).dot(parent_axis) for point in source_points]
            parent_t_min = percentile(ts, 0.04)
            parent_t_max = percentile(ts, 0.96)
            parent_span = max(0.04, parent_t_max - parent_t_min)

    for obj in mesh_objects(include_physics=False):
        if filtered_sources and not is_collision_source_object(obj):
            continue
        group_by_index = {group.index: group.name for group in obj.vertex_groups}
        target_weights = [vertex_group_weight_any(obj, vertex, influence_bones, group_by_index) for vertex in obj.data.vertices]
        selected = [weight >= threshold > 0.0 for weight in target_weights]
        selected_vertex_count += sum(1 for flag in selected if flag)
        child_weights_by_name = {
            child: [vertex_group_weight_any(obj, vertex, child_influence_bones[child], group_by_index) for vertex in obj.data.vertices]
            for child in child_names
        }
        for poly in obj.data.polygons:
            poly_vertices = [int(index) for index in poly.vertices]
            if len(poly_vertices) < 3:
                continue
            weights = [target_weights[index] for index in poly_vertices]
            selected_count = sum(1 for index in poly_vertices if selected[index])
            include = selected_count >= 2 or (max(weights) if weights else 0.0) >= max(0.20, threshold)
            include_child = False
            if not include and isinstance(parent_center, Vector) and isinstance(parent_axis, Vector) and parent_span > 0.0:
                current_overlap = (max(weights) if weights else 0.0) >= max(0.02, threshold * 0.20)
                centroid = sum((armature_inv @ (obj.matrix_world @ obj.data.vertices[index].co) for index in poly_vertices), Vector((0.0, 0.0, 0.0))) / float(len(poly_vertices))
                t = (centroid - parent_center).dot(parent_axis)
                in_joint_span = parent_t_max - parent_span * 0.12 <= t <= parent_t_max + parent_span * 0.14
                if current_overlap and in_joint_span:
                    for child, child_weights in child_weights_by_name.items():
                        child_threshold = float(child_stats.get(child, {}).get("threshold", 0.0) or 0.0)
                        if child_threshold > 0.0 and max(child_weights[index] for index in poly_vertices) >= max(0.08, child_threshold):
                            include_child = True
                            break
            if not include and not include_child:
                continue
            source_objects.add(obj.name)
            if include_child:
                child_face_count += 1
            else:
                selected_face_count += 1
            for offset in range(1, len(poly_vertices) - 1):
                add_triangle_to_region(
                    vertices,
                    faces,
                    vertex_index_map,
                    obj,
                    [poly_vertices[0], poly_vertices[offset], poly_vertices[offset + 1]],
                    armature_inv,
                )

    points = vertices
    return {
        "vertices": vertices,
        "faces": faces,
        "points": points,
        "stats": stats,
        "child_stats": child_stats,
        "influence_bones": influence_bones,
        "source_objects": sorted(source_objects, key=natural_key),
        "selected_vertex_count": selected_vertex_count,
        "selected_face_count": selected_face_count,
        "child_face_count": child_face_count,
        "method": "merged_bodygroups_weight_region",
    }


def scene_bounds_in_armature(armature: bpy.types.Object, filtered_sources: bool = True) -> tuple[Vector, Vector]:
    arm_inv = armature.matrix_world.inverted()
    points = []
    for obj in mesh_objects(include_physics=False):
        if filtered_sources and not is_collision_source_object(obj):
            continue
        for vertex in obj.data.vertices:
            points.append(arm_inv @ (obj.matrix_world @ vertex.co))
    if not points:
        return Vector((-0.5, -0.5, 0.0)), Vector((0.5, 0.5, 1.0))
    mins = Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points)))
    maxs = Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points)))
    return mins, maxs


def fit_part(
    armature: bpy.types.Object,
    bone_name: str,
    source_points: list[Vector],
    shrink: float,
    scene_mins: Vector,
    scene_maxs: Vector,
    group_bones: Iterable[str] | None = None,
) -> dict[str, object]:
    warnings: list[str] = []
    shape_type = target_shape_type(bone_name)
    head, tail = bone_span_points(armature, bone_name, group_bones)
    axis = tail - head
    if axis.length <= EPSILON:
        axis = Vector((0.0, 0.0, max(0.1, (scene_maxs - scene_mins).length * 0.08)))
        warnings.append("Bone length was too small; fallback axis was used.")
    x_axis, y_axis, z_axis = orthonormal_basis(axis)
    bone_length = max(0.04, axis.length)
    sparse = len(source_points) < 12
    if sparse:
        warnings.append("Fallback dimensions used because source vertices were sparse.")
        center = (head + tail) * 0.5
        t_min = -bone_length * 0.5
        t_max = bone_length * 0.5
        scene_extent = max(0.2, float(max((scene_maxs - scene_mins).x, (scene_maxs - scene_mins).y, (scene_maxs - scene_mins).z)))
        radius_base = max(0.018 * scene_extent, bone_length * 0.28)
        rx = radius_base
        ry = radius_base
    else:
        center = sum(source_points, Vector((0.0, 0.0, 0.0))) / float(len(source_points))
        coords = [(point - center).dot(z_axis) for point in source_points]
        xs = [abs((point - center).dot(x_axis)) for point in source_points]
        ys = [abs((point - center).dot(y_axis)) for point in source_points]
        t_min = percentile(coords, 0.08)
        t_max = percentile(coords, 0.92)
        if t_max - t_min < bone_length * 0.25:
            t_min = min(t_min, -bone_length * 0.35)
            t_max = max(t_max, bone_length * 0.35)
        rx = max(percentile(xs, 0.76), bone_length * 0.08)
        ry = max(percentile(ys, 0.76), bone_length * 0.08)
    shrink = max(0.25, min(1.25, float(shrink)))
    half_len = max(0.03, (t_max - t_min) * 0.5 * max(0.55, min(1.0, shrink + 0.12)))
    center = center + z_axis * ((t_min + t_max) * 0.5)
    rx = max(0.01, rx * shrink)
    ry = max(0.01, ry * shrink)
    if shape_type == "ellipsoid":
        rz = max(0.02, half_len * shrink)
    elif shape_type == "oriented_box":
        rz = max(0.02, half_len * 0.92)
        rx *= 0.88
        ry *= 0.88
    else:
        rz = max(0.02, half_len)
    confidence = 0.88
    if sparse:
        confidence = 0.48
    elif len(source_points) < 48:
        confidence = 0.66
    if max(rx, ry) / max(0.001, min(rx, ry)) > 3.0:
        warnings.append("Fit radii differ strongly; collision may be asymmetric.")
        confidence = min(confidence, 0.72)
    return {
        "bone": bone_name,
        "shape_type": shape_type,
        "head": head,
        "tail": tail,
        "center": center,
        "axes": (x_axis, y_axis, z_axis),
        "radii": (rx, ry, rz),
        "source_vertex_count": len(source_points),
        "confidence": confidence,
        "warnings": warnings,
        "sparse": sparse,
    }


def make_ellipsoid(
    center: Vector,
    axes: tuple[Vector, Vector, Vector],
    radii: tuple[float, float, float],
    segments: int = 12,
    rings: int = 7,
) -> tuple[list[Vector], list[tuple[int, int, int]]]:
    x_axis, y_axis, z_axis = axes
    rx, ry, rz = radii
    vertices: list[Vector] = [center - z_axis * rz]
    for ring in range(1, rings):
        theta = -math.pi * 0.5 + math.pi * ring / rings
        z = math.sin(theta) * rz
        radius_factor = math.cos(theta)
        for segment in range(segments):
            angle = math.tau * segment / segments
            vertices.append(center + x_axis * (math.cos(angle) * rx * radius_factor) + y_axis * (math.sin(angle) * ry * radius_factor) + z_axis * z)
    top_index = len(vertices)
    vertices.append(center + z_axis * rz)
    faces: list[tuple[int, int, int]] = []
    first_ring = 1
    for segment in range(segments):
        faces.append((0, first_ring + (segment + 1) % segments, first_ring + segment))
    for ring in range(rings - 2):
        start = 1 + ring * segments
        next_start = start + segments
        for segment in range(segments):
            a = start + segment
            b = start + (segment + 1) % segments
            c = next_start + (segment + 1) % segments
            d = next_start + segment
            faces.append((a, b, c))
            faces.append((a, c, d))
    last_ring = 1 + (rings - 2) * segments
    for segment in range(segments):
        faces.append((last_ring + segment, last_ring + (segment + 1) % segments, top_index))
    return vertices, faces


def make_box(
    center: Vector,
    axes: tuple[Vector, Vector, Vector],
    radii: tuple[float, float, float],
) -> tuple[list[Vector], list[tuple[int, int, int]]]:
    x_axis, y_axis, z_axis = axes
    rx, ry, rz = radii
    signs = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    vertices = [center + x_axis * (sx * rx) + y_axis * (sy * ry) + z_axis * (sz * rz) for sx, sy, sz in signs]
    faces = [
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    ]
    return vertices, faces


def make_part_geometry(fit: dict[str, object]) -> tuple[list[Vector], list[tuple[int, int, int]]]:
    center = fit["center"]
    axes = fit["axes"]
    radii = fit["radii"]
    shape_type = str(fit.get("shape_type") or "ellipsoid")
    if shape_type == "oriented_box":
        return make_box(center, axes, radii)
    return make_ellipsoid(center, axes, radii, segments=14 if shape_type == "capsule" else 12, rings=7)


def hull_config(bone_name: str) -> tuple[int, int]:
    lower = bone_name.lower()
    if any(token in lower for token in ("head", "pelvis", "spine4")):
        return 3, 2
    if "spine1" in lower:
        return 2, 2
    if any(token in lower for token in ("upperarm", "forearm", "thigh", "calf")):
        return 3, 1
    return 2, 1


def robust_filter_points(points: list[Vector], fit: dict[str, object]) -> list[Vector]:
    if len(points) < MIN_MULTI_HULL_POINTS:
        return points
    center = fit["center"]
    x_axis, y_axis, z_axis = fit["axes"]
    locals_ = [(point, (point - center).dot(x_axis), (point - center).dot(y_axis), (point - center).dot(z_axis)) for point in points]
    xs = [abs(item[1]) for item in locals_]
    ys = [abs(item[2]) for item in locals_]
    ts = [item[3] for item in locals_]
    t_min = percentile(ts, 0.03)
    t_max = percentile(ts, 0.97)
    t_margin = max(0.02, (t_max - t_min) * 0.10)
    x_limit = max(0.02, percentile(xs, 0.90) * 1.22)
    y_limit = max(0.02, percentile(ys, 0.90) * 1.22)
    filtered = [
        point
        for point, x, y, t in locals_
        if t_min - t_margin <= t <= t_max + t_margin and abs(x) <= x_limit and abs(y) <= y_limit
    ]
    return filtered if len(filtered) >= MIN_MULTI_HULL_POINTS else points


def local_tuple(point: Vector, center: Vector, axes: tuple[Vector, Vector, Vector]) -> tuple[float, float, float]:
    x_axis, y_axis, z_axis = axes
    delta = point - center
    return delta.dot(x_axis), delta.dot(y_axis), delta.dot(z_axis)


def sample_hull_points(
    points: list[Vector],
    shrink: float,
    axes: tuple[Vector, Vector, Vector],
    max_points: int = MAX_HULL_SAMPLE_POINTS,
) -> list[Vector]:
    if not points:
        return []
    center = sum(points, Vector((0.0, 0.0, 0.0))) / float(len(points))
    locals_ = [(point, *local_tuple(point, center, axes)) for point in points]
    ts = [item[3] for item in locals_]
    t_min = min(ts)
    t_max = max(ts)
    t_span = max(1e-6, t_max - t_min)
    buckets: dict[tuple[int, int], tuple[float, Vector]] = {}
    for point, x, y, t in locals_:
        axial_bin = max(0, min(3, int((t - t_min) / t_span * 4.0)))
        angle = math.atan2(y, x)
        radial_bin = max(0, min(7, int((angle + math.pi) / math.tau * 8.0)))
        radius = x * x + y * y
        key = (axial_bin, radial_bin)
        if key not in buckets or radius > buckets[key][0]:
            buckets[key] = (radius, point)
    selected = [item[1] for item in buckets.values()]
    extrema_keys = [
        min(locals_, key=lambda item: item[1])[0],
        max(locals_, key=lambda item: item[1])[0],
        min(locals_, key=lambda item: item[2])[0],
        max(locals_, key=lambda item: item[2])[0],
        min(locals_, key=lambda item: item[3])[0],
        max(locals_, key=lambda item: item[3])[0],
    ]
    selected.extend(extrema_keys)
    deduped: list[Vector] = []
    seen: set[tuple[int, int, int]] = set()
    for point in selected:
        key = (round(point.x * 10000), round(point.y * 10000), round(point.z * 10000))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(center + (point - center) * shrink)
    if len(deduped) > max_points:
        step = len(deduped) / float(max_points)
        deduped = [deduped[min(len(deduped) - 1, int(index * step))] for index in range(max_points)]
    return deduped


def convex_hull_from_points(points: list[Vector]) -> tuple[list[Vector], list[tuple[int, int, int]]]:
    unique: list[Vector] = []
    seen: set[tuple[int, int, int]] = set()
    for point in points:
        key = (round(point.x * 100000), round(point.y * 100000), round(point.z * 100000))
        if key in seen:
            continue
        seen.add(key)
        unique.append(point)
    if len(unique) < 4:
        return [], []
    bm = bmesh.new()
    try:
        for point in unique:
            bm.verts.new((point.x, point.y, point.z))
        bm.verts.ensure_lookup_table()
        result = bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
        delete_geom = []
        seen_delete: set[int] = set()
        for key in ("geom_unused", "geom_interior", "geom_holes"):
            for item in result.get(key, []):
                item_id = id(item)
                if item_id in seen_delete:
                    continue
                seen_delete.add(item_id)
                delete_geom.append(item)
        if delete_geom:
            bmesh.ops.delete(bm, geom=delete_geom, context="VERTS")
        if bm.faces:
            bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.verts.ensure_lookup_table()
        vertices = [vertex.co.copy() for vertex in bm.verts]
        index_by_vert = {vertex: index for index, vertex in enumerate(bm.verts)}
        faces = []
        for face in bm.faces:
            if len(face.verts) == 3:
                faces.append(tuple(index_by_vert[vertex] for vertex in face.verts))
        return vertices, faces
    finally:
        bm.free()


def decimate_region_mesh(vertices: list[Vector], faces: list[tuple[int, int, int]], max_faces: int = 12000) -> tuple[list[Vector], list[tuple[int, int, int]]]:
    if len(faces) <= max_faces:
        return vertices, faces
    mins = Vector((min(vertex.x for vertex in vertices), min(vertex.y for vertex in vertices), min(vertex.z for vertex in vertices)))
    maxs = Vector((max(vertex.x for vertex in vertices), max(vertex.y for vertex in vertices), max(vertex.z for vertex in vertices)))
    extent = maxs - mins
    bucket_count = max(3, int(round(max_faces ** (1.0 / 3.0))))
    buckets: dict[tuple[int, int, int], list[tuple[int, tuple[int, int, int]]]] = {}
    for index, face in enumerate(faces):
        center = (vertices[face[0]] + vertices[face[1]] + vertices[face[2]]) / 3.0
        key = (
            int(max(0, min(bucket_count - 1, ((center.x - mins.x) / max(EPSILON, extent.x)) * bucket_count))),
            int(max(0, min(bucket_count - 1, ((center.y - mins.y) / max(EPSILON, extent.y)) * bucket_count))),
            int(max(0, min(bucket_count - 1, ((center.z - mins.z) / max(EPSILON, extent.z)) * bucket_count))),
        )
        buckets.setdefault(key, []).append((index, face))
    selected_faces: list[tuple[int, int, int]] = []
    ordered_keys = sorted(buckets)
    cursor = 0
    while len(selected_faces) < max_faces and ordered_keys:
        progressed = False
        for key in ordered_keys:
            bucket = buckets[key]
            if cursor < len(bucket):
                selected_faces.append(bucket[cursor][1])
                progressed = True
                if len(selected_faces) >= max_faces:
                    break
        if not progressed:
            break
        cursor += 1
    if len(selected_faces) < max_faces:
        selected = set(selected_faces)
        for _index, face in sorted((item for bucket in buckets.values() for item in bucket), key=lambda item: item[0]):
            if face in selected:
                continue
            selected_faces.append(face)
            if len(selected_faces) >= max_faces:
                break
    used = sorted({index for face in selected_faces for index in face})
    remap = {old: new for new, old in enumerate(used)}
    return [vertices[index] for index in used], [tuple(remap[index] for index in face) for face in selected_faces]


def run_coacd_single_hull(
    vertices: list[Vector],
    faces: list[tuple[int, int, int]],
    shrink: float,
    bone_name: str = "",
    cache_key: str = "",
) -> tuple[list[Vector], list[tuple[int, int, int]], dict[str, object], list[str]]:
    warnings: list[str] = []
    started = time.monotonic()
    if len(vertices) < 4 or len(faces) < 4:
        log_progress(f"CoACD skipped: region mesh is too small ({len(vertices)} vertices, {len(faces)} faces).")
        return [], [], {"available": False, "source": "region mesh too small"}, ["CoACD fallback used because the region mesh was too small."]
    preset = current_quality_preset()
    preset_key = ACTIVE_COACD_QUALITY
    face_cap = coacd_face_cap_for_bone(bone_name)
    cache_path = ACTIVE_RESULT_CACHE_DIR / f"{cache_key}.json" if ACTIVE_RESULT_CACHE_DIR is not None and cache_key else None
    if cache_path is not None and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_vertices = [Vector((float(row[0]), float(row[1]), float(row[2]))) for row in cached.get("vertices", [])]
            cached_faces = [tuple(int(value) for value in face[:3]) for face in cached.get("faces", [])]
            cached_status = cached.get("status", {}) if isinstance(cached.get("status"), dict) else {}
            if cached_vertices and cached_faces:
                if "duration_seconds" in cached_status:
                    cached_status["cached_compute_duration_seconds"] = cached_status.get("duration_seconds")
                cached_status["duration_seconds"] = timing_entry(started)
                cached_status["cache_hit"] = True
                cached_status["cache_path"] = str(cache_path)
                cached_status.setdefault("quality_preset", preset_key)
                log_progress(f"{bone_name}: CoACD cache hit ({len(cached_vertices):,} vertices/{len(cached_faces):,} faces).")
                return cached_vertices, cached_faces, cached_status, ["CoACD geometry reused from cache."]
        except Exception as exc:
            warnings.append(f"CoACD cache read failed: {exc}")
    module, source = ensure_coacd_module()
    status = {
        "available": module is not None,
        "source": source,
        "quality_preset": preset_key,
        "quality_label": current_quality_label(),
        "threshold": float(preset.get("threshold", COACD_THRESHOLD) or COACD_THRESHOLD),
        "max_convex_hull": 1,
        "max_ch_vertex": int(preset.get("max_ch_vertex", COACD_MAX_VERTICES) or COACD_MAX_VERTICES),
        "face_cap": face_cap,
        "cache_hit": False,
    }
    if module is None:
        log_progress(f"CoACD unavailable: {source}")
        return [], [], status, [str(source)]
    try:
        import numpy as np

        mesh_vertices, mesh_faces = decimate_region_mesh(vertices, faces, max_faces=face_cap)
        log_progress(
            f"{bone_name}: running {current_quality_label()} CoACD on {len(vertices):,} vertices/{len(faces):,} faces "
            f"({len(mesh_vertices):,}/{len(mesh_faces):,} sampled), shrink={shrink:.3f}."
        )
        center = sum(mesh_vertices, Vector((0.0, 0.0, 0.0))) / float(len(mesh_vertices))
        shrink = max(0.25, min(1.25, float(shrink)))
        shrunken = [center + (vertex - center) * shrink for vertex in mesh_vertices]
        vert_array = np.array([[vertex.x, vertex.y, vertex.z] for vertex in shrunken], dtype=np.float64)
        face_array = np.array([[int(a), int(b), int(c)] for a, b, c in mesh_faces], dtype=np.int32)
        coacd_mesh = module.Mesh(vert_array, face_array)
        try:
            module.set_log_level("warn")
        except Exception:
            pass
        result = module.run_coacd(
            coacd_mesh,
            threshold=float(preset.get("threshold", COACD_THRESHOLD) or COACD_THRESHOLD),
            max_convex_hull=1,
            preprocess_mode="auto",
            preprocess_resolution=int(preset.get("preprocess_resolution", 50) or 50),
            resolution=int(preset.get("resolution", 1000) or 1000),
            mcts_nodes=int(preset.get("mcts_nodes", 8) or 8),
            mcts_iterations=int(preset.get("mcts_iterations", 40) or 40),
            mcts_max_depth=int(preset.get("mcts_max_depth", 3) or 3),
            pca=False,
            merge=True,
            decimate=True,
            max_ch_vertex=int(preset.get("max_ch_vertex", COACD_MAX_VERTICES) or COACD_MAX_VERTICES),
            apx_mode="ch",
        )
        hull_vertices: list[Vector] = []
        hull_faces: list[tuple[int, int, int]] = []
        for verts, idx in result:
            start = len(hull_vertices)
            hull_vertices.extend(Vector((float(row[0]), float(row[1]), float(row[2]))) for row in verts)
            hull_faces.extend((int(face[0]) + start, int(face[1]) + start, int(face[2]) + start) for face in idx)
        if not hull_vertices or not hull_faces:
            log_progress("CoACD returned no hull geometry.")
            return [], [], status, ["CoACD returned no hull geometry."]
        if len(result) > 1:
            warnings.append(f"CoACD returned {len(result)} hulls despite single-hull mode; merged them into one convex hull.")
            hull_vertices, hull_faces = convex_hull_from_points(hull_vertices)
        volume = mesh_volume(hull_vertices, hull_faces) if hull_vertices and hull_faces else 0.0
        if volume <= EPSILON:
            log_progress("CoACD returned a zero-volume hull.")
            return [], [], status, ["CoACD returned a zero-volume hull."]
        status["returned_hulls"] = len(result)
        status["input_vertices"] = len(vertices)
        status["input_faces"] = len(faces)
        status["sampled_faces"] = len(mesh_faces)
        status["duration_seconds"] = timing_entry(started)
        if cache_path is not None:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                write_json(
                    cache_path,
                    {
                        "version": COACD_RESULT_CACHE_VERSION,
                        "cache_key": cache_key,
                        "bone": bone_name,
                        "quality_preset": preset_key,
                        "vertices": [v3(vertex) for vertex in hull_vertices],
                        "faces": [list(face) for face in hull_faces],
                        "status": status,
                    },
                )
                status["cache_path"] = str(cache_path)
            except Exception as exc:
                warnings.append(f"CoACD cache write failed: {exc}")
        log_progress(
            f"{bone_name}: CoACD produced one hull with {len(hull_vertices):,} vertices, "
            f"{len(hull_faces):,} faces, volume {volume:.4f} in {status['duration_seconds']:.2f}s."
        )
        return hull_vertices, hull_faces, status, warnings
    except Exception as exc:
        log_progress(f"CoACD execution failed: {exc}")
        status["duration_seconds"] = timing_entry(started)
        return [], [], status, [f"CoACD execution failed: {exc}"]


def make_coacd_region_geometry(
    armature: bpy.types.Object,
    bone_name: str,
    region: dict[str, object],
    shrink: float,
    cache_key: str = "",
) -> tuple[list[Vector], list[tuple[int, int, int]], list[dict[str, object]], dict[str, object], list[str]]:
    warnings: list[str] = []
    vertices = region.get("vertices", [])
    faces = region.get("faces", [])
    if not isinstance(vertices, list) or not isinstance(faces, list) or len(vertices) < MIN_MULTI_HULL_POINTS or len(faces) < 8:
        return [], [], [], {"coverage_score": 0.0, "hull_piece_count": 0}, ["CoACD fallback used because the weight-region mesh was sparse."]
    hull_vertices, hull_faces, status, coacd_warnings = run_coacd_single_hull(vertices, faces, shrink, bone_name=bone_name, cache_key=cache_key)
    warnings.extend(coacd_warnings)
    if not hull_vertices or not hull_faces:
        return [], [], [], {"coverage_score": 0.0, "coacd": status, "hull_piece_count": 0}, warnings
    volume = mesh_volume(hull_vertices, hull_faces)
    hull_center = sum(hull_vertices, Vector((0.0, 0.0, 0.0))) / float(len(hull_vertices))
    hulls = [
        {
            "index": 1,
            "source_point_count": int(region.get("selected_vertex_count", len(vertices)) or len(vertices)),
            "vertex_count": len(hull_vertices),
            "face_count": len(hull_faces),
            "volume": round(float(volume), 6),
            "center": v3(hull_center),
            "connected": True,
            "coacd_single_hull": True,
        }
    ]
    stats = region.get("stats", {}) if isinstance(region.get("stats"), dict) else {}
    source_weight_count = float(stats.get("weighted_vertex_count", 0.0) or 0.0)
    coverage_score = min(1.0, float(region.get("selected_vertex_count", 0) or 0) / max(1.0, source_weight_count))
    child_faces = int(region.get("child_face_count", 0) or 0)
    metrics = {
        "coverage_score": round(float(coverage_score), 4),
        "piece_success_score": 1.0,
        "cluster_count": 1,
        "filtered_source_count": int(region.get("selected_vertex_count", len(vertices)) or len(vertices)),
        "selected_face_count": int(region.get("selected_face_count", 0) or 0),
        "child_face_count": child_faces,
        "hull_piece_count": 1,
        "coacd": status,
        "region_method": region.get("method", ""),
        "weight_mean": stats.get("mean", 0.0),
        "weight_stdev": stats.get("stdev", 0.0),
        "weight_threshold": stats.get("threshold", 0.0),
    }
    return hull_vertices, hull_faces, hulls, metrics, warnings


def cluster_points_for_hulls(bone_name: str, points: list[Vector], fit: dict[str, object]) -> list[list[Vector]]:
    if not points:
        return []
    center = fit["center"]
    axes = fit["axes"]
    x_axis, _y_axis, z_axis = axes
    locals_ = [(point, (point - center).dot(x_axis), (point - center).dot(z_axis)) for point in points]
    ts = [item[2] for item in locals_]
    t_min = percentile(ts, 0.04)
    t_max = percentile(ts, 0.96)
    if t_max - t_min <= 1e-6:
        return [points]
    axial_count, radial_count = hull_config(bone_name)
    slice_width = (t_max - t_min) / max(1, axial_count)
    overlap = slice_width * 0.18
    clusters: list[list[Vector]] = []
    for axial_index in range(axial_count):
        start = t_min + slice_width * axial_index
        end = start + slice_width
        axial_points = [(point, x, t) for point, x, t in locals_ if start - overlap <= t <= end + overlap]
        if not axial_points:
            continue
        if radial_count <= 1:
            clusters.append([item[0] for item in axial_points])
            continue
        x_values = [abs(item[1]) for item in axial_points]
        x_overlap = max(0.02, percentile(x_values, 0.65) * 0.18)
        left = [point for point, x, _t in axial_points if x <= x_overlap]
        right = [point for point, x, _t in axial_points if x >= -x_overlap]
        if len(left) >= 8 and len(right) >= 8:
            clusters.extend([left, right])
        else:
            clusters.append([item[0] for item in axial_points])
    return clusters


def make_multi_hull_geometry(
    bone_name: str,
    source_points: list[Vector],
    shrink: float,
    fit: dict[str, object],
) -> tuple[list[Vector], list[tuple[int, int, int]], list[dict[str, object]], dict[str, object], list[str]]:
    warnings: list[str] = []
    filtered = robust_filter_points(source_points, fit)
    if len(filtered) < MIN_MULTI_HULL_POINTS:
        return [], [], [], {"coverage_score": 0.0}, ["Primitive fallback used because source vertices were sparse."]
    axes = fit["axes"]
    clusters = cluster_points_for_hulls(bone_name, filtered, fit)
    vertices: list[Vector] = []
    faces: list[tuple[int, int, int]] = []
    hulls: list[dict[str, object]] = []
    for cluster_index, cluster in enumerate(clusters, start=1):
        if len(cluster) < 8:
            continue
        hull_points = sample_hull_points(cluster, shrink, axes)
        hull_vertices, hull_faces = convex_hull_from_points(hull_points)
        hull_volume = mesh_volume(hull_vertices, hull_faces) if hull_vertices and hull_faces else 0.0
        if hull_volume <= EPSILON or not hull_faces:
            warnings.append(f"Hull cluster {cluster_index} failed and was skipped.")
            continue
        start = len(vertices)
        vertices.extend(hull_vertices)
        faces.extend((a + start, b + start, c + start) for a, b, c in hull_faces)
        hull_center = sum(hull_vertices, Vector((0.0, 0.0, 0.0))) / float(len(hull_vertices))
        hulls.append(
            {
                "index": len(hulls) + 1,
                "source_point_count": len(cluster),
                "vertex_count": len(hull_vertices),
                "face_count": len(hull_faces),
                "volume": round(float(hull_volume), 6),
                "center": v3(hull_center),
            }
        )
    coverage_score = len(filtered) / max(1, len(source_points))
    piece_score = len(hulls) / max(1, len(clusters))
    if coverage_score < 0.55:
        warnings.append("Very low silhouette coverage after outlier filtering.")
    if len(faces) > HIGH_TRIANGLE_WARNING:
        warnings.append("Generated Physics triangle count is unusually high.")
    metrics = {
        "coverage_score": round(float(coverage_score), 4),
        "piece_success_score": round(float(piece_score), 4),
        "cluster_count": len(clusters),
        "filtered_source_count": len(filtered),
    }
    return vertices, faces, hulls, metrics, warnings


def direct_target_children(armature: bpy.types.Object, bone_name: str, target_bones: Iterable[str] | None = None) -> list[str]:
    bone = armature.data.bones.get(bone_name)
    if bone is None:
        return []
    target_set = set(str(item) for item in (target_bones or TARGET_BONES))
    return [child.name for child in bone.children if child.name in target_set]


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) * 0.5)


def connected_slice_count(bone_name: str) -> int:
    lower = bone_name.lower()
    if any(token in lower for token in ("head", "pelvis", "spine")):
        return 8
    if any(token in lower for token in ("hand", "foot", "clavicle")):
        return 5
    return 7


def connected_ring_segments(bone_name: str) -> int:
    lower = bone_name.lower()
    if any(token in lower for token in ("head", "pelvis", "spine")):
        return 12
    return 10


def augment_with_child_joint_points(
    armature: bpy.types.Object,
    bone_name: str,
    source_points: list[Vector],
    clouds: dict[str, list[Vector]],
    fit: dict[str, object],
    target_bones: Iterable[str] | None = None,
) -> tuple[list[Vector], int]:
    if not source_points:
        return source_points, 0
    center = fit["center"]
    _x_axis, _y_axis, z_axis = fit["axes"]
    source_t = [(point - center).dot(z_axis) for point in source_points]
    t_min = percentile(source_t, 0.04)
    t_max = percentile(source_t, 0.96)
    span = max(0.04, t_max - t_min)
    added: list[Vector] = []
    for child_name in direct_target_children(armature, bone_name, target_bones):
        child_points = clouds.get(child_name, [])
        if not child_points:
            continue
        candidates = []
        for point in child_points:
            t = (point - center).dot(z_axis)
            distance = abs(t - t_max)
            if t_max - span * 0.20 <= t <= t_max + span * 0.42:
                candidates.append((distance, point))
        candidates.sort(key=lambda item: item[0])
        limit = min(180, max(24, len(source_points) // 5))
        added.extend(point.copy() for _distance, point in candidates[:limit])
    if not added:
        return source_points, 0
    return source_points + added, len(added)


def make_connected_loft_geometry(
    armature: bpy.types.Object,
    bone_name: str,
    source_points: list[Vector],
    shrink: float,
    fit: dict[str, object],
    all_clouds: dict[str, list[Vector]],
    target_bones: Iterable[str] | None = None,
) -> tuple[list[Vector], list[tuple[int, int, int]], list[dict[str, object]], dict[str, object], list[str]]:
    warnings: list[str] = []
    filtered = robust_filter_points(source_points, fit)
    filtered, child_added = augment_with_child_joint_points(armature, bone_name, filtered, all_clouds, fit, target_bones=target_bones)
    if len(filtered) < MIN_MULTI_HULL_POINTS:
        return [], [], [], {"coverage_score": 0.0, "child_source_count": child_added}, ["Primitive fallback used because source vertices were sparse."]

    center = fit["center"]
    x_axis, y_axis, z_axis = fit["axes"]
    local_items = [(point, *local_tuple(point, center, fit["axes"])) for point in filtered]
    ts = [item[3] for item in local_items]
    head = fit.get("head")
    tail = fit.get("tail")
    if not isinstance(head, Vector) or not isinstance(tail, Vector):
        head, tail = bone_points(armature, bone_name)
    head_t = (head - center).dot(z_axis)
    tail_t = (tail - center).dot(z_axis)
    t_min = min(percentile(ts, 0.03), head_t, tail_t)
    t_max = max(percentile(ts, 0.97), head_t, tail_t)
    span = max(0.04, t_max - t_min)
    padding = span * 0.04
    t_min -= padding
    t_max += padding
    span = max(0.04, t_max - t_min)

    slice_count = connected_slice_count(bone_name)
    segment_count = connected_ring_segments(bone_name)
    step = span / max(1, slice_count - 1)
    all_radial = [math.hypot(item[1], item[2]) for item in local_items]
    fallback_radius = max(0.012, percentile(all_radial, 0.62) * shrink)
    min_radius = max(0.01, percentile(all_radial, 0.25) * shrink * 0.55)
    rings: list[list[int]] = []
    vertices: list[Vector] = []
    previous_radii: list[float] | None = None

    for slice_index in range(slice_count):
        t = t_min + step * slice_index
        window = max(step * 1.05, span * 0.12)
        near = [item for item in local_items if abs(item[3] - t) <= window]
        if len(near) < 10:
            near = sorted(local_items, key=lambda item: abs(item[3] - t))[: min(len(local_items), 48)]
        if not near:
            continue
        x_center = median([item[1] for item in near])
        y_center = median([item[2] for item in near])
        radial_distances = [math.hypot(item[1] - x_center, item[2] - y_center) for item in near]
        local_fallback = max(fallback_radius, percentile(radial_distances, 0.72) * shrink)
        ring_indices: list[int] = []
        current_radii: list[float] = []
        for segment in range(segment_count):
            angle = math.tau * segment / segment_count
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            projected: list[float] = []
            for _point, x, y, _sample_t in near:
                dx = x - x_center
                dy = y - y_center
                along = dx * cos_a + dy * sin_a
                perpendicular = abs(-dx * sin_a + dy * cos_a)
                if along > 0.0 and perpendicular <= max(local_fallback * 0.85, along * 0.85):
                    projected.append(along)
            if projected:
                radius = percentile(projected, 0.92) * shrink
            else:
                radius = local_fallback
            radius = max(min_radius, radius)
            if previous_radii is not None:
                radius = max(radius, previous_radii[segment] * 0.62)
                radius = min(radius, previous_radii[segment] * 1.70)
            current_radii.append(radius)
            vertex = center + x_axis * (x_center + cos_a * radius) + y_axis * (y_center + sin_a * radius) + z_axis * t
            ring_indices.append(len(vertices))
            vertices.append(vertex)
        rings.append(ring_indices)
        previous_radii = current_radii

    if len(rings) < 2:
        return [], [], [], {"coverage_score": 0.0, "child_source_count": child_added}, ["Primitive fallback used because connected loft did not produce enough slices."]

    faces: list[tuple[int, int, int]] = []
    for ring_index in range(len(rings) - 1):
        ring_a = rings[ring_index]
        ring_b = rings[ring_index + 1]
        count = min(len(ring_a), len(ring_b))
        for segment in range(count):
            a = ring_a[segment]
            b = ring_a[(segment + 1) % count]
            c = ring_b[(segment + 1) % count]
            d = ring_b[segment]
            faces.append((a, b, c))
            faces.append((a, c, d))

    start_center = sum((vertices[index] for index in rings[0]), Vector((0.0, 0.0, 0.0))) / float(len(rings[0]))
    end_center = sum((vertices[index] for index in rings[-1]), Vector((0.0, 0.0, 0.0))) / float(len(rings[-1]))
    start_index = len(vertices)
    vertices.append(start_center)
    end_index = len(vertices)
    vertices.append(end_center)
    for segment in range(len(rings[0])):
        faces.append((start_index, rings[0][(segment + 1) % len(rings[0])], rings[0][segment]))
    for segment in range(len(rings[-1])):
        faces.append((end_index, rings[-1][segment], rings[-1][(segment + 1) % len(rings[-1])]))

    volume = mesh_volume(vertices, faces)
    if volume <= EPSILON:
        return [], [], [], {"coverage_score": 0.0, "child_source_count": child_added}, ["Primitive fallback used because connected loft volume was invalid."]

    coverage_score = len(filtered) / max(1, len(source_points))
    if coverage_score < 0.55:
        warnings.append("Very low silhouette coverage after outlier filtering.")
    if len(faces) > HIGH_TRIANGLE_WARNING:
        warnings.append("Generated Physics triangle count is unusually high.")
    hull_center = sum(vertices, Vector((0.0, 0.0, 0.0))) / float(len(vertices))
    hulls = [
        {
            "index": 1,
            "source_point_count": len(filtered),
            "vertex_count": len(vertices),
            "face_count": len(faces),
            "volume": round(float(volume), 6),
            "center": v3(hull_center),
            "connected": True,
        }
    ]
    metrics = {
        "coverage_score": round(float(coverage_score), 4),
        "piece_success_score": 1.0,
        "cluster_count": 1,
        "filtered_source_count": len(filtered),
        "child_source_count": child_added,
        "slice_count": len(rings),
        "ring_segments": segment_count,
    }
    return vertices, faces, hulls, metrics, warnings


def triangle_volume(a: Vector, b: Vector, c: Vector) -> float:
    return float(a.dot(b.cross(c)) / 6.0)


def mesh_volume(vertices: list[Vector], faces: list[tuple[int, int, int]]) -> float:
    volume = 0.0
    for a, b, c in faces:
        volume += triangle_volume(vertices[a], vertices[b], vertices[c])
    return abs(volume)


def collision_preview(parts: list[dict[str, object]], armature: bpy.types.Object) -> dict[str, object]:
    triangles: list[dict[str, object]] = []
    matrix = armature.matrix_world
    for index, part in enumerate(parts, start=1):
        vertices = part.get("vertices", [])
        faces = part.get("faces", [])
        color = preview_color(str(part.get("bone") or part.get("uid") or ""), index)
        center = Vector(part.get("center", [0.0, 0.0, 0.0]))
        world_center = matrix @ center
        for face in faces:
            try:
                coords = [v3(matrix @ Vector(vertices[int(face_item)])) for face_item in face[:3]]
            except Exception:
                continue
            triangles.append(
                {
                    "points": coords,
                    "bone": str(part.get("bone") or ""),
                    "uid": str(part.get("uid") or ""),
                    "color": color,
                    "center": v3(world_center),
                }
            )
    return {"triangles": triangles, "triangle_count": len(triangles)}


def collision_part_cache_key(
    input_blend: Path | None,
    bone_name: str,
    shrink: float,
    source_index: dict[str, object],
    region: dict[str, object],
) -> str:
    stat_payload: dict[str, object] = {}
    if input_blend is not None:
        try:
            stat = input_blend.stat()
            stat_payload = {"path": str(input_blend.resolve()), "mtime_ns": int(stat.st_mtime_ns), "size": int(stat.st_size)}
        except Exception:
            stat_payload = {"path": str(input_blend)}
    return json_cache_key(
        {
            "version": COACD_RESULT_CACHE_VERSION,
            "input": stat_payload,
            "bone": bone_name,
            "quality_preset": ACTIVE_COACD_QUALITY,
            "shrink": round(float(shrink), 6),
            "source_selection": source_selection_summary(),
            "source_objects": source_index.get("object_names", []),
            "influence_bones": region.get("influence_bones", []),
            "region_vertex_count": len(region.get("vertices", [])) if isinstance(region.get("vertices"), list) else 0,
            "region_face_count": len(region.get("faces", [])) if isinstance(region.get("faces"), list) else 0,
            "selected_vertex_count": int(region.get("selected_vertex_count", 0) or 0),
            "selected_face_count": int(region.get("selected_face_count", 0) or 0),
            "child_face_count": int(region.get("child_face_count", 0) or 0),
        }
    )


def build_collision_parts(
    plan_rows: list[dict[str, object]] | None = None,
    input_blend: Path | None = None,
    target_specs: list[dict[str, object]] | None = None,
) -> tuple[list[dict[str, object]], list[str], dict[str, object]]:
    total_started = time.monotonic()
    ensure_object_mode()
    armature = main_armature()
    if armature is None:
        return [], ["Missing armature."], {}
    log_progress(f"Building collision parts from armature {armature.name}.")
    errors: list[str] = []
    additional_groups: list[dict[str, object]] = []
    if target_specs is None:
        target_specs, selection_errors, additional_groups = target_specs_for_armature(armature)
        errors.extend(selection_errors)
    else:
        target_specs = [dict(spec) for spec in target_specs]
    target_names = [str(spec.get("bone") or "") for spec in target_specs if spec.get("bone")]
    timing: dict[str, object] = {"quality_preset": ACTIVE_COACD_QUALITY, "quality_label": current_quality_label(), "bones": {}}
    scan_started = time.monotonic()
    log_progress("Building indexed collision source data for target and grouped influence bones.")
    source_index = build_collision_source_index(armature, filtered_sources=True, target_specs=target_specs)
    unfiltered_index = build_collision_source_index(armature, filtered_sources=False, target_specs=target_specs)
    timing["source_scan_seconds"] = timing_entry(scan_started)
    timing["selected_source_vertex_count"] = source_index.get("vertex_count", 0)
    timing["selected_source_face_count"] = source_index.get("face_count", 0)
    scene_mins = source_index.get("scene_mins", Vector((-0.5, -0.5, 0.0)))
    scene_maxs = source_index.get("scene_maxs", Vector((0.5, 0.5, 1.0)))
    if not isinstance(scene_mins, Vector) or not isinstance(scene_maxs, Vector):
        scene_mins, scene_maxs = scene_bounds_in_armature(armature)
    clouds = source_index.get("clouds", {}) if isinstance(source_index.get("clouds"), dict) else {}
    unfiltered_clouds = unfiltered_index.get("clouds", {}) if isinstance(unfiltered_index.get("clouds"), dict) else {}
    plan_by_bone = {
        str(row.get("bone") or ""): row
        for row in plan_rows or []
        if isinstance(row, dict) and row.get("bone")
    }
    parts: list[dict[str, object]] = []
    missing = [bone for bone in target_names if bone not in armature.data.bones]
    if missing:
        errors.extend(f"Missing required target bone: {bone}" for bone in missing)
    for index, spec in enumerate(target_specs, start=1):
        bone_name = str(spec.get("bone") or "")
        if not bone_name:
            continue
        if bone_name not in armature.data.bones:
            continue
        bone_started = time.monotonic()
        bone_timing: dict[str, object] = {}
        kind = str(spec.get("kind") or "default")
        group_bones = [str(name) for name in spec.get("group_bones", [])] if isinstance(spec.get("group_bones"), list) else [bone_name]
        if not group_bones:
            group_bones = [bone_name]
        log_progress(f"[{index}/{len(target_specs)}] Preparing {bone_name}.")
        plan_row = plan_by_bone.get(bone_name, {})
        enabled = bool(plan_row.get("enabled", True))
        shrink = float(plan_row.get("shrink", default_shrink(bone_name)) or default_shrink(bone_name))
        uid = str(plan_row.get("uid") or spec.get("uid") or f"collision_{index:02d}_{safe_fragment(bone_name)}")
        influence_bones = influence_bones_for_spec(armature, spec)
        if len(influence_bones) > 1:
            log_progress(f"{bone_name}: grouped influence bones: {', '.join(influence_bones)}.")
        source_points = clouds.get(bone_name, [])
        if len(source_points) < MIN_MULTI_HULL_POINTS and len(unfiltered_clouds.get(bone_name, [])) >= MIN_MULTI_HULL_POINTS:
            log_progress(f"{bone_name}: filtered source was sparse; retrying with unfiltered render sources.")
            source_points = unfiltered_clouds.get(bone_name, [])
        fit_started = time.monotonic()
        fit = fit_part(armature, bone_name, source_points, shrink, scene_mins, scene_maxs, group_bones=group_bones)
        bone_timing["fit_seconds"] = timing_entry(fit_started)
        region_started = time.monotonic()
        region = collect_bone_region_mesh_from_index(source_index, armature, bone_name, fit=fit)
        bone_timing["region_seconds"] = timing_entry(region_started)
        log_progress(
            f"{bone_name}: selected {int(region.get('selected_vertex_count', 0) or 0):,} region vertices, "
            f"{int(region.get('selected_face_count', 0) or 0):,} region faces, "
            f"{int(region.get('child_face_count', 0) or 0):,} child-joint faces."
        )
        if len(region.get("vertices", [])) < MIN_MULTI_HULL_POINTS and len(source_points) >= MIN_MULTI_HULL_POINTS:
            log_progress(f"{bone_name}: region mesh was sparse; retrying region selection with unfiltered render sources.")
            region_started = time.monotonic()
            region = collect_bone_region_mesh_from_index(unfiltered_index, armature, bone_name, fit=fit)
            bone_timing["unfiltered_region_seconds"] = timing_entry(region_started)
            log_progress(
                f"{bone_name}: unfiltered region has {int(region.get('selected_vertex_count', 0) or 0):,} vertices, "
                f"{int(region.get('selected_face_count', 0) or 0):,} faces."
            )
        coacd_started = time.monotonic()
        cache_key = collision_part_cache_key(input_blend, bone_name, shrink, source_index, region)
        vertices, faces, hulls, metrics, multi_warnings = make_coacd_region_geometry(armature, bone_name, region, shrink, cache_key=cache_key)
        bone_timing["coacd_seconds"] = timing_entry(coacd_started)
        method = "coacd_single_hull_weight_region"
        shape_type = "coacd_single_hull"
        confidence = min(0.96, 0.74 + float(metrics.get("coverage_score", 0.0)) * 0.14 + float(metrics.get("piece_success_score", 0.0)) * 0.08)
        if not vertices or not faces:
            log_progress(f"{bone_name}: CoACD did not produce valid geometry; trying connected loft fallback.")
            fallback_started = time.monotonic()
            loft_vertices, loft_faces, loft_hulls, loft_metrics, loft_warnings = make_connected_loft_geometry(
                armature,
                bone_name,
                source_points,
                shrink,
                fit,
                unfiltered_clouds,
                target_bones=target_names,
            )
            bone_timing["connected_loft_seconds"] = timing_entry(fallback_started)
            if loft_vertices and loft_faces:
                vertices, faces, hulls, metrics = loft_vertices, loft_faces, loft_hulls, loft_metrics
                method = "fallback_connected_loft"
                shape_type = "fallback_connected_loft"
                confidence = min(0.70, 0.52 + float(metrics.get("coverage_score", 0.0)) * 0.12 + float(metrics.get("piece_success_score", 0.0)) * 0.06)
                multi_warnings.extend(warning for warning in loft_warnings if warning not in multi_warnings)
                multi_warnings.append("Connected loft fallback used because CoACD single-hull generation failed.")
        if not vertices or not faces:
            log_progress(f"{bone_name}: connected loft failed; using primitive fallback.")
            primitive_started = time.monotonic()
            fallback_shape_type = str(fit["shape_type"])
            vertices, faces = make_part_geometry(fit)
            bone_timing["primitive_seconds"] = timing_entry(primitive_started)
            fallback_volume = mesh_volume(vertices, faces)
            hull_center = sum(vertices, Vector((0.0, 0.0, 0.0))) / float(len(vertices)) if vertices else fit["center"]
            hulls = [
                {
                    "index": 1,
                    "source_point_count": len(source_points),
                    "vertex_count": len(vertices),
                    "face_count": len(faces),
                    "volume": round(float(fallback_volume), 6),
                    "center": v3(hull_center),
                }
            ]
            method = "fallback_primitive"
            shape_type = f"fallback_{fallback_shape_type.replace('oriented_', '')}"
            confidence = min(float(fit["confidence"]), 0.52)
            multi_warnings.append("Primitive fallback used because CoACD and connected loft generation did not produce valid geometry.")
        volume = mesh_volume(vertices, faces)
        warnings = list(fit["warnings"])
        warnings.extend(warning for warning in multi_warnings if warning not in warnings)
        part = {
            "uid": uid,
            "enabled": enabled,
            "bone": bone_name,
            "shape_type": shape_type,
            "method": method,
            "shrink": shrink,
            "base_shrink": shrink,
            "shrink_offset": SHRINK_PRESENTATION_OFFSET,
            "shrink_offset_applied": True,
            "source_vertex_count": len(source_points),
            "filtered_source_count": metrics.get("filtered_source_count", len(source_points)),
            "fit_confidence": round(float(confidence), 4),
            "coverage_score": metrics.get("coverage_score", 0.0),
            "piece_success_score": metrics.get("piece_success_score", 1.0 if hulls else 0.0),
            "cluster_count": metrics.get("cluster_count", len(hulls)),
            "hull_piece_count": len(hulls),
            "hulls": hulls,
            "region": {
                "method": region.get("method", ""),
                "weight_mean": metrics.get("weight_mean", 0.0),
                "weight_stdev": metrics.get("weight_stdev", 0.0),
                "weight_threshold": metrics.get("weight_threshold", 0.0),
                "selected_vertex_count": region.get("selected_vertex_count", 0),
                "selected_face_count": metrics.get("selected_face_count", region.get("selected_face_count", 0)),
                "child_face_count": metrics.get("child_face_count", region.get("child_face_count", 0)),
                "influence_bones": region.get("influence_bones", []),
                "source_objects": region.get("source_objects", []),
            },
            "coacd": metrics.get("coacd", {}),
            "timing": bone_timing,
            "warnings": warnings,
            "volume": round(float(volume), 6),
            "vertex_count": len(vertices),
            "face_count": len(faces),
            "settings": settings_for_target_spec(spec),
            "kind": kind,
            "collision_group": spec.get("collision_group"),
            "group_bones": group_bones,
            "rotation_type": str(spec.get("rotation_type") or ""),
            "rotation_label": str(spec.get("rotation_label") or ""),
            "preview_color": preview_color(bone_name, index),
            "center": v3(fit["center"]),
            "preview_center": v3(armature.matrix_world @ fit["center"]),
            "radii": [round(float(value), 6) for value in fit["radii"]],
            "vertices": [v3(vertex) for vertex in vertices],
            "preview_vertices": [v3(armature.matrix_world @ vertex) for vertex in vertices],
            "faces": [list(face) for face in faces],
        }
        if volume <= EPSILON:
            part["warnings"].append("Generated part has zero or negative volume.")
        parts.append(part)
        bone_timing["total_seconds"] = timing_entry(bone_started)
        timing.setdefault("bones", {})[bone_name] = bone_timing
        log_progress(
            f"{bone_name}: final {shape_type} has {len(hulls)} hull piece(s), "
            f"{len(vertices):,} vertices, {len(faces):,} faces, volume {volume:.4f} "
            f"in {bone_timing['total_seconds']:.2f}s."
        )
    timing["total_seconds"] = timing_entry(total_started)
    log_progress(f"Built {len(parts)} collision parts in {timing['total_seconds']:.2f}s.")
    return parts, errors, timing


def is_informational_collision_message(text: object) -> bool:
    message = str(text or "").strip()
    return (
        message.startswith("Included ")
        and (
            message.endswith(" child-bone joint faces so this bone exports as one filled collision region.")
            or message.endswith(" child-bone joint samples to fill the connected collision span.")
        )
    )


def analyze_scene(input_blend: Path) -> tuple[dict[str, object], dict[str, object]]:
    analyze_started = time.monotonic()
    phase_timing: dict[str, object] = {"quality_preset": ACTIVE_COACD_QUALITY, "quality_label": current_quality_label()}
    log_progress(f"Analyzing collision plan for {input_blend}.")
    armature = main_armature()
    target_specs, additional_errors, additional_groups = target_specs_for_armature(armature)
    target_bones = [str(spec.get("bone") or "") for spec in target_specs if spec.get("bone")]
    settings_by_bone = {str(spec.get("bone") or ""): settings_for_target_spec(spec) for spec in target_specs if spec.get("bone")}
    collision_qc_lines = collision_qc_lines_for_specs(target_specs)
    coacd_status = coacd_runtime_status()
    log_progress(f"CoACD runtime available={coacd_status.get('available')} source={coacd_status.get('source')}.")
    preview_started = time.monotonic()
    preview = collect_model_preview()
    phase_timing["preview_seconds"] = timing_entry(preview_started)
    source_started = time.monotonic()
    source_bodygroups = collect_collision_source_bodygroups(armature, target_specs)
    phase_timing["source_bodygroup_scan_seconds"] = timing_entry(source_started)
    source_selection = source_selection_summary()
    selected_sources = set(source_selection.get("enabled_bodygroups", [])) if source_selection.get("mode") == "explicit_bodygroups" else {
        str(entry.get("name") or "") for entry in source_bodygroups
    }
    if not selected_sources:
        log_progress("No CoACD source bodygroups are enabled.")
        parts, errors, build_timing = [], ["No CoACD source bodygroups are enabled."], {}
    else:
        parts, errors, build_timing = build_collision_parts(input_blend=input_blend, target_specs=target_specs)
    errors = sorted(set(list(additional_errors) + list(errors)))
    phase_timing["build_collision"] = build_timing
    warnings: list[str] = []
    for part in parts:
        warnings.extend(
            str(warning)
            for warning in part.get("warnings", [])
            if warning and not is_informational_collision_message(warning)
        )
    collision_started = time.monotonic()
    collision = collision_preview(parts, armature) if armature is not None else {"triangles": [], "triangle_count": 0}
    phase_timing["collision_preview_seconds"] = timing_entry(collision_started)
    phase_timing["total_seconds"] = timing_entry(analyze_started)
    analysis = {
        "version": 1,
        "kind": "sort_collision",
        "input_blend": str(input_blend),
        "armature": armature.name if armature else "",
        "default_target_bones": DEFAULT_TARGET_BONES,
        "target_bones": target_bones,
        "additional_collision_groups": additional_groups,
        "collision_parts": parts,
        "part_count": len(parts),
        "source_bodygroups": source_bodygroups,
        "selected_source_bodygroups": sorted(selected_sources, key=natural_key),
        "source_selection": source_selection,
        "physics_settings": settings_by_bone,
        "collision_qc_lines": collision_qc_lines,
        "coacd": coacd_status,
        "coacd_quality": {"preset": ACTIVE_COACD_QUALITY, "label": current_quality_label(), "settings": current_quality_preset()},
        "requires_concaveperjoint": True,
        "qc_options": ["$concaveperjoint"],
        "model_preview": preview.get("model_preview", {}),
        "materials": preview.get("materials", []),
        "material_count": preview.get("material_count", 0),
        "collision_preview": collision,
        "timing": phase_timing,
        "warnings": sorted(set(warnings)),
        "errors": errors,
    }
    plan = {
        "version": 1,
        "kind": "sort_collision",
        "input_blend": str(input_blend),
        "default_target_bones": DEFAULT_TARGET_BONES,
        "target_bones": target_bones,
        "additional_collision_groups": additional_groups,
        "collision_parts": parts,
        "source_bodygroups": source_bodygroups,
        "selected_source_bodygroups": sorted(selected_sources, key=natural_key),
        "source_selection": source_selection,
        "physics_settings": settings_by_bone,
        "collision_qc_lines": collision_qc_lines,
        "coacd": coacd_status,
        "coacd_quality": {"preset": ACTIVE_COACD_QUALITY, "label": current_quality_label(), "settings": current_quality_preset()},
        "requires_concaveperjoint": True,
        "qc_options": ["$concaveperjoint"],
        "collision_preview": collision,
        "timing": phase_timing,
        "validation": validate_plan(parts, errors, target_bones=target_bones),
    }
    return analysis, plan


def validate_plan(
    parts: list[dict[str, object]],
    existing_errors: Iterable[str] = (),
    target_bones: Iterable[str] | None = None,
) -> dict[str, object]:
    errors = list(existing_errors)
    warnings: list[str] = []
    by_bone = {str(part.get("bone") or ""): part for part in parts}
    target_names = [str(name) for name in (target_bones or TARGET_BONES) if str(name)]
    for bone_name in target_names:
        part = by_bone.get(bone_name)
        if not part:
            errors.append(f"Missing collision part for {bone_name}.")
            continue
        if not bool(part.get("enabled", True)):
            errors.append(f"Collision part for {bone_name} is disabled.")
        try:
            volume = float(part.get("volume", 0.0) or 0.0)
        except Exception:
            volume = 0.0
        if volume <= EPSILON:
            errors.append(f"Collision part for {bone_name} has zero or negative volume.")
        if int(part.get("vertex_count", 0) or 0) <= 0 or int(part.get("face_count", 0) or 0) <= 0:
            errors.append(f"Collision part for {bone_name} has invalid geometry.")
        if int(part.get("hull_piece_count", 0) or 0) <= 0:
            errors.append(f"Collision part for {bone_name} has no enabled hull pieces.")
        if int(part.get("hull_piece_count", 0) or 0) > 1:
            errors.append(f"Collision part for {bone_name} has multiple disconnected pieces; exactly one connected piece is required.")
        hulls = part.get("hulls", [])
        if isinstance(hulls, list):
            for hull in hulls:
                if not isinstance(hull, dict):
                    continue
                if float(hull.get("volume", 0.0) or 0.0) <= EPSILON or int(hull.get("face_count", 0) or 0) <= 0:
                    errors.append(f"Collision part for {bone_name} has an invalid hull piece.")
        warnings.extend(
            str(warning)
            for warning in part.get("warnings", [])
            if warning and not is_informational_collision_message(warning)
        )
    return {"ok": not errors, "errors": errors, "warnings": sorted(set(warnings))}


def delete_existing_physics() -> None:
    for obj in list(bpy.data.objects):
        if obj.name == "Physics":
            bpy.data.objects.remove(obj, do_unlink=True)


def point3(raw: object, default: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> list[float]:
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        try:
            return [float(raw[0]), float(raw[1]), float(raw[2])]
        except Exception:
            pass
    return [float(default[0]), float(default[1]), float(default[2])]


def scale_point(raw: object, center: list[float], ratio: float) -> list[float]:
    point = point3(raw)
    return [
        center[0] + (point[0] - center[0]) * ratio,
        center[1] + (point[1] - center[1]) * ratio,
        center[2] + (point[2] - center[2]) * ratio,
    ]


def scaled_collision_part(part: dict[str, object]) -> dict[str, object]:
    scaled = copy.deepcopy(part)
    try:
        shrink = float(scaled.get("shrink", 1.0) or 1.0)
    except Exception:
        shrink = 1.0
    try:
        base_shrink = float(scaled.get("base_shrink", shrink) or shrink)
    except Exception:
        base_shrink = shrink
    if base_shrink <= EPSILON:
        base_shrink = shrink if shrink > EPSILON else 1.0
    ratio = max(0.05, min(4.0, shrink / base_shrink))
    scaled["shrink"] = shrink
    scaled["base_shrink"] = base_shrink
    scaled.setdefault("shrink_offset", SHRINK_PRESENTATION_OFFSET)
    scaled.setdefault("shrink_offset_applied", True)
    scaled["applied_scale_ratio"] = round(float(ratio), 6)
    vertices_raw = scaled.get("vertices", [])
    faces_raw = scaled.get("faces", [])
    if not isinstance(vertices_raw, list) or not isinstance(faces_raw, list):
        return scaled
    center = point3(scaled.get("center"))
    scaled_vertices = [scale_point(vertex, center, ratio) for vertex in vertices_raw if isinstance(vertex, (list, tuple)) and len(vertex) >= 3]
    scaled["vertices"] = scaled_vertices
    preview_vertices = scaled.get("preview_vertices", [])
    if isinstance(preview_vertices, list):
        preview_center = point3(scaled.get("preview_center"), tuple(center))
        scaled["preview_vertices"] = [
            scale_point(vertex, preview_center, ratio)
            for vertex in preview_vertices
            if isinstance(vertex, (list, tuple)) and len(vertex) >= 3
        ]
    if isinstance(scaled.get("radii"), list):
        try:
            scaled["radii"] = [round(float(value) * ratio, 6) for value in scaled.get("radii", [])]
        except Exception:
            pass
    faces = [tuple(int(value) for value in raw[:3]) for raw in faces_raw if isinstance(raw, (list, tuple)) and len(raw) >= 3]
    vector_vertices = [Vector(vertex) for vertex in scaled_vertices]
    volume = mesh_volume(vector_vertices, faces) if vector_vertices and faces else 0.0
    scaled["volume"] = round(float(volume), 6)
    scaled["vertex_count"] = len(scaled_vertices)
    scaled["face_count"] = len(faces)
    hulls = scaled.get("hulls", [])
    if isinstance(hulls, list):
        volume_ratio = ratio ** 3
        for hull in hulls:
            if not isinstance(hull, dict):
                continue
            if isinstance(hull.get("center"), list):
                hull["center"] = scale_point(hull.get("center"), center, ratio)
            try:
                hull["volume"] = round(float(hull.get("volume", 0.0) or 0.0) * volume_ratio, 6)
            except Exception:
                pass
    return scaled


def prepare_collision_parts_from_plan(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[str]]:
    parts: list[dict[str, object]] = []
    errors: list[str] = []
    for row in rows:
        bone_name = str(row.get("bone") or "")
        if not bone_name:
            errors.append("Collision plan contains a row with no bone name.")
            continue
        if not isinstance(row.get("vertices"), list) or not isinstance(row.get("faces"), list):
            errors.append(f"{bone_name}: cached analyzed collision geometry is missing; rerun Analyze Collision.")
            continue
        parts.append(scaled_collision_part(row))
    return parts, errors


def create_physics_object(armature: bpy.types.Object, parts: list[dict[str, object]]) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    vertex_ranges: list[tuple[str, list[int]]] = []
    for part in parts:
        if not bool(part.get("enabled", True)):
            continue
        bone_name = str(part.get("bone") or "")
        start = len(vertices)
        part_vertices = [tuple(float(value) for value in raw[:3]) for raw in part.get("vertices", [])]
        part_faces = [tuple(int(value) + start for value in raw[:3]) for raw in part.get("faces", [])]
        vertices.extend(part_vertices)
        faces.extend(part_faces)
        vertex_ranges.append((bone_name, list(range(start, start + len(part_vertices)))))
    mesh = bpy.data.meshes.new("PhysicsMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    delete_existing_physics()
    obj = bpy.data.objects.new("Physics", mesh)
    bpy.context.collection.objects.link(obj)
    obj.matrix_world = armature.matrix_world.copy()
    mat = bpy.data.materials.get("phy") or bpy.data.materials.new("phy")
    mat.diffuse_color = (0.2, 0.65, 1.0, 0.38)
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0
    for bone_name, indices in vertex_ranges:
        group = obj.vertex_groups.new(name=bone_name)
        group.add(indices, 1.0, "REPLACE")
    modifier = obj.modifiers.new("Armature", "ARMATURE")
    modifier.object = armature
    return obj


def validate_physics_object(
    obj: bpy.types.Object | None,
    armature: bpy.types.Object | None,
    parts: list[dict[str, object]],
    target_bones: Iterable[str] | None = None,
) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    if armature is None:
        errors.append("Missing armature.")
        return {"ok": False, "errors": errors, "warnings": warnings}
    target_names = [str(name) for name in (target_bones or TARGET_BONES) if str(name)]
    missing_bones = [bone for bone in target_names if bone not in armature.data.bones]
    errors.extend(f"Missing required target bone: {bone}" for bone in missing_bones)
    plan_validation = validate_plan(parts, target_bones=target_names)
    errors.extend(plan_validation.get("errors", []))
    warnings.extend(plan_validation.get("warnings", []))
    if obj is None:
        errors.append("Missing Physics object after apply.")
        return {"ok": False, "errors": errors, "warnings": warnings}
    if not any(mat and mat.name == "phy" for mat in obj.data.materials):
        errors.append("Missing phy material on Physics object.")
    group_names = {group.index: group.name for group in obj.vertex_groups}
    target_set = set(target_names)
    used_targets: set[str] = set()
    for vertex in obj.data.vertices:
        links = [(group_names.get(ref.group, ""), float(ref.weight)) for ref in vertex.groups if abs(float(ref.weight)) > 1e-6]
        if len(links) != 1:
            errors.append(f"Physics vertex {vertex.index} has {len(links)} nonzero weights; exactly one is required.")
            continue
        name, weight = links[0]
        if name not in target_set:
            errors.append(f"Physics vertex {vertex.index} is weighted to non-target bone {name}.")
        if abs(weight - 1.0) > 1e-6:
            errors.append(f"Physics vertex {vertex.index} weight to {name} is {weight:.6f}; expected 1.0.")
        used_targets.add(name)
    for bone_name in target_names:
        if bone_name not in used_targets:
            errors.append(f"No Physics vertices are weighted to {bone_name}.")
    if not obj.modifiers or not any(modifier.type == "ARMATURE" and modifier.object == armature for modifier in obj.modifiers):
        errors.append("Physics object is missing an Armature modifier targeting the main armature.")
    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def write_physics_smd(
    path: Path,
    armature: bpy.types.Object,
    physics: bpy.types.Object,
    fallback_bone: str | None = None,
) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    group_names = {group.index: group.name for group in physics.vertex_groups}
    used_bone_names = {
        group_names.get(ref.group, "")
        for vertex in physics.data.vertices
        for ref in vertex.groups
        if abs(float(ref.weight)) > 1e-6 and group_names.get(ref.group, "")
    }
    required_names: set[str] = set()
    for name in used_bone_names:
        bone = armature.data.bones.get(name)
        while bone is not None:
            required_names.add(bone.name)
            bone = bone.parent
    bones = [bone for bone in armature.data.bones if bone.name in required_names]
    bone_ids = {bone.name: index for index, bone in enumerate(bones)}
    physics.data.update(calc_edges=False)
    triangle_count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("version 1\n")
        handle.write("nodes\n")
        for bone in bones:
            parent_id = bone_ids.get(bone.parent.name, -1) if bone.parent and bone.parent.name in bone_ids else -1
            handle.write(f'{bone_ids[bone.name]} "{bone.name}" {parent_id}\n')
        handle.write("end\n")
        handle.write("skeleton\n")
        handle.write("time 0\n")
        for bone in bones:
            if bone.parent:
                local = bone.parent.matrix_local.inverted() @ bone.matrix_local
            else:
                local = bone.matrix_local
            pos = local.to_translation()
            rot = local.to_euler("XYZ")
            handle.write(
                f"{bone_ids[bone.name]} {pos.x:.6f} {pos.y:.6f} {pos.z:.6f} "
                f"{rot.x:.6f} {rot.y:.6f} {rot.z:.6f}\n"
            )
        handle.write("end\n")
        handle.write("triangles\n")
        for poly in physics.data.polygons:
            if len(poly.vertices) < 3:
                continue
            loop_indices = list(poly.loop_indices)
            vertex_indices = list(poly.vertices)
            for offset in range(1, len(vertex_indices) - 1):
                handle.write("phy\n")
                tri_vertex_indices = [vertex_indices[0], vertex_indices[offset], vertex_indices[offset + 1]]
                tri_loop_indices = [loop_indices[0], loop_indices[offset], loop_indices[offset + 1]]
                for vertex_index, loop_index in zip(tri_vertex_indices, tri_loop_indices):
                    vertex = physics.data.vertices[int(vertex_index)]
                    loop = physics.data.loops[int(loop_index)]
                    links = [
                        (group_names.get(ref.group, ""), float(ref.weight))
                        for ref in vertex.groups
                        if abs(float(ref.weight)) > 1e-6
                    ]
                    bone_name = links[0][0] if links else (fallback_bone or TARGET_BONES[0])
                    bone_id = bone_ids.get(bone_name, 0)
                    co = vertex.co
                    normal = loop.normal if loop.normal.length > EPSILON else poly.normal
                    handle.write(
                        f"{bone_id} {co.x:.6f} {co.y:.6f} {co.z:.6f} "
                        f"{normal.x:.6f} {normal.y:.6f} {normal.z:.6f} "
                        f"0.000000 0.000000 1 {bone_id} 1.000000\n"
                    )
                triangle_count += 1
        handle.write("end\n")
    return {"path": str(path), "triangle_count": triangle_count, "bone_count": len(bones)}


def validate_physics_smd_import(path: Path) -> dict[str, object]:
    log_progress(f"Validating Physics.smd by importing it back: {path}")
    if not path.exists():
        return {"ok": False, "skipped": False, "error": f"SMD file does not exist: {path}"}
    try:
        bpy.ops.import_scene.smd.get_rna_type()
    except Exception:
        try:
            import addon_utils

            addon_utils.enable("io_scene_valvesource", default_set=False, persistent=False)
        except Exception as exc:
            return {"ok": False, "skipped": True, "error": f"Blender Source Tools importer unavailable: {exc}"}
    try:
        bpy.ops.import_scene.smd.get_rna_type()
    except Exception as exc:
        return {"ok": False, "skipped": True, "error": f"Blender Source Tools importer unavailable: {exc}"}
    before = {obj.name for obj in bpy.data.objects}
    try:
        result = bpy.ops.import_scene.smd(filepath=str(path))
    except Exception as exc:
        return {"ok": False, "skipped": False, "error": f"Physics.smd import failed: {exc}"}
    imported = [obj for obj in bpy.data.objects if obj.name not in before]
    mesh_count = sum(1 for obj in imported if obj.type == "MESH")
    triangle_count = sum(len(obj.data.polygons) for obj in imported if obj.type == "MESH")
    for obj in imported:
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass
    log_progress(f"Physics.smd import validation imported {mesh_count} mesh object(s), {triangle_count:,} triangles.")
    return {
        "ok": mesh_count > 0,
        "skipped": False,
        "operator_result": sorted(str(item) for item in result) if isinstance(result, set) else str(result),
        "imported_object_count": len(imported),
        "imported_mesh_count": mesh_count,
        "imported_triangle_count": triangle_count,
    }


def apply_scene(
    input_blend: Path,
    plan_path: Path,
    output_blend: Path,
    report_json: Path,
    physics_settings_json: Path | None,
    physics_smd: Path | None,
) -> dict[str, object]:
    log_progress(f"Applying collision plan to {input_blend}.")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    rows = [row for row in plan.get("collision_parts", []) if isinstance(row, dict)]
    target_bones = [str(name) for name in plan.get("target_bones", []) if str(name)] if isinstance(plan.get("target_bones"), list) else []
    if not target_bones:
        target_bones = [str(row.get("bone") or "") for row in rows if row.get("bone")]
    default_target_bones = [str(name) for name in plan.get("default_target_bones", DEFAULT_TARGET_BONES) if str(name)] if isinstance(plan.get("default_target_bones", DEFAULT_TARGET_BONES), list) else DEFAULT_TARGET_BONES
    additional_groups = plan.get("additional_collision_groups", [])
    if not isinstance(additional_groups, list):
        additional_groups = []
    settings_by_bone = plan.get("physics_settings", {})
    if not isinstance(settings_by_bone, dict):
        settings_by_bone = {}
    if not settings_by_bone:
        settings_by_bone = {
            str(part.get("bone") or ""): part.get("settings", [])
            for part in rows
            if part.get("bone") and isinstance(part.get("settings", []), list)
        }
    collision_qc_lines = plan.get("collision_qc_lines", [])
    if not isinstance(collision_qc_lines, list) or not collision_qc_lines:
        collision_qc_lines = []
    log_progress("Using cached analyzed collision geometry from collision_plan.json; CoACD is not run during apply.")
    parts, plan_errors = prepare_collision_parts_from_plan(rows)
    for part in parts:
        ratio = float(part.get("applied_scale_ratio", 1.0) or 1.0)
        if abs(ratio - 1.0) > 1e-5:
            log_progress(f"{part.get('bone')}: scaled cached hull by {ratio:.4f} for shrink {float(part.get('shrink', 1.0) or 1.0):.3f}.")
    validation = validate_plan(parts, plan_errors, target_bones=target_bones)
    if validation.get("errors"):
        report = {
            "version": 1,
            "kind": "sort_collision",
            "input_blend": str(input_blend),
            "output_blend": str(output_blend),
            "collision_parts": parts,
            "validation": validation,
        }
        write_json(report_json, report)
        raise RuntimeError("Collision validation failed before apply: " + "; ".join(str(error) for error in validation.get("errors", [])))
    armature = main_armature()
    physics = create_physics_object(armature, parts) if armature is not None else None
    log_progress("Created Physics object and assigned rigid 1.0 target-bone weights.")
    final_validation = validate_physics_object(physics, armature, parts, target_bones=target_bones)
    smd_info: dict[str, object] = {}
    if physics_smd is not None and armature is not None and physics is not None:
        try:
            smd_info = write_physics_smd(physics_smd, armature, physics, fallback_bone=target_bones[0] if target_bones else None)
            log_progress(f"Wrote Physics.smd with {smd_info.get('bone_count')} bones and {smd_info.get('triangle_count')} triangles.")
        except Exception as exc:
            final_validation.setdefault("warnings", []).append(f"Physics.smd export failed: {exc}")
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    log_progress(f"Saved collision-sorted blend: {output_blend}")
    smd_import_validation: dict[str, object] = {}
    if physics_smd is not None:
        smd_import_validation = validate_physics_smd_import(physics_smd)
        if smd_import_validation and not smd_import_validation.get("ok", False):
            final_validation.setdefault("warnings", []).append(str(smd_import_validation.get("error") or "Physics.smd import validation did not pass."))
    physics_settings = {
        "version": 2,
        "target_bones": target_bones,
        "default_target_bones": default_target_bones,
        "additional_collision_groups": additional_groups,
        "settings_by_bone": settings_by_bone,
        "qc_lines": [
            str(entry.get("line") or "")
            for bone in target_bones
            for entry in settings_by_bone.get(bone, [])
            if isinstance(entry, dict) and entry.get("line")
        ],
        "collision_qc_lines": [str(line) for line in collision_qc_lines] if collision_qc_lines else [],
        "requires_concaveperjoint": True,
        "qc_options": ["$concaveperjoint"],
    }
    if physics_settings_json is not None:
        write_json(physics_settings_json, physics_settings)
    report = {
        "version": 1,
        "kind": "sort_collision",
        "input_blend": str(input_blend),
        "output_blend": str(output_blend),
        "physics_object": physics.name if physics else "",
        "physics_material": "phy",
        "collision_parts": parts,
        "part_count": len(parts),
        "source_bodygroups": plan.get("source_bodygroups", []),
        "selected_source_bodygroups": plan.get("selected_source_bodygroups", []),
        "source_selection": plan.get("source_selection", {}),
        "coacd_quality": plan.get("coacd_quality", {}),
        "timing": plan.get("timing", {}),
        "physics_settings": physics_settings,
        "physics_smd": smd_info,
        "physics_smd_import_validation": smd_import_validation,
        "requires_concaveperjoint": True,
        "qc_options": ["$concaveperjoint"],
        "validation": final_validation,
    }
    write_json(report_json, report)
    if final_validation.get("errors"):
        raise RuntimeError("Collision validation failed after apply: " + "; ".join(str(error) for error in final_validation.get("errors", [])))
    return report


def main() -> int:
    global ACTIVE_COACD_QUALITY, ACTIVE_RESULT_CACHE_DIR
    args = parse_args()
    started = time.monotonic()
    ACTIVE_COACD_QUALITY = str(args.quality_preset or "fast_preview")
    ACTIVE_RESULT_CACHE_DIR = args.coacd_cache_dir
    if ACTIVE_RESULT_CACHE_DIR is not None:
        ACTIVE_RESULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    log_progress(f"CoACD quality preset: {current_quality_label()} ({ACTIVE_COACD_QUALITY}).")
    ensure_object_mode()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend))
    ensure_object_mode()
    set_active_source_bodygroups(args.source_bodygroups_json)
    set_active_additional_bones(args.additional_bones_json)
    if args.mode == "scan-sources":
        if args.sources_json is None:
            raise SystemExit("--sources-json is required for scan-sources mode")
        sources = scan_source_bodygroups(args.input_blend)
        write_json(args.sources_json, sources)
        print(f"Wrote collision source bodygroups to {args.sources_json}")
    elif args.mode == "scan-bones":
        if args.bones_json is None:
            raise SystemExit("--bones-json is required for scan-bones mode")
        bones = scan_collision_bones(args.input_blend)
        write_json(args.bones_json, bones)
        print(f"Wrote collision bones to {args.bones_json}")
    elif args.mode == "analyze":
        if args.analysis_json is None:
            raise SystemExit("--analysis-json is required for analyze mode")
        if args.plan_json is None:
            raise SystemExit("--plan-json is required for analyze mode")
        analysis, plan = analyze_scene(args.input_blend)
        json_started = time.monotonic()
        write_json(args.analysis_json, analysis)
        write_json(args.plan_json, plan)
        log_progress(f"Wrote collision JSON files in {time.monotonic() - json_started:.2f}s.")
        print(f"Wrote collision analysis to {args.analysis_json}")
        print(f"Wrote collision plan to {args.plan_json}")
    else:
        if args.plan_json is None or args.output_blend is None or args.report_json is None:
            raise SystemExit("--output-blend and --report-json are required for apply mode")
        report = apply_scene(args.input_blend, args.plan_json, args.output_blend, args.report_json, args.physics_settings_json, args.physics_smd)
        print(f"Wrote collision report to {args.report_json}")
        print(f"Saved collision-sorted blend to {args.output_blend}")
        print(f"Validation ok: {report.get('validation', {}).get('ok')}")
    print(f"Step 8 collision helper completed in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
