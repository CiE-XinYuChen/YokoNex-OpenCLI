import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

// ── Data models ───────────────────────────────────────────────────────────────

class AgentInfo {
  final String id;
  final Map<String, dynamic> meta;
  final int clients;

  const AgentInfo({required this.id, required this.meta, required this.clients});

  factory AgentInfo.fromJson(Map<String, dynamic> j) => AgentInfo(
        id:      j['id']      as String,
        meta:    Map<String, dynamic>.from(j['meta'] as Map? ?? {}),
        clients: j['clients'] as int? ?? 0,
      );
}

class DeviceInfo {
  final String address;
  final String name;
  final String type;
  final bool connected;

  const DeviceInfo({
    required this.address,
    required this.name,
    required this.type,
    required this.connected,
  });

  factory DeviceInfo.fromJson(Map<String, dynamic> j) => DeviceInfo(
        address:   j['address']   as String,
        name:      j['name']      as String? ?? j['address'] as String,
        type:      j['type']      as String? ?? 'unknown',
        connected: j['connected'] as bool? ?? false,
      );
}

// ── Client ────────────────────────────────────────────────────────────────────

/// Manages WebSocket connection to YokoNex cloud relay server.
/// Used as a [ChangeNotifier] so Flutter widgets can rebuild on state changes.
class YokoNexClient extends ChangeNotifier {
  WebSocketChannel? _channel;
  StreamSubscription? _sub;

  int _reqCounter = 0;
  final Map<String, Completer<Map<String, dynamic>>> _pending = {};

  // ── Observable state ──────────────────────────────────────────────────────

  bool get isConnected => _channel != null;
  String? subscribedAgentId;
  String? connectedDeviceAddress;

  /// Latest device event (battery, device_info, disconnected, …)
  Map<String, dynamic>? lastEvent;

  /// Motor speeds A / B / C (0-20)
  final Map<String, int> motorSpeeds = {'A': 0, 'B': 0, 'C': 0};

  /// Motor modes A / B / C (1-4)
  final Map<String, int> motorModes = {'A': 1, 'B': 1, 'C': 1};

  // ── Connection ────────────────────────────────────────────────────────────

  Future<void> connect(String url, String token) async {
    await disconnect();
    _channel = WebSocketChannel.connect(Uri.parse(url));

    final hello = Completer<void>();

    _sub = _channel!.stream.listen(
      (raw) => _onMessage(raw as String),
      onDone:  () { _onClosed(); },
      onError: (e) { debugPrint('[ws] error: $e'); _onClosed(); },
    );

    // Auth
    _send({'type': 'client_hello', 'token': token});

    // Wait for hello
    _pending['__hello__'] = Completer<Map<String, dynamic>>();
    final resp = await _pending['__hello__']!.future
        .timeout(const Duration(seconds: 10));
    _pending.remove('__hello__');

    if (resp['ok'] != true) {
      await disconnect();
      throw Exception('Auth failed: ${resp['message']}');
    }

    notifyListeners();
  }

  Future<void> disconnect() async {
    await _sub?.cancel();
    await _channel?.sink.close();
    _channel          = null;
    _sub              = null;
    subscribedAgentId = null;
    connectedDeviceAddress = null;
    _pending.forEach((_, c) => c.completeError('disconnected'));
    _pending.clear();
    notifyListeners();
  }

  // ── Agent / device commands ───────────────────────────────────────────────

