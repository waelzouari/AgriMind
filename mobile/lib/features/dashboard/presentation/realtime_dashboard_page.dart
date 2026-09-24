import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/models/ui_status.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/dashboard/application/dashboard_controller.dart';
import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';
import 'package:agrimind/features/irrigation/presentation/manual_irrigation_card.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/weather/application/weather_controller.dart';
import 'package:agrimind/features/weather/presentation/weather_section.dart';
import 'package:flutter/material.dart';

class RealtimeDashboardPage extends StatelessWidget {
  const RealtimeDashboardPage({
    required this.authentication,
    required this.farm,
    required this.controller,
    required this.weatherController,
    super.key,
  });
  final AuthenticationController authentication;
  final Farm farm;
  final DashboardController controller;
  final WeatherController weatherController;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: controller,
    builder: (context, _) => AgriMindScaffold(
      title: 'AgriMind',
      scrollable: true,
      actions: [
        IconButton(
          tooltip: 'Se déconnecter',
          onPressed: authentication.isSubmitting
              ? null
              : authentication.signOut,
          icon: const Icon(Icons.logout_rounded),
        ),
      ],
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Align(
            alignment: Alignment.centerLeft,
            child: AgriMindLogo(compact: true),
          ),
          const SizedBox(height: AgriMindSpacing.lg),
          Text('Bonjour,', style: AgriMindTypography.bodySecondary),
          Text(farm.name, style: AgriMindTypography.heading2),
          const SizedBox(height: AgriMindSpacing.md),
          Align(
            alignment: Alignment.centerLeft,
            child: _ConnectionBadge(phase: controller.phase),
          ),
          const SizedBox(height: AgriMindSpacing.xl),
          const AgriMindSectionHeader(title: 'Capteurs en direct'),
          const SizedBox(height: AgriMindSpacing.md),
          _DashboardBody(controller: controller),
          const SizedBox(height: AgriMindSpacing.xl),
          WeatherSection(controller: weatherController),
          const SizedBox(height: AgriMindSpacing.xl),
          ManualIrrigationCard(controller: controller.manualIrrigation),
        ],
      ),
    ),
  );
}

class _ConnectionBadge extends StatelessWidget {
  const _ConnectionBadge({required this.phase});
  final MqttConnectionPhase phase;
  @override
  Widget build(BuildContext context) {
    final (status, label) = switch (phase) {
      MqttConnectionPhase.idle => (UiStatus.offline, 'MQTT inactif'),
      MqttConnectionPhase.connecting => (UiStatus.loading, 'Connexion MQTT'),
      MqttConnectionPhase.connected => (UiStatus.online, 'MQTT connecté'),
      MqttConnectionPhase.reconnecting => (
        UiStatus.warning,
        'Reconnexion MQTT',
      ),
      MqttConnectionPhase.disconnected => (UiStatus.offline, 'MQTT déconnecté'),
      MqttConnectionPhase.failure => (UiStatus.error, 'Connexion indisponible'),
    };
    return AgriMindStatusBadge(status: status, labelOverride: label);
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({required this.controller});
  final DashboardController controller;

  @override
  Widget build(BuildContext context) {
    if (controller.phase == MqttConnectionPhase.failure &&
        controller.readings.isEmpty) {
      return AgriMindErrorState(
        title: 'Mesures indisponibles',
        message: controller.errorMessage ?? 'La connexion MQTT a échoué.',
        onRetry: controller.retry,
      );
    }
    if (controller.readings.isEmpty) {
      return AgriMindCard(
        child: AgriMindEmptyState(
          icon: controller.phase == MqttConnectionPhase.connecting
              ? Icons.sync_rounded
              : Icons.sensors_rounded,
          title: 'En attente des premières mesures',
          message: 'Aucune télémétrie récente n’a encore été reçue.',
        ),
      );
    }
    final readings = TelemetryMetric.values
        .map((metric) => controller.readings[metric])
        .whereType<TelemetryReading>()
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final columns = constraints.maxWidth >= 520 ? 2 : 1;
            return GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: readings.length,
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: columns,
                crossAxisSpacing: AgriMindSpacing.md,
                mainAxisSpacing: AgriMindSpacing.md,
                mainAxisExtent: columns == 1 ? 220 : 210,
              ),
              itemBuilder: (context, index) => _MetricCard(
                reading: readings[index],
                stale: controller.isStale(readings[index]),
              ),
            );
          },
        ),
        const SizedBox(height: AgriMindSpacing.md),
        Text(
          'Dernière télémétrie : ${_formatTimestamp(controller.lastTelemetryAt!)}',
          style: AgriMindTypography.caption.copyWith(
            color: AgriMindColors.textSecondary,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.reading, required this.stale});
  final TelemetryReading reading;
  final bool stale;
  @override
  Widget build(BuildContext context) {
    final (label, icon) = switch (reading.metric) {
      TelemetryMetric.temperature => ('Température', Icons.thermostat_rounded),
      TelemetryMetric.humidity => (
        'Humidité de l’air',
        Icons.water_drop_outlined,
      ),
      TelemetryMetric.soilMoisture => ('Humidité du sol', Icons.grass_rounded),
      TelemetryMetric.tankLevel => ('Niveau du réservoir', Icons.water_rounded),
    };
    final status = stale
        ? (UiStatus.stale, 'Données anciennes')
        : reading.quality == TelemetryQuality.estimated
        ? (UiStatus.warning, 'Estimation capteur')
        : (UiStatus.success, 'Données en direct');
    return AgriMindMetricCard(
      icon: icon,
      label: label,
      value: _formatValue(reading.value),
      unit: reading.unit,
      status: AgriMindStatusBadge(status: status.$1, labelOverride: status.$2),
    );
  }
}

String _formatValue(double value) => value == value.roundToDouble()
    ? value.toStringAsFixed(0)
    : value.toStringAsFixed(1);

String _formatTimestamp(DateTime timestamp) {
  final local = timestamp.toLocal();
  String two(int value) => value.toString().padLeft(2, '0');
  return '${two(local.day)}/${two(local.month)}/${local.year} '
      '${two(local.hour)}:${two(local.minute)}:${two(local.second)}';
}
