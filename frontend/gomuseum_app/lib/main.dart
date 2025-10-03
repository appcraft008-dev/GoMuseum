import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'features/recognition/presentation/pages/recognition_page.dart';

void main() {
  runApp(const ProviderScope(child: GoMuseumApp()));
}

class GoMuseumApp extends StatelessWidget {
  const GoMuseumApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GoMuseum',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        useMaterial3: true,
      ),
      home: const RecognitionPage(), // 🚀 进入识别主界面
    );
  }
}

