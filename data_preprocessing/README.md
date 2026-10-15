# Aircraft approach data preprocessing

The larger multi-airport pipeline is documented in [EXPANSION.md](EXPANSION.md).
Run `acquire_data.py` and `prepare_expanded.py`; its separate training copy is
`../training/2596_airplanes/training.csv` with its own `schema.json`. Sources, runway
directions, threshold coordinates, elevation proxies and provenance are configured
in `config/sources.json`, `config/runways.json`, `config/approach_rules.json` and
`config/expansion.json`.

The instructions below retain the original Schiphol exercise and viewer.

Predict seconds from **first confirmed runway alignment** to **runway-threshold crossing**. The initial dataset uses real Schiphol runway 18R arrivals from 15 March 2023.

## Start here

Open [notebooks/01_view_flights.ipynb](notebooks/01_view_flights.ipynb) in **VS Code**, select **Airplanes practice (.venv)** as its kernel and click **Run All**. Choose a flight from the dropdown. The notebook is saved with executed outputs, so the first example is visible immediately.

Or double-click **prepared/viewer.html** for a browser viewer with flight selection, zoom, pan, snapshot/crossing markers and a timeline. The offline map shows actual airport runway outlines and the extended runway-18R centreline.

Your training file is **prepared/training.csv**. It remains **unsplit**. Use the feature list in **prepared/schema.json**; future observations and label diagnostics live in separate audit files. Units and cleaning rules are explained in **prepared/README.md**.

## Rebuild

The environment is already prepared on this computer. From this `data_preprocessing` folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe prepare_data.py
.\.venv\Scripts\python.exe make_share_package.py
```

The source must be present at `data/raw/EHAM_20230315_flights.parquet`. Generated files are under `prepared/`; the small ZIP is under `share/`. The raw 243 MB source and Python environment are not included in the ZIP.

For a fresh Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ipykernel install --user --name airplanes-practice --display-name "Airplanes practice (.venv)"
```

## Share after your later split

Put your unchanged source rows in `train.csv`, `validation.csv` and `test.csv`, with all the original training-table columns. Keep a flight entirely in one partition. This command validates duplicate/overlapping flight IDs, row integrity and complete coverage before packaging:

```powershell
.\.venv\Scripts\python.exe make_share_package.py --split-dir path\to\your\splits
```

Send **share/schiphol_18R_split.zip**. It includes those three files and a viewer with a partition selector. The packager does not choose or change your split.

## Project files

- `config/approach.json`: documented adjustable cleaning defaults.
- `src/approach/dataset.py`: causal snapshot extraction and retrospective target creation.
- `src/approach/notebook.py`: small Jupyter interface.
- `src/approach/viewer.py`: offline viewer generation.
- `data_research/`: source audit and geometry evidence.
- `GLOSSARY.md`: agreed domain terms.
- `data_research/design.md`: confirmed scope and choices.

This original preprocessing exercise uses one day of data and interpolated ADS-B labels. Independent position freshness and the precise March 2023 AIP/NOTAM cycle remain unverified. Its exported CSV remains unsplit; model training and in-memory partitions are documented in the [training workspace](../training/README.md).
