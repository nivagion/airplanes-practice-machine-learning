"""Meaningful geometry, time-gap and future-information checks."""
from pathlib import Path
import sys
import unittest
import math

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from approach.dataset import (read_json, local_xy, first_confirmed_alignment,
                              check_crossing, snapshot_features, has_landing_continuation)


def alignment_track():
    times = pd.date_range("2023-03-15T12:00:00Z", periods=31, freq="s")
    frame = pd.DataFrame({"timestamp": times, "distance_to_threshold_m": 3000-np.arange(31)*70,
                          "cross_track_m": [120]+[50]*30, "track_error_deg": 0.,
                          "groundspeed_mps": 70., "altitude": 2000., "latitude": 52.4,
                          "longitude": 4.71, "baro_altitude_m": 609.6, "track": 183.2,
                          "vertical_rate_mps": -3., "speed_toward_threshold_mps": 70.})
    return frame


class LabelRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = read_json(ROOT / "config/approach.json")
        cls.geo = read_json(ROOT / "data_research/source_evidence/eham_18r_historical_geometry_audit.json")

    def test_displaced_threshold_is_not_pavement_end(self):
        east, north = local_xy(self.geo["threshold_latitude_deg"], self.geo["threshold_longitude_deg"], self.geo)
        self.assertAlmostEqual(float(east), 0., places=7)
        self.assertAlmostEqual(float(north), 0., places=7)
        physical = self.geo["north_physical_end_current_aip"]
        x, y = local_xy(physical["latitude_deg"], physical["longitude_deg"], self.geo)
        h = math.radians(self.geo["true_bearing_deg"])
        along = x*math.sin(h)+y*math.cos(h)
        self.assertAlmostEqual(float(along), -270., delta=.5)

    def test_confirmation_is_not_backdated(self):
        track = alignment_track()
        index, reason, onset = first_confirmed_alignment(track, self.config)
        self.assertIsNone(reason)
        self.assertEqual(onset, 1)
        self.assertEqual(index, 11)
        self.assertEqual((track.timestamp.iloc[index]-track.timestamp.iloc[onset]).total_seconds(), 10)

    def test_initially_aligned_recording_rejected(self):
        track = alignment_track().iloc[1:].reset_index(drop=True)
        index, reason, _ = first_confirmed_alignment(track, self.config)
        self.assertIsNone(index)
        self.assertEqual(reason, "missing_alignment_onset")

    def test_gap_cannot_be_used_as_alignment_evidence(self):
        track = alignment_track().drop(index=[8,9,10,11]).reset_index(drop=True)
        index, reason, _ = first_confirmed_alignment(track, self.config)
        self.assertIsNone(reason)
        self.assertEqual(track.timestamp.iloc[index].second, 22)

    def test_future_changes_do_not_change_snapshot(self):
        track = alignment_track()
        index, _, _ = first_confirmed_alignment(track, self.config)
        features = snapshot_features(track.iloc[index])
        edited = track.copy()
        edited.loc[edited.index > index, ["cross_track_m", "track_error_deg", "groundspeed_mps"]] = [900, 90, 200]
        new_index, _, _ = first_confirmed_alignment(edited, self.config)
        self.assertEqual(index, new_index)
        self.assertEqual(features, snapshot_features(edited.iloc[new_index]))

    def segment(self, gap=1, displacement=70):
        h = math.radians(self.geo["true_bearing_deg"])
        a = pd.Series({"timestamp": pd.Timestamp("2023-03-15T12:00:00Z"), "along_m": -displacement/2,
                       "east_m": -displacement/2*math.sin(h), "north_m": -displacement/2*math.cos(h),
                       "cross_track_m": 0., "track_error_deg": 0., "altitude": 100., "groundspeed_mps": 70.})
        b = a.copy()
        b["timestamp"] += pd.Timedelta(seconds=gap)
        for name in ["along_m", "east_m", "north_m"]:
            b[name] = -a[name]
        return a,b

    def test_crossing_interpolation_from_observed_bracket(self):
        a,b = self.segment()
        result, reason = check_crossing(a,b,self.config)
        self.assertIsNone(reason)
        self.assertAlmostEqual((result["crossing"]-a.timestamp).total_seconds(), .5)
        self.assertTrue(a.timestamp < result["crossing"] < b.timestamp)

    def test_crossing_gap_and_impossible_speed_rejected(self):
        a,b = self.segment(gap=4, displacement=280)
        self.assertEqual(check_crossing(a,b,self.config)[1], "crossing_gap_too_large")
        a,b = self.segment(displacement=700)
        self.assertEqual(check_crossing(a,b,self.config)[1], "crossing_speed_inconsistent")

    def test_level_runway_deceleration_differs_from_climbing_goaround(self):
        t = np.arange(21)
        ground = pd.DataFrame({"timestamp": pd.date_range("2023-03-15T12:00:00Z", periods=21, freq="s"),
                               "along_m": 10 + 75*t - .5*t*t, "cross_track_m": 0.,
                               "groundspeed_mps": 75-t, "altitude": 100., "vertical_rate": 0.})
        event = has_landing_continuation(ground, ground.timestamp.iloc[0], self.geo, self.config,75)
        self.assertEqual(event[1], "runway_deceleration_and_level_altitude")
        climbing = ground.copy()
        climbing["altitude"] = 100+20*t
        climbing["vertical_rate"] = 1200.
        self.assertIsNone(has_landing_continuation(climbing, climbing.timestamp.iloc[0],self.geo,self.config,75))


if __name__ == "__main__":
    unittest.main()
