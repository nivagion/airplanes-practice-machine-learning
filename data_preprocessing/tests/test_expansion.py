"""Expanded-source regression checks: elevation, runway causality and duplicates."""
from pathlib import Path
import sys
import tempfile
import unittest
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from approach.dataset import add_geometry, check_crossing, first_confirmed_alignment, read_json, has_landing_continuation
from approach.multi_airport import choose_runway, process_flight
from approach.runways import advance
from approach.sources import clean_observations, iter_prc2024
from approach.multi_airport import export_results


class ExpansionRules(unittest.TestCase):
    def setUp(self):
        self.rules = read_json(ROOT / 'config/approach.json')
        self.geo = {'threshold_latitude_deg': 40., 'threshold_longitude_deg': -75.,
                    'true_bearing_deg': 0., 'threshold_elevation_ft': 3000.,
                    'runway_direction': '36', 'airport_icao': 'TEST',
                    'geometry_id': 'test36', 'geometry_status': 'fixture',
                    'landing_distance_available_m': 3000.}

    def observations(self):
        n = 40
        along = -3000. + 70 * np.arange(n)
        points = [advance(40, -75, 0, a) for a in along]
        return pd.DataFrame({'timestamp': pd.date_range('2025-01-01T12:00:00Z', periods=n, freq='s'),
                             'latitude': [p[0] for p in points], 'longitude': [p[1] for p in points],
                             'altitude': 4000., 'groundspeed': 70 * 3600 / 1852,
                             'track': [30.] + [0.] * (n - 1), 'vertical_rate': -600.})

    def test_elevated_snapshot_and_crossing_use_same_height_proxy(self):
        t = add_geometry(self.observations(), self.geo)
        index, reason, _ = first_confirmed_alignment(t, {**self.rules, 'max_snapshot_altitude_ft': 1500})
        self.assertIsNone(reason)
        self.assertEqual(index, 11)
        a = t.iloc[0].copy(); b = a.copy()
        a['along_m'] = a['north_m'] = -35.; b['along_m'] = b['north_m'] = 35.
        a['east_m'] = b['east_m'] = 0.; a['cross_track_m'] = b['cross_track_m'] = 0.
        a['track_error_deg'] = b['track_error_deg'] = 0.
        a['altitude'] = b['altitude'] = 3050.; a['height_proxy_ft'] = b['height_proxy_ft'] = 50.
        b['timestamp'] = a.timestamp + pd.Timedelta(seconds=1)
        self.assertIsNone(check_crossing(a, b, self.rules)[1])
        a['height_proxy_ft'] = b['height_proxy_ft'] = 600.
        self.assertEqual(check_crossing(a, b, self.rules)[1], 'crossing_too_high')

    def test_below_sea_level_threshold_preserves_raw_pressure_altitude(self):
        geo = {**self.geo, 'threshold_elevation_ft': -13}
        t = add_geometry(self.observations(), geo)
        self.assertEqual(t.altitude.iloc[0], 4000.)
        self.assertAlmostEqual(t.baro_altitude_m.iloc[0], 4000 * .3048)
        self.assertAlmostEqual(t.height_proxy_ft.iloc[0], 4013.)

    def test_future_cannot_choose_runway(self):
        t = self.observations()
        opposite = {**self.geo, 'runway_direction': '18', 'true_bearing_deg': 180.}
        event, reason = choose_runway(t, [opposite, self.geo], self.rules, 25.)
        self.assertIsNone(reason)
        edited = t.copy()
        edited.loc[edited.index > event[4], ['latitude', 'longitude', 'track']] = [39.9, -75.1, 180.]
        new, _ = choose_runway(edited, [opposite, self.geo], self.rules, 25.)
        self.assertEqual(event[0], new[0])
        self.assertEqual(event[2]['runway_direction'], new[2]['runway_direction'])

    def test_parallel_geometry_tie_rejected_before_future_outcome(self):
        parallel = {**self.geo, 'runway_direction': '36R', 'threshold_longitude_deg': -75.00001}
        event, reason = choose_runway(self.observations(), [self.geo, parallel], self.rules, 25.)
        self.assertIsNone(event)
        self.assertEqual(reason, 'ambiguous_runway_at_snapshot')

    def test_conflicting_timestamps_and_stale_positions_are_removed(self):
        raw = self.observations().iloc[:3].copy()
        duplicate = raw.iloc[[0]].copy(); duplicate['longitude'] += .01
        stale = raw.iloc[[1]].copy(); stale['timestamp'] += pd.Timedelta(milliseconds=500)
        cleaned, conflicts, repeats = clean_observations(pd.concat([raw, duplicate, stale]))
        self.assertEqual(conflicts, 2)
        self.assertEqual(repeats, 1)
        self.assertEqual(len(cleaned), 2)

    def test_empty_flight_returns_audit_not_a_crash(self):
        common = {'flight_id': 'test', 'airport': 'TEST'}
        opts = {'processing_version': 'test', 'runway_ambiguity_margin_m': 25}
        row, label, audit, excerpt = process_flight((self.observations().iloc[:0], common, [self.geo], self.rules, opts))
        self.assertIsNone(row)
        self.assertEqual(audit['reason'], 'no_adsb_observations')

    def test_displacement_moves_threshold_in_landing_direction(self):
        lat, lon = advance(40., -75., 90., 270.)
        self.assertAlmostEqual(lat, 40.)
        self.assertGreater(lon, -75.)

    def test_irregular_observations_can_prove_full_six_second_landing_window(self):
        seconds = np.arange(0, 21, .7)
        frame = pd.DataFrame({'timestamp': pd.Timestamp('2025-01-01T12:00:00Z') + pd.to_timedelta(seconds, unit='s'),
                              'along_m': 350 + 70 * seconds, 'cross_track_m': 0.,
                              'groundspeed_mps': 75 - seconds, 'altitude': 3050.,
                              'height_proxy_ft': 50., 'vertical_rate': 0.})
        evidence = has_landing_continuation(frame, frame.timestamp.iloc[0], self.geo, self.rules, 75.)
        self.assertEqual(evidence[1], 'runway_deceleration_and_level_altitude')
        broken = frame.drop(index=range(7, 15)).reset_index(drop=True)
        short = broken[broken.timestamp < broken.timestamp.iloc[0] + pd.Timedelta(seconds=14)]
        self.assertIsNone(has_landing_continuation(short, short.timestamp.iloc[0], self.geo, self.rules, 75.))

    def test_midnight_files_join_into_one_publisher_flight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config').mkdir()
            (root / 'config/runways.json').write_text(json.dumps({'runways': [self.geo]}))
            pd.DataFrame({'flight_id': ['42'], 'ades': ['TEST'], 'date': ['2025-01-01'],
                          'aircraft_type': ['A320']}).to_csv(root / 'metadata.csv', index=False)
            for name, when in [('one.parquet', '2025-01-01T23:59:59Z'), ('two.parquet', '2025-01-02T00:00:00Z')]:
                frame = self.observations().iloc[:1].copy()
                frame['flight_id'] = 42
                frame['timestamp'] = pd.Timestamp(when)
                frame.to_parquet(root / name, index=False)
            source = {'dataset_id': 'fixture', 'metadata_path': 'metadata.csv', 'local_paths': ['one.parquet', 'two.parquet']}
            rows = list(iter_prc2024(root, source, {'TEST'}, self.rules))
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0][0]), 2)
            self.assertEqual(rows[0][1]['flight_id'], 'prc2024:42')
            self.assertEqual(rows[0][1]['source_file'], 'one.parquet;two.parquet')

    def test_zero_accepted_exports_have_readable_schema_and_audits(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / 'preprocessing'; root.mkdir()
            (parent / 'training/194_airplanes').mkdir(parents=True)
            (parent / 'training/194_airplanes/schema.json').write_text((ROOT.parent / 'training/194_airplanes/schema.json').read_text())
            options = {'output_directory': 'out', 'training_copy_directory': '../training/{row_count}_airplanes',
                       'processing_version': 'fixture', 'minimum_rows': 1000}
            summary = export_results(root, options, self.rules, {'runways': [self.geo], 'limitations': []},
                                     None, None, None, [], [], [], [], [])
            self.assertEqual(summary['accepted_approaches'], 0)
            self.assertFalse(summary['minimum_rows_met'])
            self.assertEqual(len(pd.read_csv(root / 'out/training.csv')), 0)
            self.assertIn('reason', pd.read_csv(root / 'out/audit.csv').columns)
            self.assertEqual((root / 'out/training.csv').read_bytes(),
                             (parent / 'training/0_airplanes/training.csv').read_bytes())

    def test_unlisted_publisher_flight_is_audited_without_airport_guessing(self):
        options = {'processing_version': 'fixture', 'runway_ambiguity_margin_m': 25.}
        common = {'flight_id': 'prc2024:missing', 'airport': 'UNKNOWN', 'source_metadata_missing': True}
        row, label, audit, excerpt = process_flight((self.observations().iloc[:0], common, [], self.rules, options))
        self.assertIsNone(row)
        self.assertEqual(audit['reason'], 'missing_flight_metadata')


if __name__ == '__main__':
    unittest.main()
