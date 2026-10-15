"""Build a separate unsplit training table from the registered data sources."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from approach.multi_airport import build_expanded

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--source', action='append', help='Registered dataset ID; repeat for a subset')
    parser.add_argument('--minimum-rows', type=int, help='Fail explicitly if accepted coverage is below this count')
    parser.add_argument('--output-dir', help='Separate output directory, relative to data_preprocessing or absolute')
    parser.add_argument('--training-dir', help='Training copy directory, relative to data_preprocessing or absolute')
    parser.add_argument('--reuse-prepared', help='Previous complete outputs with matching provenance and verified output checksums')
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    if args.minimum_rows is not None and args.minimum_rows < 0:
        parser.error('--minimum-rows must be nonnegative')
    result = build_expanded(ROOT, args.workers, args.source, args.minimum_rows, args.output_dir, args.training_dir, args.reuse_prepared)
    if not result['minimum_rows_met']:
        raise SystemExit('Dataset saved, but the requested minimum count was not reached. Inspect rejection audits; rules were not relaxed.')
