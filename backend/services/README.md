# Backend services

`ingestion/` contains the independently deployed AGM-012 MQTT-to-Supabase
worker and trusted registry CLI. Privileged Supabase credentials are permitted
only in secured server runtime configuration, never in mobile or Raspberry Pi
code. Future inference services remain separate deployments.
