# Expanded arrival-time training data

**2,596 accepted approaches**, **46 airports**,
**111 airport/runway directions**. One row per recorded
flight approach. The table is unsplit and no model has been trained on it.

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
