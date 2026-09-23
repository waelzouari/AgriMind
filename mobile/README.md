# AgriMind mobile

Flutter foundation and centralized design system for the AgriMind mobile
application. AGM-014 deliberately contains no product feature or external
service integration.

## Prerequisites

- Flutter 3.44.8 stable
- Dart SDK supplied by Flutter
- Android tooling for Android runs
- Xcode on macOS for iOS runs

Only Android and iOS projects are generated. Web and desktop platforms are not
part of AGM-014.

## Setup and run

From `mobile/`:

```bash
flutter pub get
flutter run
```

Select an Android or iOS target supported by the host development environment.
The initial route displays `FoundationShowcasePage`, a technical design-system
showcase rather than a functional dashboard.

## Project structure

```text
lib/
├── app/                 # Application composition and native Flutter routing
├── core/
│   ├── config/          # Minimal public application configuration
│   ├── design_system/   # Colors, spacing, radius, typography and sizing tokens
│   ├── models/          # Presentation-only UI status
│   ├── pages/           # AGM-014 technical showcase
│   └── widgets/         # Shared accessible UI primitives
└── main.dart            # Application entry point
test/                    # Offline unit and widget tests
```

Feature folders are added only by the ticket that implements the corresponding
feature. Empty future feature shells are intentionally absent.

## Design system

The design language uses an off-white background, white cards, agricultural
greens, earth brown, sand beige, generous spacing, rounded corners, and light
elevation. Reusable decisions are centralized in `lib/core/design_system/`.
Widgets must not introduce duplicated business colors or repeated design-system
magic numbers.

`UiStatus` is presentation-only and supports online, offline, loading, error,
stale, success, and warning states. Every status includes French text and an
icon in addition to color. It is not mapped to MQTT or wire-contract quality
values in AGM-014.

## Checks

Run from `mobile/`:

```bash
dart format .
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
```

Tests are offline and require no broker, Supabase project, Raspberry Pi, GPIO,
or Internet connection.

## Configuration and security

`AppConfig` contains only public information required by this foundation. Do
not add tokens, passwords, MQTT credentials, Supabase service-role keys,
private keys, or other privileged values to Flutter or Git.

The generated Android application ID and iOS bundle identifier are temporarily
`com.example.agrimind`. They are scaffold values, not an approved production
identifier, and must be replaced through a separately validated product
decision before release.

At the AGM-014 UI foundation boundary, authorization, idempotency, hardware
integration, physical actuation safety, and external service integration are
not applicable. UI tests do not validate hardware safety.

## Explicitly out of scope

AGM-014 does not implement authentication, session restoration, Supabase,
MQTT, live sensors, a real dashboard, irrigation, weather, farm management,
inspection, history, notifications, ML, Computer Vision, or backend logic.
