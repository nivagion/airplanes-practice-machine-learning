# Expand the arrival-time dataset

The expanded pipeline predicts the same target as the original exercise:

```text
remaining_time_s = interpolated_threshold_crossing_time_utc - confirmed_alignment_snapshot_time_utc
```

One accepted flight approach produces one row. The table remains unsplit. No
model is trained. The original `training/194_airplanes/training.csv`, notebooks and
`data_preprocessing/prepared/` baseline are preserved.

## Files for your next training run

- `../training/2596_airplanes/training.csv`: new model-ready table.
- `../training/2596_airplanes/schema.json`: exact input features, target and metadata.
- `../training/2596_airplanes/dataset_summary.json`: actual accepted coverage and limitations.
- `prepared/multi_airport/`: complete extraction, label evidence, rejection reasons,
  trajectory excerpts, coverage by source/airport/runway, frozen geometry and provenance.

Use only `feature_columns` in the **new** schema. The original eleven numerical
features remain, with five additions: target threshold latitude, longitude,
true runway bearing, threshold elevation and the pressure-altitude height proxy.
Airport/runway names, IDs, timestamps and quality flags are metadata. Future
crossing and landing-continuation evidence remains in separate audit files.

The feature count changes from 11 to 16: a later model should derive its input
size from the new schema. Place the later notebook in `training/2596_airplanes/` beside its
`training.csv` and `schema.json`; the existing notebooks in
`training/194_airplanes/` continue using the original 194 rows.
Use `flight_id` as the group key. Split later by flight and time, and assess
held-out airports separately if you want to test transfer to a new airfield.
Do not use `source_date` as the actual landing day: an overnight flight can
have a snapshot on the following UTC date.

## Rebuild

From `data_preprocessing` in PowerShell:

```powershell
.\.venv\Scripts\python.exe acquire_data.py
.\.venv\Scripts\python.exe prepare_expanded.py --workers 8
.\.venv\Scripts\python.exe scripts/validate_expanded.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Acquisition downloads approximately 24.9 GB of frozen published archives and
metadata, validates publisher MD5 checksums, and resumes interrupted ZIP byte
ranges. Raw sources remain local and ignored by Git. The training copy and schema
can be versioned. The build exits unsuccessfully if fewer than the configured
1,000 rows pass, while saving the actual table and rejection audits. It never
fills observation gaps or relaxes the rules to reach a numerical target.

To inspect one source without replacing the combined training copy:

```powershell
.\.venv\Scripts\python.exe prepare_expanded.py --source prc2025_train --minimum-rows 0 --output-dir prepared/prc_sample --training-dir ../training/prc_sample
```

`--reuse-prepared path/to/previous/output` can reuse completed source extractions
when their rules, geometry, processing version, manifests and output checksums
match. It still checks duplicate flight IDs before adding new sources. A plain
rebuild without this option processes every registered source from raw data.

## Sources and quality

The [PRC 2024 trajectory release](https://data.4tu.nl/datasets/8cb8484b-dbe7-4750-8b87-a5b1dbc621b4)
contributes **1–7 January, 1–7 June and 1–7 September 2022**. Daily Parquet files are fetched anonymously from
the publisher's [OpenSky server](https://prc-data-challenge.netlify.app/data.html)
and verified against the 4TU version-2 MD5 checksums. The complete flight list
joins publisher flight IDs to destinations; take-off weights and arrival times
are excluded from model features and label creation. Observations from adjoining
files are joined before grouping, so midnight crossings stay in one flight.
Flights cut by the beginning/end of the downloaded week can still be rejected
for missing onset or landing evidence. Units are documented feet, knots and
feet/minute. The publisher README licenses the source under CC BY 4.0; cite
Junzi Sun and Enrico Spinielli and the associated PRC 2024 data paper.
Some daily trajectory IDs are absent from the published flight list; these
produce `missing_flight_metadata` audits rather than a guessed destination.

The [PRC 2025 published dataset](https://zenodo.org/records/19184662) contains
per-flight ADS-B and ACARS records covering April–October 2025. Only `source ==
adsb` observations are used here. Its fuel labels and competition partitions do
not become this exercise's labels or splits. Publisher train/rank/final phases
are simply three acquisition sources combined into our unsplit arrival table.
The publisher README explicitly licenses the dataset under CC BY 4.0; retain
attribution to Junzi Sun, Enrico Spinielli and Martin Strohmeier.

**Unit discrepancy:** the publisher's README and paper describe SI units, but
the v1 ADS-B records behave as nominal feet, knots and feet/minute. The explicit
adapter preserves nominal feet, converts knots to m/s and ft/min to m/s, and
marks every row with the empirical unit-inference flag. Five sampled flights
show cruise values around 36,000–40,000, altitude increments near 25, vertical
rate increments of 64, and position/time speed consistent with knots conversion.
Evidence and sample SHA256 hashes are in
`data_research/source_evidence/prc2025_unit_audit.json`. This is an inference,
not publisher confirmation; audit any new release before using the adapter.

The [original Dorbolo dataset](https://zenodo.org/records/10074634) supplies the
2023 Schiphol exercise plus the Heathrow file. Both use the same source adapter.
Heathrow contributes only rows that actually pass; its recordings usually end
before the threshold. Open access alone is not an explicit dataset redistribution
licence; that source's licence limitation remains in the manifest.

Directional runway geometry is frozen from
[OurAirports](https://ourairports.com/data/) at the Git commit and SHA256 recorded
in `config/runways.json`. The shared extractor has no hard-coded airport or
runway. Each direction has its own threshold; displaced thresholds are advanced
from the physical end toward the opposite end. Bearing is derived in the WGS84
local tangent plane from both ends. EHAM 18R retains the better evidenced LVNL
geometry from the original exercise.

**Community geometry is a lower-confidence practice tier:** other thresholds,
historical runway changes and NOTAMs are not verified against date-specific AIP
publications. At a displaced threshold, runway-end elevation is an explicit
proxy. These limitations appear in every row's geometry/vertical quality and
in the summary. A missing runway/elevation produces a rejection audit.

`baro_height_proxy_m = baro_altitude_m - threshold_elevation_m` is uncorrected
pressure altitude minus published elevation, **not calibrated AGL**. Height
ceilings use this proxy consistently. No QNH, geoid or terrain correction is
claimed. Raw pressure altitude remains a separate feature.

The original 10-second alignment confirmation, 3-second maximum observation gap,
speed-consistency bracket and observed landing-continuation requirements remain.
Shared numerical rules live in `config/approach_rules.json`; the original
`config/approach.json` remains the baseline's airport/date configuration.
For irregular subsecond records, landing evidence includes the last observation
at or before the six-second window boundary; otherwise a window restricted to
the last six seconds almost never spans a full six seconds. It still must span
at least six seconds and pass every gap, altitude, vertical-rate and deceleration
check. No points are invented. The original 194 rows reproduce byte-for-byte.

Runway assignment chooses the first confirmed alignment using observations
available at that snapshot. A simultaneous parallel-runway tie within 25 m of
lateral score is rejected. Later landing success never chooses a more convenient
runway or replaces an earlier rejected attempt. The publisher destination is
used to select the airport registry; this assumes a planned destination is
available when predicting.

## Add more data later

1. Add immutable assets and a source entry in `config/sources.json`: ID, adapter,
   publisher URL/version, local paths, expected checksums, licence evidence,
   timezone, units, altitude type and position-freshness capabilities. Reuse the
   `prc2025` adapter only for the audited v1 schema/unit policy. Reuse `dorbolo`
   only for its documented feet/knots/ft-min schema. Add a new explicit adapter
   in `src/approach/sources.py` for genuinely different source formats.
   For more PRC 2024 days, append daily assets/checksums and local paths to the
   existing `prc2024_week1` entry (rename its ID/coverage for the new version).
   Keep contiguous daily files in one source so midnight observations are joined.
   All daily publisher file URLs and MD5 values are recorded in
   `data_research/source_evidence/prc2024_file_manifest.json`; OpenSky's public
   object URL is `https://s3.opensky-network.org/competition-data/YYYY-MM-DD.parquet`.
