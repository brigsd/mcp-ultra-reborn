import json
import os
from pathlib import Path

from vehicle_workspace.generators.blockout import generate_blockout
from vehicle_workspace.generators.body_loft import generate_model
from vehicle_workspace.generators.rig import generate_rig
from vehicle_workspace.rendering.orthographic_views import render_views
from vehicle_workspace.validation.dimensions import audit_dimensions
from vehicle_workspace.validation.symmetry import audit_symmetry
from vehicle_workspace.validation.wheel_fitment import audit_wheel_fitment
from vehicle_workspace.vehicle.schema import load_spec


def clear_scene():
    import bpy  # type: ignore

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def _save_blend(path):
    import bpy  # type: ignore

    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def _audit(spec):
    return {
        "dimensions": audit_dimensions(spec),
        "symmetry": audit_symmetry(spec),
        "wheel_fitment": audit_wheel_fitment(spec),
    }


def run_vehicle_action(action, spec_json, output_dir, quality="draft"):
    spec = load_spec(spec_json)
    output = Path(output_dir)
    try:
        output.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        if not output.exists():
            raise
    render_dir = output / "renders"
    try:
        render_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        render_dir = output

    clear_scene()

    generation = {}
    if action == "rig":
        generation["rig"] = generate_rig(spec)
    elif action == "blockout":
        generation["rig"] = generate_rig(spec)
        generation["blockout"] = generate_blockout(spec)
    elif action == "model":
        if quality in {"standard", "high"}:
            generation["model"] = generate_model(spec)
        else:
            generation["rig"] = generate_rig(spec)
            generation["blockout"] = generate_blockout(spec)
    else:
        raise ValueError(f"Acao de veiculo desconhecida: {action}")

    artifact_errors = []
    render_report = render_views(str(render_dir), resolution=900)
    if render_report.get("errors"):
        artifact_errors.append({"stage": "render", "errors": render_report["errors"]})
    audit_report = _audit(spec) if action in {"blockout", "model"} else {}

    blend_path = output / "scene.blend"
    try:
        _save_blend(blend_path)
    except Exception as exc:
        artifact_errors.append({"stage": "save_blend", "error": str(exc)})

    report = {
        "success": True,
        "action": action,
        "quality": quality,
        "spec": spec,
        "generation": generation,
        "audit": audit_report,
        "renders": render_report["renders"],
        "artifact_errors": artifact_errors,
        "paths": {
            "output_dir": str(output),
            "blend": str(blend_path),
            "report": str(output / "report.json"),
        },
    }
    try:
        (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        report["artifact_errors"].append({"stage": "write_report", "error": str(exc)})
        report["paths"]["report"] = ""
    return report


def read_report(modelo_id):
    path = Path(modelo_id)
    if path.is_dir():
        path = path / "report.json"
    if not path.exists():
        raise FileNotFoundError(f"Relatorio nao encontrado: {modelo_id}")
    return json.loads(path.read_text(encoding="utf-8"))
