# Training workspace

Each dataset has its own folder, with `training.csv` and `schema.json` directly at its root:

| Folder | Rows | Input features | Contents |
| --- | ---: | ---: | --- |
| [194_airplanes](194_airplanes/README.md) | 194 | 11 | Original dataset, both existing notebooks and package lock file |
| [2596_airplanes](2596_airplanes/README.md) | 2,596 | 16 | Expanded multi-airport dataset, coverage and dataset summary |

Both predict `remaining_time_s`: seconds from first confirmed runway alignment to estimated threshold crossing. Use the `feature_columns` list in that folder's schema for model inputs. Identifiers and timestamps are metadata.

The existing notebooks and their saved outputs are in `194_airplanes/`. Start the next model's notebook in `2596_airplanes/`, alongside its CSV and schema. The expanded table remains unsplit; prepare flight-grouped train/validation/test partitions and fit transformations only on the training partition. The expanded model needs 16 inputs, which should be read from its schema.

Both folders share the existing `training/.venv` environment. Select **Aircraft training (Python 3.12)** as the notebook kernel. Environment setup commands are in the [repository README](../README.md). Exact installed versions are recorded in [194_airplanes/requirements.lock.txt](194_airplanes/requirements.lock.txt).

The expanded preprocessing pipeline writes future datasets to `training/<row_count>_airplanes/`, based on the accepted row count. See the [expansion guide](../data_preprocessing/EXPANSION.md) for rebuilding, validation and adding more data. The convenience copy in the repository's `prepared/` folder is also still available.
