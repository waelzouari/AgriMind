# Backend services

`ingestion/` contains the independently deployed AGM-012 MQTT-to-Supabase
worker and trusted registry CLI. Privileged Supabase credentials are permitted
only in secured server runtime configuration, never in mobile or Raspberry Pi
code. `weather/` contains the independently deployed AGM-019 Open-Meteo
aggregation and persistent snapshot-cache worker. `cv_inference/` contains the
independently deployed AGM-031 secured visual-screening API. It receives raw,
bounded JPEG/PNG requests and does not persist images or use privileged
Supabase credentials.
