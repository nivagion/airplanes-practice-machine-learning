"""Portable, offline runway map. No external scripts or map tiles required."""
from pathlib import Path
import json
import math

import pandas as pd

from .dataset import local_xy, read_json, FEATURE_COLUMNS, TARGET


def runway_shapes(root, geometry):
    rows = read_json(root / "data_research/source_evidence/dorbolo_runways_EHAM.json")
    shapes = []
    for row in rows:
        if row["le_ident"] == "18R":
            north = geometry["north_physical_end_current_aip"]
            south = geometry["runway_18r_far_end"]
            a = local_xy(north["latitude_deg"], north["longitude_deg"], geometry)
            b = local_xy(south["latitude_deg"], south["longitude_deg"], geometry)
            width = geometry["runway_width_m"]
        else:
            a = local_xy(float(row["le_latitude_deg"]), float(row["le_longitude_deg"]), geometry)
            b = local_xy(float(row["he_latitude_deg"]), float(row["he_longitude_deg"]), geometry)
            width = float(row["width_ft"]) * .3048
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        ox, oy = -dy / length * width / 2, dx / length * width / 2
        shapes.append({"name": row["le_ident"] + "/" + row["he_ident"],
                       "main": row["le_ident"] == "18R", "ends": [[float(x), float(y)] for x, y in [a, b]],
                       "polygon": [[float(x), float(y)] for x, y in [(a[0]+ox, a[1]+oy), (a[0]-ox, a[1]-oy), (b[0]-ox, b[1]-oy), (b[0]+ox, b[1]+oy)]]})
    return shapes


def make_payload(train, labels, tracks, geometry, shapes, summary, assignments=None):
    label_index = labels.set_index("example_id")
    groups = {key: group for key, group in tracks.groupby("example_id", sort=False)}
    flights = []
    for row in train.to_dict("records"):
        label = label_index.loc[row["example_id"]].to_dict()
        group = groups[row["example_id"]]
        points = []
        for p in group.itertuples():
            points.append([round(float(p.east_m), 2), round(float(p.north_m), 2),
                           str(p.timestamp), round(float(p.time_from_snapshot_s), 3),
                           round(float(p.groundspeed_mps), 2), None if pd.isna(p.baro_altitude_m) else round(float(p.baro_altitude_m), 2),
                           round(float(p.latitude), 7), round(float(p.longitude), 7)])
        sx, sy = local_xy(row["latitude_deg"], row["longitude_deg"], geometry)
        ex, ey = local_xy(label["crossing_latitude_deg"], label["crossing_longitude_deg"], geometry)
        flights.append({"id": row["example_id"], "callsign": row["callsign"], "icao24": row["icao24"],
                        "snapshot": row["snapshot_time_utc"], "crossing": label["crossing_time_utc"],
                        "before": label["crossing_before_utc"], "after": label["crossing_after_utc"],
                        "remaining": round(float(row[TARGET]), 3),
                        "bracket": [label["remaining_bracket_start_s"], label["remaining_bracket_end_s"]],
                        "baseline": round(float(row["baseline_eta_s"]), 1),
                        "start_xy": [float(sx), float(sy)], "end_xy": [float(ex), float(ey)], "points": points,
                        "split": (assignments or {}).get(row["example_id"], "unsplit")})
    return {"flights": flights, "runways": shapes, "heading": geometry["true_bearing_deg"],
            "threshold": [geometry["threshold_latitude_deg"], geometry["threshold_longitude_deg"]],
            "accepted": len(flights), "rejected": summary["rejected_approaches"],
            "date": summary["date"], "geometry_status": geometry["geometry_status"]}


def write_viewer(path, payload):
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = Path(__file__).with_name("viewer_template.html").read_text(encoding="utf-8")
    path.write_text(template.replace("__FLIGHT_DATA__", data), encoding="utf-8")


def build_viewer(root, assignments=None, destination=None):
    folder = root / "prepared"
    train = pd.read_csv(folder / "training.csv", dtype={"icao24": str})
    labels = pd.read_csv(folder / "labels_audit.csv", dtype={"icao24": str})
    tracks = pd.read_csv(folder / "tracks.csv.gz")
    geometry = read_json(folder / "runway_geometry.json")
    summary = read_json(folder / "dataset_summary.json")
    shapes = runway_shapes(root, geometry)
    (folder / "airport_runways.json").write_text(json.dumps(shapes, indent=2), encoding="utf-8")
    payload = make_payload(train, labels, tracks, geometry, shapes, summary, assignments)
    write_viewer(destination or folder / "viewer.html", payload)
    return payload
