"""Create the small VS Code/Jupyter entry point."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
nb.metadata = {"kernelspec": {"name": "airplanes-practice", "display_name": "Airplanes practice (.venv)", "language": "python"},
               "language_info": {"name": "python", "version": "3.14.2"}}
nb.cells = [
    nbf.v4.new_markdown_cell("""# Schiphol approach viewer

**Run All**, then choose a flight below. If VS Code asks for a kernel, select **Airplanes practice (.venv)**.

Green = prediction snapshot; orange = threshold-crossing estimate. The solid blue path is observed history and the dashed orange path is future data used to check the label. All times are UTC.

The training table is **unsplit**. One row = one accepted approach to runway 18R. Labels estimate threshold crossing, before touchdown."""),
    nbf.v4.new_code_cell("""%matplotlib inline
from pathlib import Path
import sys, json
from IPython.display import display, HTML

ROOT = next((candidate for p in [Path.cwd(), *Path.cwd().parents]
             for candidate in (p, p / 'data_preprocessing')
             if (candidate / 'prepared' / 'training.csv').exists()
             and (candidate / 'src' / 'approach').is_dir()), None)
if ROOT is None:
    raise FileNotFoundError('Open this project folder in VS Code and run prepare_data.py first.')
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

from approach.notebook import load_prepared, flight_selector, show_flight
training, labels, tracks, runways, schema = load_prepared(ROOT)
summary = json.loads((ROOT / 'prepared' / 'dataset_summary.json').read_text())
print(f"{len(training)} accepted approaches · {summary['rejected_approaches']} rejected · Schiphol 18R · unsplit")"""),
    nbf.v4.new_markdown_cell("## Choose a flight\nThe right-hand map enlarges the actual landing threshold, 270 metres inside the pavement's northern end."),
    nbf.v4.new_code_cell("selector = flight_selector(training, labels, tracks, runways)"),
    nbf.v4.new_markdown_cell("""## Your training table

This is the small file to split later: `prepared/training.csv`.

Use the feature list in `schema.json`. Aircraft identifiers, callsigns and timestamps are metadata; `labels_audit.csv` and `tracks.csv.gz` contain future observations and must stay out of model inputs."""),
    nbf.v4.new_code_cell("""display(training[['callsign', 'snapshot_time_utc', 'distance_to_threshold_m',
                  'groundspeed_mps', 'remaining_time_s']].head(8).round(2))

# Ready for your later split and model. No split or model fitting happens here.
FEATURE_COLUMNS = schema['feature_columns']
X = training[FEATURE_COLUMNS].copy()
y = training[schema['target_column']].copy()
flight_groups = training[schema['group_column']].copy()
print(f'X: {X.shape[0]} rows × {X.shape[1]} snapshot features; y: seconds to threshold')"""),
    nbf.v4.new_markdown_cell("""## Quick data check

Large differences from constant-speed ETA can be real deceleration, or a reason to inspect the flight. The source is only one date, and labels are interpolated from sampled ADS-B states."""),
    nbf.v4.new_code_cell("""import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(8, 3))
ax.hist(y, bins=18, color='#2563eb', edgecolor='white')
ax.set(xlabel='Remaining time to threshold (seconds)', ylabel='Approaches', title='Accepted labels')
plt.show()
print(f'Median: {y.median():.1f} s; range: {y.min():.1f}–{y.max():.1f} s')
print(f'Constant-speed baseline MAE: {(training.baseline_eta_s - y).abs().mean():.1f} s (no trained model)')"""),
    nbf.v4.new_markdown_cell("""## Share with your friend

For a simple browser view, double-click **prepared/viewer.html**. It has a flight selector, zoom, pan and a timeline.

**share/schiphol_18R_unsplit.zip** contains the viewer, training CSV and audit files. Extract the ZIP before opening the HTML. After you create `train.csv`, `validation.csv` and `test.csv`, use `make_share_package.py --split-dir <your folder>` to package those partitions instead.

Runway geometry is supported by primary charts before and after the recording date. The exact March 2023 AIP/NOTAM cycle and independent position freshness remain unverified; see `prepared/README.md`."""),
]
directory = ROOT / "notebooks"
directory.mkdir(exist_ok=True)
path = directory / "01_view_flights.ipynb"
nbf.validate(nb)
nbf.write(nb, path)
print(path)
