import 'package:agrimind/core/design_system/agrimind_colors.dart';
import 'package:flutter/material.dart';

enum UiStatus { online, offline, loading, error, stale, success, warning }

extension UiStatusPresentation on UiStatus {
  String get label => switch (this) {
    UiStatus.online => 'En ligne',
    UiStatus.offline => 'Hors ligne',
    UiStatus.loading => 'Chargement',
    UiStatus.error => 'Erreur',
    UiStatus.stale => 'Données anciennes',
    UiStatus.success => 'Succès',
    UiStatus.warning => 'Attention',
  };

  IconData get icon => switch (this) {
    UiStatus.online => Icons.wifi_rounded,
    UiStatus.offline => Icons.wifi_off_rounded,
    UiStatus.loading => Icons.sync_rounded,
    UiStatus.error => Icons.error_outline_rounded,
    UiStatus.stale => Icons.history_rounded,
    UiStatus.success => Icons.check_circle_outline_rounded,
    UiStatus.warning => Icons.warning_amber_rounded,
  };

  Color get foregroundColor => switch (this) {
    UiStatus.online || UiStatus.success => AgriMindColors.success,
    UiStatus.offline => AgriMindColors.offline,
    UiStatus.loading => AgriMindColors.primaryGreen,
    UiStatus.error => AgriMindColors.error,
    UiStatus.stale || UiStatus.warning => AgriMindColors.warning,
  };

  Color get backgroundColor => switch (this) {
    UiStatus.online || UiStatus.success => AgriMindColors.successContainer,
    UiStatus.offline => AgriMindColors.offlineContainer,
    UiStatus.loading => AgriMindColors.lightGreen,
    UiStatus.error => AgriMindColors.errorContainer,
    UiStatus.stale || UiStatus.warning => AgriMindColors.warningContainer,
  };
}
