# AgriMind mobile UI reference

## Source-of-truth hierarchy

1. GitHub issue and approved architecture: functional truth.
2. Flutter design system in `mobile/lib/core/design_system` and reusable widgets
   in `mobile/lib/core/widgets`: implementation truth for visual primitives.
3. [AgriMind mobile mockup](assets/agrimind-mobile-reference.png): visual
   direction.
4. Feature-specific design: must conform to all of the above.

The mockup is a visual reference, not a statement that all displayed features
are already implemented. A feature must never be exposed merely because it is
shown in the mockup.

## Visual language

AgriMind is a calm, trustworthy agritech product: light backgrounds, generous
spacing, rounded white cards, subtle borders and shadows, dark agricultural
green typography, and restrained semantic color. Operational screens prioritize
readable data over decoration. Agricultural illustration is reserved for
onboarding, authentication, and empty states.

The official transparent logo is stored at
`mobile/assets/branding/agrimind_logo.png`. Use `AgriMindLogo` rather than a
hardcoded asset path, generic leaf, or reconstructed wordmark.

All colors, spacing, radii, component dimensions, elevation, and typography
come from the centralized design system. Prefer `AgriMindCard`,
`AgriMindMetricCard`, `AgriMindStatusBadge`, `AgriMindButton`,
`AgriMindTextField`, and `AgriMindScaffold` over feature-local substitutes.

## Target information architecture

The target bottom navigation contains Home, Farm, Irrigation, Inspect, and
History. Notifications remain a header action; weather remains contextual.
This is a future visual specification only. Do not create routes or navigation
destinations until their issues provide the functionality.

Future dashboard work should lead with farm identity and system state, then a
farm-overview card, compact sensor metrics, weather, and the next irrigation.
Never ship illustrative mockup values as production data.

Future Farm Manager work uses a compact tree grid and text-supported green,
amber, and red states. Tree detail reuses cards, badges, metric typography, and
an activity timeline. History uses the same semantic system for sensor,
irrigation, and inspection events. Notifications should communicate severity
calmly, without alarmist styling.

AGM-029 implements the first Farm Manager presentation boundary using only the
data available from AGM-028. My Farm displays the real farm name, total tree
count, and deterministically ordered neutral grid. Tree Detail displays stable
identity, user label, and position. Health, per-tree soil moisture, irrigation,
inspection, and activity remain explicitly unavailable; the disabled inspection
action does not provide camera or Computer Vision behavior. The Home/Farm
navigation exposes only implemented destinations.

## Safety and inference semantics

Future irrigation may visually group Manual, Automatic, and Scheduled modes,
durations, farm context, and the correlated command lifecycle. UI state alone
is not proof of physical pump state. Display physical state only when supported
by the acknowledgement/state contracts. The Raspberry Pi safety gate remains
authoritative and no UI or cloud command may bypass it.

The AI view distinguishes a recommendation from physical authorization. AI can
explain inputs and confidence, but it never claims to bypass local safety.

The Computer Vision MVP wording is strictly `NORMAL` or `ANOMALY`. It may show a
model score and model version, but must not diagnose a disease.

## Accessibility and responsive behavior

- Target WCAG 2.2 AA contrast and at least 48 logical-pixel touch targets.
- Communicate status with text and icon as well as color.
- Keep errors in accessible live regions and loading controls non-interactive.
- Support narrow and normal phone widths and increased text scaling without
  fixed-height content or overflow.
- Preserve keyboard-safe scrolling and meaningful semantic labels.
- Test new or changed primitives and current screens with widget tests.

## Security boundary

Mobile UI uses only public client configuration. Supabase `service_role`,
database passwords, JWT secrets, and device credentials never belong in Flutter
or Git. Farm isolation remains enforced server-side; visual affordances do not
replace RLS or trusted-server boundaries.
