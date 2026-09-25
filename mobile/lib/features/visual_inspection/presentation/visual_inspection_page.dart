import 'dart:typed_data';

import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/models/ui_status.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/visual_inspection/application/visual_inspection_controller.dart';
import 'package:agrimind/features/visual_inspection/domain/cv_inference_result.dart';
import 'package:flutter/material.dart';

class VisualInspectionPage extends StatefulWidget {
  const VisualInspectionPage({
    required this.farm,
    required this.tree,
    required this.controller,
    this.demonstrationMode = false,
    super.key,
  });

  final Farm farm;
  final FarmTree tree;
  final VisualInspectionController controller;
  final bool demonstrationMode;

  @override
  State<VisualInspectionPage> createState() => _VisualInspectionPageState();
}

class _VisualInspectionPageState extends State<VisualInspectionPage> {
  @override
  void dispose() {
    widget.controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.controller,
    builder: (context, _) => AgriMindScaffold(
      title: 'Inspection visuelle',
      scrollable: true,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(widget.tree.label, style: AgriMindTypography.heading2),
          const SizedBox(height: AgriMindSpacing.xs),
          Text(
            '${widget.farm.name} · Position ${widget.tree.position.displayLabel}',
            style: AgriMindTypography.bodySecondary.copyWith(
              color: AgriMindColors.textSecondary,
            ),
          ),
          if (widget.demonstrationMode) ...[
            const SizedBox(height: AgriMindSpacing.md),
            const _DemoNotice(),
          ],
          const SizedBox(height: AgriMindSpacing.xl),
          if (widget.controller.image case final image?
              when widget.controller.status !=
                  VisualInspectionStatus.result) ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(AgriMindRadius.card),
              child: AspectRatio(
                aspectRatio: 4 / 3,
                child: Image.memory(
                  image.bytes,
                  key: const Key('inspection-image-preview'),
                  fit: BoxFit.cover,
                  semanticLabel: 'Aperçu de la feuille sélectionnée',
                ),
              ),
            ),
            const SizedBox(height: AgriMindSpacing.sm),
            Text(
              image.fileName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AgriMindTypography.caption.copyWith(
                color: AgriMindColors.textSecondary,
              ),
            ),
          ] else
            _UploadPrompt(
              onTap:
                  widget.controller.status == VisualInspectionStatus.selecting
                  ? null
                  : widget.controller.selectImage,
            ),
          const SizedBox(height: AgriMindSpacing.lg),
          if (widget.controller.status == VisualInspectionStatus.analyzing)
            const AgriMindCard(
              child: AgriMindLoadingIndicator(
                label: 'Analyse de l’image en cours',
              ),
            ),
          if (widget.controller.status == VisualInspectionStatus.error)
            AgriMindErrorState(
              title: widget.controller.image == null
                  ? 'Image non valide'
                  : 'Analyse impossible',
              message:
                  widget.controller.errorMessage ?? 'Une erreur est survenue.',
              onRetry: widget.controller.retry,
            ),
          if (widget.controller.status == VisualInspectionStatus.result &&
              widget.controller.result != null)
            _InspectionResult(
              result: widget.controller.result!,
              imageBytes: widget.controller.image!.bytes,
            ),
          const SizedBox(height: AgriMindSpacing.xl),
          AgriMindButton(
            label: widget.controller.image == null
                ? 'Sélectionner une image'
                : 'Choisir une autre image',
            onPressed:
                widget.controller.status == VisualInspectionStatus.analyzing ||
                    widget.controller.status == VisualInspectionStatus.selecting
                ? null
                : widget.controller.selectImage,
            loading:
                widget.controller.status == VisualInspectionStatus.selecting,
            variant: widget.controller.image == null
                ? AgriMindButtonVariant.primary
                : AgriMindButtonVariant.secondary,
            icon: Icons.photo_library_outlined,
          ),
          if (widget.controller.image != null) ...[
            const SizedBox(height: AgriMindSpacing.md),
            AgriMindButton(
              label: widget.controller.status == VisualInspectionStatus.error
                  ? 'Réessayer l’analyse'
                  : 'Analyser',
              onPressed:
                  widget.controller.status == VisualInspectionStatus.analyzing
                  ? null
                  : widget.controller.analyze,
              loading:
                  widget.controller.status == VisualInspectionStatus.analyzing,
              icon: Icons.image_search_rounded,
            ),
          ],
          const SizedBox(height: AgriMindSpacing.md),
          Text(
            'L’inspection indique uniquement NORMAL ou ANOMALY. '
            'Elle ne constitue pas un diagnostic de maladie.',
            style: AgriMindTypography.caption.copyWith(
              color: AgriMindColors.textSecondary,
            ),
          ),
        ],
      ),
    ),
  );
}

