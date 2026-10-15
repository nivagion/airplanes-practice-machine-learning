# Expanded arrival-time training data

**2,596 accepted approaches**, **46 airports**,
**111 airport/runway directions**. One row per recorded
flight approach: **about 13.4 times as many examples as the original 194-row dataset**.
The CSV is unsplit on disk; the training notebook creates partitions in memory.

## Training notebook and saved results

Open [03_more_airplanes.ipynb](03_more_airplanes.ipynb) with the shared
**Aircraft training (Python 3.12)** kernel and run the cells in order. It uses
16 inputs, one hidden layer of 8 ReLU neurons and one output in seconds.
The flight-grouped split contains **1,817 training**, **389 validation** and
**390 test** approaches. The scaler is fitted only on training inputs.

The latest saved run's best epoch is **20,604**, with **7.37 s training MAE**
and **7.66 s validation MAE**. Early stopping ends the run at epoch **21,604**
and restores the selected weights. The maximum allowed run is 30,000 epochs.
On validation, **275/389 predictions are within 10 seconds**; the distance/speed
baseline has 34.03 s MAE and the training-corrected baseline has 14.53 s MAE.

Section 13 evaluates the same frozen checkpoint on the **390 reserved test
approaches from 27 airports**: **7.71 s MAE**, **10.30 s RMSE**, and
**281/390 predictions (72.1%) within 10 seconds**. The largest error is
37.58 s. Test MAE is only 0.054 s higher than validation MAE. Test baselines
have 33.70 s MAE (distance/speed) and 15.37 s MAE (training-corrected).

Test and validation use the same prediction/error calculations. Validation
selects the checkpoint; test measures that selected model without updating
weights or fitting a scaler. To reproduce test evaluation without retraining,
run the imports, dataset loading, feature selection, split and scaling cells,
then Section 13. This random split holds out flights; airports may appear in
multiple partitions, so it does not establish unseen-airport performance.

The notebook saves `03_more_airplanes_best.pt` here, including model weights,
feature order and fitted scaler parameters. Setup instructions, the MAE graph
and comparisons with the original exercise are in the
[repository README](../../README.md#training-results).

## Data and sources

Target: `remaining_time_s`, seconds from first confirmed alignment to interpolated
runway-threshold crossing. Use `feature_columns` from `schema.json`: the eleven
original numerical features plus five runway/height features (16 inputs total).
IDs, timestamps, source names and quality flags are metadata. Group later splits
by `flight_id`; do not use future label evidence as input.

Sources include the original 2023 Schiphol data, the published PRC 2025 ADS-B
flights, and 1–7 January, 1–7 June and 1–7 September 2022 PRC trajectories.
See `dataset_summary.json` for actual source/airport coverage.

The 3-second observation-gap limit, 10-second alignment confirmation and crossing
speed checks remain. Threshold coordinates are included. Except EHAM 18R, runway
geometry is community data with unverified historical validity. Pressure height
is an uncorrected proxy. PRC 2025 v1 units are empirically inferred, with the
published unit discrepancy explicitly flagged. This is practice data with
interpolated labels, not exact measured crossing truth.

Rebuilding, source attribution, complete quality notes, rejection audits and
instructions for adding dates/airfields are in
[data_preprocessing/EXPANSION.md](../../data_preprocessing/EXPANSION.md).
Detailed exports are under `data_preprocessing/prepared/multi_airport/`.
The original `training/194_airplanes/training.csv` remains available separately.
