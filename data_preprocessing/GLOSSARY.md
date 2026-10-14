# Runway arrival prediction

This practice exercise predicts remaining time from an aircraft's aligned final approach to crossing a runway threshold.

## Language

**Runway threshold (prag piste)**:
The beginning of the runway portion available for landing in a particular direction; it can differ from the physical end of the pavement.
_Avoid_: Touchdown point, airport centre

**Threshold crossing**:
The aircraft passing the transverse line through the landing threshold while approaching along the runway direction, usually still airborne.
_Avoid_: Touchdown, landing time without specifying the event

**Landing approach**:
One approach attempt toward a runway; the same aircraft can make several attempts or flights.
_Avoid_: Airplane as a synonym for one training example

**Remaining time to threshold**:
The elapsed time between the prediction snapshot and the threshold crossing of that approach.
_Avoid_: Time to touchdown

**ADS-B-derived crossing label**:
A threshold-crossing time estimated from positions observed before and after crossing, with the observation interval retained as evidence of timing uncertainty.
_Avoid_: Independently measured exact ground truth

**Confirmed alignment snapshot**:
The first observed aircraft state at which a recent sequence of observations establishes that the aircraft is close to the extended runway centreline and moving toward its threshold.
_Avoid_: Exact centreline contact, a snapshot selected using future observations

**Already-aligned recording**:
An approach whose recording begins after the aircraft is already aligned, so the initial alignment event cannot be observed.
_Avoid_: Observed alignment onset

**Landing-continuation evidence**:
Observed low-speed movement along the runway after the threshold crossing that supports classifying the approach as a landing.
_Avoid_: Independently measured touchdown time

**Training example**:
One accepted landing approach represented by its confirmed alignment snapshot and remaining-time label.
_Avoid_: One aircraft, one entire trajectory
