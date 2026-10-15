"""Fetch the frozen source manifest; validate checksums before extracting members."""
import argparse
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from approach.acquisition import download_archive, fetch
from approach.dataset import read_json
from approach.multi_airport import verify_file

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=16, help='Concurrent archive byte ranges; downloads resume')
    args = parser.parse_args()
    if not 1 <= args.workers <= 32:
        parser.error('--workers must be between 1 and 32')
    manifest = read_json(ROOT / 'config/sources.json')
    for asset in manifest['assets']:
        target = ROOT / asset['local_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            try:
                verify_file(target, asset['checksum'])
                print(f'Verified {asset["local_path"]}', flush=True)
                continue
            except ValueError:
                raise SystemExit(f'Existing file failed integrity verification: {target}. Preserve/inspect it before retrying.')
        if target.suffix == '.zip' or asset['size'] > 32_000_000:
            download_archive(asset['url'], asset['size'], asset['checksum'].split(':')[1], target, args.workers)
        else:
            data = fetch(asset['url'])
            algorithm, expected = asset['checksum'].split(':', 1)
            if len(data) != asset['size'] or hashlib.new(algorithm, data).hexdigest() != expected:
                raise ValueError(f'Publisher checksum/size mismatch: {target.name}')
            temporary = target.with_suffix(target.suffix + '.part')
            temporary.write_bytes(data)
            temporary.replace(target)
    archive_path = ROOT / 'data/raw/dorbolo_0_files.zip'
    for source in manifest['sources']:
        if source['adapter'] != 'dorbolo':
            continue
        target = ROOT / source['local_path']
        if not target.exists():
            # Whitelisted member -> explicit file path; no extractall/ZIP path traversal.
            with zipfile.ZipFile(archive_path) as archive:
                data = archive.read(source['archive_member'])
            temporary = target.with_suffix(target.suffix + '.part')
            temporary.write_bytes(data)
            temporary.replace(target)
        verify_file(target, source['checksum'])
    print('All registered sources verified. Run prepare_expanded.py.', flush=True)
