# AgriMind mobile

Flutter application foundation, centralized design system, Supabase
authentication/session boundary, and minimal AGM-016 one-farm onboarding.

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
├── features/onboarding/ # One-farm state, repository, Supabase RPC adapter, UI
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

Tests use authentication and farm repository fakes. They are offline and
require no broker, Supabase project, Raspberry Pi, GPIO, or Internet connection.

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

After authentication, a second gate checks the current user’s RLS-visible farm.
The states `checking`, `noFarm`, `creating`, `configured`, and `failure` prevent
a lookup failure from being interpreted as a missing farm. Onboarding collects
only the schema-required farm name. Creation calls the authenticated
`create_farm_for_current_user` RPC; Flutter never inserts a farm or membership
directly and never supplies an identity or role. A failed or ambiguous creation
is recovered by reading again before another write, while the RPC provides
server-side idempotence and concurrency serialization.

### Optional real-Supabase onboarding validation

After applying the AGM-016 migration to the intended project, run with the
existing public `--dart-define` configuration and use a legitimate test user:

1. Confirm a user without a membership sees the one-field onboarding form.
2. Create a farm and confirm the configured home shows its normalized name.
3. Fully restart the app and confirm session restoration skips onboarding.
4. Sign out, sign in again, and confirm the same farm is reused.
5. Verify the database contains one owner membership for this workflow.

This manual Cloud scenario is separate from the credential-free automated
suite. Never provide Flutter with `service_role` to perform it.

## Explicitly out of scope

AGM-016 does not implement registration, password reset, multi-farm switching,
live sensors, a real dashboard, MQTT, irrigation, weather, farm management,
inspection, history, notifications, ML, Computer Vision, or backend logic.
