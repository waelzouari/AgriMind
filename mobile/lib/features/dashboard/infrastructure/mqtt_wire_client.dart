import 'dart:async';

import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

enum WireConnectionEvent { connected, reconnecting, disconnected, failure }

final class WireMessage {
  const WireMessage({required this.topic, required this.payload});
  final String topic;
  final String payload;
}

abstract interface class MqttWireClient {
  Stream<WireConnectionEvent> get connectionEvents;
  Stream<WireMessage> get messages;
  Future<void> connect({required String topicFilter});
  Future<void> disconnect();
}

final class PahoStyleMqttWireClient implements MqttWireClient {
  PahoStyleMqttWireClient({
    required this.host,
    required this.port,
    required this.username,
    required this.password,
  });

  final String host;
  final int port;
  final String username;
  final String password;
  final _connections = StreamController<WireConnectionEvent>.broadcast();
  final _messages = StreamController<WireMessage>.broadcast();
  MqttServerClient? _client;
  StreamSubscription<List<MqttReceivedMessage<MqttMessage>>>? _updates;
  bool _intentionalDisconnect = false;

  @override
  Stream<WireConnectionEvent> get connectionEvents => _connections.stream;
  @override
  Stream<WireMessage> get messages => _messages.stream;

  @override
  Future<void> connect({required String topicFilter}) async {
    await disconnect();
    _intentionalDisconnect = false;
    final identifier =
        'agrimind-mobile-${DateTime.now().microsecondsSinceEpoch}';
    final client = MqttServerClient.withPort(host, identifier, port)
      ..secure = true
      ..logging(on: false)
      ..autoReconnect = true
      ..resubscribeOnAutoReconnect = true
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
        return;
      }
      final subscription = client.subscribe(topicFilter, MqttQos.atLeastOnce);
      if (subscription == null) {
        _connections.add(WireConnectionEvent.failure);
        client.disconnect();
        return;
      }
      _updates = client.updates?.listen(_onMessages);
    } on Object {
      _connections.add(WireConnectionEvent.failure);
      client.disconnect();
    }
  }

  void _onMessages(List<MqttReceivedMessage<MqttMessage>> received) {
    for (final item in received) {
      final message = item.payload;
      if (message is! MqttPublishMessage) continue;
      final payload = MqttPublishPayload.bytesToStringAsString(
        message.payload.message,
      );
      _messages.add(WireMessage(topic: item.topic, payload: payload));
    }
  }

  @override
  Future<void> disconnect() async {
    _intentionalDisconnect = true;
    await _updates?.cancel();
    _updates = null;
    _client?.disconnect();
    _client = null;
  }
}
