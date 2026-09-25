import 'dart:async';
import 'dart:convert';

import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';
import 'package:agrimind/features/farm_manager/domain/tree_position.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/visual_inspection/application/cv_inference_repository.dart';
import 'package:agrimind/features/visual_inspection/application/inspection_image_source.dart';
import 'package:agrimind/features/visual_inspection/application/inspection_image_validator.dart';
import 'package:agrimind/features/visual_inspection/application/visual_inspection_controller.dart';
import 'package:agrimind/features/visual_inspection/domain/cv_inference_result.dart';
import 'package:agrimind/features/visual_inspection/domain/inspection_image.dart';
import 'package:agrimind/features/visual_inspection/presentation/visual_inspection_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

final farm = Farm(id: 'farm-a', name: 'Ferme de Sfax');
const tree = FarmTree(
  id: 'tree-a1',
  farmId: 'farm-a',
  label: 'Olivier A1',
  position: TreePosition(row: 1, column: 1),
);

final validPng = InspectionImage(
  bytes: base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  ),
  fileName: 'leaf.png',
  mimeType: 'image/png',
);

final class _ImageSource implements InspectionImageSource {
  _ImageSource(this.image);

  InspectionImage? image;

  @override
  Future<InspectionImage?> selectFromGallery() async => image;
}

final class _InferenceRepository implements CvInferenceRepository {
  _InferenceRepository({this.result, this.failure, this.pending});

  CvInferenceResult? result;
  CvInferenceFailure? failure;
  Completer<CvInferenceResult>? pending;
  String? farmId;
  String? treeId;

  @override
  Future<CvInferenceResult> analyze({
    required String farmId,
    required String treeId,
    required InspectionImage image,
  }) async {
    this.farmId = farmId;
    this.treeId = treeId;
    if (failure case final value?) throw value;
    if (pending case final value?) return value.future;
    return result!;
  }
}

final class _AcceptingValidator implements InspectionImageValidator {
  const _AcceptingValidator();

  @override
  Future<void> validate(InspectionImage image) async {}
}

VisualInspectionController _controller({
  required _InferenceRepository repository,
  InspectionImage? image,
}) => VisualInspectionController(
  farmId: farm.id,
  treeId: tree.id,
  repository: repository,
  imageSource: _ImageSource(image ?? validPng),
  validator: image == null
      ? const _AcceptingValidator()
      : const DefaultInspectionImageValidator(),
);

Widget app(VisualInspectionController controller) => MaterialApp(
  theme: AgriMindTheme.light,
  home: VisualInspectionPage(
    farm: farm,
    tree: tree,
    controller: controller,
    demonstrationMode: true,
  ),
);

Future<void> tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pump();
  await tester.tap(finder);
}

void main() {
  testWidgets('selects, validates and previews a gallery image', (
    tester,
  ) async {
    final repository = _InferenceRepository(
      result: const CvInferenceResult(classification: CvClassification.normal),
    );
    await tester.pumpWidget(app(_controller(repository: repository)));

    expect(find.text('Aucune image sélectionnée'), findsOneWidget);
    await tester.tap(find.text('Sélectionner une image'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('inspection-image-preview')), findsOneWidget);
    expect(find.text('leaf.png'), findsOneWidget);
    expect(find.text('Analyser'), findsOneWidget);
    expect(find.textContaining('résultat est simulé'), findsOneWidget);
  });

  testWidgets('shows loading then NORMAL with optional score semantics', (
    tester,
  ) async {
    final pending = Completer<CvInferenceResult>();
    final repository = _InferenceRepository(pending: pending);
    await tester.pumpWidget(app(_controller(repository: repository)));
    await tester.tap(find.text('Sélectionner une image'));
    await tester.pumpAndSettle();
    await tapVisible(tester, find.text('Analyser'));
    await tester.pump();

    expect(find.text('Analyse de l’image en cours'), findsOneWidget);
    pending.complete(
      const CvInferenceResult(
        classification: CvClassification.normal,
        anomalySoftmaxProbability: 0.125,
        modelVersion: 'test-model',
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('NORMAL'), findsOneWidget);
    expect(find.textContaining('12.5 %'), findsOneWidget);
    expect(find.textContaining('ce n’est pas une confiance'), findsOneWidget);
    expect(repository.farmId, farm.id);
    expect(repository.treeId, tree.id);
  });

  testWidgets('shows ANOMALY without inventing a score', (tester) async {
    final repository = _InferenceRepository(
      result: const CvInferenceResult(classification: CvClassification.anomaly),
    );
    await tester.pumpWidget(app(_controller(repository: repository)));
    await tester.tap(find.text('Sélectionner une image'));
    await tester.pumpAndSettle();
    await tapVisible(tester, find.text('Analyser'));
    await tester.pumpAndSettle();

    expect(find.text('ANOMALY'), findsOneWidget);
    expect(find.textContaining('Probabilité softmax'), findsNothing);
    expect(find.textContaining('maladie détectée'), findsNothing);
  });

  testWidgets('shows validation error for an unsupported file', (tester) async {
    final repository = _InferenceRepository(
      result: const CvInferenceResult(classification: CvClassification.normal),
    );
    final invalid = InspectionImage(
      bytes: base64Decode('bm90IGFuIGltYWdl'),
      fileName: 'leaf.txt',
      mimeType: 'text/plain',
    );
    await tester.pumpWidget(
      app(_controller(repository: repository, image: invalid)),
    );
    await tester.tap(find.text('Sélectionner une image'));
    await tester.pumpAndSettle();

    expect(find.text('Image non valide'), findsOneWidget);
    expect(
      find.text('Sélectionnez une image JPEG ou PNG valide.'),
      findsOneWidget,
    );
    expect(find.text('Réessayer'), findsOneWidget);
  });

  testWidgets('shows inference error and retries the same image', (
    tester,
  ) async {
    final repository = _InferenceRepository(
      result: const CvInferenceResult(classification: CvClassification.normal),
      failure: const CvInferenceFailure('Service temporairement indisponible.'),
    );
    await tester.pumpWidget(app(_controller(repository: repository)));
    await tester.tap(find.text('Sélectionner une image'));
    await tester.pumpAndSettle();
    await tapVisible(tester, find.text('Analyser'));
    await tester.pumpAndSettle();

    expect(find.text('Analyse impossible'), findsOneWidget);
    expect(find.text('Service temporairement indisponible.'), findsOneWidget);

    repository.failure = null;
    await tapVisible(tester, find.text('Réessayer'));
    await tester.pumpAndSettle();
    expect(find.text('NORMAL'), findsOneWidget);
  });
}
