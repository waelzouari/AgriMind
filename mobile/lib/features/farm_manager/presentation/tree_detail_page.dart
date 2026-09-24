import 'dart:async';

import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/farm_manager/application/farm_manager_controller.dart';
import 'package:agrimind/features/farm_manager/application/farm_manager_repository.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:flutter/material.dart';

class TreeDetailPage extends StatefulWidget {
  const TreeDetailPage({
    required this.farm,
    required this.treeId,
    required this.repository,
    super.key,
  });

  final Farm farm;
  final String treeId;
  final FarmManagerRepository repository;

  @override
  State<TreeDetailPage> createState() => _TreeDetailPageState();
}

class _TreeDetailPageState extends State<TreeDetailPage> {
  late final TreeDetailController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TreeDetailController(widget.repository);
    unawaited(_controller.load(farmId: widget.farm.id, treeId: widget.treeId));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: _controller,
    builder: (context, _) => AgriMindScaffold(
      title: _controller.tree?.label ?? 'Détail de l’arbre',
      scrollable: true,
      body: _TreeDetailBody(controller: _controller),
    ),
  );
}

class _TreeDetailBody extends StatelessWidget {
  const _TreeDetailBody({required this.controller});

  final TreeDetailController controller;

  @override
  Widget build(BuildContext context) => switch (controller.status) {
    TreeDetailStatus.idle || TreeDetailStatus.loading => const Center(
      child: AgriMindLoadingIndicator(label: 'Chargement de l’arbre'),
    ),
    TreeDetailStatus.notFound => const Center(
      child: AgriMindEmptyState(
        icon: Icons.search_off_rounded,
        title: 'Arbre introuvable',
        message: 'Cet arbre n’existe pas dans la ferme sélectionnée.',
      ),
    ),
    TreeDetailStatus.failure => Center(
      child: AgriMindErrorState(
        title: 'Arbre indisponible',
        message: 'Les informations ne peuvent pas être chargées.',
        onRetry: controller.retry,
      ),
    ),
    TreeDetailStatus.loaded => _LoadedTreeDetail(tree: controller.tree!),
  };
}

class _LoadedTreeDetail extends StatelessWidget {
  const _LoadedTreeDetail({required this.tree});

  final FarmTree tree;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      AgriMindCard(
        child: Row(
          children: [
            const Icon(
              Icons.park_rounded,
              size: AgriMindIconSizes.hero,
              color: AgriMindColors.primaryGreen,
            ),
            const SizedBox(width: AgriMindSpacing.lg),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(tree.label, style: AgriMindTypography.heading3),
                  Text(
                    'Position ${tree.position.displayLabel}',
                    style: AgriMindTypography.bodySecondary.copyWith(
                      color: AgriMindColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: AgriMindSpacing.md),
      const _UnavailableInformationCard(
        icon: Icons.info_outline_rounded,
        label: 'Statut',
      ),
      const SizedBox(height: AgriMindSpacing.md),
      const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: _UnavailableInformationCard(
              icon: Icons.water_drop_outlined,
              label: 'Humidité du sol',
            ),
          ),
          SizedBox(width: AgriMindSpacing.md),
          Expanded(
            child: _UnavailableInformationCard(
              icon: Icons.water_rounded,
              label: 'Dernière irrigation',
            ),
          ),
        ],
      ),
      const SizedBox(height: AgriMindSpacing.md),
      const _UnavailableInformationCard(
        icon: Icons.image_search_rounded,
        label: 'Dernière inspection',
      ),
      const SizedBox(height: AgriMindSpacing.xl),
      const AgriMindSectionHeader(title: 'Activité récente'),
      const SizedBox(height: AgriMindSpacing.md),
      const AgriMindCard(
        child: AgriMindEmptyState(
          icon: Icons.history_rounded,
          title: 'Aucune activité disponible',
          message:
              'L’historique par arbre sera affiché lorsqu’il sera disponible.',
        ),
      ),
      const SizedBox(height: AgriMindSpacing.xl),
      const AgriMindButton(
        label: 'Inspecter la plante — bientôt disponible',
        onPressed: null,
        icon: Icons.camera_alt_outlined,
      ),
    ],
  );
}

class _UnavailableInformationCard extends StatelessWidget {
  const _UnavailableInformationCard({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => AgriMindCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, color: AgriMindColors.primaryGreen),
            const SizedBox(width: AgriMindSpacing.sm),
            Expanded(child: Text(label, style: AgriMindTypography.label)),
          ],
        ),
        const SizedBox(height: AgriMindSpacing.sm),
        Text('—', style: AgriMindTypography.heading2),
        Text(
          'Indisponible',
          style: AgriMindTypography.caption.copyWith(
            color: AgriMindColors.textSecondary,
          ),
        ),
      ],
    ),
  );
}
