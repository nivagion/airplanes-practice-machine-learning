"""Validate exported targets against recorded brackets and causal snapshot windows."""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from approach.dataset import add_geometry, first_confirmed_alignment, local_xy, snapshot_features

p = ROOT / 'prepared/multi_airport'
schema = json.loads((p / 'schema.json').read_text())
rules = json.loads((p / 'rules.json').read_text())
registry = {g['geometry_id']: g for g in json.loads((p / 'runway_registry.json').read_text())['runways']}
train = pd.read_csv(p / 'training.csv', keep_default_na=False)
labels = pd.read_csv(p / 'labels_audit.csv', keep_default_na=False).set_index('example_id')
tracks = pd.read_csv(p / 'tracks.csv.gz', parse_dates=['timestamp'])
tracks['timestamp'] = pd.to_datetime(tracks.timestamp, utc=True, format='ISO8601')
summary = json.loads((p / 'dataset_summary.json').read_text())
assert len(train) == summary['accepted_approaches']
assert train.example_id.is_unique and train.flight_id.is_unique
assert set(labels.index) == set(train.example_id)
assert set(schema['feature_columns']).isdisjoint(schema['metadata_columns'])
assert set(train.columns) == set(schema['feature_columns'] + schema['metadata_columns'] + [schema['target_column']])
assert np.isfinite(train[schema['feature_columns'] + [schema['target_column']]].to_numpy()).all()
assert (train.remaining_time_s > 0).all()
track_groups = {key: group.reset_index(drop=True) for key, group in tracks.groupby('example_id', sort=False)}
for row in train.itertuples(index=False):
    label = labels.loc[row.example_id]
    start, crossing = pd.Timestamp(row.snapshot_time_utc), pd.Timestamp(label.crossing_time_utc)
    before, after = pd.Timestamp(label.crossing_before_utc), pd.Timestamp(label.crossing_after_utc)
    assert before <= crossing <= after
    assert 0 < label.crossing_gap_s <= rules['max_observation_gap_s']
    assert abs((after - before).total_seconds() - label.crossing_gap_s) < 1e-6
    assert abs((crossing - start).total_seconds() - row.remaining_time_s) <= 1.1e-6
    assert label.remaining_bracket_start_s <= row.remaining_time_s <= label.remaining_bracket_end_s
    assert rules['crossing_min_speed_ratio'] <= label.crossing_speed_ratio <= rules['crossing_max_speed_ratio']
    assert pd.Timestamp(label.landing_continuation_observed_utc) >= crossing
    geo = registry[row.geometry_id]
    assert row.airport == geo['airport_icao'] and row.runway == geo['runway_direction']
    assert abs(row.threshold_latitude_deg - geo['threshold_latitude_deg']) < 1e-10
    assert abs(row.threshold_longitude_deg - geo['threshold_longitude_deg']) < 1e-10
    assert abs(row.baro_height_proxy_m - (row.baro_altitude_m - row.threshold_elevation_m)) < 1e-6
    track = add_geometry(track_groups[row.example_id], geo)
    past = track[track.timestamp <= start]
    # At least the full confirming window is present; no future data is supplied.
    window = past[past.timestamp >= start - pd.Timedelta(seconds=rules['alignment_duration_s'])]
    assert len(window) >= 2
    assert (start - window.timestamp.iloc[0]).total_seconds() >= rules['alignment_duration_s'] - rules['max_observation_gap_s']
    assert (window.cross_track_m.abs() <= rules['alignment_cross_track_m'] + 1e-5).all()
    assert (window.track_error_deg.abs() <= rules['alignment_track_error_deg'] + 1e-7).all()
    assert (window.timestamp.diff().dt.total_seconds().dropna() <= rules['max_observation_gap_s']).all()
    snapshot = past.iloc[-1]
    assert snapshot.timestamp == start
    for key, value in snapshot_features(snapshot).items():
        assert abs(getattr(row, key) - value) < 1e-5, (row.example_id, key)
    between = track[track.timestamp.between(start, after)]
    assert (between.timestamp.diff().dt.total_seconds().dropna() <= rules['max_observation_gap_s']).all()
    # Independently reconstruct the label from the two exported observations.
    a = track.loc[track.timestamp.eq(before)].iloc[0]
    b = track.loc[track.timestamp.eq(after)].iloc[0]
    assert a.along_m < 0 <= b.along_m
    assert abs(a.latitude - label.crossing_before_latitude_deg) < 1e-8
    assert abs(a.longitude - label.crossing_before_longitude_deg) < 1e-8
    assert abs(b.latitude - label.crossing_after_latitude_deg) < 1e-8
    assert abs(b.longitude - label.crossing_after_longitude_deg) < 1e-8
    assert max(abs(a.cross_track_m), abs(b.cross_track_m)) <= rules['crossing_cross_track_m'] + 1e-5
    assert max(abs(a.track_error_deg), abs(b.track_error_deg)) <= rules['crossing_track_error_deg'] + 1e-7
    assert max(a.height_proxy_ft, b.height_proxy_ft) <= rules['crossing_max_altitude_ft'] + 1e-5
    fraction = -a.along_m / (b.along_m - a.along_m)
    rebuilt = before + pd.Timedelta(seconds=(after - before).total_seconds() * fraction)
    assert abs((rebuilt - crossing).total_seconds()) <= 1.1e-6
    position_speed = np.hypot(b.east_m - a.east_m, b.north_m - a.north_m) / label.crossing_gap_s
    reported_speed = (a.groundspeed_mps + b.groundspeed_mps) / 2
    assert abs(position_speed / reported_speed - label.crossing_speed_ratio) < 1e-5
    x, y = local_xy(label.crossing_latitude_deg, label.crossing_longitude_deg, geo)
    bearing = np.deg2rad(geo['true_bearing_deg'])
    assert abs(x * np.sin(bearing) + y * np.cos(bearing)) < .2
options = json.loads((ROOT / 'config/expansion.json').read_text())
copy = (ROOT / options['training_copy_directory'].format(row_count=len(train))).resolve()
for name in ['training.csv', 'schema.json', 'dataset_summary.json']:
    assert (p / name).read_bytes() == (copy / name).read_bytes()
print(f'Validated {len(train):,} unique approaches across {train.airport.nunique()} airports: snapshots, observed brackets, geometry, finite features and training copies.')
