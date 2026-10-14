"""Causal snapshot extraction and separate retrospective crossing labels.

One-second state vectors are sampled states, not proof of fresh ADS-B messages.
Consecutive duplicate positions are removed without filling observation gaps.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

FEATURE_COLUMNS = [
    "latitude_deg", "longitude_deg", "baro_altitude_m", "groundspeed_mps",
    "track_deg", "vertical_rate_mps", "distance_to_threshold_m",
    "cross_track_m", "track_error_deg", "speed_toward_threshold_mps",
    "baseline_eta_s",
]
TARGET = "remaining_time_s"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ecef(latitude, longitude):
    """WGS84 surface positions, metres. Altitude is not used for horizontal geometry."""
    lat, lon = np.deg2rad(latitude), np.deg2rad(longitude)
    a, e2 = 6378137.0, 6.69437999014e-3
    n = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    return np.asarray([n * np.cos(lat) * np.cos(lon),
                       n * np.cos(lat) * np.sin(lon),
                       n * (1 - e2) * np.sin(lat)])


def local_xy(latitude, longitude, geometry):
    la, lo = geometry["threshold_latitude_deg"], geometry["threshold_longitude_deg"]
    delta = ecef(latitude, longitude) - ecef(la, lo).reshape(3, *([1] if np.ndim(latitude) else []))
    lat, lon = math.radians(la), math.radians(lo)
    east = -math.sin(lon) * delta[0] + math.cos(lon) * delta[1]
    north = (-math.sin(lat) * math.cos(lon) * delta[0]
             - math.sin(lat) * math.sin(lon) * delta[1] + math.cos(lat) * delta[2])
    return east, north


def add_geometry(frame: pd.DataFrame, geometry: dict) -> pd.DataFrame:
    out = frame.copy()
    east, north = local_xy(out.latitude.to_numpy(), out.longitude.to_numpy(), geometry)
    angle = math.radians(geometry["true_bearing_deg"])
    out["east_m"], out["north_m"] = east, north
    out["along_m"] = east * math.sin(angle) + north * math.cos(angle)
    out["cross_track_m"] = east * math.cos(angle) - north * math.sin(angle)
    out["distance_to_threshold_m"] = -out.along_m
    out["track_error_deg"] = (out.track - geometry["true_bearing_deg"] + 180) % 360 - 180
    out["groundspeed_mps"] = out.groundspeed * (1852 / 3600)
    out["baro_altitude_m"] = out.altitude * 0.3048
    out["vertical_rate_mps"] = out.vertical_rate * 0.3048 / 60
    out["speed_toward_threshold_mps"] = out.groundspeed_mps * np.cos(np.deg2rad(out.track_error_deg))
    return out


def first_confirmed_alignment(track: pd.DataFrame, config: dict):
    """Returns the first causal confirmation. Never backdates it by ten seconds.

    Detect geometric alignment before applying the final-approach distance/altitude
    window, so entering that window cannot masquerade as observed alignment onset.
    The first sustained run wins, even if it must subsequently be rejected.
    """
    match = ((track.distance_to_threshold_m > 0)
             & (track.cross_track_m.abs() <= config["alignment_cross_track_m"])
             & (track.track_error_deg.abs() <= config["alignment_track_error_deg"])
             & (track.groundspeed_mps >= config["min_snapshot_groundspeed_mps"]))
    times = track.timestamp.tolist()
    started = None
    onset = None
    onset_observed = False
    for i, eligible in enumerate(match.to_numpy()):
        gap = (times[i] - times[i - 1]).total_seconds() if i else None
        if not eligible:
            started = onset = None
            onset_observed = False
            continue
        if started is None:
            started = onset = i
            onset_observed = bool(i > 0 and gap <= config["max_observation_gap_s"] and not match.iloc[i - 1])
        elif gap > config["max_observation_gap_s"]:
            # Only the uninterrupted recent run can support confirmation.
            started = i
        if (times[i] - times[started]).total_seconds() >= config["alignment_duration_s"]:
            if not onset_observed:
                return None, "missing_alignment_onset", onset
            row = track.iloc[i]
            if row.distance_to_threshold_m > config["max_snapshot_distance_m"]:
                return None, "first_alignment_outside_final_window", onset
            if row.altitude > config["max_snapshot_altitude_ft"]:
                return None, "first_alignment_too_high", onset
            return i, None, onset
    return None, "no_confirmed_alignment", onset


def first_threshold_segment(track, snapshot_index):
    """First plausible geometric crossing after the snapshot; quality checked later."""
    for i in range(snapshot_index + 1, len(track)):
        a, b = track.iloc[i - 1], track.iloc[i]
        if (a.along_m < 0 <= b.along_m and max(abs(a.cross_track_m), abs(b.cross_track_m)) <= 100
                and max(abs(a.track_error_deg), abs(b.track_error_deg)) <= 20
                and max(a.altitude, b.altitude) < 1500):
            return i - 1, i
    return None


def check_crossing(a, b, config):
    gap = (b.timestamp - a.timestamp).total_seconds()
    if not 0 < gap <= config["max_observation_gap_s"]:
        return None, "crossing_gap_too_large"
    if max(abs(a.cross_track_m), abs(b.cross_track_m)) > config["crossing_cross_track_m"]:
        return None, "crossing_outside_runway_corridor"
    if max(abs(a.track_error_deg), abs(b.track_error_deg)) > config["crossing_track_error_deg"]:
        return None, "crossing_wrong_direction"
    if not all(np.isfinite(x) for x in [a.altitude, b.altitude, a.groundspeed_mps, b.groundspeed_mps]):
        return None, "crossing_missing_state"
    if max(a.altitude, b.altitude) > config["crossing_max_altitude_ft"]:
        return None, "crossing_too_high"
    derived = math.hypot(b.east_m - a.east_m, b.north_m - a.north_m) / gap
    reported = (a.groundspeed_mps + b.groundspeed_mps) / 2
    ratio = derived / reported if reported > 0 else math.inf
    if not config["crossing_min_speed_ratio"] <= ratio <= config["crossing_max_speed_ratio"]:
        return None, "crossing_speed_inconsistent"
    fraction = -a.along_m / (b.along_m - a.along_m)
    crossing = a.timestamp + pd.Timedelta(seconds=gap * fraction)
    return {"crossing": crossing, "gap_s": gap, "fraction": fraction,
            "derived_speed_mps": derived, "reported_speed_mps": reported, "speed_ratio": ratio}, None


def has_landing_continuation(track, crossing_time, geometry, config, crossing_speed):
    """Conservative rollout evidence, not an independently measured touchdown."""
    after = track[(track.timestamp >= crossing_time)
                  & (track.timestamp <= crossing_time + pd.Timedelta(seconds=config["landing_evidence_window_s"]))]
    last = None
    start = None
    length = geometry["landing_distance_available_m"]
    for row in after.itertuples():
        good = (0 <= row.along_m <= length and abs(row.cross_track_m) <= 60
                and 0 <= row.groundspeed_mps <= config["landing_evidence_groundspeed_mps"]
                and (pd.isna(row.altitude) or row.altitude <= config["crossing_max_altitude_ft"]))
        gap = (row.timestamp - last).total_seconds() if last is not None else 0
        if not good:
            start = None
        elif start is None or gap > config["max_observation_gap_s"]:
            start = row.timestamp
        if start is not None and (row.timestamp - start).total_seconds() >= config["landing_evidence_duration_s"]:
            return row.timestamp, "slow_runway_rollout"
        last = row.timestamp
    # Some published flights end before the aircraft slows below 35 m/s. Clear
    # deceleration while maintaining level barometric altitude on the runway is
    # alternative observed landing evidence. Do not synthesize missing rollout.
    for row in after.itertuples():
        if (row.timestamp - crossing_time).total_seconds() < 8:
            continue
        recent = after[after.timestamp.between(row.timestamp - pd.Timedelta(seconds=config["landing_level_window_s"]), row.timestamp)]
        if len(recent) < 5 or (recent.timestamp.iloc[-1] - recent.timestamp.iloc[0]).total_seconds() < config["landing_level_window_s"]:
            continue
        if (recent.timestamp.diff().dt.total_seconds().dropna() > config["max_observation_gap_s"]).any():
            continue
        if not (recent.along_m.between(300, length) & (recent.cross_track_m.abs() <= 60)).all():
            continue
        if not recent.altitude.notna().all() or recent.altitude.max() > config["crossing_max_altitude_ft"]:
            continue
        if recent.altitude.max() - recent.altitude.min() > config["landing_altitude_range_ft"]:
            continue
        if (recent.vertical_rate.dropna().abs() > config["landing_max_vertical_rate_fpm"]).any():
            continue
        if row.groundspeed_mps <= crossing_speed - config["landing_deceleration_mps"]:
            return row.timestamp, "runway_deceleration_and_level_altitude"
    return None


def snapshot_features(row):
    features = {
        "latitude_deg": row.latitude, "longitude_deg": row.longitude,
        "baro_altitude_m": row.baro_altitude_m, "groundspeed_mps": row.groundspeed_mps,
        "track_deg": row.track, "vertical_rate_mps": row.vertical_rate_mps,
        "distance_to_threshold_m": row.distance_to_threshold_m, "cross_track_m": row.cross_track_m,
        "track_error_deg": row.track_error_deg,
        "speed_toward_threshold_mps": row.speed_toward_threshold_mps,
        "baseline_eta_s": row.distance_to_threshold_m / row.speed_toward_threshold_mps,
    }
    if not all(np.isfinite(value) for value in features.values()):
        raise ValueError("Snapshot features must be finite")
    return {key: float(value) for key, value in features.items()}


def build_dataset(root: Path):
    config = read_json(root / "config/approach.json")
    geometry = read_json(root / "data_research/source_evidence/eham_18r_historical_geometry_audit.json")
    source = root / "data/raw/EHAM_20230315_flights.parquet"
    output = root / "prepared"
    output.mkdir(exist_ok=True)
    columns = ["timestamp", "latitude", "longitude", "altitude", "groundspeed", "track", "vertical_rate", "icao24", "callsign", "destination"]
    file = pq.ParquetFile(source)
    print(f"Reading {file.metadata.num_rows:,} source records...", flush=True)
    table = pq.read_table(source, columns=columns, filters=[("destination", "=", "EHAM"),
        ("latitude", ">=", 51.5), ("latitude", "<=", 53.2), ("longitude", ">=", 3.2), ("longitude", "<=", 6.2)])
    frame = table.to_pandas()
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    frame["icao24"] = frame.icao24.fillna("").str.strip().str.lower()
    frame["callsign"] = frame.callsign.fillna("").str.strip()
    raw_nearby = len(frame)
    # Ground messages can omit vertical rate and altitude. Keep these observations
    # for landing-continuation checks; require complete fields at the snapshot.
    needed = ["timestamp", "latitude", "longitude", "groundspeed"]
    frame = frame.dropna(subset=needed)
    frame = frame[(frame.icao24 != "") & frame.groundspeed.between(0, 700)
                  & (frame.altitude.isna() | frame.altitude.between(-2000, 60000))]
    frame = add_geometry(frame, geometry)
    frame = frame[np.hypot(frame.east_m, frame.north_m) <= config["context_radius_m"]].copy()
    frame = frame.sort_values(["icao24", "timestamp"], kind="stable")
    # Conflicting same-aircraft/same-time positions are ambiguous; discard all
    # conflicting copies rather than selecting whichever supports a crossing.
    positions = frame.groupby(["icao24", "timestamp"], sort=False)[["latitude", "longitude"]].transform("nunique")
    conflict = positions.max(axis=1) > 1
    conflicting_rows = int(conflict.sum())
    frame = frame.loc[~conflict].drop_duplicates(["icao24", "timestamp"], keep="first").copy()
    frame["callsign"] = frame.callsign.replace("", pd.NA).groupby(frame.icao24).ffill().fillna("UNKNOWN")
    previous = frame.groupby("icao24", sort=False).shift(1)
    new_flight = ((frame.timestamp - previous.timestamp).dt.total_seconds() > config["flight_gap_s"])
    new_flight |= frame.callsign != previous.callsign
    new_flight |= previous.timestamp.isna()
    frame["flight_segment"] = new_flight.groupby(frame.icao24).cumsum().astype(int)
    print(f"Checking {len(frame):,} nearby records...", flush=True)
    training, labels, audit, trajectories = [], [], [], []
    repeated_positions = 0
    source_tracks = 0
    for (icao24, segment), group in frame.groupby(["icao24", "flight_segment"], sort=False):
        source_tracks += 1
        # Positions with identical coordinates contain no new spatial observation.
        moved = group.latitude.ne(group.latitude.shift()) | group.longitude.ne(group.longitude.shift())
        repeated_positions += int((~moved).sum())
        track = group.loc[moved].reset_index(drop=True)
        candidate = ((track.distance_to_threshold_m.between(0, 30000)) & (track.cross_track_m.abs() < 500)
                     & (track.track_error_deg.abs() < 35) & (track.altitude < 10000))
        if int(candidate.sum()) < 3:
            continue
        callsign = str(track.callsign.iloc[0])
        flight_id = f"{icao24}_{track.timestamp.iloc[0].strftime('%Y%m%dT%H%M%S')}"
        example_id = f"EHAM18R_{flight_id}"
        common = {"example_id": example_id, "flight_id": flight_id, "icao24": icao24, "callsign": callsign}
        entry = {**common, "status": "rejected", "reason": "", "track_start_utc": track.timestamp.iloc[0].isoformat(),
                 "points": len(track), "snapshot_time_utc": "", "crossing_time_utc": ""}
        snapshot_index, reason, onset_index = first_confirmed_alignment(track, config)
        if reason:
            entry["reason"] = reason
            audit.append(entry)
            continue
        snapshot = track.iloc[snapshot_index]
        entry["snapshot_time_utc"] = snapshot.timestamp.isoformat()
        crossing_segment = first_threshold_segment(track, snapshot_index)
        if crossing_segment is None:
            entry["reason"] = "no_threshold_crossing"
            audit.append(entry)
            continue
        ia, ib = crossing_segment
        a, b = track.iloc[ia], track.iloc[ib]
        crossing, reason = check_crossing(a, b, config)
        if reason:
            entry["reason"] = reason
            audit.append(entry)
            continue
        crossing_time = crossing["crossing"]
        entry["crossing_time_utc"] = crossing_time.isoformat()
        remaining = (crossing_time - snapshot.timestamp).total_seconds()
        if not 0 < remaining <= config["max_remaining_time_s"]:
            entry["reason"] = "remaining_time_outside_window"
        elif (track.timestamp.iloc[snapshot_index:ib + 1].diff().dt.total_seconds().dropna() > config["max_observation_gap_s"]).any():
            entry["reason"] = "gap_between_snapshot_and_crossing"
        elif (track.cross_track_m.iloc[snapshot_index:ia + 1].abs() > 500).any() or (track.track_error_deg.iloc[snapshot_index:ia + 1].abs() > 45).any():
            entry["reason"] = "broken_or_missed_approach"
        else:
            after = track[track.timestamp.between(crossing_time, crossing_time + pd.Timedelta(seconds=config["landing_evidence_window_s"]))]
            climb = ((after.altitude > b.altitude + 250) & (after.vertical_rate > 600) & (after.groundspeed_mps > 45))
            if int(climb.sum()) >= 5:
                entry["reason"] = "observed_missed_approach"
            landing = has_landing_continuation(track, crossing_time, geometry, config, crossing["reported_speed_mps"])
            if landing is None and not entry["reason"]:
                entry["reason"] = "no_observed_landing_continuation"
        if entry["reason"]:
            audit.append(entry)
            continue
        try:
            features = snapshot_features(snapshot)
        except ValueError:
            entry["reason"] = "snapshot_missing_features"
            audit.append(entry)
            continue
        training.append({**common, "runway": "18R", "snapshot_time_utc": snapshot.timestamp.isoformat(),
                         **features, TARGET: round(remaining, 6)})
        landing_time, landing_method = landing
        label = {**common, "snapshot_time_utc": snapshot.timestamp.isoformat(),
                 "alignment_onset_observation_utc": track.timestamp.iloc[onset_index].isoformat(),
                 "crossing_time_utc": crossing_time.isoformat(),
                 "crossing_before_utc": a.timestamp.isoformat(), "crossing_after_utc": b.timestamp.isoformat(),
                 "crossing_gap_s": crossing["gap_s"],
                 "remaining_bracket_start_s": (a.timestamp - snapshot.timestamp).total_seconds(),
                 "remaining_bracket_end_s": (b.timestamp - snapshot.timestamp).total_seconds(),
                 "crossing_speed_ratio": crossing["speed_ratio"],
                 "crossing_derived_speed_mps": crossing["derived_speed_mps"],
                 "crossing_reported_speed_mps": crossing["reported_speed_mps"],
                 "crossing_latitude_deg": a.latitude + crossing["fraction"] * (b.latitude - a.latitude),
                 "crossing_longitude_deg": a.longitude + crossing["fraction"] * (b.longitude - a.longitude),
                 "landing_continuation_observed_utc": landing_time.isoformat(),
                 "landing_evidence_method": landing_method,
                 "label_method": "adsb_linear_interpolation", "geometry_status": geometry["geometry_status"]}
        labels.append(label)
        entry.update(status="accepted", reason="accepted")
        audit.append(entry)
        excerpt = track[track.timestamp.between(snapshot.timestamp - pd.Timedelta(seconds=config["viewer_history_s"]),
                                                crossing_time + pd.Timedelta(seconds=config["viewer_after_crossing_s"]))].copy()
        excerpt["example_id"] = example_id
        excerpt["time_from_snapshot_s"] = (excerpt.timestamp - snapshot.timestamp).dt.total_seconds()
        trajectories.append(excerpt[["example_id", "timestamp", "latitude", "longitude", "east_m", "north_m", "distance_to_threshold_m",
                                    "cross_track_m", "baro_altitude_m", "groundspeed_mps", "track", "vertical_rate_mps", "time_from_snapshot_s"]])
    if not training:
        pd.DataFrame(audit).to_csv(output / "audit.csv", index=False)
        raise RuntimeError("No approaches passed the approved rules; inspect prepared/audit.csv. Rules were not relaxed.")
    train = pd.DataFrame(training).sort_values("snapshot_time_utc").reset_index(drop=True)
    label_frame = pd.DataFrame(labels).set_index("example_id").loc[train.example_id].reset_index()
    audits = pd.DataFrame(audit)
    tracks = pd.concat(trajectories, ignore_index=True)
    train.to_csv(output / "training.csv", index=False)
    label_frame.to_csv(output / "labels_audit.csv", index=False)
    audits.to_csv(output / "audit.csv", index=False)
    audits[audits.status.eq("rejected")].to_csv(output / "rejected.csv", index=False)
    tracks.to_csv(output / "tracks.csv.gz", index=False, compression="gzip")
    schema = {"feature_columns": FEATURE_COLUMNS, "target_column": TARGET, "target_unit": "seconds",
              "group_column": "flight_id", "split_status": "unsplit",
              "metadata_columns": ["example_id", "flight_id", "icao24", "callsign", "runway", "snapshot_time_utc"],
              "warning": "Future trajectories and labels_audit.csv are for label construction/visual checking, never model inputs.",
              "units": {"latitude_deg": "WGS84 degrees", "longitude_deg": "WGS84 degrees", "baro_altitude_m": "barometric metres, pressure uncorrected",
                        "groundspeed_mps": "m/s", "track_deg": "true degrees", "vertical_rate_mps": "m/s, positive up",
                        "distance_to_threshold_m": "m, positive before threshold", "cross_track_m": "signed m",
                        "track_error_deg": "signed true degrees", "speed_toward_threshold_mps": "m/s", "baseline_eta_s": "seconds"}}
    summary = {"airport": "EHAM", "runway": "18R", "date": config["source_date"],
               "source_records": file.metadata.num_rows, "nearby_arrival_records": raw_nearby,
               "flight_tracks_checked": source_tracks, "candidate_tracks": len(audits), "accepted_approaches": len(train),
               "rejected_approaches": int(audits.status.eq("rejected").sum()), "rejection_counts": dict(Counter(audits.loc[audits.status.eq("rejected"), "reason"])),
               "consecutive_repeated_positions_removed": repeated_positions, "conflicting_timestamp_rows_removed": conflicting_rows,
               "trajectory_points_exported": len(tracks), "remaining_time_min_s": float(train[TARGET].min()),
               "remaining_time_median_s": float(train[TARGET].median()), "remaining_time_max_s": float(train[TARGET].max()),
               "split_status": "unsplit", "geometry_status": geometry["geometry_status"], "rules": config,
               "landing_evidence_counts": label_frame.landing_evidence_method.value_counts().to_dict(),
               "source_url": "https://zenodo.org/records/10074634",
               "limitations": ["One date only", "No lastposupdate or onground field; sampled states do not prove independent position freshness",
                               "Labels use retrospective interpolation, not independently measured exact crossing times",
                               "Exact March 2023 AIP/NOTAM cycle unverified; primary before/after geometry evidence agrees"]}
    for name, data in [("schema.json", schema), ("dataset_summary.json", summary), ("runway_geometry.json", geometry), ("rules.json", config)]:
        (output / name).write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    (output / "README.md").write_bytes((root / "docs/data_README.md").read_bytes())
    print(json.dumps(summary, indent=2), flush=True)
    return train, label_frame, tracks, geometry, summary
