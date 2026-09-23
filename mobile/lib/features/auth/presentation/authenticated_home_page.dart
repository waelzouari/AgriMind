import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:flutter/material.dart';

class AuthenticatedHomePage extends StatelessWidget {
  const AuthenticatedHomePage({required this.controller, super.key});

  final AuthenticationController controller;

  @override
  Widget build(BuildContext context) {
    return AgriMindScaffold(
      title: 'AGRIMIND',
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Session active', style: AgriMindTypography.heading2),
          const SizedBox(height: AgriMindSpacing.sm),
          Text(
            'Votre session est restaurée. Les fonctionnalités agricoles '
            'seront ajoutées dans leurs tickets dédiés.',
            style: AgriMindTypography.bodySecondary,
          ),
          const SizedBox(height: AgriMindSpacing.xl),
          AgriMindButton(
            label: 'Se déconnecter',
            onPressed: controller.signOut,
            loading: controller.isSubmitting,
            variant: AgriMindButtonVariant.secondary,
            icon: Icons.logout_rounded,
          ),
          if (controller.errorMessage case final message?) ...[
            const SizedBox(height: AgriMindSpacing.md),
            Semantics(
              liveRegion: true,
              child: Text(
                message,
                style: AgriMindTypography.bodySecondary.copyWith(
                  color: AgriMindColors.error,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
