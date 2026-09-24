import 'dart:async';

import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/onboarding/domain/farm_failure.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_farm_repository.dart';

void main() {
  final farm = Farm(id: 'farm-a', name: 'Ferme A');

  test('checks an authenticated user and distinguishes no farm', () async {
    final repository = FakeFarmRepository();
    final controller = FarmController(repository);

    await controller.synchronizeAuthenticatedUser('user-a');

    expect(controller.status, FarmStatus.noFarm);
    expect(repository.lookupCalls, 1);
  });

  test(
    'keeps checking state until an existing farm lookup completes',
    () async {
      final repository = FakeFarmRepository()
        ..lookupCompleter = Completer<Farm?>();
      final controller = FarmController(repository);

      final lookup = controller.synchronizeAuthenticatedUser('user-a');
      expect(controller.status, FarmStatus.checking);
      repository.lookupCompleter!.complete(farm);
      await lookup;

      expect(controller.status, FarmStatus.configured);
      expect(controller.farm, farm);
    },
  );

  test('lookup failure is distinct from no farm and retry recovers', () async {
    final repository = FakeFarmRepository()
      ..lookupError = const FarmFailure(FarmFailureType.unavailable);
    final controller = FarmController(repository);

    await controller.synchronizeAuthenticatedUser('user-a');
    expect(controller.status, FarmStatus.failure);
    expect(controller.errorMessage, contains('indisponible'));

    repository
      ..lookupError = null
      ..currentFarm = farm;
    await controller.retry();
    expect(controller.status, FarmStatus.configured);
    expect(repository.lookupCalls, 2);
  });

  test('validates and normalizes the only required field', () async {
    final repository = FakeFarmRepository();
    final controller = FarmController(repository);
    await controller.synchronizeAuthenticatedUser('user-a');

    expect(controller.validateFarmName('   '), isNotNull);
    expect(controller.validateFarmName('a' * 121), isNotNull);
    await controller.createFarm('  Ferme Démo  ');

    expect(repository.submittedName, 'Ferme Démo');
    expect(controller.status, FarmStatus.configured);
    expect(controller.farm?.name, 'Ferme Démo');
  });

  test('prevents duplicate submission while creation is pending', () async {
    final repository = FakeFarmRepository()
      ..creationCompleter = Completer<Farm>();
    final controller = FarmController(repository);
    await controller.synchronizeAuthenticatedUser('user-a');

    final first = controller.createFarm('Ferme A');
    final second = controller.createFarm('Ferme A');
    expect(repository.creationCalls, 1);
    repository.creationCompleter!.complete(farm);
    await Future.wait([first, second]);
    expect(controller.status, FarmStatus.configured);
  });

  test(
    'creation failure preserves name and retry discovers server success',
    () async {
      final repository = FakeFarmRepository()
        ..creationError = const FarmFailure(FarmFailureType.unavailable);
      final controller = FarmController(repository);
      await controller.synchronizeAuthenticatedUser('user-a');

      await controller.createFarm(' Ferme reprise ');
      expect(controller.status, FarmStatus.failure);
      expect(controller.pendingFarmName, 'Ferme reprise');

      repository
        ..creationError = null
        ..currentFarm = farm;
      await controller.retry();
      expect(controller.status, FarmStatus.configured);
      expect(controller.farm, farm);
    },
  );

  test('logout clears configured farm and next user is checked', () async {
    final repository = FakeFarmRepository(currentFarm: farm);
    final controller = FarmController(repository);
    await controller.synchronizeAuthenticatedUser('user-a');

    await controller.synchronizeAuthenticatedUser(null);
    expect(controller.status, FarmStatus.idle);
    expect(controller.farm, isNull);

    repository.currentFarm = null;
    await controller.synchronizeAuthenticatedUser('user-b');
    expect(controller.status, FarmStatus.noFarm);
    expect(repository.lookupCalls, 2);
  });
}
