#!/usr/bin/env python3
"""Static PMX OpenGL preview for the MMD Character Importer."""

from __future__ import annotations

import ctypes
import colorsys
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
except Exception as exc:  # pragma: no cover - GUI dependency guard
    raise RuntimeError("PySide6 is required for model preview") from exc

try:
    from OpenGL import GL
except Exception:  # pragma: no cover - widget reports unavailable backend
    GL = None

try:
    import mmd_character_importer_core as core
except ModuleNotFoundError:
    from . import mmd_character_importer_core as core  # type: ignore[no-redef]


BONE_LINE_WIDTH = 2.2
BONE_POINT_RADIUS = 3.2
BONE_OVERLAY_LINE_WIDTH = 2.6
BONE_OVERLAY_POINT_SIZE = 5.0
BONE_HIGHLIGHT_LINE_WIDTH = 6.0
BONE_HIGHLIGHT_POINT_RADIUS = 8.0
BONE_HIGHLIGHT_POINT_SIZE = 10.0


def _truthy_env(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _preview_debug_log_path() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "MMDCharacterImporter" / "logs" / "material_preview_debug.log"
    return Path.home() / ".MMDCharacterImporter" / "logs" / "material_preview_debug.log"


@dataclass
class PreviewMaterial:
    name: str
    diffuse: tuple[float, float, float, float]
    texture_path: Path | None
    index_start: int
    index_count: int
    texture_ref: str = ""
    missing_texture: bool = False


@dataclass
class PreviewBone:
    name: str
    english_name: str
    parent: int
    position: tuple[float, float, float]


@dataclass
class StaticPreviewModel:
    path: Path
    name: str
    english_name: str
    positions: np.ndarray
    normals: np.ndarray
    uvs: np.ndarray
    indices: np.ndarray
    materials: list[PreviewMaterial]
    bones: list[PreviewBone]
    morph_count: int
    texture_count: int
    warnings: list[str]

    @property
    def vertex_count(self) -> int:
        return int(len(self.positions))

    @property
    def triangle_count(self) -> int:
        return int(len(self.indices) // 3)


def _read_vertex(reader: core.PmxReader, bone_index_size: int, additional_uvs: int) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float]]:
    position = (reader.read_f32(), reader.read_f32(), reader.read_f32())
    normal = (reader.read_f32(), reader.read_f32(), reader.read_f32())
    uv = (reader.read_f32(), reader.read_f32())
    for _ in range(additional_uvs):
        reader.read_vector_bytes(4)
    weight_type = reader.read_u8()
    if weight_type == 0:
        reader.read_index(bone_index_size)
    elif weight_type == 1:
        reader.read_index(bone_index_size)
        reader.read_index(bone_index_size)
        reader.read_f32()
    elif weight_type in (2, 4):
        for _ in range(4):
            reader.read_index(bone_index_size)
        reader.read_vector_bytes(4)
    elif weight_type == 3:
        reader.read_index(bone_index_size)
        reader.read_index(bone_index_size)
        reader.read_f32()
        reader.read_vector_bytes(3)
        reader.read_vector_bytes(3)
        reader.read_vector_bytes(3)
    else:
        raise ValueError(f"unsupported PMX vertex weight type: {weight_type}")
    reader.read_f32()
    return position, normal, uv


def _read_vertex_index(reader: core.PmxReader, vertex_index_size: int) -> int:
    return reader.read_index(vertex_index_size, signed=False)


def _texture_files(model_path: Path) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".dds"}
    out: list[Path] = []
    for base in (model_path.parent, model_path.parent / "textures"):
        if base.exists():
            out.extend(path for path in base.rglob("*") if path.is_file() and path.suffix.lower() in exts)
    return sorted(set(out))


def _texture_ref(texture_names: list[str], texture_index: int) -> str:
    if texture_index < 0 or texture_index >= len(texture_names):
        return ""
    return texture_names[texture_index].replace("\\", "/").strip()


def _resolve_texture_ref(model_path: Path, raw: str, lookup: dict[str, Path]) -> Path | None:
    if not raw or raw.startswith("*"):
        return None
    relative = Path(raw)
    for candidate in (model_path.parent / relative, model_path.parent / "textures" / relative.name):
        if candidate.exists():
            return candidate
    return lookup.get(relative.name.lower())


def _resolve_texture_path(model_path: Path, texture_names: list[str], texture_index: int, lookup: dict[str, Path]) -> Path | None:
    return _resolve_texture_ref(model_path, _texture_ref(texture_names, texture_index), lookup)


def _read_materials(reader: core.PmxReader, encoding: str, texture_index_size: int, model_path: Path, texture_names: list[str]) -> list[PreviewMaterial]:
    texture_lookup = {path.name.lower(): path for path in _texture_files(model_path)}
    materials: list[PreviewMaterial] = []
    index_start = 0
    for _ in range(reader.read_i32()):
        name = reader.read_string(encoding)
        reader.read_string(encoding)
        diffuse = (reader.read_f32(), reader.read_f32(), reader.read_f32(), reader.read_f32())
        reader.read_vector_bytes(3)
        reader.read_f32()
        reader.read_vector_bytes(3)
        reader.read_u8()
        reader.read_vector_bytes(4)
        reader.read_f32()
        texture_index = reader.read_index(texture_index_size)
        texture_ref = _texture_ref(texture_names, texture_index)
        texture_path = _resolve_texture_ref(model_path, texture_ref, texture_lookup)
        reader.read_index(texture_index_size)
        reader.read_i8()
        shared_toon = reader.read_i8()
        if shared_toon == 1:
            reader.read_i8()
        else:
            reader.read_index(texture_index_size)
        reader.read_string(encoding)
        index_count = reader.read_i32()
        materials.append(
            PreviewMaterial(
                name=name,
                diffuse=diffuse,
                texture_path=texture_path,
                index_start=index_start,
                index_count=index_count,
                texture_ref=texture_ref,
                missing_texture=bool(texture_ref and not texture_ref.startswith("*") and texture_path is None),
            )
        )
        index_start += index_count
    return materials


def _read_bone(reader: core.PmxReader, encoding: str, bone_index_size: int) -> PreviewBone:
    name = reader.read_string(encoding)
    english_name = reader.read_string(encoding)
    position = (reader.read_f32(), reader.read_f32(), reader.read_f32())
    parent = reader.read_index(bone_index_size)
    reader.read_i32()
    flags = reader.read_i16()
    if flags & 0x0001:
        reader.read_index(bone_index_size)
    else:
        reader.read_vector_bytes(3)
    if flags & 0x0300:
        reader.read_index(bone_index_size)
        reader.read_f32()
    if flags & 0x0400:
        reader.read_vector_bytes(3)
    if flags & 0x0800:
        reader.read_vector_bytes(3)
        reader.read_vector_bytes(3)
    if flags & 0x2000:
        reader.read_i32()
    if flags & 0x0020:
        reader.read_index(bone_index_size)
        reader.read_i32()
        reader.read_f32()
        for _ in range(reader.read_i32()):
            reader.read_index(bone_index_size)
            if reader.read_u8():
                reader.read_vector_bytes(3)
                reader.read_vector_bytes(3)
    return PreviewBone(name, english_name, parent, position)


def load_static_preview_model(model_path: Path) -> StaticPreviewModel:
    model_path = model_path.resolve()
    warnings: list[str] = []
    reader = core.PmxReader(model_path)
    try:
        signature = reader.read_exact(4)
        if signature != b"PMX ":
            raise ValueError(f"not a PMX file: invalid signature {signature!r}")
        reader.read_f32()
        header_size = reader.read_u8()
        encoding = "utf-16-le" if reader.read_u8() == 0 else "utf-8"
        additional_uvs = reader.read_u8()
        vertex_index_size = reader.read_u8()
        texture_index_size = reader.read_u8()
        material_index_size = reader.read_u8()
        bone_index_size = reader.read_u8()
        morph_index_size = reader.read_u8()
        rigid_index_size = reader.read_u8()
        for _ in range(max(0, header_size - 8)):
            reader.read_u8()

        name = reader.read_string(encoding)
        english_name = reader.read_string(encoding)
        reader.read_string(encoding)
        reader.read_string(encoding)

        vertex_count = reader.read_i32()
        if vertex_count > core.MAX_SUPPORTED_PMX_VERTEX_COUNT:
            raise RuntimeError(
                f"PMX vertex count {vertex_count:,} exceeds the supported limit of "
                f"{core.MAX_SUPPORTED_PMX_VERTEX_COUNT:,}. This model is too large for the importer."
            )
        positions = np.zeros((vertex_count, 3), dtype=np.float32)
        normals = np.zeros((vertex_count, 3), dtype=np.float32)
        uvs = np.zeros((vertex_count, 2), dtype=np.float32)
        for index in range(vertex_count):
            position, normal, uv = _read_vertex(reader, bone_index_size, additional_uvs)
            positions[index] = position
            normals[index] = normal
            uvs[index] = uv

        index_count = reader.read_i32()
        indices = np.array([_read_vertex_index(reader, vertex_index_size) for _ in range(index_count)], dtype=np.uint32)

        texture_names = [reader.read_string(encoding) for _ in range(reader.read_i32())]
        materials = _read_materials(reader, encoding, texture_index_size, model_path, texture_names)

        bones = [_read_bone(reader, encoding, bone_index_size) for _ in range(reader.read_i32())]
        morph_count = reader.read_i32()
        for _ in range(morph_count):
            core.skip_morph(
                reader,
                encoding,
                vertex_index_size,
                bone_index_size,
                morph_index_size,
                material_index_size,
                rigid_index_size,
            )
    finally:
        reader.close()

    unresolved = sum(1 for material in materials if material.missing_texture)
    if unresolved:
        warnings.append(f"{unresolved} material(s) have no resolved preview texture.")
    return StaticPreviewModel(
        path=model_path,
        name=name,
        english_name=english_name,
        positions=positions,
        normals=normals,
        uvs=uvs,
        indices=indices,
        materials=materials,
        bones=bones,
        morph_count=morph_count,
        texture_count=len(texture_names),
        warnings=warnings,
    )


def _translation_matrix(v: np.ndarray) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, 3] = v[:3]
    return matrix


def _rotation_x_matrix(angle: float) -> np.ndarray:
    c, s = float(math.cos(angle)), float(math.sin(angle))
    matrix = np.eye(4, dtype=np.float64)
    matrix[1, 1] = c
    matrix[1, 2] = -s
    matrix[2, 1] = s
    matrix[2, 2] = c
    return matrix


def _rotation_z_matrix(angle: float) -> np.ndarray:
    c, s = float(math.cos(angle)), float(math.sin(angle))
    matrix = np.eye(4, dtype=np.float64)
    matrix[0, 0] = c
    matrix[0, 1] = -s
    matrix[1, 0] = s
    matrix[1, 1] = c
    return matrix


def _upright_orbit_view_matrix(scene_center: np.ndarray, azimuth: float, elevation: float) -> np.ndarray:
    # MMD/Source characters are upright on Z. Rotate azimuth around Z so left/right
    # drag orbits around the head-to-feet axis instead of tilting around Y.
    return _rotation_x_matrix(-math.pi * 0.5 + elevation) @ _rotation_z_matrix(azimuth) @ _translation_matrix(-scene_center)


def _scalar_float(value: object, default: float = 0.0) -> float:
    try:
        array = np.asarray(value, dtype=np.float64)
        if array.size:
            return float(array.reshape(-1)[0])
    except Exception:
        pass
    try:
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return float(default)


