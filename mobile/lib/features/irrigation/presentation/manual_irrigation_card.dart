import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/models/ui_status.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_controller.dart';
import 'package:flutter/material.dart';

class ManualIrrigationCard extends StatefulWidget {
  const ManualIrrigationCard({required this.controller, super.key});
  final ManualIrrigationController controller;

  @override
  State<ManualIrrigationCard> createState() => _ManualIrrigationCardState();
}

class _ManualIrrigationCardState extends State<ManualIrrigationCard> {
  int _durationSeconds = 300;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.controller,
    builder: (context, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const AgriMindSectionHeader(
          title: 'Irrigation manuelle',
          subtitle: 'La sécurité physique reste contrôlée par le Raspberry Pi.',
        ),
        const SizedBox(height: AgriMindSpacing.md),
        AgriMindCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _ConnectionStatus(phase: widget.controller.connectionPhase),
              const SizedBox(height: AgriMindSpacing.lg),
              Text('Durée demandée', style: AgriMindTypography.cardTitle),
              const SizedBox(height: AgriMindSpacing.sm),
              Wrap(
                spacing: AgriMindSpacing.sm,
                runSpacing: AgriMindSpacing.sm,
                children: [60, 300, 600]
                    .map(
                      (seconds) => ChoiceChip(
                        label: Text(_durationLabel(seconds)),
                        selected: _durationSeconds == seconds,
                        onSelected: widget.controller.isPending
                            ? null
                            : (selected) {
                                if (selected) {
                                  setState(() => _durationSeconds = seconds);
                                }
                              },
                      ),
                    )
                    .toList(),
              ),
              const SizedBox(height: AgriMindSpacing.lg),
              AgriMindButton(
                label: widget.controller.isPending
                    ? 'Commande en cours'
                    : 'Demander l’irrigation',
                icon: Icons.play_arrow_rounded,
                loading: widget.controller.isPending,
                onPressed: widget.controller.canSubmit ? _confirm : null,
              ),
              const SizedBox(height: AgriMindSpacing.md),
              Text(
                'La connexion MQTT ne prouve pas la disponibilité physique de '
                'la pompe. Seul un ACK de l’edge confirme sa décision.',
                style: AgriMindTypography.caption.copyWith(
                  color: AgriMindColors.textSecondary,
                ),
              ),
              if (widget.controller.phase != ManualIrrigationPhase.idle) ...[
                const SizedBox(height: AgriMindSpacing.lg),
                _CommandResult(controller: widget.controller),
              ],
            ],
          ),
        ),
      ],
    ),
  );

  Future<void> _confirm() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirmer la demande'),
        content: Text(
          'Demander une irrigation manuelle de '
          '${_durationLabel(_durationSeconds)} ? Le Raspberry Pi pourra la refuser.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Envoyer la demande'),
          ),
        ],
      ),
    );
    if (confirmed == true) await widget.controller.submit(_durationSeconds);
  }
}

class _ConnectionStatus extends StatelessWidget {
  const _ConnectionStatus({required this.phase});
  final MqttConnectionPhase phase;
  @override
  Widget build(BuildContext context) {
    final (status, label) = switch (phase) {
      MqttConnectionPhase.idle => (UiStatus.offline, 'Contrôle MQTT inactif'),
      MqttConnectionPhase.connecting => (
        UiStatus.loading,
        'Connexion du contrôle',
      ),
      MqttConnectionPhase.connected => (
        UiStatus.online,
        'Canal de contrôle connecté',
      ),
      MqttConnectionPhase.reconnecting => (
        UiStatus.warning,
        'Reconnexion du contrôle',
      ),
      MqttConnectionPhase.disconnected => (
        UiStatus.offline,
        'Canal de contrôle déconnecté',
      ),
      MqttConnectionPhase.failure => (UiStatus.error, 'Contrôle indisponible'),
    };
    return Align(
      alignment: Alignment.centerLeft,
      child: AgriMindStatusBadge(status: status, labelOverride: label),
    );
  }
}

class _CommandResult extends StatelessWidget {
  const _CommandResult({required this.controller});
  final ManualIrrigationController controller;
  @override
  Widget build(BuildContext context) {
    final (status, title, message) = switch (controller.phase) {
      ManualIrrigationPhase.publishing => (
        UiStatus.loading,
        'Transmission au broker',
        'La demande est en cours de publication. La pompe n’est pas confirmée.',
      ),
      ManualIrrigationPhase.awaitingAcknowledgement => (
        UiStatus.loading,
        'En attente de l’edge',
        'Le broker a confirmé la publication. Attente de la décision du Raspberry Pi.',
      ),
      ManualIrrigationPhase.accepted => (
        UiStatus.success,
        'Commande acceptée par l’edge',
        controller.acknowledgement?.pumpState == true
            ? 'La pompe a été confirmée active. Attente de l’arrêt automatique.'
            : 'L’edge a accepté la commande. Attente de sa finalisation.',
      ),
      ManualIrrigationPhase.rejected => (
        UiStatus.warning,
        'Commande refusée par l’edge',
        _reason(controller.acknowledgement?.reasonCode),
      ),
      ManualIrrigationPhase.completed => (
        UiStatus.success,
        'Irrigation terminée',
        'L’edge a confirmé la fin de la commande et l’arrêt de la pompe.',
      ),
      ManualIrrigationPhase.failed => (
        UiStatus.error,
        'Commande non aboutie',
        controller.acknowledgement == null
            ? 'La transmission au broker n’a pas été confirmée. Aucun état physique ne peut être déduit.'
            : _reason(controller.acknowledgement?.reasonCode),
      ),
      ManualIrrigationPhase.timedOut => (
        UiStatus.warning,
        'Résultat non confirmé',
        'Aucun ACK final n’a été reçu à temps. L’état physique est inconnu.',
      ),
      ManualIrrigationPhase.idle => (UiStatus.offline, '', ''),
    };
    return Semantics(
      liveRegion: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: AgriMindStatusBadge(status: status, labelOverride: title),
          ),
          const SizedBox(height: AgriMindSpacing.sm),
          Text(message, style: AgriMindTypography.bodySecondary),
          if (!controller.isPending) ...[
            const SizedBox(height: AgriMindSpacing.md),
            AgriMindButton(
              label: 'Nouvelle demande',
              variant: AgriMindButtonVariant.secondary,
              onPressed: controller.resetResult,
              icon: Icons.refresh_rounded,
            ),
          ],
        ],
      ),
    );
  }
}

String _durationLabel(int seconds) =>
    seconds == 60 ? '1 min' : '${seconds ~/ 60} min';

String _reason(String? code) => switch (code) {
  'already_running' => 'Une irrigation est déjà en cours.',
  'expired_command' => 'La demande a expiré avant son traitement.',
  'duration_exceeds_local_limit' =>
    'La durée dépasse la limite locale autorisée.',
  'controller_fault' ||
  'state_inconsistent' => 'Le contrôleur local est en état de sécurité.',
  'pump_actuation_failed' || 'scheduler_failed' =>
    'Le système local n’a pas pu exécuter la commande en sécurité.',
  'wrong_farm' ||
  'wrong_device' ||
  'invalid_command' ||
  'command_id_conflict' =>
    'La commande a été refusée car elle ne correspond pas au contrat ou à la cible.',
  _ => 'La commande a été refusée ou a échoué côté edge.',
};
