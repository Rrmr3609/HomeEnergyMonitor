import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import precision_score, recall_score
from sklearn.model_selection import TimeSeriesSplit
from anomaly_detector import load_and_preprocess, group_power, fit_detector

def test_isolation_forest_cv_performance():
    #load and preprocess full dataset
    df = load_and_preprocess("household_power_consumption.xlsx")

    #group at hourly resolution
    grouped = group_power(df, "hour")

    #prepare features and labels
    X = grouped[["total_power"]].values.flatten()
    #label top 5% as anomalies
    threshold = np.percentile(X, 95)
    y_true = (X > threshold).astype(int)  #1=anomaly, 0=normal

    #set up time series cross-validator
    tscv = TimeSeriesSplit(n_splits=5)

    precisions = []
    recalls    = []

    for train_idx, test_idx in tscv.split(X):
        #train/test slices
        train_slice = grouped.iloc[train_idx]
        test_slice  = grouped.iloc[test_idx]

        #fit detector on train
        model = fit_detector(train_slice.rename(columns={
            "group": "group",
            "total_power": "total_power"
        })[["group", "total_power"]])

        #predict on test
        preds = model.predict(
            pd.DataFrame({"total_power": test_slice["total_power"].values})
        )
        #convert to binary {0,1}
        y_pred = (np.array(preds) == -1).astype(int)
        y_test = y_true[test_idx]

        precisions.append(precision_score(y_test, y_pred, zero_division=0))
        recalls.append   (recall_score   (y_test, y_pred, zero_division=0))

    mean_prec = np.mean(precisions)
    mean_rec  = np.mean(recalls)

    print(f"\nCV Precision: {mean_prec:.3f}  ± {np.std(precisions):.3f}")
    print(f"CV Recall:    {mean_rec:.3f}  ± {np.std(recalls):.3f}\n")

    #assert minimal acceptable performance
    assert mean_prec > 0.3, "Precision is too low! Try tuning contamination or features."
    assert mean_rec  > 0.3, "Recall is too low! Try tuning contamination or features."
