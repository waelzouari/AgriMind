import 'package:agrimind/features/onboarding/application/farm_repository.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/onboarding/domain/farm_failure.dart';
import 'package:flutter/foundation.dart';

enum FarmStatus { idle, checking, noFarm, creating, configured, failure }

enum FarmOperation { lookup, creation }

final class FarmController extends ChangeNotifier {
  FarmController(this._repository);

  final FarmRepository _repository;
  FarmStatus _status = FarmStatus.idle;
  Farm? _farm;
  String? _activeUserId;
  FarmOperation? _failedOperation;
  String? _errorMessage;
  String _pendingFarmName = '';

  FarmStatus get status => _status;
  Farm? get farm => _farm;
  String? get errorMessage => _errorMessage;
  String get pendingFarmName => _pendingFarmName;

  Future<void> synchronizeAuthenticatedUser(String? userId) async {
    if (userId == null) {
      if (_activeUserId != null || _status != FarmStatus.idle) {
        _reset();
        notifyListeners();
      }
      return;
    }
    if (_activeUserId == userId && _status != FarmStatus.idle) return;
    _activeUserId = userId;
    _pendingFarmName = '';
    await checkFarm();
  }

  Future<void> checkFarm() async {
    final userId = _activeUserId;
    if (userId == null || _status == FarmStatus.checking) return;
    _status = FarmStatus.checking;
    _farm = null;
    _errorMessage = null;
    notifyListeners();
    try {
      final farm = await _repository.findCurrentFarm();
      if (_activeUserId != userId) return;
      _farm = farm;
      _status = farm == null ? FarmStatus.noFarm : FarmStatus.configured;
      _failedOperation = null;
    } on FarmFailure catch (failure) {
      if (_activeUserId != userId) return;
      _fail(FarmOperation.lookup, failure.userMessage);
    } on Object {
      if (_activeUserId != userId) return;
      _fail(
        FarmOperation.lookup,
        const FarmFailure(FarmFailureType.unknown).userMessage,
      );
    }
    notifyListeners();
  }

  String? validateFarmName(String value) {
    final normalized = value.trim();
    if (normalized.isEmpty) return 'Saisissez le nom de la ferme.';
    if (normalized.length > 120) {
      return 'Le nom ne doit pas dépasser 120 caractères.';
    }
    return null;
  }

  Future<void> createFarm(String name) async {
    if (_activeUserId == null || _status == FarmStatus.creating) return;
    final normalized = name.trim();
    if (validateFarmName(normalized) != null) return;
    final userId = _activeUserId;
    _pendingFarmName = normalized;
    _status = FarmStatus.creating;
    _errorMessage = null;
    notifyListeners();
    try {
      final farm = await _repository.createCurrentUserFarm(name: normalized);
      if (_activeUserId != userId) return;
      _farm = farm;
      _status = FarmStatus.configured;
      _failedOperation = null;
      _pendingFarmName = '';
    } on FarmFailure catch (failure) {
      if (_activeUserId != userId) return;
      _fail(FarmOperation.creation, failure.userMessage);
    } on Object {
      if (_activeUserId != userId) return;
      _fail(
        FarmOperation.creation,
        const FarmFailure(FarmFailureType.unknown).userMessage,
      );
    }
    notifyListeners();
  }

  Future<void> retry() async {
    if (_failedOperation == null) return;
    // A creation response may have been lost. Always re-read first so the
    // server-side idempotent result is recovered without a blind second write.
    await checkFarm();
  }

  void _fail(FarmOperation operation, String message) {
    _status = FarmStatus.failure;
    _failedOperation = operation;
    _errorMessage = message;
  }

  void _reset() {
    _activeUserId = null;
    _status = FarmStatus.idle;
    _farm = null;
    _failedOperation = null;
    _errorMessage = null;
    _pendingFarmName = '';
  }
}
