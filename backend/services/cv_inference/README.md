# AGM-031 secured CV inference service

This independently deployed FastAPI service exposes only binary visual
screening (`NORMAL` or `ANOMALY`). It accepts bounded raw JPEG/PNG bytes at
`POST /v1/farms/{farm_id}/cv-inferences` after validating a Supabase access
token and confirming farm membership with that same user JWT under RLS.

The public Supabase publishable/anon key is runtime configuration, not an
authorization credential. The service does not use `service_role`, persist
images, create Storage objects, diagnose disease, recommend treatment, or
produce irrigation decisions.

Before reporting readiness, runtime startup validates the external model
metadata, artifact size and SHA-256, versions, label mapping, preprocessing,
fingerprints and frozen validation threshold. MobileNetV2 is constructed with
`weights=None`; implicit model downloads are forbidden. Weights remain outside
Git and are supplied by deployment through a later approved distribution
mechanism.

The Phase B1 test suite uses fake authentication, authorization and model
boundaries. It requires no network, Supabase project, dataset, weights, GPU,
camera, GPIO or robot.
