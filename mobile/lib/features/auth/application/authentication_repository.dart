import 'package:agrimind/features/auth/domain/auth_session.dart';

abstract interface class AuthenticationRepository {
  Stream<AuthSession?> get authStateChanges;

  Future<AuthSession?> restoreSession();

  Future<AuthSession> signIn({required String email, required String password});

  Future<void> signOut();
}
