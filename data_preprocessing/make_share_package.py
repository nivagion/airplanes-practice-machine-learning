"""Package existing prepared data. Optional user-created splits are validated."""
from pathlib import Path
import argparse
import json
import sys
import tempfile
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from approach.viewer import build_viewer
from approach.dataset import FEATURE_COLUMNS, TARGET


def package(split_dir=None, output_path=None):
    prepared = ROOT / "prepared"
    source = pd.read_csv(prepared / "training.csv", dtype={"icao24": str})
    assignments = None
    partitions = {}
    if split_dir is not None:
        assignments = {}
        flight_groups = set()
        source_by_id = source.set_index("example_id")
        for name in ("train", "validation", "test"):
            path = Path(split_dir) / f"{name}.csv"
            part = pd.read_csv(path, dtype={"icao24": str})
            if set(part.columns) != set(source.columns):
                raise ValueError(f"{path.name} must have the same columns as prepared/training.csv")
            if part.example_id.duplicated().any():
                raise ValueError(f"Repeated example IDs in {path.name}")
            ids, groups = set(part.example_id), set(part.flight_id)
            if ids & assignments.keys() or groups & flight_groups:
                raise ValueError("A flight/example occurs in more than one partition")
            if not ids <= set(source.example_id):
                raise ValueError(f"Unknown example IDs in {path.name}")
            # Partitions must be source rows, not arbitrary edited labels/features.
            expected = source_by_id.loc[part.example_id].reset_index()[source.columns]
            actual = part[source.columns].reset_index(drop=True)
            pd.testing.assert_frame_equal(expected, actual, check_dtype=False, check_exact=False, rtol=1e-9, atol=1e-9)
            assignments.update({key: name for key in ids})
            flight_groups.update(groups)
            partitions[name] = path
        if set(assignments) != set(source.example_id):
            raise ValueError("The three partitions must cover every prepared example exactly once")
    folder = ROOT / "share"
    folder.mkdir(exist_ok=True)
    suffix = "split" if assignments is not None else "unsplit"
    target = Path(output_path) if output_path is not None else folder / f"schiphol_18R_{suffix}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder, prefix=".package-") as temporary:
        assert Path(temporary).resolve().is_relative_to(folder.resolve())
        viewer = Path(temporary) / "viewer.html"
        build_viewer(ROOT, assignments=assignments, destination=viewer)
        summary = json.loads((prepared / "dataset_summary.json").read_text())
        schema = json.loads((prepared / "schema.json").read_text())
        if assignments is not None:
            summary.update(split_status="split", partition_counts={key: len(pd.read_csv(path)) for key,path in partitions.items()})
            schema["split_status"] = "split"
        instructions = (prepared / "README.md").read_text()
        if assignments is not None:
            instructions = instructions.replace("**Unsplit**: you create train/validation/test later.",
                "**Split**: use train.csv, validation.csv and test.csv. The viewer can filter each partition.")
            instructions = instructions.replace("training.csv", "train.csv / validation.csv / test.csv")
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(viewer, "viewer.html")
            archive.writestr("README.md", instructions)
            archive.writestr("schema.json", json.dumps(schema, indent=2))
            archive.writestr("dataset_summary.json", json.dumps(summary, indent=2))
            if assignments is None:
                archive.write(prepared / "training.csv", "training.csv")
            else:
                for name,path in partitions.items():
                    archive.write(path, f"{name}.csv")
            for name in ["tracks.csv.gz", "labels_audit.csv", "audit.csv", "rejected.csv", "runway_geometry.json", "airport_runways.json", "rules.json"]:
                archive.write(prepared / name, name)
    print(f"Share: {target} ({target.stat().st_size / 1024 / 1024:.2f} MB)")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-dir", type=Path, help="Folder containing your train.csv, validation.csv and test.csv")
    parser.add_argument("--output", type=Path, help="Optional ZIP destination")
    args = parser.parse_args()
    package(args.split_dir, args.output)
