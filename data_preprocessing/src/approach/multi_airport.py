"""Configurable multi-source extraction, causal runway selection and audit exports."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from .dataset import FEATURE_COLUMNS, TARGET, add_geometry, first_alignment_event, local_xy, read_json
from .labeling import label_approach
from .sources import clean_observations, iter_source

EXTRA_FEATURES = ['threshold_latitude_deg', 'threshold_longitude_deg', 'runway_true_bearing_deg',
                  'threshold_elevation_m', 'baro_height_proxy_m']
METADATA = ['example_id', 'flight_id', 'dataset_id', 'source_flight_id', 'icao24', 'callsign',
            'airport', 'runway', 'snapshot_time_utc', 'source_date', 'source_file', 'aircraft_type',
            'geometry_id', 'geometry_status', 'vertical_quality', 'identity_status', 'unit_quality', 'processing_version']


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def choose_runway(track, geometries, rules, ambiguity_margin_m):
    """Choose the earliest sustained alignment, including unusable first events.

    Events are computed independently, but future crossings, landing evidence and
    publisher runway labels never enter the ranking. At the first confirmation
    time, competing events are scored using only the current lateral distance.
    """
    events = []
    for geometry in geometries:
        projected = add_geometry(track, geometry)
        index, reason, onset = first_alignment_event(projected, rules)
        if index is not None:
            events.append((projected.timestamp.iloc[index], abs(projected.cross_track_m.iloc[index]),
                           geometry, projected, index, reason, onset))
    if not events:
        return None, 'no_confirmed_alignment'
    first_time = min(e[0] for e in events)
    candidates = sorted([e for e in events if e[0] == first_time], key=lambda e: e[1])
    if len(candidates) > 1 and candidates[1][1] - candidates[0][1] < ambiguity_margin_m:
        return None, 'ambiguous_runway_at_snapshot'
    return candidates[0], candidates[0][5]


def process_flight(task):
    raw, common, geometries, rules, options = task
    common = {**common, 'processing_version': options['processing_version'],
              'vertical_quality': 'uncorrected_pressure_minus_threshold_elevation_proxy'}
    audit = {**common, 'status': 'rejected', 'reason': '', 'runway': '', 'snapshot_time_utc': '',
             'conflicting_timestamp_rows_removed': 0, 'repeated_positions_removed': 0}
    if common.get('source_metadata_missing'):
        audit['reason'] = 'missing_flight_metadata'
        return None, None, audit, None
    if not geometries:
        audit['reason'] = 'missing_runway_geometry'
        return None, None, audit, None
    if raw.empty:
        audit['reason'] = 'no_adsb_observations'
        return None, None, audit, None
    # Broad geographic context, derived from registry coordinates, not EHAM bounds.
    geometry = geometries[0]
    lat, lon = geometry['threshold_latitude_deg'], geometry['threshold_longitude_deg']
    radius = rules['context_radius_m']
    near = raw.latitude.between(lat - radius / 110000, lat + radius / 110000) & raw.longitude.between(
        lon - radius / (110000 * np.cos(np.deg2rad(lat))), lon + radius / (110000 * np.cos(np.deg2rad(lat))))
    track, conflicts, repeats = clean_observations(raw.loc[near])
    audit.update(conflicting_timestamp_rows_removed=conflicts, repeated_positions_removed=repeats, points=len(track))
    if track.empty:
        audit['reason'] = 'no_usable_airport_observations'
        return None, None, audit, None
    event, reason = choose_runway(track, geometries, rules, options['runway_ambiguity_margin_m'])
    if event is None:
        audit['reason'] = reason
        return None, None, audit, None
    time, _, geometry, track, index, _, onset = event
    metadata = {**common, 'example_id': f"{common['flight_id']}:{common['airport']}:{geometry['runway_direction']}",
                'runway': geometry['runway_direction'], 'snapshot_time_utc': time.isoformat(),
                'geometry_id': geometry['geometry_id'], 'geometry_status': geometry['geometry_status']}
    audit.update(metadata)
    if reason:
        audit['reason'] = reason
        return None, None, audit, None
    features, label, reason = label_approach(track, index, onset, geometry, rules)
    if reason:
        audit['reason'] = reason
        return None, None, audit, None
    audit.update(status='accepted', reason='accepted')
    crossing_time = pd.Timestamp(label['crossing_time_utc'])
    excerpt = track[track.timestamp.between(time - pd.Timedelta(seconds=rules['viewer_history_s']),
                                           crossing_time + pd.Timedelta(seconds=rules['viewer_after_crossing_s']))].copy()
    excerpt['example_id'] = metadata['example_id']
    excerpt['time_from_snapshot_s'] = (excerpt.timestamp - time).dt.total_seconds()
    excerpt = excerpt[['example_id', 'timestamp', 'latitude', 'longitude', 'altitude', 'groundspeed',
                       'track', 'vertical_rate', 'height_proxy_ft', 'east_m', 'north_m',
                       'distance_to_threshold_m', 'cross_track_m', 'time_from_snapshot_s']]
    return {**metadata, **features}, {**metadata, **label}, audit, excerpt


def verify_file(path, checksum):
    algorithm, expected = checksum.split(':', 1)
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, algorithm).hexdigest()
    if actual != expected:
        raise ValueError(f'Integrity mismatch: {path}')
    return actual


def build_expanded(root: Path, workers=4, source_ids=None, minimum_rows=None, output_dir=None, training_dir=None, reuse_prepared=None):
    options = read_json(root / 'config/expansion.json')
    rules = read_json(root / options['rules_file'])
    sources = read_json(root / options['source_manifest'])['sources']
    if source_ids:
        unknown = set(source_ids) - {s['dataset_id'] for s in sources}
        if unknown:
            raise ValueError(f'Unknown sources: {sorted(unknown)}')
        sources = [s for s in sources if s['dataset_id'] in source_ids]
    geometries = read_json(root / options['runway_registry'])
    by_airport = {}
    for geometry in geometries['runways']:
        by_airport.setdefault(geometry['airport_icao'], []).append(geometry)
    out = root / (output_dir or options['output_directory'])
    out.mkdir(parents=True, exist_ok=True)
    training, labels, audits, tracks, provenance = [], [], [], [], []
    seen = set()
    if reuse_prepared:
        previous = Path(reuse_prepared)
        saved_sources = read_json(previous / 'sources.json')['sources']
        saved_registry = read_json(previous / 'runway_registry.json')
        saved_rules = read_json(previous / 'rules.json')
        saved_schema = read_json(previous / 'schema.json')
        if saved_registry != geometries or saved_rules != rules or saved_schema['processing_version'] != options['processing_version']:
            raise ValueError('Cannot reuse outputs from different geometry, rules or processing version')
        reuse_ids = {s['dataset_id'] for s in saved_sources}
        wanted = {s['dataset_id']: s for s in sources}
        if not reuse_ids <= set(wanted):
            raise ValueError('Reused sources must all be in this build manifest')
        for saved in saved_sources:
            saved = {k: v for k, v in saved.items() if k != 'input_checksum_verified'}
            if saved != wanted[saved['dataset_id']]:
                raise ValueError('Reused source provenance differs from manifest')
        for name, checksum in read_json(previous / 'dataset_summary.json')['output_checksums'].items():
            verify_file(previous / name, checksum)
        training.extend(pd.read_csv(previous / 'training.csv', keep_default_na=False).to_dict('records'))
        labels.extend(pd.read_csv(previous / 'labels_audit.csv', keep_default_na=False).to_dict('records'))
        previous_audits = pd.read_csv(previous / 'audit.csv', keep_default_na=False)
        audits.extend(previous_audits.to_dict('records'))
        seen.update(previous_audits.flight_id)
        tracks.append(pd.read_csv(previous / 'tracks.csv.gz'))
        provenance.extend(saved_sources)
        sources = [s for s in sources if s['dataset_id'] not in reuse_ids]
        print(f'Reusing {len(training):,} verified rows from {len(reuse_ids)} sources.', flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for source in sources:
            if source.get('local_paths'):
                for name, checksum in zip(source['local_paths'], source['checksums'], strict=True):
                    verify_file(root / name, checksum)
            else:
                primary = root / source.get('archive_path', source.get('local_path', ''))
                if not primary.is_file():
                    raise FileNotFoundError(f'{primary}; run acquire_data.py first')
                checksum = source.get('archive_checksum', source.get('checksum'))
                verify_file(primary, checksum)
            if source.get('metadata_path'):
                verify_file(root / source['metadata_path'], source['metadata_checksum'])
            provenance.append({**source, 'input_checksum_verified': True})
            def tasks():
                for frame, common in iter_source(root, source, set(by_airport), rules):
                    # Publisher IDs shared across PRC phases must never count twice.
                    key = common['flight_id']
                    if key in seen:
                        raise ValueError(f'Duplicate flight across sources: {key}')
                    seen.add(key)
                    yield frame, common, by_airport.get(common['airport'], []), rules, options
            print(f"Processing {source['dataset_id']}...", flush=True)
            count = accepted = 0
            # Bounded batches avoid queuing the entire source's raw trajectories.
            iterator = iter(tasks())
            while True:
                batch = []
                for _ in range(64):
                    try:
                        batch.append(next(iterator))
                    except StopIteration:
                        break
                if not batch:
                    break
                for row, label, audit, excerpt in pool.map(process_flight, batch, chunksize=4):
                    audits.append(audit)
                    count += 1
                    if row is not None:
                        training.append(row)
                        labels.append(label)
                        tracks.append(excerpt)
                        accepted += 1
                if count % 512 == 0 or len(batch) < 64:
                    print(f"  {count:,} flights checked; {accepted:,} accepted", flush=True)
    return export_results(root, options, rules, geometries, output_dir, training_dir,
                          minimum_rows, training, labels, audits, tracks, provenance)


def export_results(root, options, rules, geometries, output_dir, training_dir,
                   minimum_rows, training, labels, audits, tracks, provenance):
    out = root / (output_dir or options['output_directory'])
    out.mkdir(parents=True, exist_ok=True)
    train = pd.DataFrame(training, columns=METADATA + FEATURE_COLUMNS + EXTRA_FEATURES + [TARGET])
    train = train.sort_values('snapshot_time_utc').reset_index(drop=True)
    label_frame = pd.DataFrame(labels)
    audits = pd.DataFrame(audits) if audits else pd.DataFrame(columns=METADATA + ['status', 'reason'])
    if len(train):
        label_frame = label_frame.set_index('example_id').loc[train.example_id].reset_index()
        if not train.example_id.is_unique or not train.flight_id.is_unique:
            raise ValueError('Duplicate accepted flight/approach')
        if not np.isfinite(train[FEATURE_COLUMNS + EXTRA_FEATURES + [TARGET]].to_numpy()).all():
            raise ValueError('Nonfinite training values')
    else:
        label_frame = pd.DataFrame(columns=METADATA + ['crossing_time_utc', 'crossing_gap_s'])
    track_frame = pd.concat(tracks, ignore_index=True) if tracks else pd.DataFrame(columns=['example_id', 'timestamp'])
    for name, frame in [('training.csv', train), ('labels_audit.csv', label_frame), ('audit.csv', audits)]:
        frame.to_csv(out / name, index=False)
    rejected = audits[audits.status.eq('rejected')] if len(audits) else audits
    rejected.to_csv(out / 'rejected.csv', index=False)
    track_frame.to_csv(out / 'tracks.csv.gz', index=False, compression='gzip')
    # Schema keeps the existing eleven features in the same order, then adds
    # target runway context. Identifiers and retrospective label evidence stay out.
    base_schema = read_json(root.parent / 'training/194_airplanes/schema.json')
    schema = {**base_schema, 'feature_columns': FEATURE_COLUMNS + EXTRA_FEATURES,
              'metadata_columns': METADATA, 'processing_version': options['processing_version'],
              'vertical_quality': 'baro_height_proxy_m is NOT calibrated height above ground',
              'units': {**base_schema['units'], 'threshold_latitude_deg': 'WGS84 degrees',
                        'threshold_longitude_deg': 'WGS84 degrees', 'runway_true_bearing_deg': 'true degrees',
                        'threshold_elevation_m': 'metres AMSL, runway-end proxy where displaced',
                        'baro_height_proxy_m': 'uncorrected pressure-altitude metres minus threshold-elevation metres'}}
    threshold = minimum_rows if minimum_rows is not None else options['minimum_rows']
    summary = {'processing_version': options['processing_version'], 'accepted_approaches': len(train),
               'rejected_approaches': len(rejected), 'flights_checked': len(audits),
               'minimum_rows': threshold, 'minimum_rows_met': len(train) >= threshold, 'split_status': 'unsplit',
               'airport_count': int(train.airport.nunique()),
               'airport_runway_count': len(train[['airport', 'runway']].drop_duplicates()),
               'accepted_by_source': train.dataset_id.value_counts().to_dict(),
               'accepted_by_airport': train.airport.value_counts().to_dict(),
               'rejection_counts': dict(Counter(rejected.reason)) if len(rejected) else {},
               'trajectory_points_exported': len(track_frame),
               'snapshot_dates': sorted(pd.to_datetime(train.snapshot_time_utc, utc=True, format='ISO8601').dt.strftime('%Y-%m-%d').unique().tolist()),
               'limitations': geometries['limitations'] + [
                   'PRC v1 ADS-B units are empirically inferred; published SI-unit documentation conflicts with recorded values.',
                   'Pressure altitude is not corrected with QNH; relative height is a proxy.',
                   'ADS-B position/timestamp noise remains; crossing interpolation is not exact measured truth.',
                   'One conservative first approach per source flight; a rejected go-around is not replaced by its later successful approach.',
                   'Historical runway changes/closures are not verified for community geometry.',
                   'No last-position-update age or onground evidence; source sampling is not independent proof of freshness.',
                   'No cross-collection physical-flight deduplication without aircraft identity; included collections have disjoint years.']}
    coverage = audits.groupby(['dataset_id', 'airport', 'runway', 'status', 'reason'], dropna=False).size().rename('rows').reset_index() if len(audits) else pd.DataFrame()
    coverage.to_csv(out / 'coverage.csv', index=False)
    summary['output_checksums'] = {}
    for name in ['training.csv', 'labels_audit.csv', 'audit.csv', 'tracks.csv.gz', 'coverage.csv']:
        with (out / name).open('rb') as stream:
            summary['output_checksums'][name] = 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()
    write_json(out / 'schema.json', schema)
    write_json(out / 'dataset_summary.json', summary)
    write_json(out / 'runway_registry.json', geometries)
    write_json(out / 'sources.json', {'sources': provenance})
    write_json(out / 'rules.json', rules)
    copy_path = (training_dir or options['training_copy_directory']).format(row_count=len(train))
    copy_dir = (root / copy_path).resolve()
    if copy_dir == (root.parent / 'training/194_airplanes').resolve():
        raise ValueError('The expanded export must not overwrite the 194-row baseline folder')
    copy_dir.mkdir(parents=True, exist_ok=True)
    for name in ['training.csv', 'schema.json', 'dataset_summary.json']:
        shutil.copyfile(out / name, copy_dir / name)
    print(f"Ready: {len(train):,} accepted approaches across {summary['airport_count']} airports; "
          f"minimum {threshold:,} {'met' if summary['minimum_rows_met'] else 'not met'}.", flush=True)
    print(f"Training copy: {copy_dir / 'training.csv'}", flush=True)
    print(f"Audits and provenance: {out}", flush=True)
    return summary
