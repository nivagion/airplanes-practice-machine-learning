# ADS-B dataset source audit

Research date: 14 October 2026. This folder records evidence for choosing a source for an independent mock machine-learning exercise. It is not a finished training dataset.

## Recommended source: Schiphol (EHAM), 15 March 2023

Source: Lorenzo Dorbolo, Marco Pretto, Pietro Giannattasio, *Datasets and codes for Exploiting high-resolution ADS-B data for flight operation reconstruction towards environmental impact assessment*.

- [Dataset record](https://zenodo.org/records/10074634), DOI `10.5281/zenodo.10074634`.
- [Authors' paper](https://journals.open.tudelft.nl/joas/article/download/7208/5893/27325).
- [Original archive](https://zenodo.org/records/10074634/files/0_files.zip?download=1): 505,887,939 bytes, published MD5 `ab07064323cd8586b3138ec47eaee01f`.
- The archive contains separate Heathrow (EGLL) and Schiphol (EHAM) Parquet files. Only EHAM is proposed for this exercise.
- The EHAM member is `0_files/files/EHAM_20230315/EHAM_20230315_flights.parquet`, 243,480,264 bytes uncompressed.
- The paper describes one-second OpenSky traffic data and usable ground observations. Its reported EHAM results include 550 arrivals and 527 departures; these are the authors' processed-operation counts, not our accepted-label counts.

**Downloaded and audited:** `data/raw/EHAM_20230315_flights.parquet`, 6,924,104 records. The EHAM member's ZIP CRC32 (`c09a2447`) was verified; the full outer archive was not downloaded, so its published MD5 was not independently checked. The extracted file's SHA256 is `4cb0c59595c1cf37457fd7748167e1373206daf882167016ce0858255a9b3039`. Extraction provenance is in `source_evidence/eham_range_extraction.json`.

**Recommendation:** start with EHAM arrivals aligned to runway 18R. The initial audit found 351 plausible one-second threshold-crossing brackets (351 callsigns, 272 aircraft). Requiring position-derived speed to be 75-125% of reported groundspeed retains 265 brackets. These are source-suitability candidates, not a finalized count of distinct landing attempts or training labels; alignment onset, repeated positions, missed approaches and landing continuation still need the agreed extraction and quality rules.

### Concrete observed example

MSR757, ICAO24 `0101b7`, 15 March 2023:

| Event | UTC time | Latitude | Longitude | Evidence |
| --- | --- | --- | --- | --- |
| Illustrative aligned point | 12:45:22 | 52.4677237818 | 4.7215314593 | Within 12 km of threshold, lateral offset about 2.17 m, track 183.691 degrees, 155 kt |
| Last sampled state before crossing | 12:47:56 | 52.3602905273 | 4.7117614746 | About 3.72 m before threshold |
| Next sampled state after crossing | 12:47:57 | 52.3596760378 | 4.7117222377 | About 64.73 m beyond threshold |

Interpolated crossing estimate: `2023-03-15T12:47:56.054Z`. Remaining time from the illustrative aligned point is about 154.054 seconds; the observed crossing interval gives 154-155 seconds. The fractional estimate is not independent subsecond truth. The aligned point demonstrates that the source contains both the input state and subsequent crossing; it has **not** been identified as the first confirmed alignment event.

Spatial motion over the crossing segment is about 68.46 m/s; reported groundspeed of 144 kt is about 74.08 m/s. A 620-point trajectory excerpt is saved in `samples/eham_first_valid_18R_arrival.csv`, and candidate brackets are in `eham_18R_sample_crossings.json`. Summary and methods notes are in `source_evidence/`.

### Remaining quality limits

The published export lacks `onground` and `lastposupdate`. A one-second state-vector interval does not establish an independently fresh position report every second. Repeated-position and motion checks are necessary, and the crossing interval represents sampled-state evidence rather than a guaranteed bound covering all sensor and synchronization error. Timestamp storage is timezone-naive; UTC interpretation follows the OpenSky source semantics.

The source is one day, making it useful for a starter mock exercise. It cannot by itself establish performance across other dates or weather conditions.

Use the original `0_files` trajectories. The later processing code can add or adjust runway points and reconstruct tracks; these results must not become supposedly observed ground truth.

The bundled runway database includes displaced thresholds (e.g. RWY 18R: 886 ft, about 270 m). Its coordinates are runway-end positions, so a displaced threshold must be applied. Cross-check the eventual selected runway against the period-appropriate official [LVNL AIP](https://eaip.lvnl.nl/). A currently published threshold or a later approach chart is not by itself proof of its exact March 2023 coordinates.

For the source audit, official published RWY 18R threshold coordinates are latitude **52.3602583333**, longitude **4.711725**, with true runway bearing **183.20 degrees**. Source details and the historical-matching limitation are saved in `source_evidence/eham_18r_official_geometry.json`.

The record's API metadata identifies open access but contains no explicit dataset license. The paper's CC BY 4.0 notice concerns the article; it must not be silently assigned to the dataset. Original data is kept locally outside Git.

## Rejected for the main target: Zurich arrivals 2019

- [Publisher record](https://doi.org/10.6084/m9.figshare.11406735.v1).
- [Original file](https://ndownloader.figshare.com/files/20291079): `landing_dataset.parquet`, 553,337,088 bytes, MIT license.
- Downloaded to `data/raw/landing_dataset.parquet`; published MD5 `c5577f450424fa74ca673ed8a168c67f` was verified.
- The file contains 18,177,597 rows and 19,480 flight identifiers.
- Endpoint audit is saved in `zurich_all_flight_endpoints.csv`. With the published threshold geometry, most flights stop before the threshold: the 14,457 approaches assigned to RWY 14 have median end distance about 232 m before it; the 3,166 assigned to RWY 28 stop about 76 m before it.
- This source is useful for approach geometry but cannot supply a reliably observed threshold crossing for the requested main target. Do not extrapolate its endpoints to manufacture labels.

Threshold source for that diagnostic: [Skyguide VFR manual, Zurich threshold table](https://forum.drohnenverband.ch/uploads/default/original/2X/7/7c9d00a8d54938f97d6595507a2ccf77b5fce246.pdf). The Zurich table is revised December 2016; the same values appear in later Skyguide tables. Exact 2019 chart matching was not completed, so this is a source-suitability diagnostic rather than final label geometry.

## Secondary candidate with timing concerns: TartanAviation KAGC

- [Dataset authors' website](https://theairlab.org/tartanaviation/).
- [ADS-B documentation](https://github.com/castacks/TartanAviation/tree/main/adsb).
- [Paper](https://www.nature.com/articles/s41597-025-04775-6).
- [KAGC raw 2022 archive](https://airlab-cloud.andrew.cmu.edu:8080/swift/v1/AUTH_ac8533a83cff4d48bc8c608ad222d330/tartanaviation-adsb/kagc/raw/2022.zip): 236,594,743 bytes, 245 daily CSV files.
- One daily CSV has been sampled under `samples/`. Raw fields include aircraft ID, date, time, latitude, longitude, altitude, speed, track (named Heading), and Age.
- The recorder can repeatedly write an old position for up to 60 seconds. Near-threshold candidate segments in the sampled day include implausible position-derived speeds, so timestamp gaps alone do not establish good labels. One candidate has a plausible approximately 10-second crossing bracket, but this is insufficient evidence for choosing it over a better source.
- `kagc_sample_crossings.json` contains unvalidated candidate brackets, including bad candidates. It is explicitly **not ground truth**.
- The raw ZIP uses Deflate64, requiring a compatible decoder. The processed trajectories already interpolate to one-second sampling and can hide long observation gaps.

## Agreed design and remaining decisions

The user confirmed the implementation choices. The extractor and viewers are now implemented: **194 accepted approaches**, **166 rejected candidates**, and **61,238 exported trajectory points**. The latest counts and reasons are in `prepared/dataset_summary.json`; one unsplit training row per approach is in `prepared/training.csv`.

Use the executed notebook at `notebooks/01_view_flights.ipynb`, or the offline map at `prepared/viewer.html`. `share/schiphol_18R_unsplit.zip` is the small package for sharing. Exact feature columns and units are specified in `prepared/schema.json`; future label/trajectory diagnostics are separate.

See [design.md](design.md) and the root [glossary](../GLOSSARY.md) for the confirmed definitions. No model has been fitted and no train/validation/test split has been performed.
