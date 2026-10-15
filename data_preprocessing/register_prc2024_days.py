"""Register another non-overlapping daily window from the frozen PRC2024 release."""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-id', required=True)
    parser.add_argument('--start-date', required=True, type=date.fromisoformat)
    parser.add_argument('--days', type=int, default=7)
    args = parser.parse_args()
    if not 1 <= args.days <= 366:
        parser.error('--days must be 1 to 366')
    catalog = json.loads((ROOT / 'data_research/source_evidence/prc2024_file_manifest.json').read_text())
    path = ROOT / 'config/sources.json'
    manifest = json.loads(path.read_text())
    if args.dataset_id in {s['dataset_id'] for s in manifest['sources']}:
        parser.error('Dataset ID already exists; extend its paths/checksums explicitly to join adjacent days')
    names = [(args.start_date + timedelta(days=i)).isoformat() + '.parquet' for i in range(args.days)]
    if any(name not in catalog for name in names):
        parser.error('Requested dates are outside the frozen published release')
    paths = [catalog[name]['local_path'] for name in names]
    existing = {p for s in manifest['sources'] if s['adapter'] == 'prc2024' for p in s['local_paths']}
    if set(paths) & existing:
        parser.error('This window overlaps an existing source; extend that source instead')
    # Adjacent windows can share a real flight at midnight. Keep adjoining days
    # in one source; non-overlapping windows separated by a day are independent.
    existing_dates = {date.fromisoformat(Path(p).stem) for p in existing}
    requested_dates = {date.fromisoformat(Path(p).stem) for p in paths}
    if any(d + timedelta(days=1) in existing_dates or d - timedelta(days=1) in existing_dates for d in requested_dates):
        parser.error('Adjacent windows must be joined in the existing source to preserve midnight flights')
    seed = next(s for s in manifest['sources'] if s['adapter'] == 'prc2024')
    entry = {**seed, 'dataset_id': args.dataset_id, 'local_paths': paths,
             'checksums': [catalog[name]['checksum'] for name in names],
             'coverage': f'{args.start_date} through {args.start_date + timedelta(days=args.days - 1)} UTC; bordering partial flights can be rejected'}
    for name in names:
        asset = catalog[name].copy()
        asset['publisher_file_url'] = asset.get('publisher_file_url', asset['url'])
        asset['url'] = 'https://s3.opensky-network.org/competition-data/' + name
        if asset['local_path'] not in {a['local_path'] for a in manifest['assets']}:
            manifest['assets'].append(asset)
    manifest['sources'].append(entry)
    temporary = path.with_suffix('.json.part')
    temporary.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    temporary.replace(path)
    print(f'Registered {args.dataset_id}: {len(names)} daily files. Run acquire_data.py, then prepare_expanded.py.')
