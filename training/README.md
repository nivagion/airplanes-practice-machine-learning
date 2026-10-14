# Training workspace

`training.csv` contains **194 rows**, one accepted landing approach per row, with 11 numeric input features. It is copied unchanged from `../data_preprocessing/prepared/training.csv` and remains **unsplit**.

- Inputs: the `feature_columns` allowlist in `schema.json`.
- Target: `remaining_time_s`, seconds from first confirmed alignment until estimated runway-threshold crossing.
- Metadata: example/flight identifiers, aircraft identifier, callsign, runway and snapshot timestamp. Do not add these to the model inputs.

`01_training.ipynb` is an empty notebook for your next work: data inspection, train/validation/test split, transformations fitted on the training partition, PyTorch model selection and evaluation. No model or split has been created.

Select **Aircraft training (Python 3.12)** as the notebook kernel. Setup commands are in the repository's root README. This environment installs the supplied requirements plus PyTorch 2.8.0 (CPU), ipykernel and scikit-learn.

`requirements.lock.txt` records all installed package versions, including dependencies. To reproduce those exact versions, install the CPU PyTorch wheel using the root README command first, then use `pip install -r training/requirements.lock.txt` instead of the root requirements file.

Keep every flight in one partition. Fit scalers only on the training partition, and keep the test partition for final evaluation. Future trajectory points and crossing diagnostics in `data_preprocessing/prepared/` are for auditing labels and visualization, not model inputs.

If you later want a shareable viewer containing your split, preserve all original table columns and rows in `train.csv`, `validation.csv` and `test.csv`, then run from the repository root:

```powershell
.\data_preprocessing\.venv\Scripts\python.exe data_preprocessing/make_share_package.py --split-dir training/splits
```

Data source attribution and uncertainty: [data README](../data_preprocessing/docs/data_README.md), [source audit](../data_preprocessing/data_research/README.md).
