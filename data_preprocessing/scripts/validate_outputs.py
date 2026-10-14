"""Validate actual exports, including snapshot/label separation and widget errors."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import nbformat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from approach.dataset import local_xy

p = ROOT / "prepared"
train = pd.read_csv(p / "training.csv",dtype={"icao24":str})
labels = pd.read_csv(p / "labels_audit.csv",dtype={"icao24":str}).set_index("example_id")
tracks = pd.read_csv(p / "tracks.csv.gz",parse_dates=["timestamp"])
schema = json.loads((p / "schema.json").read_text())
rules = json.loads((p / "rules.json").read_text())
geo = json.loads((p / "runway_geometry.json").read_text())
assert train.example_id.is_unique and train.flight_id.is_unique
assert np.isfinite(train[schema["feature_columns"]+[schema["target_column"]]].to_numpy()).all()
assert (train.remaining_time_s > 0).all()
assert schema["split_status"] == "unsplit"
assert not {"crossing_time_utc","crossing_before_utc","crossing_speed_ratio","landing_evidence_method"} & set(train.columns)
for row in train.itertuples():
    label = labels.loc[row.example_id]
    start, end = pd.Timestamp(row.snapshot_time_utc), pd.Timestamp(label.crossing_time_utc)
    assert abs((end-start).total_seconds()-row.remaining_time_s) < 2e-6
    assert pd.Timestamp(label.crossing_before_utc) <= end <= pd.Timestamp(label.crossing_after_utc)
    assert 0 < label.crossing_gap_s <= rules["max_observation_gap_s"]
    assert .75 <= label.crossing_speed_ratio <= 1.25
    track = tracks[tracks.example_id.eq(row.example_id)]
    snapshot = track[track.timestamp.eq(start)].iloc[0]
    for field, target in [("latitude","latitude_deg"),("longitude","longitude_deg"),("baro_altitude_m","baro_altitude_m"),("groundspeed_mps","groundspeed_mps"),("vertical_rate_mps","vertical_rate_mps")]:
        assert abs(float(snapshot[field])-float(getattr(row,target))) < 1e-7
    window = track[track.timestamp.between(start-pd.Timedelta(seconds=10),start)]
    assert (window.cross_track_m.abs() <= 100).all()
    errors = (window.track-geo["true_bearing_deg"]+180)%360-180
    assert (errors.abs() <= 10).all()
    assert (window.timestamp.diff().dt.total_seconds().dropna() <= 3).all()
    between = track[track.timestamp.between(start,pd.Timestamp(label.crossing_after_utc))]
    assert (between.timestamp.diff().dt.total_seconds().dropna() <= 3).all()
    x,y = local_xy(label.crossing_latitude_deg,label.crossing_longitude_deg,geo)
    angle = np.deg2rad(geo["true_bearing_deg"])
    assert abs(x*np.sin(angle)+y*np.cos(angle)) < .05
nb = nbformat.read(ROOT / "notebooks/01_view_flights.ipynb",as_version=4)
nbformat.validate(nb)
errors = [o for c in nb.cells for o in c.get("outputs",[]) if o.output_type=="error"]
state = nb.metadata.get("widgets",{}).get("application/vnd.jupyter.widget-state+json",{}).get("state",{})
widget_outputs = [o for v in state.values() for o in v.get("state",{}).get("outputs",[])]
errors.extend(o for o in widget_outputs if o.get("output_type")=="error")
assert not errors,errors
assert any("image/png" in o.get("data",{}) for o in widget_outputs), "Flight map must have a saved PNG output"
print(f"Validated {len(train)} rows, {len(tracks)} observed points, causal confirmation windows, target brackets, feature separation and executed notebook/widget outputs.")
