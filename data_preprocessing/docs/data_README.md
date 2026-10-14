# Schiphol 18R practice data

1. **Extract the ZIP** if you received this folder as an archive.
2. Double-click **viewer.html**. Choose a flight; inspect its snapshot, trajectory and threshold crossing. Everything needed for the map is embedded in the HTML.
3. Load **training.csv** for machine learning. One row is one accepted approach, and `remaining_time_s` is the target in seconds.

**Unsplit**: you create train/validation/test later.

Use only `schema.json`'s `feature_columns` as model inputs. `example_id`, `flight_id`, `icao24`, `callsign`, `runway` and `snapshot_time_utc` are metadata. Keep each `flight_id` in one partition. A chronological split is preferable for checking later traffic; this dataset contains only one date.

```python
import json
import pandas as pd

data = pd.read_csv('training.csv', dtype={'icao24': str})
schema = json.load(open('schema.json'))
X = data[schema['feature_columns']]
y = data[schema['target_column']]
groups = data[schema['group_column']]
```

## Files

| File | Purpose |
| --- | --- |
| training.csv | Snapshot features and remaining-time target |
| viewer.html | Simple airport map, flight selector and observation timeline |
| schema.json | Exact model-input allowlist, target, units and grouping field |
| labels_audit.csv | Crossing brackets, interpolation and landing evidence; for checking labels |
| tracks.csv.gz | Observed positions before and after each snapshot; for visualization only |
| rejected.csv / audit.csv | Rejection reasons and complete candidate decisions |
| dataset_summary.json | Actual accepted/rejected counts and processing rules |
| runway_geometry.json | Threshold coordinates and source evidence |
| airport_runways.json | Airport layout for the offline map |
| rules.json | Adjustable preprocessing settings |

**Do not use future trajectories, crossing timestamps or label diagnostics as model inputs.** These are deliberately separate from training.csv. No future interpolation or smoothing is used for the snapshot features; retrospective interpolation is used only to create the target.

## Definitions and rules

- The endpoint is the landing **threshold**, 270 m inside the northern pavement end, not touchdown or the airport centre.
- Prediction occurs at the first observed confirmation of alignment: at most 100 m from the extended centreline, ground track within 10 degrees, sustained for 10 seconds. Confirmation is not backdated to alignment onset.
- A prior non-aligned observation must establish onset. The first sustained geometric alignment must be inside the final-approach window (25 km, 6000 ft); a later convenient point is not substituted.
- Consecutive duplicate positions are removed with their original timestamps retained. Maximum gap is 3 s in the confirmation window, between snapshot and crossing, and across the crossing bracket.
- Crossing states must be within 50 m of the axis, within 10 degrees of its direction and below 500 ft barometric altitude. Position-derived speed must be 75-125% of reported groundspeed.
- Landing continuation is supported by either slow runway movement for 3 s, or at least 6 s of level-altitude runway movement with a speed reduction of at least 8 m/s. These are mock-exercise quality rules, not independently verified touchdown measurements. Observed missed/broken approaches and insufficient evidence are rejected.

## Source and limits

Real OpenSky trajectories for **15 March 2023**, Schiphol **EHAM**, runway **18R**, published by Dorbolo, Pretto and Giannattasio: [dataset](https://zenodo.org/records/10074634), [paper](https://journals.open.tudelft.nl/joas/article/view/7208).

The extracted source file's archive CRC32 was checked. Its SHA256 is `4cb0c59595c1cf37457fd7748167e1373206daf882167016ce0858255a9b3039`. The raw source is not included in this small package.

The label is an **ADS-B-derived estimate**. Bracket times describe sampled states, not a guaranteed sensor-error interval or independently measured exact crossing. The export lacks `lastposupdate` and `onground`. UTC follows OpenSky semantics; the original Parquet does not declare a timezone. Barometric altitude is pressure-uncorrected and is not a calibrated height above the runway.

LVNL's 2019 chart matches later official threshold coordinates; a report dated 16 March 2023 corroborates the displacement. The exact March 2023 AIP and temporary NOTAM changes were not independently retrieved. Geometry status: `historically_supported_exact_cycle_unverified`. Runway outlines other than 18R are contextual airport geometry from the source archive's database.

The source record is publicly accessible but does not specify a separate dataset licence. The article's CC BY notice describes the article; no new dataset licence is asserted here. Retain the source attribution when sharing this exercise.
