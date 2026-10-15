# Scripts and supporting files

Paths below link to the existing implementation. There is no duplicated code in this summary folder.

## Acquisition and provenance

| File | What it does / how to extend it |
| --- | --- |
| [data_research/README.md](../data_preprocessing/data_research/README.md) | Compares EHAM, Zurich and KAGC; records download links, coverage, suitability and source limitations. Start here when choosing another source. |
| [source_evidence/dataset_audit_notes.md](../data_preprocessing/data_research/source_evidence/dataset_audit_notes.md) | Records parsing, endpoint and freshness findings. The research scripts that produced these audits are not retained as reusable acquisition commands. |
| [eham_range_extraction.json](../data_preprocessing/data_research/source_evidence/eham_range_extraction.json) | EHAM archive member, byte offsets, sizes and integrity evidence. Metadata only; it does not perform extraction. |
| [dorbolo_zenodo_metadata.json](../data_preprocessing/data_research/dorbolo_zenodo_metadata.json), [zenodo_10074634.json](../data_preprocessing/data_research/source_evidence/zenodo_10074634.json), [zurich_figshare_metadata.json](../data_preprocessing/data_research/zurich_figshare_metadata.json) | Saved publisher metadata for provenance; not normalized trajectory data. |
| [tartanaviation_adsb_README.md](../data_preprocessing/data_research/tartanaviation_adsb_README.md) | Saved upstream ADS-B documentation. |
| [tartanaviation_recording_source.py](../data_preprocessing/data_research/tartanaviation_recording_source.py) | Upstream live recorder evidence explaining retained states, `Age` and `AltisGNSS`. Uses a private receiver WebSocket, platform-specific paths and an external `utils` module. Not a runnable project ingestion pipeline. |
| [EHAM candidate brackets](../data_preprocessing/data_research/eham_18R_sample_crossings.json), [Zurich diagnostic](../data_preprocessing/data_research/zurich_sample_crossings.json), [KAGC candidate brackets](../data_preprocessing/data_research/kagc_sample_crossings.json) | Research examples and diagnostics, not final training labels. |
| [EHAM audit summary](../data_preprocessing/data_research/source_evidence/eham_audit_summary.json) | Preliminary source-suitability results; distinguish these counts from prepared output counts. |

## Extraction and label creation

| File / functions | Responsibility and expansion point |
| --- | --- |
| [prepare_data.py](../data_preprocessing/prepare_data.py) | Calls `build_dataset()` and `build_viewer()`. Future entry point could accept a source manifest and airport/runway selection. |
| [config/approach.json](../data_preprocessing/config/approach.json) | Adjustable alignment, gap, crossing and landing-evidence rules. Airport/runway labels here do not parameterize all hard-coded EHAM behavior. |
| [dataset.py](../data_preprocessing/src/approach/dataset.py): `build_dataset()` | Source reading, cleanup, segment IDs, candidate selection, orchestration and exports. Main place to separate source adapters from shared processing. |
| Same module: `ecef()`, `local_xy()`, `add_geometry()` | Horizontal coordinates and runway-relative features. Geometry functions accept threshold coordinates/bearing; altitude currently receives unit conversion only. |
| Same module: `first_confirmed_alignment()` | Causal snapshot selection. Preserve confirmation-time semantics when handling multiple runway candidates. |
| Same module: `first_threshold_segment()`, `check_crossing()` | Locate an observed bracket and validate/interpolate the target. Preliminary search includes hard-coded altitude/corridor limits. |
| Same module: `has_landing_continuation()` | Post-crossing quality evidence using available landing distance, speed, altitude stability and deceleration. Rules currently assume the EHAM source. |
| Same module: `snapshot_features()`, `FEATURE_COLUMNS` | Finite snapshot features and input allowlist. Update with explicit altitude datum and threshold-relative height when supported. |
| [eham_18r_historical_geometry_audit.json](../data_preprocessing/data_research/source_evidence/eham_18r_historical_geometry_audit.json) | Geometry actually loaded by the extractor: threshold, bearing, displacement, landing distance, elevation evidence and historical limits. |
| [eham_18r_official_geometry.json](../data_preprocessing/data_research/source_evidence/eham_18r_official_geometry.json), [dorbolo_runways_EHAM.json](../data_preprocessing/data_research/source_evidence/dorbolo_runways_EHAM.json) | Additional official geometry evidence and source runway database. The database supplies contextual runway shapes. |
| [docs/data_README.md](../data_preprocessing/docs/data_README.md), [data_research/design.md](../data_preprocessing/data_research/design.md), [GLOSSARY.md](../data_preprocessing/GLOSSARY.md) | Export instructions, agreed extraction semantics and definitions. Update the export instructions when source/geometry behavior changes. |
| [requirements.txt](../data_preprocessing/requirements.txt), [src/approach/__init__.py](../data_preprocessing/src/approach/__init__.py) | Preprocessing dependencies and package initializer. |

## Inspection, validation and packaging

These support checking the prepared data; they do not acquire raw data or create additional labels.

| File | Responsibility and expansion point |
| --- | --- |
| [viewer.py](../data_preprocessing/src/approach/viewer.py), [viewer_template.html](../data_preprocessing/src/approach/viewer_template.html) | Build an offline map and embed trajectories/labels. Runway shape selection, source paths and presentation contain 18R/EHAM assumptions. |
| [notebook.py](../data_preprocessing/src/approach/notebook.py) | Load prepared files and display selectable approaches. Default bearing and titles are specific to Schiphol 18R. |
| [scripts/create_notebook.py](../data_preprocessing/scripts/create_notebook.py), [notebooks/01_view_flights.ipynb](../data_preprocessing/notebooks/01_view_flights.ipynb) | Generate and use the inspection notebook. Generator writes the notebook; generalize its airport text if regenerating for other airports. |
| [tests/test_labels.py](../data_preprocessing/tests/test_labels.py) | Tests displacement, causal confirmation, missing onset, gaps, future-input isolation, interpolation, speed consistency and landing versus climbing evidence. |
| [scripts/validate_outputs.py](../data_preprocessing/scripts/validate_outputs.py) | Checks prepared row integrity, targets, confirmation windows, crossing geometry and saved notebook/widget outputs. Some rule values are literal constants; generalize alongside configuration. |
| [make_share_package.py](../data_preprocessing/make_share_package.py) | Packages existing prepared data and viewer. Optionally verifies user-supplied partitions against source rows; never chooses partitions. ZIP naming is Schiphol-specific. |
| [scripts/validate_sharing.py](../data_preprocessing/scripts/validate_sharing.py) | Exercises ZIP integrity, partition coverage, overlapping-flight rejection and edited-row rejection using temporary fixtures. |
