import 'dart:async';

import 'package:agrimind/features/auth/application/authentication_repository.dart';
import 'package:agrimind/features/auth/domain/auth_session.dart';
import 'package:agrimind/features/auth/domain/authentication_failure.dart';
import 'package:flutter/foundation.dart';

enum AuthenticationStatus { restoring, unauthenticated, authenticated }

final class AuthenticationController extends ChangeNotifier {
  AuthenticationController(this._repository);

  final AuthenticationRepository _repository;
  AuthenticationStatus _status = AuthenticationStatus.restoring;
  AuthSession? _session;
  StreamSubscription<AuthSession?>? _subscription;
  bool _started = false;
  bool _submitting = false;
  bool _receivedAuthEvent = false;
  AuthSession? _latestAuthEvent;
  String? _errorMessage;

  AuthenticationStatus get status => _status;
  AuthSession? get session => _session;
  bool get isSubmitting => _submitting;
  String? get errorMessage => _errorMessage;

  Future<void> restoreSession() async {
    if (_started) return;
    _started = true;
    _subscription = _repository.authStateChanges.listen((session) {
      _receivedAuthEvent = true;
      _latestAuthEvent = session;
      _applySession(session);
    }, onError: (_, _) => _becomeUnauthenticated());
    try {
      final restored = await _repository.restoreSession();
      _applySession(_receivedAuthEvent ? _latestAuthEvent : restored);
    } on Object {
      _becomeUnauthenticated(
        message: 'La session précédente n’a pas pu être restaurée.',
      );
    }
  }

  Future<void> signIn({required String email, required String password}) async {
    if (_submitting) return;
    _submitting = true;
    _errorMessage = null;
    notifyListeners();
    try {
      final session = await _repository.signIn(
        email: email,
        password: password,
      );
      _applySession(session);
    } on AuthenticationFailure catch (failure) {
      _becomeUnauthenticated(message: failure.userMessage);
    } on Object {
      _becomeUnauthenticated(
        message: const AuthenticationFailure(
          AuthenticationFailureType.unknown,
        ).userMessage,
      );
    } finally {
      _submitting = false;
      notifyListeners();
    }
  }

  Future<void> signOut() async {
    if (_submitting) return;
    _submitting = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _repository.signOut();
      _becomeUnauthenticated();
    } on Object {
      _errorMessage = 'La déconnexion a échoué. Veuillez réessayer.';
    } finally {
      _submitting = false;
      notifyListeners();
    }
  }

  void _applySession(AuthSession? session) {
    _session = session;
    _status = session == null
        ? AuthenticationStatus.unauthenticated
        : AuthenticationStatus.authenticated;
    _errorMessage = null;
    notifyListeners();
  }

  void _becomeUnauthenticated({String? message}) {
    _session = null;
    _status = AuthenticationStatus.unauthenticated;
    _errorMessage = message;
    notifyListeners();
  }

  @override
  void dispose() {
    unawaited(_subscription?.cancel());
    super.dispose();
  }
}
