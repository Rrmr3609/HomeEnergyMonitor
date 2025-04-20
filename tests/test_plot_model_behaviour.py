import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, average_precision_score
from anomaly_detector import load_and_preprocess, group_power, fit_detector

#load data and train
df = load_and_preprocess("household_power_consumption.xlsx")
grouped = group_power(df, "hour")     #picking the resolution
model = fit_detector(grouped)

#build test set of scores + ground truth
X = grouped[["total_power"]].values
#anything > 2.0 is an anomaly
y_true = np.where(grouped["total_power"] > 2.0, -1, 1)
#get anomaly scores, for IsolationForest higher score = more normal
scores = model.decision_function(X)

#precision and recall
precision, recall, thresholds = precision_recall_curve(    #treat "anomaly" as the *positive* class so flip sign
    (y_true == -1).astype(int),
    -scores
)
avg_prec = average_precision_score((y_true == -1).astype(int), -scores)

plt.figure(figsize=(6,4))
plt.plot(recall, precision, lw=2, label=f"AP={avg_prec:.2f}")
plt.xlabel("Recall")
plt.ylabel("Precision")
plt.title("Precision–Recall Curve for IsolationForest")
plt.legend(loc="best")
plt.grid(True)
plt.tight_layout()
plt.show()

#histogram of raw scores
plt.figure(figsize=(6,3))
plt.hist(scores, bins=30, edgecolor="k")
plt.axvline(x=np.percentile(scores, 100 * (1 - 0.1)), color="r", linestyle="--",
            label="0.10 contamination cutoff")
plt.xlabel("Anomaly Score (higher = more normal)")
plt.ylabel("Count")
plt.title("IsolationForest Score Distribution")
plt.legend()
plt.tight_layout()
plt.show()
