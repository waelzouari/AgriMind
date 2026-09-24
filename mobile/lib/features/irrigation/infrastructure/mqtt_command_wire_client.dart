import 'dart:async';

import 'package:agrimind/features/dashboard/infrastructure/mqtt_wire_client.dart';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

abstract interface class MqttCommandWireClient {
  Stream<WireConnectionEvent> get connectionEvents;
  Future<void> connect();
  Future<bool> publish({required String topic, required String payload});
  Future<void> disconnect();
}

final class MqttCommandPublisherClient implements MqttCommandWireClient {
  MqttCommandPublisherClient({
    required this.host,
    required this.port,
    required this.username,
    required this.password,
    this.confirmationTimeout = const Duration(seconds: 10),
  });

  final String host;
  final int port;
  final String username;
  final String password;
  final Duration confirmationTimeout;
  final _connections = StreamController<WireConnectionEvent>.broadcast();
  MqttServerClient? _client;
  bool _intentionalDisconnect = false;

  @override
  Stream<WireConnectionEvent> get connectionEvents => _connections.stream;

  @override
  Future<void> connect() async {
    await disconnect();
    _intentionalDisconnect = false;
    final identifier =
        'agrimind-mobile-command-${DateTime.now().microsecondsSinceEpoch}';
    final client = MqttServerClient.withPort(host, identifier, port)
      ..secure = true
      ..logging(on: false)
      ..autoReconnect = true
      ..keepAlivePeriod = 30
      ..connectTimeoutPeriod = 10000
      ..connectionMessage = MqttConnectMessage()
          .withClientIdentifier(identifier)
          .authenticateAs(username, password)
          .startClean();
    client.onConnected = () => _connections.add(WireConnectionEvent.connected);
    client.onAutoReconnect = () =>
        _connections.add(WireConnectionEvent.reconnecting);
    client.onAutoReconnected = () =>
        _connections.add(WireConnectionEvent.connected);
    client.onDisconnected = () {
      if (!_intentionalDisconnect) {
        _connections.add(WireConnectionEvent.disconnected);
      }
    };
    _client = client;
    try {
      final status = await client.connect(username, password);
      if (status?.state != MqttConnectionState.connected) {
        _connections.add(WireConnectionEvent.failure);
        client.disconnect();
      }
    } on Object {
      _connections.add(WireConnectionEvent.failure);
      client.disconnect();
    }
  }

  @override
  Future<bool> publish({required String topic, required String payload}) async {
    final client = _client;
    if (client?.connectionStatus?.state != MqttConnectionState.connected) {
      return false;
    }
    final builder = MqttClientPayloadBuilder()..addUTF8String(payload);
    final confirmation = Completer<bool>();
    late StreamSubscription<MqttPublishMessage> subscription;
    subscription = client!.published!.listen((message) {
      if (message.variableHeader?.topicName == topic &&
          !confirmation.isCompleted) {
        confirmation.complete(true);
      }
    });
    try {
      client.publishMessage(
        topic,
        MqttQos.atLeastOnce,
        builder.payload!,
        retain: false,
      );
      return await confirmation.future.timeout(
        confirmationTimeout,
        onTimeout: () => false,
      );
    } on Object {
      return false;
    } finally {
      await subscription.cancel();
    }
  }

  @override
  Future<void> disconnect() async {
    _intentionalDisconnect = true;
    _client?.disconnect();
    _client = null;
  }
}
