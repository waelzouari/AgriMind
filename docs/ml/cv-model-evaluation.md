# AGM-031 CV evaluation protocol

AGM-031 is split into two controlled stages. Phase B1 provides deterministic
evaluation machinery, threshold selection, runtime contracts and the secured
inference boundary. Official weights, a final threshold and held-out TEST
metrics are **not yet available**. Phase B2 will regenerate a clean artifact,
select its threshold on VALIDATION, then evaluate TEST exactly once.

TRAIN is used only for fitting. VALIDATION owns early stopping, model selection
and threshold selection. TEST is accepted only by the final evaluator together
with evidence that model, preprocessing and threshold are frozen and that the
validation fingerprint and artifact SHA-256 are known.

The positive class is `ANOMALY`, with class order `NORMAL`, `ANOMALY`. Threshold
selection maximizes validation macro-F1, then ANOMALY recall, then chooses the
lower threshold with deterministic numeric ordering. Reported metrics comprise
confusion matrix, accuracy, class precision/recall/F1/support, macro metrics,
ROC-AUC and Average Precision.

Model weights, raw data and detailed generated manifests remain external to
Git and are identified by SHA-256. B1 intentionally does not choose whether a
future deployment obtains them through a release artifact, private artifact
storage or an immutable image.

PlantVillage predominantly contains controlled single-leaf images. Future
metrics on that dataset will not demonstrate performance on field photographs,
Tunisian farms, unseen species, natural backgrounds, lighting, blur or
occlusion. The model remains visual screening only.
