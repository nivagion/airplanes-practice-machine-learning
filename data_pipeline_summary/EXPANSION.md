# Expanding acquisition and preprocessing

The multi-airport pipeline is now implemented in
[data_preprocessing/EXPANSION.md](../data_preprocessing/EXPANSION.md), with frozen
source acquisition, explicit adapters, directional runway geometry, causal
runway selection, separate expanded training files and rejection audits. The
notes below retain the broader design considerations. QNH/datum correction,
historical AIP verification for all runways and repeated-attempt segmentation
remain future work; a shared interface alone cannot establish suitability for
every airstrip.

## Elevation audit

**The original baseline recorded elevation without using it.** The expanded
pipeline now uses threshold-relative pressure-altitude proxies consistently
while preserving raw pressure altitude and marking the uncorrected vertical
reference. It does not claim calibrated height above ground. The audit below
describes the original baseline.

Evidence in the current files:

- [The loaded geometry](../data_preprocessing/data_research/source_evidence/eham_18r_historical_geometry_audit.json) contains `threshold_elevation_ft_current_aip: -13.2` and historical rounded elevation `-13`. These are saved evidence values, not newly verified current AIP values.
- [The runway database](../data_preprocessing/data_research/source_evidence/dorbolo_runways_EHAM.json) contains runway-end elevations in `le_elevation_ft` and `he_elevation_ft`.
- [dataset.py](../data_preprocessing/src/approach/dataset.py) never reads those elevation fields. `add_geometry()` only computes `baro_altitude_m = altitude * 0.3048`.
- `ecef()` explicitly uses surface positions without altitude for horizontal geometry. Its 2D projection does not produce vertical clearance.
- The exported schema labels altitude as **barometric metres, pressure uncorrected**. No QNH correction, threshold-relative height or terrain-height calculation is implemented.

| Stage | Current altitude use | Expansion problem |
| --- | --- | --- |
| Initial source sanity filter | Retain missing altitude or values from -2,000 to 60,000 ft | Source-specific range/datum assumptions need validation. |
| Loose candidate search | Below 10,000 ft, hard-coded | Absolute pressure altitude can exclude high airports or inappropriate approach windows. |
| Snapshot | At most 6,000 ft from configuration | Does not describe height above the landing threshold. |
| Preliminary threshold segment | Below 1,500 ft, hard-coded | Can prevent a crossing bracket from reaching the later checks at an elevated airport. |
| Accepted crossing | At most 500 ft from configuration | Rejects otherwise valid elevated-airport approaches because runway height is not subtracted. |
| Landing continuation | Also uses the 500 ft ceiling; allows missing altitude for slow rollout | Carries the same absolute-altitude assumption into landing evidence. |
| Go-around / level checks | Altitude changes, altitude range and vertical rate | Constant elevation offsets cancel in differences, but source consistency and associated absolute ceilings still matter. |

For example, a hypothetical runway at 3,000 ft with an aircraft around 3,050 ft at threshold would fail the present absolute 500 ft ceiling, even with otherwise suitable observations. Schiphol's threshold is close to sea level, so this issue is easy to overlook in the initial dataset.

### Required vertical handling

Keep raw altitude, units and altitude type (pressure, barometric corrected to local pressure, or GNSS), together with the vertical reference and source evidence. Use the **landing threshold's elevation**, rather than only the airport reference elevation. Opposite runway ends may differ, and a displaced threshold needs its own verified value.

When aircraft altitude and threshold elevation are expressed in a compatible vertical reference:

```text
height_above_threshold_m = aircraft_altitude_amsl_m - threshold_elevation_amsl_m
```

Subtracting threshold elevation from uncorrected pressure altitude provides only a proxy, not calibrated height. A defensible barometric path requires suitable time/location-specific pressure information and a documented correction. GNSS height needs its datum identified and, where necessary, conversion from ellipsoidal height to the elevation datum. If required information is missing, retain an explicit quality/availability flag and do not silently call the result true height.

Height above threshold is also different from height above terrain along an approach. Terrain clearance would require separate terrain data.

Use documented threshold-relative height limits consistently in candidate search, snapshot selection, preliminary crossing search, crossing validation and landing continuation. Reassess the numerical limits with each source/airport rather than simply relabeling the current 500 ft rule. Preserve the original pressure-altitude feature and correction provenance for auditing.

## Shared pipeline to build

