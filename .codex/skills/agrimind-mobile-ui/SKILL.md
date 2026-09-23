---
name: agrimind-mobile-ui
description: Apply the official AgriMind Flutter mobile design system and visual reference when creating or changing mobile UI, widgets, screens, navigation, states, or UI tests in this repository.
---

# AgriMind mobile UI

Read `docs/design/mobile-ui-reference.md` before changing mobile UI.

Use this source priority:

1. GitHub issue and approved architecture are the functional truth.
2. `mobile/lib/core/design_system` and `mobile/lib/core/widgets` are the
   implementation truth for visual primitives.
3. `docs/design/assets/agrimind-mobile-reference.png` is visual direction.
4. Feature-specific design must conform to all three.

Reuse semantic tokens and existing components. Do not hardcode raw colors,
invent spacing, redraw the logo, add fake production metrics, or expose routes
and actions without implemented behavior. Use `AgriMindLogo` for branding.

Cover loading, error, empty, offline, and stale states when the feature needs
them. Status needs text or icon in addition to color. Preserve 48-pixel touch
targets, contrast, semantics, text scaling, keyboard behavior, and narrow-phone
layouts. Add or update focused widget tests.

Keep irrigation UI honest: a request or UI toggle is not proof of pump state,
and the Raspberry Pi safety gate remains authoritative. Keep AI recommendation
separate from physical authorization. Computer Vision wording is only `NORMAL`
or `ANOMALY`, never a disease diagnosis. Preserve farm isolation and never put
privileged Supabase credentials in Flutter.

Do not implement functionality just because it appears in the visual mockup.
