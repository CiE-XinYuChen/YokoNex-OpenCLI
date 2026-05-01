import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'api/yokonex_client.dart';
import 'screens/connect_screen.dart';
import 'screens/agent_screen.dart';
import 'screens/scan_screen.dart';
import 'screens/control_screen.dart';

void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => YokoNexClient(),
      child: const YokoNexApp(),
    ),
  );
}

class YokoNexApp extends StatelessWidget {
  const YokoNexApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'YokoNex',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6750A4)),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6750A4),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      themeMode: ThemeMode.system,
      routerConfig: _router,
    );
  }
}

final _router = GoRouter(
  initialLocation: '/connect',
  routes: [
    GoRoute(path: '/connect',  builder: (_, __) => const ConnectScreen()),
    GoRoute(path: '/agents',   builder: (_, __) => const AgentScreen()),
    GoRoute(path: '/scan',     builder: (_, __) => const ScanScreen()),
    GoRoute(path: '/control',  builder: (_, __) => const ControlScreen()),
  ],
);
