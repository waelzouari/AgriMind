# AgriMind mobile

Flutter application foundation, centralized design system, and AGM-015
Supabase authentication/session boundary for AgriMind.

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
flutter run \
  --dart-define=AGRIMIND_SUPABASE_URL=https://PROJECT.supabase.co \
  --dart-define=AGRIMIND_SUPABASE_ANON_KEY=PUBLIC_CLIENT_KEY
```

Select an Android or iOS target supported by the host development environment.
Only the public Supabase URL and anonymous/publishable client key belong in
these defines. Never pass a service-role key, database password, JWT secret,
MQTT credential, or other privileged credential to Flutter.

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
├── features/auth/       # Auth domain, application port, Supabase adapter, UI
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

Tests use an authentication repository fake. They are offline and require no
broker, Supabase project, Raspberry Pi, GPIO, or Internet connection.

## Configuration and security

`AppConfig` contains only the Supabase URL and anonymous/publishable client key.
`supabase_flutter` owns persisted user-session storage and token refresh; the
application does not create a second token store. Startup remains on a neutral
loading screen until restoration completes, and all known application routes
pass through the authentication gate.

Authentication errors shown to users are stable, generic messages and must
never contain provider exceptions, passwords, tokens, or credentials. Do not
add MQTT credentials, Supabase service-role keys, database passwords, private
keys, or other privileged values to Flutter or Git.

The generated Android application ID and iOS bundle identifier are temporarily
`com.example.agrimind`. They are scaffold values, not an approved production
identifier, and must be replaced through a separately validated product
decision before release.

Supabase RLS remains the server-side authorization boundary; route guards are
only a user-experience control. Cloud authorization does not replace the
Raspberry Pi pump safety gate. UI tests do not validate hardware safety.

## Explicitly out of scope

AGM-015 does not implement registration, password reset, onboarding, MQTT,
live sensors, a real dashboard, irrigation, weather, farm management,
inspection, history, notifications, ML, Computer Vision, or backend logic.
