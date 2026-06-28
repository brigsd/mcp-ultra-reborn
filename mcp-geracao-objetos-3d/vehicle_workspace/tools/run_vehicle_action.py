import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vehicle_workspace.orchestration.pipeline import run_vehicle_action


def _resolve_path(value, default_base=ROOT):
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == ROOT.name:
        return ROOT.parent / path
    return default_base / path


def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description="Run a vehicle workspace action inside Blender.")
    parser.add_argument("--action", choices=["rig", "blockout", "model"], default="model")
    parser.add_argument("--spec", default=str(ROOT / "vehicle_workspace" / "specs" / "examples" / "supercar_sv24.json"))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--quality", default="draft")
    return parser.parse_args(argv)


def main():
    args = _parse_args()
    spec_path = _resolve_path(args.spec)
    if spec_path.exists():
        spec_json = spec_path.read_text(encoding="utf-8")
    else:
        spec_json = args.spec

    output_dir = args.output_dir
    if not output_dir:
        run_id = f"{args.action}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        output_root = Path(os.environ.get("VEHICLE_OUTPUT_ROOT", r"C:\tmp\mcp-ultra-vehicle-runs"))
        output_dir = str(output_root / run_id)
    else:
        output_dir = str(_resolve_path(output_dir))

    try:
        report = run_vehicle_action(args.action, spec_json, output_dir, args.quality)
        print("VEHICLE_JSON_START")
        print(json.dumps(report, ensure_ascii=False))
        print("VEHICLE_JSON_END")
    except Exception as exc:
        import traceback

        print("VEHICLE_JSON_START")
        print(json.dumps({
            "success": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "paths": {"output_dir": output_dir},
        }, ensure_ascii=False))
        print("VEHICLE_JSON_END")
        raise


if __name__ == "__main__":
    main()
