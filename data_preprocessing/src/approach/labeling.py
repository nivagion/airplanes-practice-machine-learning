"""Label a causally selected runway; future data only validates the outcome."""
from __future__ import annotations

import pandas as pd

from .dataset import (TARGET, check_crossing, first_threshold_segment,
                      has_landing_continuation, snapshot_features)


def label_approach(track, snapshot_index, onset_index, geometry, config):
    snapshot = track.iloc[snapshot_index]
    segment = first_threshold_segment(track, snapshot_index)
    if segment is None:
        return None, None, "no_threshold_crossing"
    ia, ib = segment
    a, b = track.iloc[ia], track.iloc[ib]
    crossing, reason = check_crossing(a, b, config)
    if reason:
        return None, None, reason
    crossing_time = crossing["crossing"]
    remaining = (crossing_time - snapshot.timestamp).total_seconds()
    if not 0 < remaining <= config["max_remaining_time_s"]:
        return None, None, "remaining_time_outside_window"
    between = track.iloc[snapshot_index:ib + 1]
    if (between.timestamp.diff().dt.total_seconds().dropna() > config["max_observation_gap_s"]).any():
        return None, None, "gap_between_snapshot_and_crossing"
    if (between.cross_track_m.abs() > 500).any() or (between.track_error_deg.abs() > 45).any():
        return None, None, "broken_or_missed_approach"
    after = track[track.timestamp.between(crossing_time, crossing_time + pd.Timedelta(seconds=config["landing_evidence_window_s"]))]
    climb = ((after.altitude > b.altitude + 250) & (after.vertical_rate > 600) & (after.groundspeed_mps > 45))
    if int(climb.sum()) >= 5:
        return None, None, "observed_missed_approach"
    landing = has_landing_continuation(track, crossing_time, geometry, config, crossing["reported_speed_mps"])
    if landing is None:
        return None, None, "no_observed_landing_continuation"
    try:
        features = snapshot_features(snapshot)
    except ValueError:
        return None, None, "snapshot_missing_features"
    if 'threshold_elevation_ft' in geometry:
        features.update({"threshold_latitude_deg": geometry["threshold_latitude_deg"],
                         "threshold_longitude_deg": geometry["threshold_longitude_deg"],
                         "runway_true_bearing_deg": geometry["true_bearing_deg"],
                         "threshold_elevation_m": geometry["threshold_elevation_ft"] * .3048,
                         "baro_height_proxy_m": snapshot.height_proxy_ft * .3048})
    features[TARGET] = round(remaining, 6)
    landing_time, landing_method = landing
    label = {"alignment_onset_observation_utc": track.timestamp.iloc[onset_index].isoformat(),
             "crossing_time_utc": crossing_time.isoformat(),
             "crossing_before_utc": a.timestamp.isoformat(), "crossing_after_utc": b.timestamp.isoformat(),
             "crossing_before_latitude_deg": float(a.latitude), "crossing_before_longitude_deg": float(a.longitude),
             "crossing_after_latitude_deg": float(b.latitude), "crossing_after_longitude_deg": float(b.longitude),
             "crossing_gap_s": crossing["gap_s"], "crossing_speed_ratio": crossing["speed_ratio"],
             "crossing_derived_speed_mps": crossing["derived_speed_mps"],
             "crossing_reported_speed_mps": crossing["reported_speed_mps"],
             "remaining_bracket_start_s": (a.timestamp - snapshot.timestamp).total_seconds(),
             "remaining_bracket_end_s": (b.timestamp - snapshot.timestamp).total_seconds(),
             "crossing_latitude_deg": a.latitude + crossing["fraction"] * (b.latitude - a.latitude),
             "crossing_longitude_deg": a.longitude + crossing["fraction"] * (b.longitude - a.longitude),
             "landing_continuation_observed_utc": landing_time.isoformat(),
             "landing_evidence_method": landing_method, "label_method": "adsb_linear_interpolation"}
    return features, label, None
