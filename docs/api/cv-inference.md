# CV inference HTTP API v1

## Request

`POST /v1/farms/{farm_id}/cv-inferences` accepts raw `image/jpeg` or
`image/png` bytes and a verified Supabase `Authorization: Bearer` access token.
`X-Correlation-ID` may contain a UUID; otherwise the server supplies one.
The requested farm ID is not authorization proof. The service validates the
user through Supabase Auth and queries `farm_memberships` using the same JWT,
thereby retaining existing RLS isolation. Owner and member access is allowed;
anonymous, non-member and cross-farm access fails closed without revealing
whether another farm exists.

## Image policy

- encoded body: at most 8 MiB;
- width and height: positive and each at most 4096 pixels;
- decoded image: at most 16,000,000 pixels;
- one JPEG or PNG frame only;
- MIME must match real decoded format;
- malformed, truncated, animated, multipage and decompression-bomb inputs are
  rejected;
- grayscale and RGBA inputs are converted to RGB.

Small positive dimensions are accepted but may reduce inference quality. The
AGM-030 preprocessing contract resizes and center-crops to 224×224. It does not
apply EXIF orientation, so AGM-031 deliberately does not add EXIF transposition.

## Response semantics

The response and safe error bodies are defined by the JSON Schemas under
`contracts/v1/`. `anomaly_softmax_probability` is an uncalibrated softmax
probability, not confidence. The only classifications are `NORMAL` and
`ANOMALY`; neither is a disease diagnosis, treatment recommendation, field
accuracy claim or irrigation decision.

Images, JWTs, authorization headers and complete request payloads are never
logged. No image is persisted by AGM-031.
