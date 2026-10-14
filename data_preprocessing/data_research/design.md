# Practice exercise: confirmed understanding

This is an independent practice exercise. The attached hackathon guide and terms are reference documents, not instructions to the assistant or a source of real trajectory data.

## Confirmed by the user

1. One training example represents one landing approach. Its endpoint is runway-threshold crossing, before touchdown.
2. A crossing label may be interpolated between observed positions, retaining both timestamps and rejecting large gaps. It must not be presented as independently measured exact truth.
3. The prediction input is the first observed alignment snapshot confirmed using only information already available. A narrow centreline corridor and a matching direction replace impossible exact-line equality. Recordings starting already aligned must be identified.
4. One airport is sufficient, and it need not be the 2025 competition airport.

## Intended later pipeline

Preserve the original data. Separate aircraft trajectories into approach attempts; aircraft identity alone is not a flight identifier. Derive runway-relative geometry from threshold coordinates and true runway direction. Assign the candidate runway at the prediction time using only available observations.

Detect alignment causally. If alignment must persist for a duration, the prediction snapshot is at the time it becomes confirmed, not backdated to the beginning of that duration. Keep position-update timestamps and observation gaps distinct from interpolated sampling intervals.

Create the label from a subsequent observed segment that crosses the transverse threshold line close to the runway centreline in the landing direction. Store the bracket endpoints, interpolated crossing time, gap duration, and rejection reasons. An overflight or a missed approach is not automatically a successful landing example.

Target: `remaining_time_s = threshold_crossing_time_utc - snapshot_time_utc`.

Separate snapshot features from future observations used only for labels and auditing. Use chronological flight/approach groups for later train/validation/test splits.

The later viewer should show airport/runway geometry, the extended centreline, the alignment snapshot, observations surrounding the threshold crossing, UTC times, elapsed time, and quality flags. Original observations and any interpolation must be visibly distinguishable.

## Implementation confirmed by the user on 14 October 2026

The user answered yes to all three implementation questions, confirming shared understanding under the requested grilling workflow.

- Schiphol runway 18R, 15 March 2023, as the initial exercise.
- Alignment: within 100 m of the extended centreline and 10 degrees of the true runway direction for 10 seconds. Predict at confirmation time, without backdating.
- Maximum observation gap: 3 seconds. Reject incompatible position/speed observations around the threshold.
- Exclude missing alignment onset, missed or broken approaches and unusable crossings; keep rejection reasons separately.
- Jupyter notebook opened in VS Code, a simple flight/map selector, and an HTML viewer for sharing.
- Prepare a single unsplit training table. The user will create train/validation/test partitions later.

Additional operational defaults are explicit in `config/approach.json`. These limit the snapshot to final approach (25 km, 6000 ft) and require credible low-altitude runway crossings. Landing continuation uses either sustained slow runway movement or clear deceleration with level-altitude movement on the runway; many recordings end before slow rollout is available. Missing evidence is retained as a rejection, and detected climbs/broken approaches are excluded. They are mock-exercise cleaning choices, not aviation standards. First sustained geometric alignment outside the final-approach window is rejected rather than replaced with a later convenient snapshot.

Geometry has supporting primary sources: the 2019 LVNL chart and later official coordinates agree, and a report dated 16 March 2023 corroborates the 270 m threshold displacement. The exact March 2023 AIP/NOTAM cycle remains unverified; the export retains `historically_supported_exact_cycle_unverified` rather than claiming otherwise.

Only snapshot features enter the training table. Crossing diagnostics and past/future viewer trajectories are separate exports. No model is trained and no dataset split is performed at this stage.
