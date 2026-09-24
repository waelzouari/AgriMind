import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/models/ui_status.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/weather/application/weather_controller.dart';
import 'package:agrimind/features/weather/domain/weather_failure.dart';
import 'package:agrimind/features/weather/domain/weather_snapshot.dart';
import 'package:flutter/material.dart';

class WeatherSection extends StatelessWidget {
  const WeatherSection({required this.controller, super.key});

  final WeatherController controller;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: controller,
    builder: (context, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const AgriMindSectionHeader(title: 'Météo'),
        const SizedBox(height: AgriMindSpacing.md),
        _WeatherBody(controller: controller),
      ],
    ),
  );
}

class _WeatherBody extends StatelessWidget {
  const _WeatherBody({required this.controller});

  final WeatherController controller;

  @override
  Widget build(BuildContext context) => switch (controller.status) {
    WeatherStatus.idle || WeatherStatus.loading => const AgriMindCard(
      child: Center(child: AgriMindLoadingIndicator(label: 'Chargement météo')),
    ),
    WeatherStatus.locationNotConfigured => const AgriMindCard(
      child: AgriMindEmptyState(
        icon: Icons.location_off_outlined,
        title: 'Localisation non configurée',
        message: 'La météo nécessite la localisation de la ferme.',
      ),
    ),
    WeatherStatus.noSnapshot => AgriMindCard(
      child: AgriMindEmptyState(
        icon: Icons.cloud_off_outlined,
        title: 'Données météo en attente',
        message: 'Les données météo ne sont pas encore disponibles.',
        action: AgriMindButton(
          label: 'Réessayer',
          onPressed: controller.refresh,
          loading: controller.isRefreshing,
          variant: AgriMindButtonVariant.secondary,
          icon: Icons.refresh_rounded,
        ),
      ),
    ),
    WeatherStatus.unavailable => AgriMindCard(
      child: AgriMindErrorState(
        title: 'Météo indisponible',
        message: controller.isOffline
            ? 'La dernière météo est trop ancienne et la connexion est indisponible.'
            : 'La dernière météo est trop ancienne pour être affichée.',
        onRetry: controller.isRefreshing ? null : controller.refresh,
      ),
    ),
    WeatherStatus.failure => AgriMindCard(
      child: AgriMindErrorState(
        title: controller.failure?.type == WeatherFailureType.network
            ? 'Météo hors ligne'
            : 'Météo indisponible',
        message:
            controller.failure?.userMessage ??
            'La météo est momentanément indisponible.',
        onRetry:
            controller.failure?.type == WeatherFailureType.unauthorized ||
                controller.isRefreshing
            ? null
            : controller.refresh,
      ),
    ),
    WeatherStatus.ready => _WeatherData(controller: controller),
  };
}

class _WeatherData extends StatelessWidget {
  const _WeatherData({required this.controller});

  final WeatherController controller;

  @override
  Widget build(BuildContext context) {
    final snapshot = controller.snapshot!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: AgriMindSpacing.sm,
          runSpacing: AgriMindSpacing.sm,
          children: [
            AgriMindStatusBadge(
              status: controller.freshness == WeatherFreshness.fresh
                  ? UiStatus.success
                  : UiStatus.stale,
              labelOverride: controller.freshness == WeatherFreshness.fresh
                  ? 'À jour'
                  : 'Données anciennes',
            ),
            if (controller.isOffline)
              const AgriMindStatusBadge(
                status: UiStatus.offline,
                labelOverride: 'Hors ligne',
              ),
            if (controller.failure != null && !controller.isOffline)
              const AgriMindStatusBadge(
                status: UiStatus.warning,
                labelOverride: 'Actualisation impossible',
              ),
          ],
        ),
        const SizedBox(height: AgriMindSpacing.md),
        _MetricWrap(
          metrics: [
            _WeatherMetric(
              icon: Icons.thermostat_rounded,
              label: 'Température',
              value: snapshot.temperatureC.toStringAsFixed(1),
              unit: '°C',
            ),
            _WeatherMetric(
              icon: Icons.water_drop_outlined,
              label: 'Humidité',
              value: snapshot.relativeHumidityPercent.round().toString(),
              unit: '%',
            ),
            _WeatherMetric(
              icon: Icons.air_rounded,
              label: 'Vent',
              value: snapshot.windSpeedKmh.toStringAsFixed(1),
              unit: 'km/h',
            ),
            _WeatherMetric(
              icon: Icons.grain_rounded,
              label: 'Précipitations actuelles',
              value: snapshot.currentPrecipitationMm.toStringAsFixed(1),
              unit: 'mm',
              note: _intervalLabel(snapshot.currentIntervalSeconds),
            ),
            _WeatherMetric(
              icon: Icons.umbrella_outlined,
              label: 'Pluie sur 24 h',
              value: snapshot.precipitationLast24hMm.toStringAsFixed(1),
              unit: 'mm',
            ),
            _WeatherMetric(
              icon: Icons.eco_outlined,
              label: 'ET₀ sur 24 h',
              value: snapshot.et0Last24hMm.toStringAsFixed(1),
              unit: 'mm',
            ),
          ],
        ),
        const SizedBox(height: AgriMindSpacing.md),
        Text(
          'Mis à jour le ${_formatTimestamp(snapshot.fetchedAt)}',
          style: AgriMindTypography.caption.copyWith(
            color: AgriMindColors.textSecondary,
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: AgriMindSpacing.sm),
        Align(
          child: AgriMindButton(
            label: 'Actualiser la météo',
            onPressed: controller.refresh,
            loading: controller.isRefreshing,
            variant: AgriMindButtonVariant.text,
            icon: Icons.refresh_rounded,
          ),
        ),
      ],
    );
  }
}

class _MetricWrap extends StatelessWidget {
  const _MetricWrap({required this.metrics});
  final List<_WeatherMetric> metrics;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final width = constraints.maxWidth >= 520
          ? (constraints.maxWidth - AgriMindSpacing.md) / 2
          : constraints.maxWidth;
      return Wrap(
        spacing: AgriMindSpacing.md,
        runSpacing: AgriMindSpacing.md,
        children: [
          for (final metric in metrics) SizedBox(width: width, child: metric),
        ],
      );
    },
  );
}

class _WeatherMetric extends StatelessWidget {
  const _WeatherMetric({
    required this.icon,
    required this.label,
    required this.value,
    required this.unit,
    this.note,
  });
  final IconData icon;
  final String label;
  final String value;
  final String unit;
  final String? note;

  @override
  Widget build(BuildContext context) => AgriMindMetricCard(
    icon: icon,
    label: label,
    value: value,
    unit: unit,
    status: note == null
        ? null
        : Text(
            note!,
            style: AgriMindTypography.caption.copyWith(
              color: AgriMindColors.textSecondary,
            ),
          ),
  );
}

String _intervalLabel(int seconds) =>
    seconds % 60 == 0 ? 'sur ${seconds ~/ 60} min' : 'sur $seconds s';

String _formatTimestamp(DateTime timestamp) {
  final local = timestamp.toLocal();
  String two(int value) => value.toString().padLeft(2, '0');
  return '${two(local.day)}/${two(local.month)}/${local.year} '
      '${two(local.hour)}:${two(local.minute)}';
}
