"""Export MAE panels from saved notebook PNGs without rerunning training.

Run from the repository root:
    python scripts/export_readme_plots.py

Pillow is included in requirements.txt. Crops match the current notebook layouts;
visually check the exported images if the plot layouts change.
"""

import base64
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "training"
OUTPUT = ROOT / "docs" / "images"


def export_panel(notebook_name, filename, crop_fraction, clean_right_margin=False):
    notebook = json.loads((NOTEBOOKS / notebook_name).read_text(encoding="utf-8"))
    # Select the final saved MAE training figure, excluding prediction diagnostics.
    candidates = [
        output["data"]["image/png"]
        for cell in notebook["cells"]
        if any(
            marker in "".join(cell.get("source", []))
            for marker in ("train_mae_line", "line_train_mae")
        )
        for output in cell.get("outputs", [])
        if "image/png" in output.get("data", {})
    ]
    if not candidates:
        raise ValueError(f"No saved MAE training figure in {notebook_name}")
    encoded = candidates[-1]
    if isinstance(encoded, list):
        encoded = "".join(encoded)
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as source:
        width, height = source.size
        panel = source.crop(
            (0, 0, round(width * crop_fraction[0]), round(height * crop_fraction[1]))
        ).convert("RGB")
        if clean_right_margin:
            # The neighbouring MSE ylabel overlaps the last MAE tick horizontally.
            # Remove only that neighbour, keeping the full 30,000-epoch tick below.
            ImageDraw.Draw(panel).rectangle(
                (round(width * 0.484), 0, panel.width, round(height * 0.872)),
                fill="white",
            )
        OUTPUT.mkdir(parents=True, exist_ok=True)
        path = OUTPUT / filename
        panel.save(path, optimize=True)
        print(f"{path.relative_to(ROOT)}: {panel.width} x {panel.height}")


if __name__ == "__main__":
    export_panel("194_airplanes/01_training.ipynb", "01-training-mae.png", (0.502, 1.0), True)
    export_panel("194_airplanes/02_two_hidden_layers.ipynb", "02-two-hidden-layers-mae.png", (0.493, 0.496))
    export_panel("2596_airplanes/03_more_airplanes.ipynb", "03-more-airplanes-mae.png", (0.493, 0.496))
