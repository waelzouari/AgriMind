# AI

Reproducible irrigation and computer-vision work will live in separate
subdirectories with data contracts, configurations, source, tests, and
versioned artifact metadata.

Tank level, pump status, and sensor status are system state and are excluded
from agronomic ML features. Computer vision is limited to `NORMAL` and
`VISUAL_ANOMALY_DETECTED`; disease diagnosis and robot autonomy are excluded.