```text
source manifest -> reproducible acquisition -> source adapter -> normalized observations
                -> deduplication/flight and attempt segmentation
runway registry -> causal runway selection + runway-relative geometry + vertical handling
                -> alignment snapshot -> observed crossing + landing evidence
                -> snapshot table + label/rejection audits + provenance
```

1. **Add a source manifest and acquisition command.** For each dataset record a stable ID/version, publisher URL, archive member, checksum, licence evidence, coverage dates, timezone, raw units, altitude type, freshness fields and local raw path. Download/extract into separate immutable source folders and verify available integrity evidence. Existing byte offsets describe one archived file, not a general extraction method.
2. **Implement source adapters.** Convert each schema into a common observation table before shared rules run. Proposed fields include `dataset_id`, `source_file`, `source_row_id`, `timestamp_utc`, `icao24`, `callsign`, `latitude_deg`, `longitude_deg`, `groundspeed_mps`, `track_deg`, `vertical_rate_mps`, raw altitude/type/datum and optional `last_position_update_utc`, `position_age_s`, `onground`. Missing capabilities must remain explicit. Verify ground track versus heading semantics instead of mapping names blindly; preserve TartanAviation's `Age` and `AltisGNSS` evidence.
3. **Create a runway-direction registry.** Key geometry by airport, runway direction and validity interval. Store threshold coordinates, true bearing, threshold elevation/datum, displacement, width, landing distance, provenance and geometry quality. Calculate geographic search bounds from that geometry instead of the EHAM bounding box. Treat opposite directions as separate landing thresholds.
4. **Separate shared cleaning from source policy.** Preserve original times and position-update age. Distinguish exact duplicate records, conflicting simultaneous positions, stale positions and independently fresh observations. Keep missing ground fields where justified. Do not fill gaps to make a source pass quality limits, and do not label reconstructed runway points as observed crossings.
5. **Strengthen identity and approach segmentation.** Current callsign/time-gap segments can contain repeated attempts; the extractor emits at most one example per segment. Add explicit attempt segmentation for go-arounds/re-approaches. Use dataset-scoped IDs plus an overlap policy so the same real flight present in two datasets is not counted twice or assigned incompatible identities.
6. **Select runways causally.** Consider available runway directions using only observations up to the prediction snapshot. Parallel/intersecting runway ambiguity needs a declared policy or rejection reason. Do not pick a runway using the eventual future crossing and then claim it was known at prediction time.
7. **Apply vertical normalization and consistent rules.** Implement the elevation changes above; move remaining hard-coded candidate/crossing/rollout limits into documented policy. Keep geometry-dependent limits and source-quality decisions distinct. A source with a 10 s crossing bracket cannot silently pass a 3 s quality rule.
8. **Export auditable combined data.** Add dataset, airport, runway direction, attempt ID, geometry version, processing version and vertical-quality metadata. Keep normalized snapshot features separate from future label evidence. Write per-source/per-airport acceptance counts and reasons, and handle zero accepted examples cleanly; the current export assumes accepted rows exist. Emit separate prepared folders or a combined run ID to avoid overwriting one dataset with another.

Current hard-coded items to remove include the raw filename, geometry filename, EHAM destination/bounding box, candidate limits, preliminary crossing limits, `EHAM18R_` example prefix, exported `18R` metadata, EHAM summary/source URL and viewer/package assumptions. Changing only `config/approach.json` is insufficient.

The reusable core is already present: runway-local horizontal geometry, causal alignment confirmation, observed crossing interpolation, gap/speed checks and separate snapshot/audit exports. Reuse those semantics while adding adapters and configurable context.

## Data checks before expanding coverage

Extend the existing label tests and output validation with an elevated-runway case, below-sea-level threshold, incompatible/missing altitude datum, both runway directions, displaced threshold, parallel-runway ambiguity, repeated approach attempts, duplicate flights across datasets, stale position updates and an empty accepted set. Check that editing future observations cannot change the prediction snapshot or its runway assignment.

Report accepted/rejected coverage separately for each source, airport and runway, including vertical-data availability and crossing-bracket duration. Add more days and seasonal conditions as well as airports. The current 194 examples from one day establish a starting extraction workflow, not coverage across all airstrips.

An additional EHAM day would first exercise acquisition/normalization repeatability; EGLL from the same archive could then exercise new geometry with a similar source schema. Zurich requires actual observed threshold coverage before inclusion for this target. KAGC requires a dedicated freshness/timestamp audit before its examples can be treated as comparable labels.