  Future<List<AgentInfo>> listAgents() async {
    final r = await _request({'type': 'list_agents'});
    return (r['agents'] as List? ?? [])
        .map((e) => AgentInfo.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<void> subscribeAgent(String agentId) async {
    await _request({'type': 'subscribe', 'agent_id': agentId});
    subscribedAgentId = agentId;
    notifyListeners();
  }

  Future<List<DeviceInfo>> scan({double duration = 5.0}) async {
    final r = await _request({
      'type': 'scan',
      'params': {'duration': duration},
    }, timeout: Duration(seconds: (duration + 5).toInt()));
    return (r['devices'] as List? ?? [])
        .map((e) => DeviceInfo.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<bool> connectDevice(String address, String name,
      {String deviceType = 'toy'}) async {
    final r = await _request({
      'type': 'connect',
      'params': {'address': address, 'name': name, 'device_type': deviceType},
    });
    if (r['ok'] == true) {
      connectedDeviceAddress = address;
      notifyListeners();
    }
    return r['ok'] == true;
  }

  Future<bool> disconnectDevice(String address) async {
    final r = await _request({
      'type': 'disconnect',
      'params': {'address': address},
    });
    if (r['ok'] == true) {
      connectedDeviceAddress = null;
      notifyListeners();
    }
    return r['ok'] == true;
  }

  Future<void> setSpeed(
      String address, int motorA, int motorB, int motorC) async {
    motorSpeeds['A'] = motorA;
    motorSpeeds['B'] = motorB;
    motorSpeeds['C'] = motorC;
    notifyListeners();
    await _request({
      'type': 'command',
      'params': {
        'address': address,
        'action':  'set_speed',
        'data':    {'motor_a': motorA, 'motor_b': motorB, 'motor_c': motorC},
      },
    });
  }

  Future<void> setMode(String address, String motors, int mode) async {
    for (final m in motors.toUpperCase().split('')) {
      if (motorModes.containsKey(m)) motorModes[m] = mode;
    }
    notifyListeners();
    await _request({
      'type': 'command',
      'params': {
        'address': address,
        'action':  'set_mode',
        'data':    {'motors': motors, 'mode': mode},
      },
    });
  }

  Future<void> stop(String address) async {
    motorSpeeds.updateAll((_, __) => 0);
    notifyListeners();
    await _request({
      'type': 'command',
      'params': {'address': address, 'action': 'stop', 'data': {}},
    });
  }

  Future<List<DeviceInfo>> listDevices() async {
    final r = await _request({'type': 'list_devices', 'params': {}});
    return (r['devices'] as List? ?? [])
        .map((e) => DeviceInfo.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ── Internals ─────────────────────────────────────────────────────────────

  void _onMessage(String raw) {
    final Map<String, dynamic> msg;
    try {
      msg = json.decode(raw) as Map<String, dynamic>;
    } catch (_) {
      return;
    }

    // hello response (auth)
    if (msg['type'] == 'hello') {
      _pending.remove('__hello__')?.complete(msg);
      return;
    }

    // unsolicited error (e.g. agent disconnected)
    if (msg['type'] == 'error' && msg['id'] == null) {
      debugPrint('[yokonex] server error: ${msg['message']}');
      lastEvent = msg;
      notifyListeners();
      return;
    }

    // device event
    if (msg['type'] == 'event') {
      _handleDeviceEvent(msg);
      return;
    }

    // response to a pending request
    final id = msg['id'] as String?;
    if (id != null) {
      _pending.remove(id)?.complete(msg);
    }
  }

  void _handleDeviceEvent(Map<String, dynamic> msg) {
    lastEvent = msg;
    final event = msg['event'] as String?;
    final data  = msg['data'] as Map<String, dynamic>? ?? {};

    if (event == 'disconnected' &&
        msg['address'] == connectedDeviceAddress) {
      connectedDeviceAddress = null;
    }
    if (event == 'device_info') {
      // motor info available — no UI state change needed here
    }
    notifyListeners();
  }

  void _onClosed() {
    _channel = null;
    _pending.forEach((_, c) => c.completeError('connection closed'));
    _pending.clear();
    notifyListeners();
  }

  Future<Map<String, dynamic>> _request(
    Map<String, dynamic> payload, {
    Duration timeout = const Duration(seconds: 30),
  }) async {
    if (_channel == null) throw StateError('Not connected');
    final id = 'req-${++_reqCounter}';
    final completer = Completer<Map<String, dynamic>>();
    _pending[id] = completer;
    _send({'id': id, ...payload});
    return completer.future.timeout(timeout, onTimeout: () {
      _pending.remove(id);
      throw TimeoutException('Request timeout: ${payload['type']}');
    });
  }

  void _send(Map<String, dynamic> data) {
    _channel?.sink.add(json.encode(data));
  }
}
