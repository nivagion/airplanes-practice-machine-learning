"""Small notebook interface over already prepared files."""
import json
from pathlib import Path

import pandas as pd


def load_prepared(root: Path):
    folder = root / "prepared"
    return (pd.read_csv(folder / "training.csv", dtype={"icao24": str}),
            pd.read_csv(folder / "labels_audit.csv", dtype={"icao24": str}),
            pd.read_csv(folder / "tracks.csv.gz", parse_dates=["timestamp"]),
            json.loads((folder / "airport_runways.json").read_text()),
            json.loads((folder / "schema.json").read_text()))


def show_flight(example_id, training, labels, tracks, runways, heading=183.2):
    import math
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    from IPython.display import display, HTML

    row = training.loc[training.example_id.eq(example_id)].iloc[0]
    label = labels.loc[labels.example_id.eq(example_id)].iloc[0]
    track = tracks.loc[tracks.example_id.eq(example_id)].sort_values("timestamp")
    snapshot = track.loc[track.time_from_snapshot_s.abs().idxmin()]
    crossing = track.loc[(track.time_from_snapshot_s - row.remaining_time_s).abs().idxmin()]
    table = pd.DataFrame([
        {"Event": "Prediction snapshot", "UTC time": pd.Timestamp(row.snapshot_time_utc).strftime("%H:%M:%S"),
         "Latitude": row.latitude_deg, "Longitude": row.longitude_deg},
        {"Event": "Threshold crossing estimate", "UTC time": pd.Timestamp(label.crossing_time_utc).strftime("%H:%M:%S.%f")[:-5],
         "Latitude": label.crossing_latitude_deg, "Longitude": label.crossing_longitude_deg},
    ])
    display(HTML(table.to_html(index=False, float_format=lambda value: f"{value:.6f}")))
    print(f"{row.callsign} · remaining time ≈ {row.remaining_time_s:.1f} s · sampled crossing bracket {label.remaining_bracket_start_s:.1f}–{label.remaining_bracket_end_s:.1f} s")
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), layout="constrained")
    h = math.radians(heading)
    past, future = track[track.time_from_snapshot_s <= 0], track[track.time_from_snapshot_s >= 0]
    for ax in axes:
        ax.set_facecolor("#f5f8f5")
        for runway in runways:
            ax.add_patch(Polygon([[x/1000, y/1000] for x, y in runway["polygon"]],
                                 facecolor="#647d8c" if runway["main"] else "#b2bec7", edgecolor="#7e919f"))
        ax.plot([0, -math.sin(h)*27], [0, -math.cos(h)*27], "--", color="#7c8e99", lw=1.2, label="Extended centreline")
        ax.plot(past.east_m/1000, past.north_m/1000, color="#2563eb", lw=2, label="Observed history")
        ax.plot(future.east_m/1000, future.north_m/1000, "--", color="#d97706", lw=2, label="Future path: label check")
        ax.scatter(snapshot.east_m/1000, snapshot.north_m/1000, color="#15803d", s=60, edgecolor="white", zorder=6, label="Prediction snapshot")
        # Interpolated threshold point, distinguished from sampled positions.
        f = (pd.Timestamp(label.crossing_time_utc) - pd.Timestamp(label.crossing_before_utc)).total_seconds() / label.crossing_gap_s
        before = track.loc[track.timestamp.eq(pd.Timestamp(label.crossing_before_utc))].iloc[0]
        after = track.loc[track.timestamp.eq(pd.Timestamp(label.crossing_after_utc))].iloc[0]
        ex, ey = (before.east_m+f*(after.east_m-before.east_m))/1000, (before.north_m+f*(after.north_m-before.north_m))/1000
        ax.scatter(ex, ey, color="#d97706", s=65, marker="D", edgecolor="white", zorder=7, label="Crossing estimate")
        ax.annotate("18R threshold", (ex, ey), xytext=(9, 8), textcoords="offset points", fontsize=9)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("East / west from threshold (km)")
        ax.set_ylabel("North / south from threshold (km)")
        ax.grid(alpha=.18)
    all_x = [x/1000 for r in runways for x,y in r["ends"]] + list(track.east_m/1000)
    all_y = [y/1000 for r in runways for x,y in r["ends"]] + list(track.north_m/1000)
    axes[0].set_xlim(min(all_x)-1, max(all_x)+1)
    axes[0].set_ylim(min(all_y)-1, max(all_y)+1)
    axes[0].set_title("Full approach · north up", loc="left")
    axes[0].legend(loc="upper left", fontsize=8, framealpha=.9)
    axes[1].set_xlim(-.35,.35)
    axes[1].set_ylim(-.65,.4)
    axes[1].scatter([before.east_m/1000,after.east_m/1000], [before.north_m/1000,after.north_m/1000],
                    color="#334155", s=30, zorder=8, label="Bracket observations")
    axes[1].set_title("Threshold close-up · 270 m displaced", loc="left")
    axes[1].legend(loc="lower left", fontsize=8)
    fig.suptitle(f"{row.callsign} · Schiphol runway 18R", fontsize=15, fontweight="bold")
    return fig


def flight_selector(training, labels, tracks, runways):
    import ipywidgets as widgets
    import matplotlib.pyplot as plt
    from IPython.display import display, clear_output
    options = [(f"{r.callsign} · {r.snapshot_time_utc[11:19]} UTC", r.example_id) for r in training.itertuples()]
    dropdown = widgets.Dropdown(options=options, description="Flight:", layout=widgets.Layout(width="520px"))
    output = widgets.Output()

    def render(change=None):
        with output:
            clear_output(wait=True)
            fig = show_flight(dropdown.value, training, labels, tracks, runways)
            display(fig)
            plt.close(fig)

    dropdown.observe(render, names="value")
    display(dropdown, output)
    render()
    return dropdown
