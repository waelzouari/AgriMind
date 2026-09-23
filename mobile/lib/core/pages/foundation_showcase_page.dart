import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/models/ui_status.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:flutter/material.dart';

class FoundationShowcasePage extends StatelessWidget {
  const FoundationShowcasePage({super.key});

  @override
  Widget build(BuildContext context) {
    return AgriMindScaffold(
      title: 'AGRIMIND',
      scrollable: true,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            header: true,
            child: Text(
              'Fondation visuelle',
              style: AgriMindTypography.heading1,
            ),
          ),
          const SizedBox(height: AgriMindSpacing.sm),
          Text(
            'Démonstration technique du design system mobile AgriMind. '
            'Aucune donnée agricole ou commande réelle n’est présentée.',
            style: AgriMindTypography.body.copyWith(
              color: AgriMindColors.textSecondary,
            ),
          ),
          const SizedBox(height: AgriMindSpacing.xxl),
          const AgriMindSectionHeader(
            title: 'États de présentation',
            subtitle: 'Chaque état associe un texte, une icône et une couleur.',
          ),
          const SizedBox(height: AgriMindSpacing.md),
          AgriMindCard(
            child: Wrap(
              spacing: AgriMindSpacing.sm,
              runSpacing: AgriMindSpacing.sm,
              children: UiStatus.values
                  .map((status) => AgriMindStatusBadge(status: status))
                  .toList(),
            ),
          ),
          const SizedBox(height: AgriMindSpacing.xxl),
          const AgriMindSectionHeader(
            title: 'Actions',
            subtitle: 'Variantes, état désactivé et chargement accessibles.',
          ),
          const SizedBox(height: AgriMindSpacing.md),
          AgriMindCard(
            child: Wrap(
              spacing: AgriMindSpacing.sm,
              runSpacing: AgriMindSpacing.sm,
              children: [
                AgriMindButton(label: 'Action principale', onPressed: () {}),
                AgriMindButton(
                  label: 'Action secondaire',
                  onPressed: () {},
                  variant: AgriMindButtonVariant.secondary,
                ),
                const AgriMindButton(label: 'Indisponible', onPressed: null),
                AgriMindButton(
                  label: 'Chargement',
                  onPressed: () {},
                  loading: true,
                ),
              ],
            ),
          ),
          const SizedBox(height: AgriMindSpacing.xxl),
          const AgriMindSectionHeader(
            title: 'Retours système',
            subtitle: 'États génériques sans intégration réseau ou matérielle.',
          ),
          const SizedBox(height: AgriMindSpacing.md),
          const AgriMindCard(
            child: AgriMindLoadingIndicator(
              label: 'Chargement de la démonstration',
            ),
          ),
          const SizedBox(height: AgriMindSpacing.lg),
          const AgriMindCard(
            child: AgriMindEmptyState(
              title: 'Aucun exemple supplémentaire',
              message:
                  'Les futures fonctionnalités seront ajoutées par leurs tickets dédiés.',
            ),
          ),
          const SizedBox(height: AgriMindSpacing.lg),
          const AgriMindCard(
            child: AgriMindErrorState(
              title: 'Exemple d’erreur',
              message:
                  'Ce composant illustre uniquement un retour visuel accessible.',
            ),
          ),
        ],
      ),
    );
  }
}
