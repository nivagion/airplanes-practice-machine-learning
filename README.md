# Aircraft arrival-time prediction

Predict the seconds from first confirmed alignment with Schiphol runway 18R to crossing its landing threshold. The starting dataset contains **194 accepted approaches** from 15 March 2023.

```text
data_preprocessing/   Source research, cleaning, label creation and visualizations
training/
  training.csv        Unsplit data: one approach per row
  schema.json         Input feature list, target, metadata and units
  01_training.ipynb   Empty notebook for your next steps
requirements.txt      Supplied dependency pins plus PyTorch/notebook dependencies
```

## Training workspace

Open `training/01_training.ipynb` in VS Code and select **Aircraft training (Python 3.12)** as the kernel. The notebook is intentionally empty: no data split, preprocessing for the model, architecture selection or training has been implemented.

Use only `feature_columns` from `training/schema.json` for inputs. The target is `remaining_time_s`; identifiers and timestamps are metadata. The copied CSV is byte-for-byte identical to the accepted preprocessing output. See [training/README.md](training/README.md).

The supplied NumPy 1.26.4 pin requires Python 3.9–3.12, so this workspace uses **Python 3.12**. PyTorch 2.8.0 is installed using its official CPU wheel index. The full supplied requirements are retained; extra entries provide PyTorch, a Jupyter kernel and scikit-learn for your later split and scaling work.

From the repository root in PowerShell:

```powershell
py -3.12 -m venv training/.venv
.\training\.venv\Scripts\python.exe -m pip install --upgrade pip
.\training\.venv\Scripts\python.exe -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.\training\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\training\.venv\Scripts\python.exe -m pip check
.\training\.venv\Scripts\python.exe -m ipykernel install --user --name aircraft-training --display-name "Aircraft training (Python 3.12)"
```

Compatibility: [NumPy 1.26.4 release notes](https://numpy.org/devdocs/release/1.26.4-notes.html), [official PyTorch installation commands](https://pytorch.org/get-started/previous-versions/).

## Existing preprocessing work

Everything created for source research, cleaning and visualization is now under [data_preprocessing/](data_preprocessing/README.md). It has its own pinned dependencies and Python 3.14 environment. Open its existing viewer notebook with **Airplanes practice (.venv)**, or open `data_preprocessing/prepared/viewer.html` directly in a browser.

To rebuild from the local raw source:

```powershell
Set-Location data_preprocessing
.\.venv\Scripts\python.exe prepare_data.py
.\.venv\Scripts\python.exe make_share_package.py
```

The raw datasets, generated viewer packages and virtual environments stay local and are ignored by Git. The training CSV and schema are committed so a clone can start the training exercise without downloading the large source. Rebuilding preprocessing does not automatically replace your training copy.

This is a practice dataset with interpolated ADS-B labels. Source, geometry and label limitations are documented in [data_preprocessing/docs/data_README.md](data_preprocessing/docs/data_README.md).
