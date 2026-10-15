"""Build a frozen, directional threshold registry from runway-end coordinates."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .dataset import local_xy, read_json


def advance(latitude, longitude, bearing, distance):
    """Short WGS84 displacement; adequate for a runway's displaced threshold."""
    lat = math.radians(latitude)
    e2, a = 6.69437999014e-3, 6378137.0
    n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    m = a * (1 - e2) / (1 - e2 * math.sin(lat) ** 2) ** 1.5
    angle = math.radians(bearing)
    return (latitude + math.degrees(distance * math.cos(angle) / m),
            longitude + math.degrees(distance * math.sin(angle) / (n * math.cos(lat))))


def make_registry(csv_path: Path, airports, root: Path):
    frame = pd.read_csv(csv_path, keep_default_na=False)
    entries = []
    skipped = []
    for row in frame[frame.airport_ident.isin(airports)].to_dict('records'):
        if str(row['closed']) == '1' or row['surface'] not in {'ASP', 'CON', 'ASPH', 'CONC'}:
            continue
        for end, opposite in [('le', 'he'), ('he', 'le')]:
            required = [f'{end}_latitude_deg', f'{end}_longitude_deg', f'{opposite}_latitude_deg',
                        f'{opposite}_longitude_deg', f'{end}_elevation_ft', 'length_ft', 'width_ft']
            if any(row[k] == '' for k in required):
                skipped.append({'airport': row['airport_ident'], 'runway': row[f'{end}_ident'], 'reason': 'missing_geometry_or_elevation'})
                continue
            lat, lon = float(row[f'{end}_latitude_deg']), float(row[f'{end}_longitude_deg'])
            base = {'threshold_latitude_deg': lat, 'threshold_longitude_deg': lon}
            east, north = local_xy(float(row[f'{opposite}_latitude_deg']), float(row[f'{opposite}_longitude_deg']), base)
            bearing = math.degrees(math.atan2(east, north)) % 360
            displacement = float(row[f'{end}_displaced_threshold_ft'] or 0) * .3048
            thlat, thlon = advance(lat, lon, bearing, displacement)
            length, width = float(row['length_ft']) * .3048, float(row['width_ft']) * .3048
            if not all(np.isfinite(v) for v in [lat, lon, bearing, length, width]) or length - displacement < 1000:
                continue
            entries.append({'geometry_id': f"ourairports_20261014_{row['airport_ident']}_{row[f'{end}_ident']}",
                            'airport_icao': row['airport_ident'], 'runway_direction': row[f'{end}_ident'],
                            'threshold_latitude_deg': thlat, 'threshold_longitude_deg': thlon,
                            'true_bearing_deg': bearing, 'threshold_elevation_ft': float(row[f'{end}_elevation_ft']),
                            'runway_width_m': width, 'physical_runway_length_m': length,
                            'landing_distance_available_m': length - displacement,
                            'threshold_displacement_m': displacement,
                            'geometry_status': 'community_runway_ends_displacement_applied_historical_validity_unverified',
                            'geometry_source_url': 'https://ourairports.com/data/',
                            'geometry_snapshot_date': '2026-10-14',
                            'elevation_status': 'runway_end_elevation_proxy_at_displaced_threshold',
                            'valid_from_utc': None, 'valid_to_utc': None})
    # Retain the better evidenced threshold used in the original exercise.
    original = read_json(root / 'data_research/source_evidence/eham_18r_historical_geometry_audit.json')
    original.update({'geometry_id': 'lvnl_eham_18r_historical_audit_v1',
                     'threshold_elevation_ft': original['threshold_elevation_ft_historical_chart_rounded'],
                     'elevation_status': 'published_threshold_elevation',
                     'geometry_source_url': original['sources'][0]['url'],
                     'valid_from_utc': None, 'valid_to_utc': None})
    entries = [g for g in entries if (g['airport_icao'], g['runway_direction']) != ('EHAM', '18R')]
    if 'EHAM' in airports:
        entries.append(original)
    return {'registry_version': 1, 'runways': entries, 'skipped': skipped,
            'limitations': ['Except EHAM 18R, coordinates are community runway-end data, not verified historical AIP thresholds.',
                            'Displacement is applied toward the opposite end; displaced-threshold elevation uses the runway-end proxy.',
                            'Unknown historical geometry validity and NOTAMs remain explicit. Practice use only.']}