class _UploadPrompt extends StatelessWidget {
  const _UploadPrompt({required this.onTap});

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Zone de sélection d’une image de feuille',
    button: true,
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AgriMindRadius.card),
      child: Ink(
        padding: const EdgeInsets.symmetric(
          horizontal: AgriMindSpacing.xl,
          vertical: AgriMindSpacing.xxl,
        ),
        decoration: BoxDecoration(
          color: AgriMindColors.decorativeGreen,
          borderRadius: BorderRadius.circular(AgriMindRadius.card),
          border: Border.all(color: AgriMindColors.primaryGreen),
        ),
        child: Column(
          children: [
            const DecoratedBox(
              decoration: BoxDecoration(
                color: AgriMindColors.surface,
                shape: BoxShape.circle,
              ),
              child: Padding(
                padding: EdgeInsets.all(AgriMindSpacing.lg),
                child: Icon(
                  Icons.eco_rounded,
                  size: AgriMindIconSizes.hero,
                  color: AgriMindColors.primaryGreen,
                ),
              ),
            ),
            const SizedBox(height: AgriMindSpacing.md),
            Text(
              'Importer une image de feuille',
              style: AgriMindTypography.heading3,
            ),
            const SizedBox(height: AgriMindSpacing.xs),
            Text(
              'Sélectionnez une photo nette au format JPEG ou PNG.',
              textAlign: TextAlign.center,
              style: AgriMindTypography.bodySecondary.copyWith(
                color: AgriMindColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _DemoNotice extends StatelessWidget {
  const _DemoNotice();

  @override
  Widget build(BuildContext context) => AgriMindCard(
    semanticLabel: 'Mode démonstration',
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.science_outlined, color: AgriMindColors.info),
        const SizedBox(width: AgriMindSpacing.sm),
        Expanded(
          child: Text(
            'Mode démonstration : le résultat est simulé et ne provient pas '
            'du modèle CV.',
            style: AgriMindTypography.bodySecondary,
          ),
        ),
      ],
    ),
  );
}

class _InspectionResult extends StatelessWidget {
  const _InspectionResult({required this.result, required this.imageBytes});

  final CvInferenceResult result;
  final Uint8List imageBytes;

  @override
  Widget build(BuildContext context) {
    final isNormal = result.classification == CvClassification.normal;
    return Semantics(
      liveRegion: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Résultat de l’analyse', style: AgriMindTypography.heading3),
          const SizedBox(height: AgriMindSpacing.md),
          LayoutBuilder(
            builder: (context, constraints) {
              final details = Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  AgriMindStatusBadge(
                    status: isNormal ? UiStatus.success : UiStatus.warning,
                    labelOverride: result.classification.label,
                    semanticLabel: 'Résultat : ${result.classification.label}',
                  ),
                  const SizedBox(height: AgriMindSpacing.md),
                  Text(
                    isNormal
                        ? 'Aucune anomalie détectée par cette analyse.'
                        : 'Une anomalie visuelle a été détectée.',
                    style: AgriMindTypography.body,
                  ),
                  if (result.anomalySoftmaxProbability case final score?) ...[
                    const SizedBox(height: AgriMindSpacing.md),
                    Text(
                      'Probabilité softmax d’anomalie : '
                      '${(score * 100).toStringAsFixed(1)} %',
                      style: AgriMindTypography.label,
                    ),
                    const SizedBox(height: AgriMindSpacing.xs),
                    Text(
                      'Score non calibré — ce n’est pas une confiance.',
                      style: AgriMindTypography.caption.copyWith(
                        color: AgriMindColors.textSecondary,
                      ),
                    ),
                  ],
                  if (result.modelVersion case final version?) ...[
                    const SizedBox(height: AgriMindSpacing.sm),
                    Text('Version du modèle : $version'),
                  ],
                ],
              );
              final preview = ClipRRect(
                borderRadius: BorderRadius.circular(AgriMindRadius.large),
                child: AspectRatio(
                  aspectRatio: 1,
                  child: Image.memory(imageBytes, fit: BoxFit.cover),
                ),
              );
              if (constraints.maxWidth < 340) {
                return Column(
                  children: [
                    preview,
                    const SizedBox(height: AgriMindSpacing.md),
                    details,
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: preview),
                  const SizedBox(width: AgriMindSpacing.md),
                  Expanded(child: details),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}
