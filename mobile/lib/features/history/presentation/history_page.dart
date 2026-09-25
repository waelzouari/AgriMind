import 'dart:async';

import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/models/ui_status.dart';
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
            ),
          },
        ],
      ),
    ),
  );
}

class _HistoryContent extends StatelessWidget {
  const _HistoryContent({required this.snapshot});
  final HistorySnapshot snapshot;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _Section(
        title: 'Capteurs',
        icon: Icons.sensors_rounded,
        empty: snapshot.sensors.isEmpty,
        children: snapshot.sensors
            .map(
              (e) => _Event(
                title: e.label,
                value: e.value,
                timestamp: e.recordedAt,
              ),
            )
            .toList(),
      ),
      const SizedBox(height: AgriMindSpacing.xl),
      _Section(
        title: 'Irrigation',
        icon: Icons.water_rounded,
        empty: snapshot.irrigations.isEmpty,
        children: snapshot.irrigations
            .map(
              (e) => _Event(
                title: 'Irrigation terminée',
                value:
                    '${e.before.toStringAsFixed(0)} % → ${e.after.toStringAsFixed(0)} %',
                timestamp: e.completedAt,
              ),
            )
            .toList(),
      ),
      const SizedBox(height: AgriMindSpacing.xl),
      _Section(
        title: 'Inspections visuelles',
        icon: Icons.image_search_rounded,
        empty: snapshot.inspections.isEmpty,
        children: snapshot.inspections
            .map((e) => _InspectionEvent(entry: e))
            .toList(),
      ),
    ],
  );
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.icon,
    required this.empty,
    required this.children,
  });
  final String title;
  final IconData icon;
  final bool empty;
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      AgriMindSectionHeader(title: title),
      const SizedBox(height: AgriMindSpacing.md),
      if (empty)
        AgriMindCard(
          child: AgriMindEmptyState(
            icon: icon,
            title: 'Aucun événement',
            message: 'Aucune donnée disponible pour cette catégorie.',
          ),
        )
      else
        ...children.expand(
          (child) => [child, const SizedBox(height: AgriMindSpacing.sm)],
        ),
    ],
  );
}

class _Event extends StatelessWidget {
  const _Event({
    required this.title,
    required this.value,
    required this.timestamp,
  });
  final String title;
  final String value;
  final DateTime timestamp;
  @override
  Widget build(BuildContext context) => AgriMindCard(
    child: Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: AgriMindTypography.label),
              Text(
                _time(timestamp),
                style: AgriMindTypography.caption.copyWith(
                  color: AgriMindColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
        Text(value, style: AgriMindTypography.heading3),
      ],
    ),
  );
}

class _InspectionEvent extends StatelessWidget {
  const _InspectionEvent({required this.entry});
  final InspectionHistoryEntry entry;
  @override
  Widget build(BuildContext context) => AgriMindCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(entry.treeLabel, style: AgriMindTypography.label),
            ),
            AgriMindStatusBadge(
              status: entry.classification == CvClassification.normal
                  ? UiStatus.success
                  : UiStatus.warning,
              labelOverride: entry.classification.label,
            ),
          ],
        ),
        const SizedBox(height: AgriMindSpacing.sm),
        Text(
          _time(entry.completedAt),
          style: AgriMindTypography.caption.copyWith(
            color: AgriMindColors.textSecondary,
          ),
        ),
        if (entry.anomalySoftmaxProbability case final score?)
          Text(
            'Probabilité softmax d’anomalie : ${(score * 100).toStringAsFixed(1)} % (score non calibré)',
          ),
      ],
    ),
  );
}

String _time(DateTime value) =>
    '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year} · ${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')} UTC';
