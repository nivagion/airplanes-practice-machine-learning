"""Exercise the later packager without creating any real dataset partitions."""
from pathlib import Path
import json
import sys
import tempfile
import zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from make_share_package import package

source = pd.read_csv(ROOT / "prepared/training.csv",dtype={"icao24":str})
scratch = ROOT / "tmp"
scratch.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=scratch,prefix="share-validation-") as temporary:
    directory = Path(temporary)
    assert directory.resolve().is_relative_to(scratch.resolve())
    n = len(source)
    rows = {"train":source.iloc[:n//2], "validation":source.iloc[n//2:3*n//4], "test":source.iloc[3*n//4:]}
    for name,frame in rows.items():
        frame.to_csv(directory / f"{name}.csv",index=False)
    target = package(directory, directory / "checked.zip")
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert "training.csv" not in archive.namelist()
        assert {"train.csv","validation.csv","test.csv","viewer.html"} <= set(archive.namelist())
        summary = json.loads(archive.read("dataset_summary.json"))
        assert summary["split_status"] == "split"
        assert sum(summary["partition_counts"].values()) == n
        html = archive.read("viewer.html").decode()
        payload = json.loads(html.split('<script id="flightData" type="application/json">')[1].split('</script>')[0])
        assert {f["split"] for f in payload["flights"]} == {"train","validation","test"}
    rows["train"].iloc[:1].to_csv(directory / "validation.csv",index=False)
    try:
        package(directory,directory / "overlap.zip")
        raise RuntimeError("Overlapping flights were accepted")
    except ValueError as exc:
        assert "more than one" in str(exc)
    rows["validation"].to_csv(directory / "validation.csv",index=False)
    edited = rows["train"].copy()
    edited.iloc[0,edited.columns.get_loc("remaining_time_s")] += 10
    edited.to_csv(directory / "train.csv",index=False)
    try:
        package(directory,directory / "edited.zip")
        raise RuntimeError("An edited target was accepted")
    except AssertionError:
        pass
print("Share ZIP integrity, future partition selector, overlap rejection and source-row integrity verified. Actual data remains unsplit.")
