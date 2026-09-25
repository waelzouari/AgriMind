import 'dart:async';

import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/farm_manager/presentation/farm_navigation_bar.dart';
import 'package:agrimind/features/history/application/history_controller.dart';
import 'package:agrimind/features/history/domain/history_snapshot.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/visual_inspection/domain/cv_inference_result.dart';
import 'package:flutter/material.dart';

class HistoryPage extends StatefulWidget {
  const HistoryPage({
    required this.farm,
    required this.controller,
    required this.onHome,
    required this.onFarm,
    this.demonstrationMode = false,
    super.key,
  });
  final Farm farm;
  final HistoryController controller;
  final VoidCallback onHome;
  final VoidCallback onFarm;
  final bool demonstrationMode;
  @override
  State<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends State<HistoryPage> {
  _HistoryFilter _filter = _HistoryFilter.all;

  @override
  void initState() {
    super.initState();
    unawaited(widget.controller.load());
  }

  @override
  void dispose() {
    widget.controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.controller,
    builder: (context, _) => AgriMindScaffold(
      title: 'Historique',
      scrollable: true,
      bottomNavigationBar: FarmNavigationBar(
        selectedIndex: 2,
        onHome: widget.onHome,
        onFarm: widget.onFarm,
        onHistory: () {},
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(widget.farm.name, style: AgriMindTypography.heading2),
          if (widget.demonstrationMode) ...[
            const SizedBox(height: AgriMindSpacing.md),
            const AgriMindCard(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.science_outlined, color: AgriMindColors.info),
                  SizedBox(width: AgriMindSpacing.sm),
                  Expanded(
                    child: Text(
                      'Mode démonstration : ces événements sont simulés et ne proviennent pas du cloud ni du modèle CV.',
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: AgriMindSpacing.xl),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: _HistoryFilter.values
                  .map(
                    (filter) => Padding(
                      padding: const EdgeInsets.only(right: AgriMindSpacing.sm),
                      child: ChoiceChip(
                        label: Text(filter.label),
                        selected: _filter == filter,
                        onSelected: (_) => setState(() => _filter = filter),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
          const SizedBox(height: AgriMindSpacing.lg),
          switch (widget.controller.status) {
            HistoryStatus.idle ||
            HistoryStatus.loading => const AgriMindLoadingIndicator(
              label: 'Chargement de l’historique',
            ),
            HistoryStatus.failure => AgriMindErrorState(
              title: 'Historique indisponible',
              message:
                  widget.controller.errorMessage ?? 'Le chargement a échoué.',
              onRetry: widget.controller.load,
            ),
            HistoryStatus.empty => const AgriMindEmptyState(
              icon: Icons.history_rounded,
              title: 'Aucun événement',
              message: 'L’historique apparaîtra après les premières activités.',
            ),
            HistoryStatus.loaded => _HistoryContent(
              snapshot: widget.controller.snapshot,
              filter: _filter,
            ),
          },
        ],
      ),
    ),
  );
}

enum _HistoryFilter { all, sensors, irrigation, inspections }

extension on _HistoryFilter {
  String get label => switch (this) {
    _HistoryFilter.all => 'Tout',
    _HistoryFilter.sensors => 'Capteurs',
    _HistoryFilter.irrigation => 'Irrigation',
    _HistoryFilter.inspections => 'Inspections',
  };
}

class _HistoryContent extends StatelessWidget {
  const _HistoryContent({required this.snapshot, required this.filter});
  final HistorySnapshot snapshot;
  final _HistoryFilter filter;
  @override
  Widget build(BuildContext context) {
    final records = <_HistoryRecord>[
      if (filter == _HistoryFilter.all || filter == _HistoryFilter.sensors)
        ...snapshot.sensors.map(
          (e) => _HistoryRecord(
            timestamp: e.recordedAt,
            icon: Icons.sensors_rounded,
            title: '${e.label} : ${e.value}',
            subtitle: 'Mesure enregistrée',
          ),
        ),
      if (filter == _HistoryFilter.all || filter == _HistoryFilter.irrigation)
        ...snapshot.irrigations.map(
          (e) => _HistoryRecord(
            timestamp: e.completedAt,
            icon: Icons.water_drop_rounded,
            title: 'Irrigation terminée',
            subtitle:
                '${e.before.toStringAsFixed(0)} % → ${e.after.toStringAsFixed(0)} %',
          ),
        ),
      if (filter == _HistoryFilter.all || filter == _HistoryFilter.inspections)
        ...snapshot.inspections.map(
          (e) => _HistoryRecord(
            timestamp: e.completedAt,
            icon: Icons.eco_rounded,
            title: 'Inspection — ${e.classification.label}',
            subtitle: e.anomalySoftmaxProbability == null
                ? e.treeLabel
                : '${e.treeLabel} · score non calibré ${(e.anomalySoftmaxProbability! * 100).toStringAsFixed(1)} %',
            warning: e.classification == CvClassification.anomaly,
          ),
        ),
    ]..sort((a, b) => b.timestamp.compareTo(a.timestamp));
    if (records.isEmpty) {
      return const AgriMindCard(
        child: AgriMindEmptyState(
          icon: Icons.history_rounded,
          title: 'Aucun événement',
          message: 'Aucune donnée disponible pour cette catégorie.',
        ),
      );
    }
    final newest = DateUtils.dateOnly(records.first.timestamp);
    final children = <Widget>[];
    DateTime? previousDay;
    for (final record in records) {
      if (previousDay == null ||
          !DateUtils.isSameDay(previousDay, record.timestamp)) {
        if (previousDay != null) {
          children.add(const SizedBox(height: AgriMindSpacing.lg));
        }
        children
          ..add(
            Text(
              _dayLabel(record.timestamp, newest),
              style: AgriMindTypography.heading3,
            ),
          )
          ..add(const SizedBox(height: AgriMindSpacing.sm));
      }
      children
        ..add(_TimelineEvent(record: record))
        ..add(const SizedBox(height: AgriMindSpacing.sm));
      previousDay = record.timestamp;
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    );
  }
}

final class _HistoryRecord {
  const _HistoryRecord({
    required this.timestamp,
    required this.icon,
    required this.title,
    required this.subtitle,
    this.warning = false,
  });
  final DateTime timestamp;
  final IconData icon;
  final String title;
  final String subtitle;
  final bool warning;
}

class _TimelineEvent extends StatelessWidget {
  const _TimelineEvent({required this.record});
  final _HistoryRecord record;
  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.center,
    children: [
      SizedBox(
        width: 48,
        child: Text(_clock(record.timestamp), style: AgriMindTypography.label),
      ),
      Container(
        width: 10,
        height: 10,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: record.warning
              ? AgriMindColors.warning
              : AgriMindColors.primaryGreen,
        ),
      ),
      const SizedBox(width: AgriMindSpacing.sm),
      Expanded(
        child: AgriMindCard(
          child: Row(
            children: [
              DecoratedBox(
                decoration: const BoxDecoration(
                  color: AgriMindColors.primaryContainer,
                  shape: BoxShape.circle,
                ),
                child: Padding(
                  padding: const EdgeInsets.all(AgriMindSpacing.sm),
                  child: Icon(record.icon, color: AgriMindColors.primaryGreen),
                ),
              ),
              const SizedBox(width: AgriMindSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(record.title, style: AgriMindTypography.label),
                    Text(
                      record.subtitle,
                      style: AgriMindTypography.caption.copyWith(
                        color: AgriMindColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    ],
  );
}

String _clock(DateTime value) =>
    '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
String _dayLabel(DateTime value, DateTime newest) {
  final day = DateUtils.dateOnly(value);
  if (day == newest) return 'Aujourd’hui';
  if (day == newest.subtract(const Duration(days: 1))) return 'Hier';
  return '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';
}
