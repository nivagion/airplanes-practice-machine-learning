# Flight data acquisition and preprocessing summary

Repository audit: 14 October 2026. This folder summarizes the existing data work and provides a starting point for adding datasets, airports and runway directions. It covers acquisition, cleaning, snapshot extraction and label creation. Model training is outside this summary.

Start with this page, then [SCRIPT_MAP.md](SCRIPT_MAP.md) for the implementation inventory and [EXPANSION.md](EXPANSION.md) for the proposed changes. The implementation remains in `data_preprocessing/`; this folder contains documentation, not a second copy of the pipeline.

## What exists now

The implemented extractor uses **one dataset, one date and one runway direction: EHAM/Schiphol 18R, 15 March 2023**. Other datasets were researched but are not combined by the current code.

One accepted example represents one approach. Its inputs come from the first observed confirmation of alignment, and its target is:

```text
remaining_time_s = estimated_threshold_crossing_time - snapshot_time
```

The endpoint is the landing threshold, before touchdown. Crossing time is interpolated between observed positions, with the original bracket retained for auditing.

**Elevation finding:** threshold elevation is recorded in the geometry evidence, but is not used by the extractor. `baro_altitude_m` is pressure-uncorrected altitude converted to metres, not height above the runway. Fixed altitude limits make the present implementation unsuitable for arbitrary elevated airports without changes. See [the elevation audit](EXPANSION.md#elevation-audit).

## Getting the data

The following summarizes the repository's recorded source audits; external availability has not been rechecked for this summary.

| Dataset | Acquisition and evidence | Current suitability |
| --- | --- | --- |
| Dorbolo/Pretto/Giannattasio OpenSky, EHAM, 15 March 2023 | Zenodo record `10074634`; EHAM Parquet extracted from `0_files.zip` using HTTP byte ranges. Archive member CRC32 verified, extracted SHA256 recorded. | Implemented source. Contains approach, crossing and useful runway continuation observations. |
| Same Zenodo archive, EGLL/Heathrow | Separate EGLL Parquet is documented in the archive. | Possible next airport; not processed or validated by this pipeline. |
| Zurich arrivals, 2019 | Figshare DOI `10.6084/m9.figshare.11406735.v1`; `landing_dataset.parquet` downloaded and published MD5 verified. | Most tracks end before the threshold. Useful for approach research, but cannot supply most labels for this target. |
| TartanAviation, KAGC, raw 2022 | Raw ZIP contains 245 daily CSVs; a day was sampled. Archive uses Deflate64. Recorder code was retained as evidence. | Conditional candidate: repeated stale states and coarse crossing brackets require a source adapter and freshness checks. Not integrated. |

The EHAM raw file is expected at `data_preprocessing/data/raw/EHAM_20230315_flights.parquet`. Its archive member is `0_files/files/EHAM_20230315/EHAM_20230315_flights.parquet`.

```text
SHA256: 4cb0c59595c1cf37457fd7748167e1373206daf882167016ce0858255a9b3039
ZIP member CRC32: c09a2447
Uncompressed size: 243,480,264 bytes
```

Only the EHAM member was fetched; the published checksum of the full ZIP was not independently verified. Raw files, local samples and generated packages are ignored by Git.

**Acquisition gap:** there is no reusable download/extraction script in the checked-in project. The existing rebuild starts from a local raw file. `tartanaviation_recording_source.py` is upstream recorder evidence, not a downloader for this project.

Source details and links are in [the source audit](../data_preprocessing/data_research/README.md), [audit notes](../data_preprocessing/data_research/source_evidence/dataset_audit_notes.md), and [EHAM extraction provenance](../data_preprocessing/data_research/source_evidence/eham_range_extraction.json). The source audit records an MIT licence for Zurich and no explicit separate dataset licence in the Zenodo metadata; it does not assign the article's licence to the data.

## Current preprocessing, in order

Implemented in [dataset.py](../data_preprocessing/src/approach/dataset.py), with configurable rules in [approach.json](../data_preprocessing/config/approach.json).

1. **Read nearby arrivals.** Read selected Parquet columns, filter destination to EHAM and use a hard-coded geographic bounding box. Interpret timestamps as UTC, normalize aircraft IDs and strip callsigns.
2. **Clean basic states.** Require time, position, speed and aircraft ID. Keep plausible speed/altitude ranges; retain missing altitude/vertical rate on ground observations for later continuation checks. Complete finite features are required at the prediction snapshot.
3. **Compute runway geometry and units.** Project WGS84 surface positions into east/north coordinates relative to the landing threshold. Rotate using true runway bearing to obtain along-track distance, signed cross-track offset and track error. Convert knots to m/s, feet to metres and ft/min to m/s. Keep observations within 80 km of the threshold.
4. **Resolve timestamps and segment flights.** Discard conflicting positions for the same aircraft/time; deduplicate remaining same-time rows. Forward-fill callsigns within an aircraft's history. Start a segment when callsign changes or the observation gap exceeds 1,200 s. Remove consecutive repeated coordinates without filling the resulting gaps.
5. **Find approach candidates.** Require at least three observations in a loose approach window: 0–30 km before threshold, lateral offset under 500 m, track error under 35 degrees, altitude below 10,000 ft. These candidate limits are hard-coded.
6. **Select the causal snapshot.** Alignment must persist for 10 s within 100 m and 10 degrees, with speed at least 40 m/s and gaps at most 3 s. A prior non-aligned observation must establish onset. Use confirmation time, without backdating. Reject the first confirmation if farther than 25 km or higher than 6,000 ft; do not substitute a later convenient point.
7. **Build the crossing label.** Find a subsequent observed segment spanning the transverse threshold line. The accepted bracket has gaps at most 3 s, lateral offset at most 50 m, track error at most 10 degrees and altitude at most 500 ft. Position-derived speed must be 75–125% of reported groundspeed. Interpolate time within that bracket.
8. **Validate the approach outcome.** Reject gaps between snapshot and crossing, broken alignment, observed go-arounds, targets outside 0–600 s, or insufficient landing continuation. Within 120 s after crossing, require either sustained slow runway movement or level-altitude movement with deceleration. This supports a landing classification; it does not independently measure touchdown.
9. **Export features separately from future evidence.** Emit one snapshot row per accepted approach, label brackets, rejection decisions, trajectory excerpts, schema, geometry, rules and counts.

The threshold is displaced 270 m from the physical northern pavement end. Geometry is historically supported, but the exact March 2023 AIP/NOTAM cycle remains unverified. The source lacks `lastposupdate` and `onground`: one-second state-vector sampling does not prove a fresh position every second.

## Existing results and output contract

The local `data_preprocessing/prepared/dataset_summary.json` records **6,924,104 source rows, 578 checked flight segments, 360 candidate segments, 194 accepted approaches and 166 rejected candidates**. These are existing output counts, not a rebuild performed for this summary. Earlier research crossing counts describe preliminary scans and should not be confused with final examples.

The 166 rejections comprise 89 inconsistent crossing speeds, 71 missing landing-continuation cases, 4 observation gaps, 1 absent crossing and 1 broken/missed approach. Exported trajectory excerpts contain 61,238 observed points.

| Output under `data_preprocessing/prepared/` | Role |
| --- | --- |
| `training.csv` | One snapshot and target per accepted approach; currently unsplit. |
| `schema.json` | Feature allowlist, target, units and flight grouping field. |
| `labels_audit.csv` | Observed crossing bracket, interpolation, speed consistency and landing evidence. Contains future information. |
| `audit.csv`, `rejected.csv` | Candidate acceptance/rejection decisions and reasons. |
| `tracks.csv.gz` | Past/future observed excerpts for visual inspection; not snapshot inputs. |
| `dataset_summary.json`, `rules.json` | Counts, limitations and processing rules. |
| `runway_geometry.json`, `airport_runways.json` | Label geometry/provenance and contextual runway layout. |
| `viewer.html`, `README.md` | Inspection interface and data instructions. |

The 11 current input fields are latitude, longitude, barometric altitude, groundspeed, true track, vertical rate, distance to threshold, cross-track offset, track error, speed toward threshold and constant-speed baseline ETA. Only the schema's allowlist should be treated as inputs. Crossing/rollout observations are used retrospectively to construct and audit labels.

## Existing commands

From the repository root, with the preprocessing environment and raw source already present:

```powershell
Set-Location data_preprocessing
.\.venv\Scripts\python.exe prepare_data.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts/validate_outputs.py
```

`prepare_data.py` rebuilds data and the browser viewer; it does not download sources. Output validation also expects the existing viewer notebook with saved outputs. See [SCRIPT_MAP.md](SCRIPT_MAP.md) for the optional inspection and packaging scripts.
