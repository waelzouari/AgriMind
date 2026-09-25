import 'dart:async';

import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/farm_manager/application/farm_manager_controller.dart';
import 'package:agrimind/features/farm_manager/application/farm_manager_repository.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';
import 'package:agrimind/features/farm_manager/presentation/farm_navigation_bar.dart';
import 'package:agrimind/features/farm_manager/presentation/tree_detail_page.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/visual_inspection/application/cv_inference_repository.dart';
import 'package:agrimind/features/visual_inspection/application/inspection_image_source.dart';
import 'package:flutter/material.dart';

class FarmManagerPage extends StatefulWidget {
  const FarmManagerPage({
    required this.farm,
    required this.repository,
    this.cvInferenceRepository,
    this.inspectionImageSource,
    this.onOpenHistory,
    super.key,
  });

  final Farm farm;
  final FarmManagerRepository repository;
  final CvInferenceRepository? cvInferenceRepository;
  final InspectionImageSource? inspectionImageSource;
  final VoidCallback? onOpenHistory;

  @override
  State<FarmManagerPage> createState() => _FarmManagerPageState();
}

class _FarmManagerPageState extends State<FarmManagerPage> {
  late final FarmManagerController _controller;

  @override
  void initState() {
    super.initState();
    _controller = FarmManagerController(widget.repository);
    unawaited(_controller.load(widget.farm.id));
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
      title: 'Ma ferme',
      scrollable: true,
      bottomNavigationBar: FarmNavigationBar(
        selectedIndex: 1,
        onHome: () => Navigator.of(context).pop(),
        onFarm: () {},
        onHistory: widget.onOpenHistory,
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(
                Icons.location_on_outlined,
                color: AgriMindColors.primaryGreen,
              ),
              const SizedBox(width: AgriMindSpacing.sm),
              Expanded(
                child: Text(
                  widget.farm.name,
                  style: AgriMindTypography.bodySecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: AgriMindSpacing.xl),
          _FarmManagerBody(
            controller: _controller,
            onTreeSelected: (tree) => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => TreeDetailPage(
                  farm: widget.farm,
                  treeId: tree.id,
                  repository: widget.repository,
                  cvInferenceRepository: widget.cvInferenceRepository,
                  inspectionImageSource: widget.inspectionImageSource,
                ),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

class _FarmManagerBody extends StatelessWidget {
  const _FarmManagerBody({
    required this.controller,
    required this.onTreeSelected,
  });

  final FarmManagerController controller;
  final ValueChanged<FarmTree> onTreeSelected;

  @override
  Widget build(BuildContext context) => switch (controller.status) {
    FarmManagerStatus.idle || FarmManagerStatus.loading => const Center(
      child: AgriMindLoadingIndicator(label: 'Chargement de la ferme'),
    ),
    FarmManagerStatus.failure => Center(
      child: AgriMindErrorState(
        title: 'Ferme indisponible',
        message: 'Les arbres ne peuvent pas être chargés pour le moment.',
        onRetry: controller.retry,
      ),
    ),
    FarmManagerStatus.empty => _LoadedFarm(
      totalTrees: controller.summary?.totalTrees ?? 0,
      trees: const [],
      onTreeSelected: onTreeSelected,
    ),
    FarmManagerStatus.loaded => _LoadedFarm(
      totalTrees: controller.summary?.totalTrees ?? controller.trees.length,
      trees: controller.trees,
      onTreeSelected: onTreeSelected,
    ),
  };
}

class _LoadedFarm extends StatelessWidget {
  const _LoadedFarm({
    required this.totalTrees,
    required this.trees,
    required this.onTreeSelected,
  });

  final int totalTrees;
  final List<FarmTree> trees;
  final ValueChanged<FarmTree> onTreeSelected;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _FarmSummary(totalTrees: totalTrees),
      const SizedBox(height: AgriMindSpacing.xl),
      const AgriMindSectionHeader(
        title: 'Arbres',
        subtitle: 'Disposition de la ferme',
      ),
      const SizedBox(height: AgriMindSpacing.md),
      if (trees.isEmpty)
        const AgriMindCard(
          child: AgriMindEmptyState(
            icon: Icons.park_outlined,
            title: 'Aucun arbre configuré',
            message: 'La grille apparaîtra lorsque des arbres seront ajoutés.',
          ),
        )
      else
        LayoutBuilder(
          builder: (context, constraints) {
            final columns = constraints.maxWidth >= 560
                ? 5
                : constraints.maxWidth >= 360
                ? 4
                : 3;
            return GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: trees.length,
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: columns,
                crossAxisSpacing: AgriMindSpacing.sm,
                mainAxisSpacing: AgriMindSpacing.sm,
                mainAxisExtent: 104,
              ),
              itemBuilder: (context, index) {
                final tree = trees[index];
                return AgriMindCard(
                  key: Key('farm-tree-${tree.id}'),
                  padding: const EdgeInsets.all(AgriMindSpacing.sm),
                  semanticLabel:
                      '${tree.label}, position ${tree.position.displayLabel}',
                  onTap: () => onTreeSelected(tree),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(
                        Icons.park_rounded,
                        size: AgriMindIconSizes.large,
                        color: AgriMindColors.primaryGreen,
                      ),
                      const SizedBox(height: AgriMindSpacing.sm),
                      Text(
                        tree.position.displayLabel,
                        style: AgriMindTypography.label,
                      ),
                    ],
                  ),
                );
              },
            );
          },
        ),
    ],
  );
}

class _FarmSummary extends StatelessWidget {
  const _FarmSummary({required this.totalTrees});

  final int totalTrees;

  @override
  Widget build(BuildContext context) => AgriMindCard(
    padding: EdgeInsets.zero,
    child: Row(
      children: [
        Expanded(
          child: _SummaryValue(value: '$totalTrees', label: 'Arbres'),
        ),
        const Expanded(
          child: _SummaryValue(value: '—', label: 'Sains'),
        ),
        const Expanded(
          child: _SummaryValue(value: '—', label: 'À surveiller'),
        ),
      ],
    ),
  );
}

class _SummaryValue extends StatelessWidget {
  const _SummaryValue({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(
      horizontal: AgriMindSpacing.sm,
      vertical: AgriMindSpacing.lg,
    ),
    child: Column(
      children: [
        Text(value, style: AgriMindTypography.heading2),
        const SizedBox(height: AgriMindSpacing.xs),
        Text(
          label,
          style: AgriMindTypography.caption.copyWith(
            color: AgriMindColors.textSecondary,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    ),
  );
}