class StaticModelPreviewWidget(QOpenGLWidget):
    statsChanged = QtCore.Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.model: StaticPreviewModel | None = None
        self._scene_center = np.zeros(3, dtype=np.float64)
        self._scene_extent = 1.0
        self._scene_mins = np.zeros(3, dtype=np.float64)
        self._scene_maxs = np.ones(3, dtype=np.float64)
        self._view_yaw = math.pi
        self._view_pitch = 0.0
        self._view_zoom = 1.0
        self._view_pan = QtCore.QPointF(0.0, 0.0)
        self._last_mouse_pos: QtCore.QPoint | None = None
        self._show_bones = True
        self._show_bone_names = False
        self._show_wireframe = False
        self._hide_missing_texture_materials = False
        self._texture_ids: dict[Path, int] = {}
        self._gl_ready = False
        self._gl_error = ""
        self._vertex_data: np.ndarray | None = None
        self.setMinimumSize(520, 340)
        self.setMouseTracking(True)

    def load_model(self, model_path: Path) -> StaticPreviewModel:
        self.model = load_static_preview_model(model_path)
        self._prepare_scene()
        self.reset_front_view()
        self._gl_ready = False
        self._gl_error = ""
        self.update()
        self._emit_stats()
        return self.model

    def clear_model(self) -> None:
        self.model = None
        self._gl_ready = False
        self._gl_error = ""
        self.update()
        self._emit_stats()

    def set_bones_visible(self, visible: bool) -> None:
        self._show_bones = bool(visible)
        self.update()

    def set_bone_names_visible(self, visible: bool) -> None:
        self._show_bone_names = bool(visible)
        self.update()

    def set_wireframe_visible(self, visible: bool) -> None:
        self._show_wireframe = bool(visible)
        self.update()

    def set_hide_missing_texture_materials(self, hidden: bool) -> None:
        next_value = bool(hidden)
        if next_value == self._hide_missing_texture_materials:
            return
        self._hide_missing_texture_materials = next_value
        self.update()
        self._emit_stats()

    def reset_front_view(self, *_args: object) -> None:
        self._view_yaw = math.pi
        self._view_pitch = 0.0
        self._view_zoom = 1.0
        self._view_pan = QtCore.QPointF(0.0, 0.0)
        self.update()

    def _prepare_scene(self) -> None:
        if not self.model or len(self.model.positions) == 0:
            return
        positions = self.model.positions.astype(np.float64)
        self._scene_mins = positions.min(axis=0)
        self._scene_maxs = positions.max(axis=0)
        self._scene_center = (self._scene_mins + self._scene_maxs) * 0.5
        self._scene_extent = max(1.0, float(np.max(self._scene_maxs - self._scene_mins)))
        self._vertex_data = np.zeros((len(self.model.positions), 8), dtype=np.float32)
        self._vertex_data[:, 0:3] = self.model.positions
        self._vertex_data[:, 3:6] = self.model.normals
        self._vertex_data[:, 6:8] = self.model.uvs

    def initializeGL(self) -> None:
        if GL:
            GL.glClearColor(0.08, 0.09, 0.10, 1.0)
            GL.glEnable(GL.GL_DEPTH_TEST)
            GL.glDisable(GL.GL_CULL_FACE)

    def paintGL(self) -> None:
        if GL:
            try:
                GL.glViewport(0, 0, *self._gl_viewport_size())
                GL.glClearColor(0.08, 0.09, 0.10, 1.0)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
                if self.model:
                    self._draw_mesh_gl()
            except Exception as exc:
                self._gl_error = str(exc)

        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            if not self.model:
                painter.fillRect(self.rect(), QtGui.QColor(22, 24, 27))
                painter.setPen(QtGui.QColor(230, 230, 230))
                painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "Select a PMX model to preview.")
            elif not GL:
                painter.fillRect(self.rect(), QtGui.QColor(22, 24, 27))
                painter.setPen(QtGui.QColor(255, 210, 120))
                painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "PyOpenGL is required for mesh preview rendering.")
            elif self._gl_error:
                painter.fillRect(self.rect(), QtGui.QColor(22, 24, 27))
                painter.setPen(QtGui.QColor(255, 210, 120))
                painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "OpenGL preview is unavailable in this context.")
            try:
                if self.model and (self._show_bones or self._show_bone_names):
                    self._draw_skeleton(painter)
                self._draw_overlay(painter)
            except Exception as exc:
                self._gl_error = str(exc)
                painter.setPen(QtGui.QColor(255, 210, 120))
                painter.drawText(12, max(64, self.height() - 18), "Preview overlay error; see status text.")
        finally:
            painter.end()
        self._emit_stats()

    def _gl_viewport_size(self) -> tuple[int, int]:
        dpr = max(1.0, float(self.devicePixelRatioF()))
        return max(1, int(round(self.width() * dpr))), max(1, int(round(self.height() * dpr)))

    def _ensure_textures(self) -> None:
        if self._gl_ready or not GL or not self.model:
            return
        self._texture_ids = {}
        for material in self.model.materials:
            if material.texture_path and material.texture_path.exists() and material.texture_path not in self._texture_ids:
                texture_id = self._create_texture(material.texture_path)
                if texture_id:
                    self._texture_ids[material.texture_path] = texture_id
        self._gl_ready = True

    def _create_texture(self, path: Path) -> int:
        image = QtGui.QImage(str(path))
        if image.isNull() or not GL:
            return 0
        image = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
        try:
            texture_id = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT)
            bits = image.constBits()
            data = bits.tobytes() if hasattr(bits, "tobytes") else bytes(bits)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, image.width(), image.height(), 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, data)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            return int(texture_id)
        except Exception:
            return 0

    def _draw_mesh_gl(self) -> None:
        if not GL or not self.model or self._vertex_data is None:
            return
        self._ensure_textures()
        projection, view = self._projection_view_matrices()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadMatrixf(np.ascontiguousarray(projection.T, dtype=np.float32))
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadMatrixf(np.ascontiguousarray(view.T, dtype=np.float32))

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glTexEnvi(GL.GL_TEXTURE_ENV, GL.GL_TEXTURE_ENV_MODE, GL.GL_MODULATE)
        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE if self._show_wireframe else GL.GL_FILL)

        stride = 8 * 4
        base_ptr = int(self._vertex_data.ctypes.data)
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glVertexPointer(3, GL.GL_FLOAT, stride, ctypes.c_void_p(base_ptr))
        GL.glEnableClientState(GL.GL_NORMAL_ARRAY)
        GL.glNormalPointer(GL.GL_FLOAT, stride, ctypes.c_void_p(base_ptr + 12))
        GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glTexCoordPointer(2, GL.GL_FLOAT, stride, ctypes.c_void_p(base_ptr + 24))

        for material in self.model.materials:
            if self._hide_missing_texture_materials and material.missing_texture:
                continue
            if material.index_count <= 0 or material.index_start >= len(self.model.indices):
                continue
            color = material.diffuse
            GL.glColor4f(float(color[0]), float(color[1]), float(color[2]), max(0.25, float(color[3])))
            texture_id = self._texture_ids.get(material.texture_path) if material.texture_path else None
            GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id or 0)
            start = int(material.index_start)
            stop = min(len(self.model.indices), start + int(material.index_count))
            GL.glDrawElements(GL.GL_TRIANGLES, stop - start, GL.GL_UNSIGNED_INT, self.model.indices[start:stop])

        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)
        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glDisableClientState(GL.GL_NORMAL_ARRAY)
        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    def _projection_view_matrices(self) -> tuple[np.ndarray, np.ndarray]:
        width = max(1, self.width())
        height = max(1, self.height())
        aspect = width / height
        scene_extent = max(1.0, _scalar_float(self._scene_extent, 1.0))
        view_zoom = max(0.001, _scalar_float(self._view_zoom, 1.0))
        view_yaw = _scalar_float(self._view_yaw, math.pi)
        view_pitch = _scalar_float(self._view_pitch, 0.0)
        scene_center = np.asarray(self._scene_center, dtype=np.float64).reshape(-1)
        if scene_center.size < 3:
            scene_center = np.zeros(3, dtype=np.float64)
        else:
            scene_center = scene_center[:3]

        view_height = scene_extent / max(0.001, view_zoom * 0.78)
        view_width = view_height * aspect
        pixel_scale = min(width, height) * 0.78 * view_zoom / max(0.001, scene_extent)
        pan_x = -float(self._view_pan.x()) / max(0.001, pixel_scale)
        pan_y = float(self._view_pan.y()) / max(0.001, pixel_scale)
        left = -view_width * 0.5 + pan_x
        right = view_width * 0.5 + pan_x
        bottom = -view_height * 0.5 + pan_y
        top = view_height * 0.5 + pan_y
        near = -scene_extent * 4.0
        far = scene_extent * 4.0
        projection = np.array(
            [
                [2.0 / (right - left), 0.0, 0.0, -(right + left) / (right - left)],
                [0.0, 2.0 / (top - bottom), 0.0, -(top + bottom) / (top - bottom)],
                [0.0, 0.0, -2.0 / (far - near), -(far + near) / (far - near)],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        cy, sy = float(math.cos(view_yaw)), float(math.sin(view_yaw))
        cp, sp = float(math.cos(view_pitch)), float(math.sin(view_pitch))
        yaw = np.eye(4, dtype=np.float64)
        yaw[0, 0] = cy
        yaw[0, 2] = sy
        yaw[2, 0] = -sy
        yaw[2, 2] = cy
        pitch = np.eye(4, dtype=np.float64)
        pitch[1, 1] = cp
        pitch[1, 2] = -sp
        pitch[2, 1] = sp
        pitch[2, 2] = cp
        view = pitch @ yaw @ _translation_matrix(-scene_center)
        return projection, view

    def _project_np(self, positions: np.ndarray) -> list[QtCore.QPointF]:
        if len(positions) == 0:
            return []
        projection, view = self._projection_view_matrices()
        homogeneous = np.concatenate([positions[:, :3], np.ones((len(positions), 1), dtype=np.float64)], axis=1)
        clip = ((projection @ view) @ homogeneous.T).T
        safe_w = np.where(np.abs(clip[:, 3]) <= 1e-8, 1.0, clip[:, 3])
        ndc = clip[:, :3] / safe_w[:, None]
        x = self.width() * (0.5 + ndc[:, 0] * 0.5)
        y = self.height() * (0.5 - ndc[:, 1] * 0.5)
        return [QtCore.QPointF(float(px), float(py)) for px, py in zip(x, y)]

    def _draw_skeleton(self, painter: QtGui.QPainter) -> None:
        if not self.model or not self.model.bones:
            return
        positions = np.array([bone.position for bone in self.model.bones], dtype=np.float64)
        points = self._project_np(positions)
        if self._show_bones:
            painter.setPen(QtGui.QPen(QtGui.QColor(80, 170, 255, 220), BONE_LINE_WIDTH))
            for index, bone in enumerate(self.model.bones):
                if 0 <= bone.parent < len(points):
                    painter.drawLine(points[bone.parent], points[index])
            painter.setBrush(QtGui.QColor(245, 245, 245, 180))
            painter.setPen(QtGui.QPen(QtGui.QColor(20, 20, 20, 180), 1.4))
            stride = max(1, len(points) // 90)
            for point in points[::stride]:
                painter.drawEllipse(point, BONE_POINT_RADIUS, BONE_POINT_RADIUS)
        if self._show_bone_names:
            old_font = painter.font()
            font = QtGui.QFont(old_font)
            font.setPointSize(max(7, old_font.pointSize() - 1))
            painter.setFont(font)
            painter.setPen(QtGui.QColor(235, 235, 235, 220))
            visible_rect = self.rect().adjusted(-80, -20, 160, 40)
            stride = max(1, len(points) // 140)
            for index in range(0, len(points), stride):
                point = points[index]
                if visible_rect.contains(point.toPoint()):
                    bone = self.model.bones[index]
                    painter.drawText(QtCore.QPointF(point.x() + 5.0, point.y() - 3.0), bone.name or bone.english_name or str(index))
            painter.setFont(old_font)

    def _draw_overlay(self, painter: QtGui.QPainter) -> None:
        if not self.model:
            return
        backend = "OpenGL" if GL and not self._gl_error else ("OpenGL error" if self._gl_error else "No OpenGL")
        textured = sum(1 for material in self.model.materials if material.texture_path)
        text = (
            f"{self.model.name or self.model.path.stem} | "
            f"{self.model.vertex_count:,} verts | {self.model.triangle_count:,} tris | "
            f"{len(self.model.bones):,} bones | {self.model.morph_count:,} morphs | "
            f"{len(self.model.materials):,} materials | {textured}/{self.model.texture_count} textures | {backend}"
        )
        painter.setPen(QtGui.QColor(235, 235, 235))
        painter.drawText(12, 22, text)
        if self.model.warnings:
            painter.setPen(QtGui.QColor(255, 210, 120))
            painter.drawText(12, 44, self.model.warnings[0])

    def _emit_stats(self) -> None:
        if not self.model:
            self.statsChanged.emit("Preview idle")
            return
        backend = "OpenGL" if GL and not self._gl_error else ("OpenGL error: " + self._gl_error if self._gl_error else "PyOpenGL unavailable")
        self.statsChanged.emit(
            f"{backend} | {self.model.vertex_count:,} verts | {self.model.triangle_count:,} tris | "
            f"{len(self.model.bones):,} bones | {self.model.morph_count:,} morphs | warnings {len(self.model.warnings)}"
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        self._last_mouse_pos = event.position().toPoint()
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        elif event.button() in (QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.MiddleButton):
            self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._last_mouse_pos is None:
            self._last_mouse_pos = event.position().toPoint()
            return
        current = event.position().toPoint()
        delta = current - self._last_mouse_pos
        self._last_mouse_pos = current
        buttons = event.buttons()
        if buttons & QtCore.Qt.MouseButton.LeftButton:
            self._view_yaw = _scalar_float(self._view_yaw, math.pi) + float(delta.x()) * 0.008
            self._view_pitch = max(-1.45, min(1.45, _scalar_float(self._view_pitch, 0.0) + float(delta.y()) * 0.008))
            self.update()
        elif buttons & (QtCore.Qt.MouseButton.RightButton | QtCore.Qt.MouseButton.MiddleButton):
            self._view_pan += QtCore.QPointF(delta.x(), delta.y())
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if not event.buttons():
            self._last_mouse_pos = None
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.reset_front_view()
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta:
            self._view_zoom = max(0.2, min(8.0, _scalar_float(self._view_zoom, 1.0) * math.pow(1.0015, float(delta))))
            self.update()
        event.accept()


class SkeletonPlanPreviewWidget(QtWidgets.QWidget):
    """Interactive 3D-ish skeleton preview for step-3 spine repair plans."""

    statsChanged = QtCore.Signal(str)
    boneContextActionRequested = QtCore.Signal(str, str)
    DEFAULT_FRONT_YAW = 0.0
    DEFAULT_FRONT_PITCH = 0.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.analysis: dict[str, object] | None = None
        self.plan: dict[str, object] | None = None
        self._bones: dict[str, dict[str, object]] = {}
        self._scene_center = np.zeros(3, dtype=np.float64)
        self._scene_extent = 1.0
        self._default_yaw = self.DEFAULT_FRONT_YAW
        self._default_pitch = self.DEFAULT_FRONT_PITCH
        self._view_yaw = self._default_yaw
        self._view_pitch = self._default_pitch
        self._view_zoom = 1.0
        self._view_pan = QtCore.QPointF(0.0, 0.0)
        self._using_default_view = True
        self._last_mouse_pos: QtCore.QPoint | None = None
        self._hovered_bone: str | None = None
        self._hover_pos = QtCore.QPointF(0.0, 0.0)
        self._show_model = True
        self._show_bone_names = False
        self.setMinimumSize(520, 340)
        self.setMouseTracking(True)

    def clear(self) -> None:
        self.analysis = None
        self.plan = None
        self._bones = {}
        self._default_yaw = self.DEFAULT_FRONT_YAW
        self._default_pitch = self.DEFAULT_FRONT_PITCH
        self._view_yaw = self._default_yaw
        self._view_pitch = self._default_pitch
        self._view_zoom = 1.0
        self._view_pan = QtCore.QPointF(0.0, 0.0)
        self._using_default_view = True
        self._hovered_bone = None
        self.update()
        self.statsChanged.emit("Skeleton preview idle")

    def set_model_visible(self, visible: bool) -> None:
        self._show_model = bool(visible)
        self.update()

    def set_bone_names_visible(self, visible: bool) -> None:
        self._show_bone_names = bool(visible)
        self.update()

    def reset_front_view(self, *_args: object) -> None:
        self._view_yaw = self._default_yaw
        self._view_pitch = self._default_pitch
        self._view_zoom = 1.0
        self._view_pan = QtCore.QPointF(0.0, 0.0)
        self._using_default_view = True
        self.update()

    def set_analysis(self, analysis: dict[str, object] | None, plan: dict[str, object] | None) -> None:
        self.analysis = analysis
        self.plan = plan
        self._bones = {}
        if analysis:
            for raw in analysis.get("bones", []):
                if isinstance(raw, dict) and raw.get("name"):
                    self._bones[str(raw["name"])] = raw
        self._prepare_scene()
        self._update_default_front_view_from_landmarks()
        if self._using_default_view:
            self._view_yaw = self._default_yaw
            self._view_pitch = self._default_pitch
        self.update()
        count = len(self._bones)
        validation = self._validation()
        status = "valid" if validation.get("ok") else f"{len(validation.get('errors', []))} validation error(s)"
        if self._is_merge_plan():
            estimated = self.plan.get("estimated_final_bone_count") if self.plan else None
            limit = self.plan.get("bone_limit") if self.plan else None
            self.statsChanged.emit(f"Bone merge preview | {count:,} bones | estimated {estimated} / limit {limit} | {status}")
        else:
            self.statsChanged.emit(f"Spine preview | {count:,} bones | {status}")

    def _is_merge_plan(self) -> bool:
        return bool(self.plan and str(self.plan.get("kind") or "") == "sort_bones")

    def _prepare_scene(self) -> None:
        points: list[np.ndarray] = []
        for bone in self._bones.values():
            for key in ("head", "tail"):
                value = bone.get(key)
                if isinstance(value, list) and len(value) >= 3:
                    points.append(np.array(value[:3], dtype=np.float64))
        preview = self._model_preview()
        vertices = preview.get("vertices") if isinstance(preview, dict) else None
        if isinstance(vertices, list):
            for raw in vertices:
                if isinstance(raw, list) and len(raw) >= 3:
                    points.append(np.array(raw[:3], dtype=np.float64))
        for entry in self._target_entries().values():
            position = entry.get("position") if isinstance(entry, dict) else None
            if isinstance(position, dict):
                for key in ("head", "tail"):
                    value = position.get(key)
                    if isinstance(value, list) and len(value) >= 3:
                        points.append(np.array(value[:3], dtype=np.float64))
        if not points:
            self._scene_center = np.zeros(3, dtype=np.float64)
            self._scene_extent = 1.0
            return
        array = np.vstack(points)
        mins = array.min(axis=0)
        maxs = array.max(axis=0)
        self._scene_center = (mins + maxs) * 0.5
        self._scene_extent = max(0.2, float(np.max(maxs - mins)))

    def _bone_head_vector(self, names: list[str]) -> np.ndarray | None:
        for name in names:
            bone = self._bones.get(name)
            if not bone:
                continue
            head = bone.get("head")
            if isinstance(head, list) and len(head) >= 3:
                return np.array(head[:3], dtype=np.float64)
        return None

    def _update_default_front_view_from_landmarks(self) -> None:
        self._default_yaw = self.DEFAULT_FRONT_YAW
        self._default_pitch = self.DEFAULT_FRONT_PITCH
        pelvis = self._bone_head_vector(["ValveBiped.Bip01_Pelvis"])
        left_arm = self._bone_head_vector(
            [
                "ValveBiped.Bip01_L_UpperArm",
                "ValveBiped.Bip01_L_Clavicle",
                "ValveBiped.Bip01_L_Forearm",
                "ValveBiped.Bip01_L_Hand",
            ]
        )
        right_arm = self._bone_head_vector(
            [
                "ValveBiped.Bip01_R_UpperArm",
                "ValveBiped.Bip01_R_Clavicle",
                "ValveBiped.Bip01_R_Forearm",
                "ValveBiped.Bip01_R_Hand",
            ]
        )
        if pelvis is None or left_arm is None or right_arm is None:
            return
        left_dx = float(left_arm[0] - pelvis[0])
        right_dx = float(right_arm[0] - pelvis[0])
        # Source convention places the model's left side on positive X and right side on negative X.
        # If a blend has that axis reversed, use the opposite upright front view.
        if left_dx < right_dx:
            self._default_yaw = math.pi
            self._default_pitch = 0.0

    def _target_entries(self) -> dict[str, dict[str, object]]:
        if not self.plan or not isinstance(self.plan.get("targets"), dict):
            return {}
        return {str(key): value for key, value in self.plan["targets"].items() if isinstance(value, dict)}

    def _validation(self) -> dict[str, object]:
        if not self.analysis:
            return {"ok": False, "errors": [], "warnings": []}
        current = self.analysis.get("current_validation")
        if isinstance(current, dict):
            return current
        return {"ok": False, "errors": [], "warnings": []}

    def _model_preview(self) -> dict[str, object]:
        if not self.analysis:
            return {}
        preview = self.analysis.get("model_preview")
        return preview if isinstance(preview, dict) else {}

    def _vector_for_target(self, target: str, key: str = "head") -> np.ndarray | None:
        entry = self._target_entries().get(target)
        if not entry:
            return None
        if str(entry.get("action")) == "add":
            position = entry.get("position")
            if isinstance(position, dict):
                value = position.get(key)
                if isinstance(value, list) and len(value) >= 3:
                    return np.array(value[:3], dtype=np.float64)
        source = entry.get("source")
        if source and str(source) in self._bones:
            value = self._bones[str(source)].get(key)
            if isinstance(value, list) and len(value) >= 3:
                return np.array(value[:3], dtype=np.float64)
        return None

    def _projection_view_matrices(self) -> tuple[np.ndarray, np.ndarray]:
        width = max(1, self.width())
        height = max(1, self.height())
        aspect = width / height
        scene_extent = max(0.2, _scalar_float(self._scene_extent, 1.0))
        view_zoom = max(0.001, _scalar_float(self._view_zoom, 1.0))
        view_height = scene_extent / max(0.001, view_zoom * 0.78)
        view_width = view_height * aspect
        pixel_scale = min(width, height) * 0.78 * view_zoom / max(0.001, scene_extent)
        pan_x = -float(self._view_pan.x()) / max(0.001, pixel_scale)
        pan_y = float(self._view_pan.y()) / max(0.001, pixel_scale)
        left = -view_width * 0.5 + pan_x
        right = view_width * 0.5 + pan_x
        bottom = -view_height * 0.5 + pan_y
        top = view_height * 0.5 + pan_y
        near = -scene_extent * 4.0
        far = scene_extent * 4.0
        projection = np.array(
            [
                [2.0 / (right - left), 0.0, 0.0, -(right + left) / (right - left)],
                [0.0, 2.0 / (top - bottom), 0.0, -(top + bottom) / (top - bottom)],
                [0.0, 0.0, -2.0 / (far - near), -(far + near) / (far - near)],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        yaw_angle = _scalar_float(self._view_yaw, self._default_yaw)
        pitch_angle = _scalar_float(self._view_pitch, self._default_pitch)
        return projection, _upright_orbit_view_matrix(self._scene_center, yaw_angle, pitch_angle)

    def _project_np(self, positions: np.ndarray) -> list[QtCore.QPointF]:
        if len(positions) == 0:
            return []
        projection, view = self._projection_view_matrices()
        homogeneous = np.concatenate([positions[:, :3], np.ones((len(positions), 1), dtype=np.float64)], axis=1)
        clip = ((projection @ view) @ homogeneous.T).T
        safe_w = np.where(np.abs(clip[:, 3]) <= 1e-8, 1.0, clip[:, 3])
        ndc = clip[:, :3] / safe_w[:, None]
        x = self.width() * (0.5 + ndc[:, 0] * 0.5)
        y = self.height() * (0.5 - ndc[:, 1] * 0.5)
        return [QtCore.QPointF(float(px), float(py)) for px, py in zip(x, y)]

    def _project_one(self, vector: np.ndarray | None) -> QtCore.QPointF | None:
        if vector is None:
            return None
        return self._project_np(vector.reshape(1, 3))[0]

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QtGui.QColor(22, 24, 27))
            if not self._bones:
                painter.setPen(QtGui.QColor(230, 230, 230))
                painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "Analyze a blend to preview the skeleton plan.")
                return
            if self._show_model:
                self._draw_model_preview(painter)
            self._draw_all_bones(painter)
            self._draw_side_landmarks(painter)
            if self._is_merge_plan():
                self._draw_merge_plan(painter)
            else:
                self._draw_target_chain(painter)
            if self._show_bone_names:
                self._draw_bone_names(painter)
            self._draw_hovered_bone(painter)
            self._draw_overlay(painter)
        finally:
            painter.end()

    def _draw_model_preview(self, painter: QtGui.QPainter) -> None:
        preview = self._model_preview()
        vertices = preview.get("vertices")
        if not isinstance(vertices, list) or not vertices:
            return
        vectors: list[np.ndarray] = []
        for raw in vertices:
            if isinstance(raw, list) and len(raw) >= 3:
                vectors.append(np.array(raw[:3], dtype=np.float64))
        if not vectors:
            return
        points = self._project_np(np.vstack(vectors))
        edges = preview.get("edges")
        painter.setPen(QtGui.QPen(QtGui.QColor(160, 170, 185, 38), 1))
        if isinstance(edges, list):
            for raw_edge in edges:
                if not isinstance(raw_edge, list) or len(raw_edge) < 2:
                    continue
                a = int(raw_edge[0])
                b = int(raw_edge[1])
                if 0 <= a < len(points) and 0 <= b < len(points):
                    painter.drawLine(points[a], points[b])
        painter.setPen(QtGui.QPen(QtGui.QColor(178, 190, 205, 55), 1))
        for point in points[:: max(1, len(points) // 3500)]:
            painter.drawPoint(point)

    def _draw_all_bones(self, painter: QtGui.QPainter) -> None:
        points: dict[str, QtCore.QPointF] = {}
        names: list[str] = []
        vectors: list[np.ndarray] = []
        for name, bone in self._bones.items():
            head = bone.get("head")
            if isinstance(head, list) and len(head) >= 3:
                names.append(name)
                vectors.append(np.array(head[:3], dtype=np.float64))
        projected = self._project_np(np.vstack(vectors)) if vectors else []
        points.update(zip(names, projected))
        painter.setPen(QtGui.QPen(QtGui.QColor(130, 142, 156, 150), BONE_LINE_WIDTH))
        for name, bone in self._bones.items():
            parent = bone.get("parent")
            if parent in points and name in points:
                painter.drawLine(points[str(parent)], points[name])

    def _draw_bone_names(self, painter: QtGui.QPainter) -> None:
        points = self._projected_bone_heads()
        painter.setFont(QtGui.QFont(self.font().family(), 7))
        painter.setPen(QtGui.QColor(220, 225, 232, 170))
        for name, point in points.items():
            painter.drawText(QtCore.QPointF(point.x() + 4.0, point.y() - 3.0), name)

    def _draw_side_landmarks(self, painter: QtGui.QPainter) -> None:
        colors = {
            "ValveBiped.Bip01_R_Clavicle": QtGui.QColor(255, 132, 92),
            "ValveBiped.Bip01_R_UpperArm": QtGui.QColor(255, 132, 92),
            "ValveBiped.Bip01_R_Thigh": QtGui.QColor(255, 132, 92),
            "ValveBiped.Bip01_L_Clavicle": QtGui.QColor(88, 196, 140),
            "ValveBiped.Bip01_L_UpperArm": QtGui.QColor(88, 196, 140),
            "ValveBiped.Bip01_L_Thigh": QtGui.QColor(88, 196, 140),
        }
        for name, color in colors.items():
            bone = self._bones.get(name)
            if not bone:
                continue
            head = bone.get("head")
            if not isinstance(head, list) or len(head) < 3:
                continue
            point = self._project_one(np.array(head[:3], dtype=np.float64))
            if point is None:
                continue
            painter.setBrush(color)
            painter.setPen(QtGui.QPen(QtGui.QColor(15, 15, 15), 1.4))
            painter.drawEllipse(point, BONE_POINT_RADIUS + 1.4, BONE_POINT_RADIUS + 1.4)

    def _draw_target_chain(self, painter: QtGui.QPainter) -> None:
        chain = ["ValveBiped.Bip01_Pelvis", "ValveBiped.Bip01_Spine", "ValveBiped.Bip01_Spine1", "ValveBiped.Bip01_Spine2", "ValveBiped.Bip01_Spine4"]
        colors = [QtGui.QColor(79, 192, 255), QtGui.QColor(88, 166, 255), QtGui.QColor(163, 113, 247), QtGui.QColor(255, 203, 107)]
        points = [self._project_one(self._vector_for_target(target, "head")) for target in chain]
        for index in range(len(points) - 1):
            if points[index] is None or points[index + 1] is None:
                continue
            painter.setPen(QtGui.QPen(colors[min(index, len(colors) - 1)], BONE_HIGHLIGHT_LINE_WIDTH - 1.0))
            painter.drawLine(points[index], points[index + 1])
        painter.setPen(QtGui.QPen(QtGui.QColor(245, 245, 245), 1.4))
        for target, point in zip(chain, points):
            if point is None:
                continue
            entry = self._target_entries().get(target, {})
            action = str(entry.get("action") or "")
            painter.setBrush(QtGui.QColor(255, 210, 120) if action == "add" else QtGui.QColor(235, 235, 235))
            painter.drawEllipse(point, BONE_POINT_RADIUS + 1.8, BONE_POINT_RADIUS + 1.8)
            painter.drawText(QtCore.QPointF(point.x() + 6.0, point.y() - 5.0), target.rsplit("_", 1)[-1])
        for target, entry in self._target_entries().items():
            if str(entry.get("action")) != "add":
                continue
            head = self._project_one(self._vector_for_target(target, "head"))
            tail = self._project_one(self._vector_for_target(target, "tail"))
            if head is None or tail is None:
                continue
            pen = QtGui.QPen(QtGui.QColor(255, 210, 120), BONE_LINE_WIDTH + 0.8)
            pen.setStyle(QtCore.Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(head, tail)

    def _projected_bone_heads(self) -> dict[str, QtCore.QPointF]:
        names: list[str] = []
        vectors: list[np.ndarray] = []
        for name, bone in self._bones.items():
            head = bone.get("head")
            if isinstance(head, list) and len(head) >= 3:
                names.append(name)
                vectors.append(np.array(head[:3], dtype=np.float64))
        projected = self._project_np(np.vstack(vectors)) if vectors else []
        return dict(zip(names, projected))

    def _draw_merge_plan(self, painter: QtGui.QPainter) -> None:
        if not self.plan:
            return
        points = self._projected_bone_heads()
        protected = set(str(name) for name in self.plan.get("protected_bones", []) if name) if isinstance(self.plan.get("protected_bones"), list) else set()
        operations = self.plan.get("operations", [])
        enabled_ops = [entry for entry in operations if isinstance(entry, dict) and entry.get("enabled", True)] if isinstance(operations, list) else []
        disabled_ops = [entry for entry in operations if isinstance(entry, dict) and not entry.get("enabled", True)] if isinstance(operations, list) else []

        for entry in disabled_ops[:120]:
            source = str(entry.get("source") or "")
            target = str(entry.get("target") or "")
            source_point = points.get(source)
            target_point = points.get(target)
            if source_point is None or target_point is None:
                continue
            pen = QtGui.QPen(QtGui.QColor(145, 150, 160, 120), BONE_LINE_WIDTH)
            pen.setStyle(QtCore.Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(source_point, target_point)
            painter.setPen(QtGui.QPen(QtGui.QColor(145, 150, 160, 170), 1.6))
            painter.drawLine(QtCore.QPointF(source_point.x() - 3, source_point.y() - 3), QtCore.QPointF(source_point.x() + 3, source_point.y() + 3))
            painter.drawLine(QtCore.QPointF(source_point.x() - 3, source_point.y() + 3), QtCore.QPointF(source_point.x() + 3, source_point.y() - 3))

        painter.setPen(QtGui.QPen(QtGui.QColor(87, 171, 90, 230), BONE_LINE_WIDTH + 0.8))
        painter.setBrush(QtGui.QColor(87, 171, 90, 190))
        for name in protected:
            point = points.get(name)
            if point is not None:
                painter.drawEllipse(point, BONE_POINT_RADIUS + 0.8, BONE_POINT_RADIUS + 0.8)

        for entry in enabled_ops[:140]:
            source = str(entry.get("source") or "")
            target = str(entry.get("target") or "")
            source_point = points.get(source)
            target_point = points.get(target)
            if source_point is None or target_point is None:
                continue
            round_index = int(entry.get("round", 0) or 0)
            color = QtGui.QColor(255, 158, 77, 180) if round_index else QtGui.QColor(255, 220, 112, 210)
            pen = QtGui.QPen(color, BONE_LINE_WIDTH + 0.8)
            if round_index == 0:
                pen.setStyle(QtCore.Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(source_point, target_point)
            painter.setBrush(QtGui.QColor(248, 81, 73, 220))
            painter.setPen(QtGui.QPen(QtGui.QColor(20, 20, 20), 1.4))
            painter.drawEllipse(source_point, BONE_POINT_RADIUS + 0.8, BONE_POINT_RADIUS + 0.8)
            painter.setBrush(QtGui.QColor(163, 113, 247, 220))
            painter.drawEllipse(target_point, BONE_POINT_RADIUS + 1.2, BONE_POINT_RADIUS + 1.2)

        if len(enabled_ops) > 140:
            painter.setPen(QtGui.QColor(255, 210, 120))
            painter.drawText(12, 66, f"Preview limited to first 140 enabled merge lines out of {len(enabled_ops):,}.")

    def _draw_overlay(self, painter: QtGui.QPainter) -> None:
        validation = self._validation()
        errors = validation.get("errors", []) if isinstance(validation.get("errors"), list) else []
        warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
        painter.setPen(QtGui.QColor(235, 235, 235))
        if self._is_merge_plan() and self.plan:
            operations = self.plan.get("operations", [])
            enabled = sum(1 for entry in operations if isinstance(entry, dict) and entry.get("enabled", True)) if isinstance(operations, list) else 0
            disabled = sum(1 for entry in operations if isinstance(entry, dict) and not entry.get("enabled", True)) if isinstance(operations, list) else 0
            estimated = self.plan.get("estimated_final_bone_count", "?")
            limit = self.plan.get("bone_limit", "?")
            painter.drawText(12, 22, f"{len(self._bones):,} bones | enabled merges {enabled:,} | disabled {disabled:,} | estimated {estimated} / {limit} | errors {len(errors)} | warnings {len(warnings)}")
        else:
            painter.drawText(12, 22, f"{len(self._bones):,} bones | current validation errors {len(errors)} | warnings {len(warnings)}")
        if self.plan and isinstance(self.plan.get("warnings"), list) and self.plan["warnings"]:
            painter.setPen(QtGui.QColor(255, 210, 120))
            painter.drawText(12, 44, str(self.plan["warnings"][0]))
        if self._hovered_bone:
            painter.setPen(QtGui.QColor(235, 235, 235))
            painter.drawText(12, self.height() - 14, f"Hovered bone: {self._hovered_bone}")

    def _draw_hovered_bone(self, painter: QtGui.QPainter) -> None:
        if not self._hovered_bone or self._hovered_bone not in self._bones:
            return
        points = self._projected_bone_heads()
        point = points.get(self._hovered_bone)
        if point is None:
            return
        parent = self._bones[self._hovered_bone].get("parent")
        parent_point = points.get(str(parent)) if parent else None
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 230, 120), BONE_HIGHLIGHT_LINE_WIDTH))
        if parent_point is not None:
            painter.drawLine(parent_point, point)
        painter.setBrush(QtGui.QColor(255, 230, 120))
        painter.setPen(QtGui.QPen(QtGui.QColor(20, 20, 20), 1.6))
        painter.drawEllipse(point, BONE_HIGHLIGHT_POINT_RADIUS, BONE_HIGHLIGHT_POINT_RADIUS)
        text = self._hovered_bone
        metrics = painter.fontMetrics()
        rect = metrics.boundingRect(text).adjusted(-6, -4, 6, 4)
        x = min(max(8.0, self._hover_pos.x() + 12.0), max(8.0, self.width() - rect.width() - 8.0))
        y = min(max(24.0, self._hover_pos.y() - 12.0), max(24.0, self.height() - rect.height() - 8.0))
        label_rect = QtCore.QRectF(x, y - rect.height(), rect.width(), rect.height())
        painter.setBrush(QtGui.QColor(16, 18, 22, 225))
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 230, 120), 1))
        painter.drawRoundedRect(label_rect, 4.0, 4.0)
        painter.setPen(QtGui.QColor(245, 245, 245))
        painter.drawText(label_rect.adjusted(6, 2, -6, -2), QtCore.Qt.AlignmentFlag.AlignVCenter, text)

    @staticmethod
    def _distance_to_segment(point: QtCore.QPointF, start: QtCore.QPointF, end: QtCore.QPointF) -> float:
        px, py = float(point.x()), float(point.y())
        ax, ay = float(start.x()), float(start.y())
        bx, by = float(end.x()), float(end.y())
        dx = bx - ax
        dy = by - ay
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-8:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
        nearest_x = ax + t * dx
        nearest_y = ay + t * dy
        return math.hypot(px - nearest_x, py - nearest_y)

    def _nearest_bone_at(self, position: QtCore.QPointF) -> str | None:
        points = self._projected_bone_heads()
        best_name: str | None = None
        best_distance = 10.0
        for name, point in points.items():
            distance = math.hypot(float(position.x() - point.x()), float(position.y() - point.y()))
            if distance < best_distance:
                best_distance = distance
                best_name = name
        for name, bone in self._bones.items():
            point = points.get(name)
            parent = bone.get("parent")
            parent_point = points.get(str(parent)) if parent else None
            if point is None or parent_point is None:
                continue
            distance = self._distance_to_segment(position, parent_point, point)
            if distance < best_distance:
                best_distance = distance
                best_name = name
        return best_name

    def _update_hovered_bone(self, position: QtCore.QPointF) -> None:
        hovered = self._nearest_bone_at(position)
        moved = abs(float(position.x() - self._hover_pos.x())) > 1.0 or abs(float(position.y() - self._hover_pos.y())) > 1.0
        self._hover_pos = position
        if hovered != self._hovered_bone:
            self._hovered_bone = hovered
            self.setToolTip(hovered or "")
            self.update()
        elif hovered and moved:
            self.update()

    def _protected_plan_sets(self) -> tuple[set[str], set[str], tuple[str, ...]]:
        if not self.plan:
            return set(), set(), ()
        protected = set(str(name) for name in self.plan.get("protected_bones", []) if name) if isinstance(self.plan.get("protected_bones"), list) else set()
        base = set(str(name) for name in self.plan.get("base_protected_bones", []) if name) if isinstance(self.plan.get("base_protected_bones"), list) else set()
        prefixes = tuple(str(prefix) for prefix in self.plan.get("protected_prefixes", []) if prefix) if isinstance(self.plan.get("protected_prefixes"), list) else ()
        return protected, base, prefixes

    def _enabled_operations_touching_bone(self, bone_name: str) -> list[dict[str, object]]:
        if not self.plan:
            return []
        raw = self.plan.get("operations", [])
        if not isinstance(raw, list):
            return []
        return [
            entry
            for entry in raw
            if isinstance(entry, dict)
            and entry.get("enabled", True)
            and (str(entry.get("source") or "") == bone_name or str(entry.get("target") or "") == bone_name)
        ]

    def _show_bone_context_menu(self, global_pos: QtCore.QPoint) -> None:
        bone_name = self._hovered_bone
        if not bone_name:
            return
        menu = QtWidgets.QMenu(self)
        title = menu.addAction(bone_name)
        title.setEnabled(False)
        if self._is_merge_plan():
            protected, base, prefixes = self._protected_plan_sets()
            is_prefix_protected = any(bone_name.startswith(prefix) for prefix in prefixes)
            is_core_protected = bone_name in base or is_prefix_protected
            is_protected = bone_name in protected or is_core_protected
            parent = self._bones.get(bone_name, {}).get("parent")
            if parent and not is_protected:
                action = menu.addAction("Merge to parent")
                action.triggered.connect(lambda _checked=False, b=bone_name: self.boneContextActionRequested.emit("merge_to_parent", b))
            if not is_protected:
                action = menu.addAction("Protect bone")
                action.triggered.connect(lambda _checked=False, b=bone_name: self.boneContextActionRequested.emit("protect", b))
            elif bone_name in protected and not is_core_protected:
                action = menu.addAction("Disable protect bone")
                action.triggered.connect(lambda _checked=False, b=bone_name: self.boneContextActionRequested.emit("unprotect", b))
            touching = self._enabled_operations_touching_bone(bone_name)
            if touching:
                action = menu.addAction("Cancel merge")
                action.triggered.connect(lambda _checked=False, b=bone_name: self.boneContextActionRequested.emit("cancel_merge", b))
        if len(menu.actions()) <= 1:
            no_action = menu.addAction("No editable action for this bone")
            no_action.setEnabled(False)
        menu.exec(global_pos)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            self._update_hovered_bone(event.position())
            if self._hovered_bone:
                self._show_bone_context_menu(event.globalPosition().toPoint())
                event.accept()
                return
        self._last_mouse_pos = event.position().toPoint()
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.buttons() == QtCore.Qt.MouseButton.NoButton:
            self._update_hovered_bone(event.position())
            super().mouseMoveEvent(event)
            return
        if self._last_mouse_pos is None:
            self._last_mouse_pos = event.position().toPoint()
            return
        current = event.position().toPoint()
        delta = current - self._last_mouse_pos
        self._last_mouse_pos = current
        buttons = event.buttons()
        if buttons & QtCore.Qt.MouseButton.LeftButton:
            self._view_yaw = _scalar_float(self._view_yaw, self._default_yaw) + float(delta.x()) * 0.008
            self._view_pitch = max(-math.pi * 0.5 + 0.02, min(math.pi * 0.5 - 0.02, _scalar_float(self._view_pitch, self._default_pitch) + float(delta.y()) * 0.008))
            self._using_default_view = False
            self.update()
        elif buttons & QtCore.Qt.MouseButton.MiddleButton:
            self._view_pan += QtCore.QPointF(delta.x(), delta.y())
            self._using_default_view = False
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if not event.buttons():
            self._last_mouse_pos = None
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.reset_front_view()
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta:
            self._view_zoom = max(0.2, min(8.0, _scalar_float(self._view_zoom, 1.0) * math.pow(1.0015, float(delta))))
            self._using_default_view = False
            self.update()
        event.accept()


class MaterialPreviewWidget(QOpenGLWidget):
    """Material-region preview for step 5 scans."""

    statsChanged = QtCore.Signal(str)

    VIEW_DIRECTIONS: dict[str, tuple[float, float]] = {
        "Front": (0.0, 0.0),
        "Back": (math.pi, 0.0),
        "Right": (-math.pi * 0.5, 0.0),
        "Left": (math.pi * 0.5, 0.0),
        "Top": (0.0, math.pi * 0.5),
        "Bottom": (0.0, -math.pi * 0.5),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scan: dict[str, object] | None = None
        self.plan: dict[str, object] | None = None
        self._materials: dict[str, dict[str, object]] = {}
        self._triangles: list[dict[str, object]] = []
        self._material_positions: dict[str, np.ndarray] = {}
        self._material_uvs: dict[str, np.ndarray] = {}
        self._material_base_vertex_data: dict[str, np.ndarray] = {}
        self._material_vertex_data: dict[str, np.ndarray] = {}
        self._material_flex_deltas: dict[str, dict[str, np.ndarray]] = {}
        self._material_texture_paths: dict[str, Path] = {}
        self._material_texture_ids: dict[str, int] = {}
        self._collision_lines: dict[str, np.ndarray] = {}
        self._collision_colors: dict[str, tuple[float, float, float, float]] = {}
        self._collision_labels: dict[str, str] = {}
        self._hovered_collision_uid = ""
        self._highlighted_collision_uids: set[str] = set()
        self._bone_lines: dict[str, np.ndarray] = {}
        self._bone_labels: dict[str, str] = {}
        self._hovered_bone_uid = ""
        self._highlighted_bone_uids: set[str] = set()
        self._highlighted_uids: set[str] = set()
        self._flex_sources: dict[str, list[tuple[str, float]]] = {}
        self._flex_rest_values: dict[str, float] = {}
        self._flex_scales: dict[str, float] = {}
        self._enabled_flex_uids: set[str] = set()
        self._active_flex_uid = ""
        self._active_flex_value = 1.0
        self._isolated_bodygroup = ""
        self._scene_center = np.zeros(3, dtype=np.float64)
        self._scene_extent = 1.0
        self._view_yaw, self._view_pitch = self.VIEW_DIRECTIONS["Front"]
        self._view_zoom = 1.0
        self._view_pan = QtCore.QPointF(0.0, 0.0)
        self._last_mouse_pos: QtCore.QPoint | None = None
        self._wireframe = False
        self._respect_alpha = False
        self._selected_uid = ""
        self._hovered_uid = ""
        self._gl_error = ""
        self._gl_error_count = 0
        self._hover_update_queued = False
        self._textured_preview_disabled = _truthy_env("MCI_DISABLE_TEXTURED_PREVIEW")
        self._preview_debug_enabled = _truthy_env("MCI_MATERIAL_PREVIEW_DEBUG")
        self._preview_debug_log_path = _preview_debug_log_path()
        self._empty_message = "Scan a blend to preview material regions."
        self._opengl_unavailable_message = "OpenGL material preview is unavailable."
        self._textured_disabled_message = "Textured preview disabled; using solid material colors."
        self.setMinimumSize(520, 340)
        self.setMouseTracking(True)

    def set_i18n_texts(self, texts: dict[str, str]) -> None:
        self._empty_message = str(texts.get("material_empty", self._empty_message) or self._empty_message)
        self._opengl_unavailable_message = str(texts.get("material_opengl_unavailable", self._opengl_unavailable_message) or self._opengl_unavailable_message)
        self._textured_disabled_message = str(texts.get("material_textured_disabled", self._textured_disabled_message) or self._textured_disabled_message)
        self.update()

    def clear(self) -> None:
        self.scan = None
        self.plan = None
        self._materials = {}
        self._triangles = []
        self._material_positions = {}
        self._material_uvs = {}
        self._material_base_vertex_data = {}
        self._material_vertex_data = {}
        self._material_flex_deltas = {}
        self._material_texture_paths = {}
        self._material_texture_ids = {}
        self._collision_lines = {}
        self._collision_colors = {}
        self._collision_labels = {}
        self._hovered_collision_uid = ""
        self._highlighted_collision_uids = set()
        self._bone_lines = {}
        self._bone_labels = {}
        self._hovered_bone_uid = ""
        self._highlighted_bone_uids = set()
        self._highlighted_uids = set()
        self._flex_sources = {}
        self._flex_rest_values = {}
        self._flex_scales = {}
        self._enabled_flex_uids = set()
        self._active_flex_uid = ""
        self._active_flex_value = 1.0
        self._isolated_bodygroup = ""
        self._selected_uid = ""
        self._hovered_uid = ""
        self._gl_error = ""
        self._gl_error_count = 0
        self.reset_view("Front")
        self.update()
        self.statsChanged.emit("Material preview idle")

    def set_material_data(self, scan: dict[str, object] | None, plan: dict[str, object] | None) -> None:
        self.scan = scan
        self.plan = plan
        self._materials = {}
        if plan and isinstance(plan.get("materials"), list):
            for entry in plan["materials"]:
                if isinstance(entry, dict) and entry.get("uid"):
                    self._materials[str(entry["uid"])] = entry
        elif scan and isinstance(scan.get("materials"), list):
            for entry in scan["materials"]:
                if isinstance(entry, dict) and entry.get("uid"):
                    self._materials[str(entry["uid"])] = entry
        self._load_flex_plan(plan)
        preview = scan.get("model_preview") if isinstance(scan, dict) else None
        triangles = preview.get("triangles") if isinstance(preview, dict) else []
        self._triangles = [entry for entry in triangles if isinstance(entry, dict)] if isinstance(triangles, list) else []
        self._material_texture_ids = {}
        self._gl_error = ""
        self._gl_error_count = 0
        self._build_material_arrays()
        self._prepare_scene()
        self.update()
        self._emit_stats()

    def update_material_entry(self, uid: str, **updates: object) -> None:
        uid = str(uid or "")
        if not uid:
            return
        entry = self._materials.get(uid)
        if entry is None:
            return
        entry.update(updates)
        self.update()
        self._emit_stats()

    def set_visible_bodygroups(self, bodygroups: set[str] | list[str] | tuple[str, ...]) -> None:
        enabled = {str(name) for name in bodygroups if str(name)}
        changed = False
        for entry in self._materials.values():
            bodygroup = str(entry.get("bodygroup") or "")
            if not bodygroup:
                continue
            keep = bodygroup in enabled
            if bool(entry.get("keep", True)) != keep:
                entry["keep"] = keep
                changed = True
            if not bool(entry.get("render_when_highlighted", False)):
                entry["render_when_highlighted"] = True
                changed = True
        if changed:
            self.update()
            self._emit_stats()

    def set_model_preview_data(self, model_preview: dict[str, object] | None) -> None:
        if not self.scan:
            self.set_material_data({"materials": [], "material_count": 0, "model_preview": model_preview or {}}, self.plan)
            return
        updated_scan = dict(self.scan)
        updated_scan["model_preview"] = model_preview or {}
        self.scan = updated_scan
        triangles = updated_scan.get("model_preview", {}).get("triangles") if isinstance(updated_scan.get("model_preview"), dict) else []
        self._triangles = [entry for entry in triangles if isinstance(entry, dict)] if isinstance(triangles, list) else []
        self._build_material_arrays()
        self._prepare_scene()
        self.update()
        self._emit_stats()

    def set_collision_overlay(self, collision_preview: dict[str, object] | None) -> None:
        grouped: dict[str, list[list[float]]] = {}
        colors: dict[str, tuple[float, float, float, float]] = {}
        labels: dict[str, str] = {}
        triangles = collision_preview.get("triangles") if isinstance(collision_preview, dict) else []
        if isinstance(triangles, list):
            for index, triangle in enumerate(triangles, start=1):
                if not isinstance(triangle, dict):
                    continue
                raw_points = triangle.get("points")
                if not isinstance(raw_points, list) or len(raw_points) < 3:
                    continue
                points: list[list[float]] = []
                for raw in raw_points[:3]:
                    if isinstance(raw, list) and len(raw) >= 3:
                        points.append([float(raw[0]), float(raw[1]), float(raw[2])])
                if len(points) != 3:
                    continue
                uid = str(triangle.get("uid") or triangle.get("bone") or f"collision_{index:03d}")
                labels[uid] = str(triangle.get("bone") or uid)
                grouped.setdefault(uid, []).extend([points[0], points[1], points[1], points[2], points[2], points[0]])
                raw_color = triangle.get("color")
                if isinstance(raw_color, list) and len(raw_color) >= 3:
                    colors[uid] = (
                        max(0.0, min(1.0, float(raw_color[0]))),
                        max(0.0, min(1.0, float(raw_color[1]))),
                        max(0.0, min(1.0, float(raw_color[2]))),
                        max(0.2, min(1.0, float(raw_color[3]) if len(raw_color) > 3 else 0.82)),
                    )
        self._collision_lines = {
            uid: np.ascontiguousarray(np.asarray(points, dtype=np.float32).reshape((-1, 3)), dtype=np.float32)
            for uid, points in grouped.items()
            if len(points) >= 2
        }
        self._collision_colors = colors
        self._collision_labels = labels
        self._prepare_scene()
        self.update()
        self._emit_stats()

    def set_hovered_collision(self, uid: str) -> None:
        new_uid = str(uid or "")
        if new_uid == self._hovered_collision_uid:
            return
        self._hovered_collision_uid = new_uid
        self.update()

    def set_highlighted_collisions(self, uids: set[str] | list[str] | tuple[str, ...]) -> None:
        next_uids = {str(uid) for uid in uids if uid}
        if next_uids == self._highlighted_collision_uids:
            return
        self._highlighted_collision_uids = next_uids
        self.update()

    def set_bone_overlay(self, bone_preview: dict[str, object] | list[dict[str, object]] | None) -> None:
        bones = bone_preview.get("bones") if isinstance(bone_preview, dict) else bone_preview
        if not isinstance(bones, list):
            bones = []
        positions: dict[str, list[float]] = {}
        parents: dict[str, str] = {}
        for raw in bones:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or raw.get("uid") or "")
            head = raw.get("head")
            if name and isinstance(head, list) and len(head) >= 3:
                positions[name] = [float(head[0]), float(head[1]), float(head[2])]
                parents[name] = str(raw.get("parent") or "")
        lines: dict[str, list[list[float]]] = {}
        labels: dict[str, str] = {}
        for name, head in positions.items():
            parent = parents.get(name, "")
            if parent and parent in positions:
                lines[name] = [positions[parent], head]
                labels[name] = name
        self._bone_lines = {
            uid: np.ascontiguousarray(np.asarray(points, dtype=np.float32).reshape((-1, 3)), dtype=np.float32)
            for uid, points in lines.items()
            if len(points) >= 2
        }
        self._bone_labels = labels
        self._prepare_scene()
        self.update()
        self._emit_stats()

    def set_hovered_bone_overlay(self, uid: str) -> None:
        new_uid = str(uid or "")
        if new_uid == self._hovered_bone_uid:
            return
        self._hovered_bone_uid = new_uid
        self.update()

    def set_highlighted_bone_overlay(self, uids: set[str] | list[str] | tuple[str, ...]) -> None:
        next_uids = {str(uid) for uid in uids if uid}
        if next_uids == self._highlighted_bone_uids:
            return
        self._highlighted_bone_uids = next_uids
        self.update()

    def set_flex_plan(self, plan: dict[str, object] | None) -> None:
        self.plan = plan
        self._load_flex_plan(plan)
        self._refresh_flex_vertex_data()
        self.update()

    def _plan_float(self, value: object, default: float) -> float:
        if value is None or value == "":
            return float(default)
        return float(value)

    def _load_flex_plan(self, plan: dict[str, object] | None) -> None:
        self._flex_sources = {}
        self._flex_rest_values = {}
        self._flex_scales = {}
        self._enabled_flex_uids = set()
        entries = []
        if plan and isinstance(plan.get("flexes"), list):
            entries = [entry for entry in plan["flexes"] if isinstance(entry, dict) and entry.get("uid")]
        by_uid = {str(entry["uid"]): entry for entry in entries}
        for entry in entries:
            uid = str(entry["uid"])
            enabled = bool(entry.get("enabled", True)) and str(entry.get("action") or "keep") != "remove"
            try:
                rest_value = self._plan_float(entry.get("rest_value", 0.0), 0.0)
                max_value = self._plan_float(entry.get("max_amplitude", 1.0), 1.0)
            except Exception:
                rest_value = 0.0
                max_value = 1.0
            self._flex_rest_values[uid] = rest_value
            self._flex_scales[uid] = max_value - rest_value
            if enabled:
                self._enabled_flex_uids.add(uid)
            sources: list[tuple[str, float]] = []
            for source in entry.get("source_flexes", []):
                if not isinstance(source, dict) or not source.get("uid"):
                    continue
                source_uid = str(source["uid"])
                source_entry = by_uid.get(source_uid)
                try:
                    if source_entry is not None:
                        source_rest = self._plan_float(source_entry.get("rest_value", 0.0), 0.0)
                        source_max = self._plan_float(source_entry.get("max_amplitude", 1.0), 1.0)
                        weight = source_max - source_rest
                    else:
                        raw_weight = source.get("weight", None)
                        if raw_weight not in (None, ""):
                            weight = float(raw_weight)
                        else:
                            source_rest = self._plan_float(source.get("rest_value", 0.0), 0.0)
                            source_max = self._plan_float(source.get("max_amplitude", 1.0), 1.0)
                            weight = source_max - source_rest
                except Exception:
                    weight = 1.0
                sources.append((source_uid, weight))
            if sources:
                self._flex_sources[uid] = sources

    def set_active_flex(self, uid: str, value: float = 1.0) -> None:
        self._active_flex_uid = str(uid or "")
        try:
            self._active_flex_value = float(value)
        except Exception:
            self._active_flex_value = 1.0
        self._refresh_flex_vertex_data()
        self.update()

    def set_isolated_bodygroup(self, bodygroup: str) -> None:
        self._isolated_bodygroup = str(bodygroup or "")
        self.update()

    def set_selected_material(self, uid: str) -> None:
        self._selected_uid = str(uid or "")
        self.update()

    def set_hovered_material(self, uid: str) -> None:
        new_uid = str(uid or "")
        if new_uid == self._hovered_uid:
            return
        self._hovered_uid = new_uid
        self._preview_log(f"hover uid={new_uid!r} name={self._materials.get(new_uid, {}).get('material_name', '')!r}")
        self._queue_hover_update()

    def set_highlighted_materials(self, uids: set[str] | list[str] | tuple[str, ...]) -> None:
        self._highlighted_uids = {str(uid) for uid in uids if uid}
        self.update()

    def set_wireframe_visible(self, visible: bool) -> None:
        self._wireframe = bool(visible)
        self.update()

    def set_respect_alpha(self, visible: bool) -> None:
        self._respect_alpha = bool(visible)
        self.update()

    def reset_view(self, direction: str = "Front") -> None:
        self._view_yaw, self._view_pitch = self.VIEW_DIRECTIONS.get(direction, self.VIEW_DIRECTIONS["Front"])
        self._view_zoom = 1.0
        self._view_pan = QtCore.QPointF(0.0, 0.0)
        self.update()

    def _build_material_arrays(self) -> None:
        grouped: dict[str, list[list[float]]] = {}
        grouped_uvs: dict[str, list[list[float]]] = {}
        grouped_flex_deltas: dict[str, dict[str, list[tuple[int, list[list[float]]]]]] = {}
        texture_paths: dict[str, Path] = {}
        for triangle in self._triangles:
            uid = str(triangle.get("material_uid") or "")
            raw_points = triangle.get("points")
            raw_uvs = triangle.get("uvs")
            if not uid or not isinstance(raw_points, list) or len(raw_points) < 3:
                continue
            bucket = grouped.setdefault(uid, [])
            uv_bucket = grouped_uvs.setdefault(uid, [])
            triangle_points: list[list[float]] = []
            for raw in raw_points[:3]:
                if isinstance(raw, list) and len(raw) >= 3:
                    triangle_points.append([float(raw[0]), float(raw[1]), float(raw[2])])
            if len(triangle_points) != 3:
                continue
            start_count = len(bucket)
            bucket.extend(triangle_points)
            if isinstance(raw_uvs, list) and len(raw_uvs) >= 3:
                for raw_uv in raw_uvs[:3]:
                    if isinstance(raw_uv, list) and len(raw_uv) >= 2:
                        uv_bucket.append([float(raw_uv[0]), float(raw_uv[1])])
                    else:
                        uv_bucket.append([0.0, 0.0])
            else:
                uv_bucket.extend([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
            raw_flex_deltas = triangle.get("flex_deltas")
            if isinstance(raw_flex_deltas, dict):
                for flex_uid, raw_deltas in raw_flex_deltas.items():
                    if not isinstance(raw_deltas, list) or len(raw_deltas) < 3:
                        continue
                    deltas: list[list[float]] = []
                    for raw_delta in raw_deltas[:3]:
                        if isinstance(raw_delta, list) and len(raw_delta) >= 3:
                            deltas.append([float(raw_delta[0]), float(raw_delta[1]), float(raw_delta[2])])
                        else:
                            deltas.append([0.0, 0.0, 0.0])
                    flex_uid = str(flex_uid)
                    grouped_flex_deltas.setdefault(flex_uid, {}).setdefault(uid, []).append((start_count, deltas))
            texture_raw = str(triangle.get("texture_path") or self._materials.get(uid, {}).get("base_color_path") or "")
            if texture_raw:
                path = Path(texture_raw)
                if path.exists():
                    texture_paths[uid] = path
        self._material_positions = {
            uid: np.asarray(points, dtype=np.float32).reshape((-1, 3))
            for uid, points in grouped.items()
            if len(points) >= 3
        }
        self._material_uvs = {}
        for uid, points in self._material_positions.items():
            uvs = grouped_uvs.get(uid, [])
            if len(uvs) == len(points):
                self._material_uvs[uid] = np.asarray(uvs, dtype=np.float32).reshape((-1, 2))
        self._material_base_vertex_data = {}
        for uid, positions in self._material_positions.items():
            uvs = self._material_uvs.get(uid)
            if uvs is None or len(uvs) != len(positions):
                uvs = np.zeros((len(positions), 2), dtype=np.float32)
            interleaved = np.empty((len(positions), 5), dtype=np.float32)
            interleaved[:, 0:3] = positions
            interleaved[:, 3:5] = uvs
            self._material_base_vertex_data[uid] = np.ascontiguousarray(interleaved, dtype=np.float32)
        self._material_flex_deltas = {}
        for flex_uid, by_material in grouped_flex_deltas.items():
            converted: dict[str, np.ndarray] = {}
            for uid, spans in by_material.items():
                positions = self._material_positions.get(uid)
                if positions is None:
                    continue
                delta_array = np.zeros((len(positions), 3), dtype=np.float32)
                for start, deltas in spans:
                    if start < 0 or start + 3 > len(delta_array):
                        continue
                    delta_array[start : start + 3, :] = np.asarray(deltas[:3], dtype=np.float32).reshape((3, 3))
                converted[uid] = delta_array
            if converted:
                self._material_flex_deltas[flex_uid] = converted
        self._material_texture_paths = texture_paths
        self._refresh_flex_vertex_data()

    def _combined_flex_delta(self, uid: str, material_uid: str) -> np.ndarray | None:
        if not uid:
            return None
        direct = self._material_flex_deltas.get(uid, {}).get(material_uid)
        sources = self._flex_sources.get(uid, [])
        if not sources:
            return direct
        base = self._material_positions.get(material_uid)
        if base is None:
            return direct
        total = np.zeros((len(base), 3), dtype=np.float32)
        used = False
        if direct is not None and len(direct) == len(total):
            total += direct
            used = True
        for source_uid, weight in sources:
            delta = self._material_flex_deltas.get(source_uid, {}).get(material_uid)
            if delta is not None and len(delta) == len(total):
                total += delta * float(weight)
                used = True
        return total if used else None

    def _refresh_flex_vertex_data(self) -> None:
        self._material_vertex_data = {}
        active_uid = str(self._active_flex_uid or "")
        active_value = float(self._active_flex_value)
        active_scale = float(self._flex_scales.get(active_uid, 1.0))
        for uid, base_data in self._material_base_vertex_data.items():
            deformed = np.array(base_data, copy=True)
            for flex_uid in self._enabled_flex_uids:
                rest_value = float(self._flex_rest_values.get(flex_uid, 0.0))
                if abs(rest_value) <= 1e-8:
                    continue
                rest_delta = self._combined_flex_delta(flex_uid, uid)
                if rest_delta is not None and len(rest_delta) == len(deformed):
                    deformed[:, 0:3] += rest_delta * rest_value
            if active_uid and abs(active_value) > 1e-8:
                active_delta = self._combined_flex_delta(active_uid, uid)
                if active_delta is not None and len(active_delta) == len(deformed):
                    deformed[:, 0:3] += active_delta * active_value * active_scale
            self._material_vertex_data[uid] = np.ascontiguousarray(deformed, dtype=np.float32)

    def _queue_hover_update(self) -> None:
        if self._hover_update_queued:
            return
        self._hover_update_queued = True
        QtCore.QTimer.singleShot(16, self._flush_hover_update)

    def _flush_hover_update(self) -> None:
        self._hover_update_queued = False
        self.update()

    def _preview_log(self, message: str) -> None:
        if not self._preview_debug_enabled:
            return
        try:
            self._preview_debug_log_path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with self._preview_debug_log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{timestamp} {message}\n")
        except Exception:
            pass

    def _gl_debug_error(self, context: str) -> int:
        if not GL or not self._preview_debug_enabled:
            return 0
        try:
            error = int(GL.glGetError())
        except Exception as exc:
            self._preview_log(f"glGetError failed after {context}: {exc}")
            return 0
        if error:
            self._gl_error_count += 1
            self._preview_log(f"GL error after {context}: 0x{error:04x} count={self._gl_error_count}")
            if self._gl_error_count >= 3 and not self._textured_preview_disabled:
                self._textured_preview_disabled = True
                self._preview_log("Disabled textured material preview after repeated GL errors.")
        return error

    def _prepare_scene(self) -> None:
        points: list[np.ndarray] = []
        for positions in self._material_positions.values():
            if len(positions):
                points.append(positions.astype(np.float64))
        for positions in self._collision_lines.values():
            if len(positions):
                points.append(positions.astype(np.float64))
        for positions in self._bone_lines.values():
            if len(positions):
                points.append(positions.astype(np.float64))
        if not points:
            self._scene_center = np.zeros(3, dtype=np.float64)
            self._scene_extent = 1.0
            return
        array = np.vstack(points)
        mins = array.min(axis=0)
        maxs = array.max(axis=0)
        self._scene_center = (mins + maxs) * 0.5
        self._scene_extent = max(0.2, float(np.max(maxs - mins)))

    def _projection_view_matrices(self) -> tuple[np.ndarray, np.ndarray]:
        width = max(1, self.width())
        height = max(1, self.height())
        aspect = width / height
        scene_extent = max(0.2, _scalar_float(self._scene_extent, 1.0))
        view_zoom = max(0.001, _scalar_float(self._view_zoom, 1.0))
        view_height = scene_extent / max(0.001, view_zoom * 0.78)
        view_width = view_height * aspect
        pixel_scale = min(width, height) * 0.78 * view_zoom / max(0.001, scene_extent)
        pan_x = -float(self._view_pan.x()) / max(0.001, pixel_scale)
        pan_y = float(self._view_pan.y()) / max(0.001, pixel_scale)
        left = -view_width * 0.5 + pan_x
        right = view_width * 0.5 + pan_x
        bottom = -view_height * 0.5 + pan_y
        top = view_height * 0.5 + pan_y
        near = -scene_extent * 5.0
        far = scene_extent * 5.0
        projection = np.array(
            [
                [2.0 / (right - left), 0.0, 0.0, -(right + left) / (right - left)],
                [0.0, 2.0 / (top - bottom), 0.0, -(top + bottom) / (top - bottom)],
                [0.0, 0.0, -2.0 / (far - near), -(far + near) / (far - near)],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        yaw_angle = _scalar_float(self._view_yaw, 0.0)
        pitch_angle = _scalar_float(self._view_pitch, 0.0)
        return projection, _upright_orbit_view_matrix(self._scene_center, yaw_angle, pitch_angle)

    def _project_np(self, positions: np.ndarray) -> tuple[list[QtCore.QPointF], np.ndarray]:
        projection, view = self._projection_view_matrices()
        homogeneous = np.concatenate([positions[:, :3], np.ones((len(positions), 1), dtype=np.float64)], axis=1)
        view_space = (view @ homogeneous.T).T
        clip = (projection @ view_space.T).T
        safe_w = np.where(np.abs(clip[:, 3]) <= 1e-8, 1.0, clip[:, 3])
        ndc = clip[:, :3] / safe_w[:, None]
        x = self.width() * (0.5 + ndc[:, 0] * 0.5)
        y = self.height() * (0.5 - ndc[:, 1] * 0.5)
        return [QtCore.QPointF(float(px), float(py)) for px, py in zip(x, y)], view_space[:, 2]

    def _material_visible(self, uid: str) -> bool:
        entry = self._materials.get(uid)
        if not entry:
            return True
        if self._isolated_bodygroup:
            bodygroup = str(entry.get("bodygroup") or entry.get("material_name") or entry.get("proposed_name") or "")
            if bodygroup != self._isolated_bodygroup:
                return False
        if bool(entry.get("keep", True)):
            return True
        return bool(entry.get("render_when_highlighted", False)) and self._material_is_highlighted(uid)

    def _material_highlight_group(self, uid: str) -> str:
        entry = self._materials.get(uid, {})
        return str(entry.get("highlight_group") or entry.get("bodygroup_uid") or uid)

    def _material_is_highlighted(self, uid: str) -> bool:
        if not uid:
            return False
        if uid == self._hovered_uid:
            return True
        group_uid = self._material_highlight_group(uid)
        return bool(
            (self._hovered_uid and group_uid == self._hovered_uid)
            or uid in self._highlighted_uids
            or group_uid in self._highlighted_uids
        )

    def _material_rgba(self, uid: str, highlighted: bool = False) -> tuple[float, float, float, float]:
        entry = self._materials.get(uid, {})
        raw_color = entry.get("preview_color") or entry.get("swatch") or [0.75, 0.75, 0.75, 1.0]
        if not isinstance(raw_color, list):
            raw_color = [0.75, 0.75, 0.75, 1.0]
        values = [float(raw_color[index]) if index < len(raw_color) else 1.0 for index in range(4)]
        if max(values[:3]) - min(values[:3]) < 0.08 and max(values[:3]) > 0.82:
            seed = uid + str(entry.get("base_color_key") or entry.get("material_name") or "")
            value = sum((offset + 1) * ord(char) for offset, char in enumerate(seed))
            values[:3] = colorsys.hsv_to_rgb((value % 360) / 360.0, 0.62, 0.86)
        alpha = float(entry.get("alpha", values[3]) or 1.0)
        if not self._respect_alpha:
            alpha = 1.0
        elif alpha <= 0.02:
            alpha = 0.04
        if highlighted:
            alpha = max(alpha, 0.82)
            values = [min(1.0, value * 1.25 + 0.08) for value in values]
        return (
            max(0.0, min(1.0, values[0])),
            max(0.0, min(1.0, values[1])),
            max(0.0, min(1.0, values[2])),
            max(0.02, min(1.0, alpha)),
        )

    def _material_color(self, uid: str, highlighted: bool = False) -> QtGui.QColor:
        red, green, blue, alpha = self._material_rgba(uid, highlighted)
        return QtGui.QColor.fromRgbF(red, green, blue, alpha)

    def initializeGL(self) -> None:
        if GL:
            GL.glClearColor(0.08, 0.09, 0.10, 1.0)
            GL.glEnable(GL.GL_DEPTH_TEST)
            GL.glDisable(GL.GL_CULL_FACE)

    def paintGL(self) -> None:
        if GL:
            try:
                GL.glViewport(0, 0, *self._gl_viewport_size())
                GL.glClearColor(0.08, 0.09, 0.10, 1.0)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
                if self._material_positions:
                    self._draw_mesh_gl()
                    self._gl_error = ""
            except Exception as exc:
                self._gl_error = str(exc)

        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            if not self._material_positions:
                painter.fillRect(self.rect(), QtGui.QColor(22, 24, 27))
                painter.setPen(QtGui.QColor(230, 230, 230))
                painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, self._empty_message)
                return
            if not GL or self._gl_error:
                painter.fillRect(self.rect(), QtGui.QColor(22, 24, 27))
                painter.setPen(QtGui.QColor(255, 210, 120))
                painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, self._opengl_unavailable_message)
            self._draw_overlay(painter)
        finally:
            painter.end()

    def _gl_viewport_size(self) -> tuple[int, int]:
        dpr = max(1.0, float(self.devicePixelRatioF()))
        return max(1, int(round(self.width() * dpr))), max(1, int(round(self.height() * dpr)))

    def _load_texture_image(self, path: Path) -> QtGui.QImage:
        image = QtGui.QImage(str(path))
        if image.isNull():
            try:
                from PIL import Image

                with Image.open(path) as pil_image:
                    rgba = pil_image.convert("RGBA")
                    data = rgba.tobytes("raw", "RGBA")
                    image = QtGui.QImage(data, rgba.width, rgba.height, QtGui.QImage.Format.Format_RGBA8888).copy()
            except Exception:
                image = QtGui.QImage()
        if not image.isNull():
            image = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888).mirrored(False, True)
        return image

    def _texture_id_for_uid(self, uid: str) -> int:
        if uid in self._material_texture_ids:
            return self._material_texture_ids[uid]
        if not GL:
            return 0
        path = self._material_texture_paths.get(uid)
        if path is None or not path.exists():
            self._material_texture_ids[uid] = 0
            self._preview_log(f"texture missing uid={uid!r} path={str(path) if path else ''!r}")
            return 0
        image = self._load_texture_image(path)
        if image.isNull():
            self._material_texture_ids[uid] = 0
            self._preview_log(f"texture load failed uid={uid!r} path={str(path)!r}")
            return 0
        try:
            texture_id = int(GL.glGenTextures(1))
            GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT)
            bits = image.constBits()
            data = bits.tobytes() if hasattr(bits, "tobytes") else bytes(bits)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, image.width(), image.height(), 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, data)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            self._material_texture_ids[uid] = texture_id
            self._preview_log(f"texture loaded uid={uid!r} id={texture_id} size={image.width()}x{image.height()} path={str(path)!r}")
            self._gl_debug_error(f"texture upload {uid}")
            return texture_id
        except Exception as exc:
            self._material_texture_ids[uid] = 0
            self._preview_log(f"texture upload failed uid={uid!r} path={str(path)!r}: {exc}")
            return 0

    def _draw_mesh_gl(self) -> None:
        if not GL:
            return
        projection, view = self._projection_view_matrices()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadMatrixf(np.ascontiguousarray(projection.T, dtype=np.float32))
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadMatrixf(np.ascontiguousarray(view.T, dtype=np.float32))

        try:
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        except Exception:
            pass

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE if self._wireframe else GL.GL_FILL)
        stride = 5 * 4
        for uid, vertex_data in self._material_vertex_data.items():
            if not self._material_visible(uid) or len(vertex_data) < 3:
                continue
            hovered = self._material_is_highlighted(uid)
            red, green, blue, alpha = self._material_rgba(uid, hovered)
            base_ptr = int(vertex_data.ctypes.data)
            GL.glVertexPointer(3, GL.GL_FLOAT, stride, ctypes.c_void_p(base_ptr))
            texture_id = 0 if hovered or self._wireframe or self._textured_preview_disabled else self._texture_id_for_uid(uid)
            if texture_id:
                GL.glEnable(GL.GL_TEXTURE_2D)
                GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)
                GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
                GL.glTexCoordPointer(2, GL.GL_FLOAT, stride, ctypes.c_void_p(base_ptr + 12))
                GL.glColor4f(1.0, 1.0, 1.0, alpha)
                draw_mode = "textured"
            else:
                GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
                GL.glDisable(GL.GL_TEXTURE_2D)
                GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
                GL.glColor4f(red, green, blue, alpha)
                draw_mode = "solid-hover" if hovered else "solid"
            self._preview_log(f"draw uid={uid!r} mode={draw_mode} vertices={len(vertex_data)} texture={texture_id}")
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, int(len(vertex_data)))
            self._gl_debug_error(f"draw {uid} {draw_mode}")

        highlighted_uids = {
            uid
            for uid in self._material_vertex_data
            if self._material_is_highlighted(uid)
        }
        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glLineWidth(2.2)
        for uid in highlighted_uids:
            vertex_data = self._material_vertex_data.get(uid)
            if vertex_data is None or len(vertex_data) < 3 or not self._material_visible(uid):
                continue
            base_ptr = int(vertex_data.ctypes.data)
            GL.glColor4f(1.0, 0.86, 0.22, 1.0)
            GL.glVertexPointer(3, GL.GL_FLOAT, stride, ctypes.c_void_p(base_ptr))
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, int(len(vertex_data)))
            self._gl_debug_error(f"highlight {uid}")
        self._draw_collision_overlay_gl(stride)
        self._draw_bone_overlay_gl()
        GL.glLineWidth(1.0)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)
        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)
        GL.glDisable(GL.GL_BLEND)
        GL.glDisable(GL.GL_TEXTURE_2D)

    def _draw_collision_overlay_gl(self, _stride: int) -> None:
        if not GL or not self._collision_lines:
            return
        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glLineWidth(1.6)
        for uid, lines in self._collision_lines.items():
            if len(lines) < 2:
                continue
            highlighted = uid == self._hovered_collision_uid or uid in self._highlighted_collision_uids
            color = self._collision_colors.get(uid, (0.2, 0.75, 1.0, 0.85))
            if highlighted:
                GL.glDisable(GL.GL_DEPTH_TEST)
                GL.glLineWidth(3.0)
                GL.glColor4f(1.0, 0.78, 0.08, 1.0)
            else:
                GL.glEnable(GL.GL_DEPTH_TEST)
                GL.glLineWidth(1.6)
                GL.glColor4f(float(color[0]), float(color[1]), float(color[2]), float(color[3]))
            GL.glVertexPointer(3, GL.GL_FLOAT, 0, ctypes.c_void_p(int(lines.ctypes.data)))
            GL.glDrawArrays(GL.GL_LINES, 0, int(len(lines)))
            self._gl_debug_error(f"collision overlay {uid}")
        GL.glLineWidth(1.0)
        GL.glEnable(GL.GL_DEPTH_TEST)

    def _draw_bone_overlay_gl(self) -> None:
        if not GL or not self._bone_lines:
            return
        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glLineWidth(BONE_OVERLAY_LINE_WIDTH)
        GL.glPointSize(BONE_OVERLAY_POINT_SIZE)
        for uid, lines in self._bone_lines.items():
            if len(lines) < 2:
                continue
            highlighted = uid == self._hovered_bone_uid or uid in self._highlighted_bone_uids
            if highlighted:
                GL.glDisable(GL.GL_DEPTH_TEST)
                GL.glLineWidth(BONE_HIGHLIGHT_LINE_WIDTH)
                GL.glPointSize(BONE_HIGHLIGHT_POINT_SIZE)
                GL.glColor4f(1.0, 0.72, 0.05, 1.0)
            else:
                GL.glEnable(GL.GL_DEPTH_TEST)
                GL.glLineWidth(BONE_OVERLAY_LINE_WIDTH)
                GL.glPointSize(BONE_OVERLAY_POINT_SIZE)
                GL.glColor4f(0.78, 0.84, 0.94, 0.86)
            GL.glVertexPointer(3, GL.GL_FLOAT, 0, ctypes.c_void_p(int(lines.ctypes.data)))
            GL.glDrawArrays(GL.GL_LINES, 0, int(len(lines)))
            GL.glDrawArrays(GL.GL_POINTS, 0, int(len(lines)))
        GL.glLineWidth(1.0)
        GL.glPointSize(1.0)
        GL.glEnable(GL.GL_DEPTH_TEST)

    def _draw_overlay(self, painter: QtGui.QPainter) -> None:
        visible = sum(int(len(positions) // 3) for uid, positions in self._material_positions.items() if self._material_visible(uid))
        total = sum(int(len(positions) // 3) for positions in self._material_positions.values())
        material_count = len(self._materials)
        painter.setPen(QtGui.QColor(235, 235, 235))
        painter.drawText(
            12,
            22,
            f"{material_count:,} materials | {visible:,}/{total:,} preview triangles | {'wireframe' if self._wireframe else 'colored'}",
        )
        if self._textured_preview_disabled:
            painter.setPen(QtGui.QColor(255, 210, 120))
            painter.drawText(12, 44, self._textured_disabled_message)
        if self._active_flex_uid:
            painter.setPen(QtGui.QColor(255, 220, 130))
            painter.drawText(12, 66 if self._textured_preview_disabled else 44, f"Flex preview: {self._active_flex_uid} x {self._active_flex_value:.2f}")
        if self._collision_lines:
            y = 88 if self._active_flex_uid and self._textured_preview_disabled else 66 if self._active_flex_uid or self._textured_preview_disabled else 44
            painter.setPen(QtGui.QColor(120, 205, 255))
            label = self._collision_labels.get(self._hovered_collision_uid, self._hovered_collision_uid)
            suffix = f" | {label}" if label else ""
            painter.drawText(12, y, f"Physics overlay: {len(self._collision_lines):,} parts{suffix}")
        if self._bone_lines:
            y = 110 if self._collision_lines else 88 if self._active_flex_uid and self._textured_preview_disabled else 66 if self._active_flex_uid or self._textured_preview_disabled else 44
            painter.setPen(QtGui.QColor(220, 225, 235))
            label = self._bone_labels.get(self._hovered_bone_uid, self._hovered_bone_uid)
            suffix = f" | {label}" if label else ""
            painter.drawText(12, y, f"Bone overlay: {len(self._bone_lines):,} bones{suffix}")

    def _emit_stats(self) -> None:
        if not self.scan:
            self.statsChanged.emit("Material preview idle")
            return
        material_count = int(self.scan.get("material_count", len(self._materials)) or len(self._materials))
        sampled = len(self._triangles)
        source = 0
        preview = self.scan.get("model_preview") if isinstance(self.scan, dict) else None
        if isinstance(preview, dict):
            source = int(preview.get("source_triangle_count", 0) or 0)
        self.statsChanged.emit(f"Material preview | {material_count:,} materials | {sampled:,}/{source:,} sampled triangles")

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        self._last_mouse_pos = event.position().toPoint()
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        elif event.button() in (QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.MiddleButton):
            self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._last_mouse_pos is None:
            self._last_mouse_pos = event.position().toPoint()
            return
        current = event.position().toPoint()
        delta = current - self._last_mouse_pos
        self._last_mouse_pos = current
        buttons = event.buttons()
        if buttons & QtCore.Qt.MouseButton.LeftButton:
            self._view_yaw = _scalar_float(self._view_yaw, 0.0) + float(delta.x()) * 0.008
            self._view_pitch = max(-math.pi * 0.5 + 0.02, min(math.pi * 0.5 - 0.02, _scalar_float(self._view_pitch, 0.0) + float(delta.y()) * 0.008))
            self.update()
        elif buttons & (QtCore.Qt.MouseButton.RightButton | QtCore.Qt.MouseButton.MiddleButton):
            self._view_pan += QtCore.QPointF(delta.x(), delta.y())
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if not event.buttons():
            self._last_mouse_pos = None
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.reset_view("Front")
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta:
            self._view_zoom = max(0.2, min(8.0, _scalar_float(self._view_zoom, 1.0) * math.pow(1.0015, float(delta))))
            self.update()
        event.accept()
