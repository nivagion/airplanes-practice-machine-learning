# Dataset audit evidence

## Zurich real landing reference dataset

Primary metadata: https://figshare.com/articles/dataset/Reference_data_sets_for_detection_and_identification_of_significant_events_in_historical_aircraft_trajectory_data_/11406735

Downloaded file `data/raw/landing_dataset.parquet` is 553337088 bytes; verified MD5 c5577f450424fa74ca673ed8a168c67f. The Figshare API declares MIT license. There are 18177597 rows and 19480 unique flight IDs, with UTC timestamps in October and November 2019. All `onground` values are false. The file has one Parquet row group. Processed or resampled values occur; every one-second row should not be treated as an independent original ADS-B message.

Endpoint audit: `data_research/zurich_all_flight_endpoints.csv`. Using provisional historical Skyguide threshold geometry supplied by the parent researcher, endpoints stop before the true threshold for 19474 of 19480 flights. Runway 14 has 14457 flights and median final along-axis distance -231.59 m; only six end past its threshold. Runway 28 has 3166 flights and median -75.54 m; none end past the threshold. Runway 16 has nine flights and median -68.55 m; none end past the threshold. Runway 34 has 1598 flights and median -555.83 m; none end past the threshold. The remaining 250 have unclassified runway. This source is unsuitable for most actual runway-threshold crossing labels.

## TartanAviation KAGC

Primary dataset: https://theairlab.org/tartanaviation/

Raw 2022 archive: https://airlab-cloud.andrew.cmu.edu:8080/swift/v1/AUTH_ac8533a83cff4d48bc8c608ad222d330/tartanaviation-adsb/kagc/raw/2022.zip

It is publicly reachable and contains 245 daily CSVs in 236594743 bytes. ZIP compression method 9 is Deflate64; the inflate64 wheel handles it. The first day required 327815 bytes via HTTP ranges, yielding a 4612096-byte CSV saved as `data_research/samples/kagc_01-01-22_1.csv`.

The first day has 29576 rows, 4147 observations after deduplicating aircraft plus timestamps, and 113 aircraft IDs. There were 382 rows failing basic parsing or numeric validation. The published recorder persists previous state for up to 60 seconds while Age grows. Two candidate runway-28 brackets fail position-versus-speed kinematics dramatically; a decimal Time must not be equated with accurate fresh position measurement. CNS242 has a plausible bracket from 2022-01-01T21:18:08.473Z to 2022-01-01T21:18:18.463Z, spanning about 492 m in 9.99 seconds, consistent with reported speed. KAGC is only conditionally suitable after strict quality filters, with coarse label uncertainty.

## Dorbolo / Pretto / Giannattasio high-resolution OpenSky source

Primary paper: https://journals.open.tudelft.nl/joas/article/view/7208

Primary PDF: https://journals.open.tudelft.nl/joas/article/download/7208/5893/27325

Primary data and code: https://zenodo.org/records/10074634

The paper explicitly states one-second data and good on-ground coverage. Its Schiphol EHAM example on 15 March 2023 has 1077 operations, comprising 550 arrivals and 527 departures. The code defaults to EGLL on 2023-03-15, so the archive may include both airports. The 0_files.zip archive is 505887939 bytes. Zenodo API access_right is open, but metadata omits license and rights. The paper has a CC BY 4.0 license; this alone does not establish a separate data license.

The function in 2_preproc/codes/databases.py adjusts displaced thresholds with geod.fwd using physical-end coordinates and threshold offsets. However, 2_preproc also inserts or adjusts runway points via arrival_runway_points_assignment and align_runway_points, and alters altitude. Use original trajectories in 0_files for crossing labels; avoid using reconstructed output as observed ground truth.


### Verified EHAM audit result

The EHAM member was fetched directly with HTTP byte ranges, then inflated and checked against the ZIP CRC32 c09a2447. The extracted Parquet file is 243480264 bytes and has SHA256 4cb0c59595c1cf37457fd7748167e1373206daf882167016ce0858255a9b3039. Exact extraction provenance is in eham_range_extraction.json.

It contains 6924104 rows. Its exported fields include timestamp, latitude, longitude, altitude, callsign, icao24, origin, destination, groundspeed, track, and vertical_rate. The timestamp lacks explicit timezone metadata; interpret as UTC using OpenSky semantics and the published date. Unlike the paper's broader source, this particular export lacks onground and lastposupdate.

Using the official published threshold-18R coordinate 52.3602583333, 4.711725 and true track 183.20 degrees, the initial scan found 351 plausible arrival crossing brackets. These represent 351 callsigns and 272 aircraft, and every bracket spans one second. Requiring implied speed within 75 to 125 percent of reported speed retains 265 brackets. These counts are initial audit candidates, not final training rows. Threshold geometry agrees between the supplied current AIP and an approach chart revised 28 December 2023; an exact March 2023 AIP match remains unverified.

An example is MSR757 (0101b7), with a position 3.72 m before the threshold at 12:47:56 UTC and one 64.73 m beyond it at 12:47:57 UTC on 15 March 2023. The implied ground speed is 68.46 m/s, compared with reported 144 kt (74.08 m/s). Linear interpolation gives approximately 12:47:56.054 UTC; this is a crossing estimate, not independent subsecond ground truth. A 620-row trajectory excerpt is saved as data_research/samples/eham_first_valid_18R_arrival.csv, with only one repeated consecutive position. At 12:45:22 UTC it is already within a 100 m alignment corridor, with a 2.17 m cross-track distance and approximately 11.98 km remaining.

EHAM is the recommended airport and source for this exercise, subject to final filtering, observed-point freshness limitations, and geometry provenance. Sample bracket and summary JSON files use valid JSON with unavailable values represented by null.
