import 'dart:async';

import 'package:agrimind/features/onboarding/application/farm_repository.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';

final class FakeFarmRepository implements FarmRepository {
  FakeFarmRepository({this.currentFarm});

  Farm? currentFarm;
  Object? lookupError;
  Object? creationError;
  Completer<Farm?>? lookupCompleter;
  Completer<Farm>? creationCompleter;
  int lookupCalls = 0;
  int creationCalls = 0;
  String? submittedName;

  @override
  Future<Farm?> findCurrentFarm() async {
    lookupCalls += 1;
    if (lookupError case final error?) throw error;
    return lookupCompleter?.future ?? currentFarm;
  }

  @override
  Future<Farm> createCurrentUserFarm({required String name}) async {
    creationCalls += 1;
    submittedName = name;
    if (creationError case final error?) throw error;
    final farm =
        await (creationCompleter?.future ??
            Future.value(Farm(id: 'farm-created', name: name)));
    currentFarm = farm;
    return farm;
  }
}
