"""Explicit source adapters. Shared code consumes feet, knots, ft/min and UTC."""
from __future__ import annotations

import zipfile
import json
from pathlib import Path

import pandas as pd
import numpy as np
import pyarrow.parquet as pq


def clean_observations(frame):
    frame = frame.copy()
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True)
    numeric = ['latitude', 'longitude', 'altitude', 'groundspeed', 'track', 'vertical_rate']
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    frame = frame.dropna(subset=['timestamp', 'latitude', 'longitude', 'groundspeed'])
    frame = frame[frame.latitude.between(-90, 90) & frame.longitude.between(-180, 180)
                  & frame.groundspeed.between(0, 700)
                  & (frame.altitude.isna() | frame.altitude.between(-2000, 60000))]
    frame = frame.sort_values('timestamp', kind='stable')
    conflict = frame.groupby('timestamp')[['latitude', 'longitude']].transform('nunique').max(axis=1).gt(1)
    conflicting = int(conflict.sum())
    frame = frame.loc[~conflict].drop_duplicates('timestamp').copy()
    moved = frame.latitude.ne(frame.latitude.shift()) | frame.longitude.ne(frame.longitude.shift())
    repeated = int((~moved).sum())
    return frame.loc[moved].reset_index(drop=True), conflicting, repeated


def iter_prc(root: Path, source: dict, airports):
    metadata = pd.read_parquet(root / source['metadata_path'])
    with zipfile.ZipFile(root / source['archive_path']) as archive:
        names = {Path(n).stem: n for n in archive.namelist() if n.endswith('.parquet')}
        for row in metadata.sort_values('flight_id').to_dict('records'):
            fid = row['flight_id']
            if fid not in names:
                raise ValueError(f'Missing published trajectory: {fid}')
            if row['destination_icao'] in airports:
                with archive.open(names[fid]) as stream:
                    frame = pq.read_table(stream).to_pandas()
            else:
                frame = pd.DataFrame(columns=['source'])
            # ACARS timestamps/positions are not interchangeable with ADS-B.
            frame = frame[frame.source.eq('adsb')].copy()
            # v1's published SI-unit description conflicts with the actual ADS-B
            # values. This explicit, audited inference is pinned to this version.
            # Preserve nominal feet (tiny 0.999744 quantization factor uncorrected),
            # knots and ft/min. Never infer units dynamically per flight.
            if source['unit_policy'] != 'prc2025_v1_empirically_inferred_ft_kt_fpm':
                raise ValueError('Unaudited PRC unit policy')
            yield frame, {'dataset_id': source['dataset_id'], 'source_flight_id': fid,
                          'flight_id': f"prc2025:{fid}", 'icao24': '', 'callsign': '',
                          'airport': row['destination_icao'], 'aircraft_type': row['aircraft_type'],
                          'source_file': names[fid], 'source_date': row['flight_date'],
                          'identity_status': 'publisher_flight_id_aircraft_identity_unavailable',
                          'unit_quality': 'empirical_aviation_units_publisher_SI_description_conflicts'}


def iter_dorbolo(root: Path, source: dict, airports, gap_s):
    columns = ['timestamp', 'latitude', 'longitude', 'altitude', 'groundspeed', 'track',
               'vertical_rate', 'icao24', 'callsign', 'destination']
    airport = source['airport']
    if airport not in airports:
        return
    frame = pq.read_table(root / source['local_path'], columns=columns,
                          filters=[('destination', '=', airport)]).to_pandas()
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True)
    frame['icao24'] = frame.icao24.fillna('').str.strip().str.lower()
    frame = frame[frame.icao24.ne('')].sort_values(['icao24', 'timestamp'], kind='stable')
    frame['callsign'] = frame.callsign.fillna('').str.strip().replace('', pd.NA).groupby(frame.icao24).ffill().fillna('UNKNOWN')
    previous = frame.groupby('icao24').shift(1)
    new = previous.timestamp.isna() | ((frame.timestamp - previous.timestamp).dt.total_seconds() > gap_s) | frame.callsign.ne(previous.callsign)
    frame['segment'] = new.groupby(frame.icao24).cumsum()
    for (icao24, segment), group in frame.groupby(['icao24', 'segment'], sort=False):
        fid = f"{icao24}_{group.timestamp.iloc[0].strftime('%Y%m%dT%H%M%S')}"
        yield group, {'dataset_id': source['dataset_id'], 'source_flight_id': fid,
                      'flight_id': f'dorbolo20230315:{fid}', 'icao24': icao24,
                      'callsign': str(group.callsign.iloc[0]), 'airport': airport,
                      'aircraft_type': '', 'source_file': source['local_path'],
                      'source_date': source['source_date'], 'identity_status': 'icao24_callsign_time_gap_segment',
                      'unit_quality': 'documented_ft_kt_fpm'}


