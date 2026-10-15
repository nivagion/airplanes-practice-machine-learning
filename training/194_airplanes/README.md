# Original 194-row training exercise

`training.csv` contains 194 accepted Schiphol runway 18R approaches and is unchanged from `data_preprocessing/prepared/training.csv`. `schema.json` lists the 11 numerical input features, target, metadata and units.

- Target: `remaining_time_s`, seconds from first confirmed alignment to estimated threshold crossing.
- Existing notebooks: `01_training.ipynb` and `02_two_hidden_layers.ipynb`. Their saved outputs and metadata are preserved, and their loading paths select this dataset.
- `requirements.lock.txt`: installed package versions for the existing training environment.

Use the shared **Aircraft training (Python 3.12)** kernel from `training/.venv`. Environment setup is in the [repository README](../../README.md). To reproduce the locked dependencies, install the CPU PyTorch wheel using that guide first, then install `training/194_airplanes/requirements.lock.txt` from the repository root.

Keep each flight in one partition. Fit scalers on the training partition and reserve the test partition for final evaluation. Labels and future trajectory diagnostics in the preprocessing exports are audit evidence, not model inputs.

For a later shareable viewer, preserve the original table columns in `train.csv`, `validation.csv` and `test.csv` under this folder's `splits/`, then run from the repository root:

```powershell
.\data_preprocessing\.venv\Scripts\python.exe data_preprocessing/make_share_package.py --split-dir training/194_airplanes/splits
```

Source attribution and uncertainty: [data README](../../data_preprocessing/docs/data_README.md), [source audit](../../data_preprocessing/data_research/README.md). The expanded dataset is in [2596_airplanes](../2596_airplanes/README.md).
