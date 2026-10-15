# Training workspace

Each dataset has its own folder, with `training.csv` and `schema.json` directly at its root:

| Folder | Rows | Input features | Contents |
| --- | ---: | ---: | --- |
| [194_airplanes](194_airplanes/README.md) | 194 | 11 | Original dataset, both existing notebooks and package lock file |
| [2596_airplanes](2596_airplanes/README.md) | 2,596 | 16 | Expanded multi-airport dataset, notebook 03 with saved results, coverage and dataset summary |

Both predict `remaining_time_s`: seconds from first confirmed runway alignment to estimated threshold crossing. Use the `feature_columns` list in that folder's schema for model inputs. Identifiers and timestamps are metadata.

The original notebooks and their saved outputs are in `194_airplanes/`. [03_more_airplanes.ipynb](2596_airplanes/03_more_airplanes.ipynb) trains a 16 → 8 → 1 model on the expanded dataset, which has about **13.4 times as many approaches**. Its latest saved run reports **7.66 s validation MAE** on 389 approaches and **7.71 s test MAE** on 390 reserved approaches, with 1,817 used for training. Section 13 evaluates the saved checkpoint without retraining. See the [repository README](../README.md#training-results) for all three MAE graphs, baseline comparisons and the test evaluation explanation.

The expanded CSV remains unsplit on disk; notebook 03 creates flight-grouped train/validation/test partitions in memory and fits transformations only on the training partition. Its input size comes from the expanded schema's 16 features.

Both folders share the existing `training/.venv` environment. Select **Aircraft training (Python 3.12)** as the notebook kernel. Environment setup commands are in the [repository README](../README.md). Exact installed versions are recorded in [194_airplanes/requirements.lock.txt](194_airplanes/requirements.lock.txt).

The expanded preprocessing pipeline writes future datasets to `training/<row_count>_airplanes/`, based on the accepted row count. See the [expansion guide](../data_preprocessing/EXPANSION.md) for rebuilding, validation and adding more data. The convenience copy in the repository's `prepared/` folder is also still available.
