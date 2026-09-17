"""Check reported analysis invariants against the saved snapshot and evidence tables."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

root = Path(__file__).resolve().parents[1]
out = root / "reports/replication"
manifest = json.loads((out / "manifest.json").read_text())
ml = json.loads((out / "ml_manifest.json").read_text())
panel = pd.read_parquet(out / "panel.parquet")
daily = pd.read_parquet(out / "daily_panel.parquet")
files = pd.read_csv(out / "tables/source_files.csv")
assert len(files) == manifest["committed_files"]
assert files.bytes.sum() == manifest["raw_bytes"]
assert all(
    hashlib.sha256(Path(r.path).read_bytes()).hexdigest() == r.sha256 for r in files.itertuples()
)
assert len(panel) == manifest["common_rows"] == manifest["common_days"] * manifest["locations"] * 24
assert len(daily) == manifest["common_days"] * manifest["locations"]
assert panel.location_id.nunique() == manifest["locations"]
assert not panel.duplicated(["location_id", "timestamp"]).any()
assert daily.hours.eq(24).all()
metrics = [
    "temperature_2m",
    "precipitation",
    "wind_speed_10m",
    "relative_humidity_2m",
    "pressure_msl",
]
assert panel[metrics].notna().all().all()
assert daily[metrics].notna().all().all()
agg = pd.read_csv(out / "tables/location_summary.csv")
np.testing.assert_allclose(agg.temperature_2m.mean(), panel.temperature_2m.mean())
np.testing.assert_allclose(agg.period_rainfall_mm.sum(), panel.precipitation.sum())
correlations = pd.read_csv(out / "tables/correlations.csv")
reported = (
    correlations.query(
        "scope == 'Regional' and predictor == 'elevation_m' and outcome == 'temperature_2m'"
    )
    .iloc[0]
    .r
)
np.testing.assert_allclose(reported, np.corrcoef(agg.elevation_m, agg.temperature_2m)[0, 1])
reg = pd.read_csv(out / "tables/regression_comparison.csv")
reported_slope = reg.query("scope == 'Regional' and model == 1").iloc[0].elevation_per_km
np.testing.assert_allclose(
    reported_slope, np.polyfit(agg.elevation_m, agg.temperature_2m, 1)[0] * 1000
)
annual = pd.read_csv(out / "tables/original_six_annual.csv")
assert annual.complete.all() and len(annual) == 36
train = panel[panel.timestamp < pd.Timestamp(ml["test_start"])].sort_values(
    ["timestamp", "location_id"]
)
test = panel[panel.timestamp >= pd.Timestamp(ml["test_start"])]
assert len(train) == ml["train_rows"] and len(test) == ml["test_rows"]
assert train.timestamp.max() < test.timestamp.min()
assert set(train.location_id) == set(test.location_id)
models = pd.read_csv(out / "tables/model_comparison.csv")
baseline = models[models.Model == "Mean baseline"].iloc[0]
np.testing.assert_allclose(
    baseline.RMSE, np.sqrt(((test.temperature_2m - train.temperature_2m.mean()) ** 2).mean())
)
importance = pd.read_csv(out / "tables/feature_importance.csv").set_index("feature")
np.testing.assert_allclose(importance.built_in.sum(), 1)
assert importance.loc[["month_sin", "month_cos", "year"], "permutation_r2_drop"].eq(0).all()
# Reconstruct and retain the actual deterministic timestamp fold boundaries.
hours = np.array(sorted(train.timestamp.unique()))
selected = hours[np.linspace(0, len(hours) - 1, min(400, len(hours)), dtype=int)]
tuning = train[train.timestamp.isin(selected)].reset_index(drop=True)
folds = []
for i, (a, b) in enumerate(TimeSeriesSplit(n_splits=4).split(selected), 1):
    tr = tuning[tuning.timestamp.isin(selected[a])]
    va = tuning[tuning.timestamp.isin(selected[b])]
    assert tr.timestamp.max() < va.timestamp.min()
    folds.append(
        {
            "fold": i,
            "train_start": str(tr.timestamp.min()),
            "train_end": str(tr.timestamp.max()),
            "validation_start": str(va.timestamp.min()),
            "validation_end": str(va.timestamp.max()),
            "train_rows": len(tr),
            "validation_rows": len(va),
        }
    )
pd.DataFrame(folds).to_csv(out / "tables/tuning_folds.csv", index=False)
spark = json.loads((out / "spark_validation.json").read_text())
assert spark["status"] == "passed" and spark["daily_rows"] == len(daily)
result = {
    "status": "passed",
    "checks": [
        "source hashes",
        "balanced complete panel",
        "unique keys",
        "aggregation reconciliation",
        "independent correlation and slope",
        "complete historical years",
        "strict temporal holdout",
        "baseline RMSE",
        "constant-feature importance",
        "chronological tuning folds",
        "Spark parity",
    ],
}
(out / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
