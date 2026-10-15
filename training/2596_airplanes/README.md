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

The saved run's best epoch is **15,000**, with **7.58 s training MAE** and
**7.89 s validation MAE**. Early stopping did not trigger. The current code
allows up to 30,000 epochs; those saved outputs reflect the earlier
15,000-epoch run. On validation, **279/389 predictions are within 10 seconds**;
the distance/speed baseline has 34.03 s MAE and the training-corrected baseline
has 14.53 s MAE. The test partition has not been evaluated. This split holds
out flights, while airports may appear in both training and validation.

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