2. Add each airport's directional thresholds to `config/runways.json`. Prefer
   period-appropriate official AIP geometry with threshold coordinates,
   elevation, true bearing, landing distance, geometry ID, source URL and known
   validity intervals. Opposite landing directions are separate entries. Do not
   substitute physical runway ends for displaced landing thresholds.
3. Run acquisition, extraction and validation. Inspect `coverage.csv` and
   rejection reasons; the number of downloaded flights is not the number of
   valid labels. Add dates, seasons and airports with accepted coverage rather
   than duplicating snapshots from the same approach.
4. For a later version, use `--output-dir prepared/multi_airport_v2`.
   The default training folder is `training/<row_count>_airplanes/`, named from
   the accepted row count (currently `2596_airplanes`). A rebuild with the same
   row count replaces that folder's data, so use `--training-dir` with a separate
   versioned path when preserving an earlier run. Keep that version's schema, source
   manifest, geometry and processing rules together. Increase `minimum_rows` in
   `config/expansion.json` when you are ready for a larger target.

For example, this helper registers another separated window using the recorded
publisher URLs/checksums; acquisition and preprocessing then handle it:

```powershell
.\.venv\Scripts\python.exe register_prc2024_days.py --dataset-id prc2024_october_week --start-date 2022-10-01 --days 7
.\.venv\Scripts\python.exe acquire_data.py
.\.venv\Scripts\python.exe prepare_expanded.py --reuse-prepared prepared/multi_airport --output-dir prepared/multi_airport_v2
```

The helper rejects overlapping or immediately adjacent windows; extend an
existing source explicitly for adjacent days so midnight flights are joined.
Reusing completed outputs still requires the same extraction rules and geometry.

For much larger coverage, PRC 2024 provides the remaining daily 2022 files; its
published flight count is not a promise of threshold labels. Prefer additional
dates at airports with accepted coverage, then audit newly added airports.
Zurich's earlier arrival table, synthetic
trajectories, flight-list-only datasets and reconstructed runway points do not
supply observed threshold crossings for this target. TartanAviation raw data
needs a dedicated stale-position/age audit before use.

Repeated go-around attempts currently remain conservatively rejected at the
first selected attempt. Future attempt segmentation must preserve one flight's
group identity across all attempts. Cross-collection overlap also needs real
flight matching; PRC IDs obscure aircraft identity, so don't assume IDs from a
different publisher prove disjoint flights. The included 2022, 2023 and 2025
collections have disjoint years, and publisher flight IDs are checked for
duplicates across PRC phases.