def iter_source(root, source, airports, rules):
    if source['adapter'] == 'prc2025':
        yield from iter_prc(root, source, airports)
    elif source['adapter'] == 'dorbolo':
        yield from iter_dorbolo(root, source, airports, rules['flight_gap_s'])
    elif source['adapter'] == 'prc2024':
        yield from iter_prc2024(root, source, airports, rules)
    else:
        raise ValueError(f"Unknown source adapter {source['adapter']}")


def iter_prc2024(root, source, airports, rules):
    """Join flight metadata and concatenate adjoining UTC files before grouping.

    Keep just the destination's broad context to bound memory. The complete
    observation sequence around midnight survives; one flight remains one group.
    """
    metadata = pd.read_csv(root / source['metadata_path'], dtype={'flight_id': str},
                           usecols=['flight_id', 'ades', 'date', 'aircraft_type'])
    if not metadata.flight_id.is_unique:
        raise ValueError('Duplicate PRC2024 metadata flight IDs')
    registry = json.loads((root / 'config/runways.json').read_text())['runways']
    airport_coords = {g['airport_icao']: (g['threshold_latitude_deg'], g['threshold_longitude_deg']) for g in registry}
    metadata = metadata.set_index('flight_id')
    columns = ['flight_id', 'timestamp', 'latitude', 'longitude', 'altitude', 'groundspeed', 'track', 'vertical_rate']
    pieces = []
    present = set()
    for name in source['local_paths']:
        file = pq.ParquetFile(root / name)
        for batch in file.iter_batches(batch_size=250000, columns=columns):
            frame = batch.to_pandas()
            frame['flight_id'] = frame.flight_id.astype(str)
            present.update(frame.flight_id.unique())
            destination = frame.flight_id.map(metadata.ades)
            lat = destination.map({k: v[0] for k, v in airport_coords.items()})
            lon = destination.map({k: v[1] for k, v in airport_coords.items()})
            radius = rules['context_radius_m'] / 110000
            nearby = (frame.latitude - lat).abs().le(radius) & (frame.longitude - lon).abs().le(radius / np.cos(np.deg2rad(lat)))
            if nearby.any():
                frame = frame.loc[nearby].copy()
                frame['source_file'] = name
                pieces.append(frame)
        print(f'  Loaded {Path(name).name}; {len(present):,} flight IDs seen across days', flush=True)
    missing = present - set(metadata.index)
    joined = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=columns + ['source_file'])
    groups = {key: group for key, group in joined.groupby('flight_id', sort=False)}
    for fid in sorted(present):
        if fid in missing:
            yield pd.DataFrame(columns=columns), {'dataset_id': source['dataset_id'], 'source_flight_id': fid,
                'flight_id': f'prc2024:{fid}', 'airport': 'UNKNOWN', 'source_date': '', 'aircraft_type': '',
                'source_file': ';'.join(source['local_paths']), 'icao24': '', 'callsign': '',
                'identity_status': 'publisher_flight_id_absent_from_metadata', 'unit_quality': 'documented_ft_kt_fpm',
                'source_metadata_missing': True}
            continue
        row = metadata.loc[fid]
        frame = groups.get(fid, pd.DataFrame(columns=columns + ['source_file']))
        yield frame, {'dataset_id': source['dataset_id'], 'source_flight_id': fid,
                      'flight_id': f'prc2024:{fid}', 'airport': row.ades,
                      'source_date': row.date, 'aircraft_type': row.aircraft_type,
                      'source_file': ';'.join(sorted(frame.source_file.unique())) if len(frame) else ';'.join(source['local_paths']),
                      'icao24': '', 'callsign': '', 'identity_status': 'publisher_flight_id_aircraft_identity_obfuscated',
                      'unit_quality': 'documented_ft_kt_fpm'}
