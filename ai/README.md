# AI

Reproducible irrigation and computer-vision work will live in separate
subdirectories with data contracts, configurations, source, tests, and
versioned artifact metadata.

The implemented computer-vision audit and training boundary is documented in
[computer_vision/README.md](computer_vision/README.md). Public images and model
binaries remain outside Git.

Tank level, pump status, and sensor status are system state and are excluded
from agronomic ML features. Computer vision is limited to `NORMAL` and
`ANOMALY`; disease diagnosis and robot autonomy are excluded.
