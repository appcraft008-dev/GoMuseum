import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

/// 语音问答服务
class VoiceQaService {
  final Dio _dio;
  final stt.SpeechToText _speech = stt.SpeechToText();

  bool _isInitialized = false;
  bool get isInitialized => _isInitialized;

  bool _isListening = false;
  bool get isListening => _isListening;

  VoiceQaService({required Dio dio}) : _dio = dio;

  /// 初始化语音识别
  Future<bool> initialize() async {
    if (_isInitialized) return true;

    try {
      // 请求麦克风权限
      final status = await Permission.microphone.request();
      if (!status.isGranted) {
        debugPrint('麦克风权限未授予');
        return false;
      }

      // 初始化语音识别
      _isInitialized = await _speech.initialize(
        onError: (error) => debugPrint('语音识别错误: $error'),
        onStatus: (status) => debugPrint('语音识别状态: $status'),
      );

      return _isInitialized;
    } catch (e) {
      debugPrint('语音识别初始化失败: $e');
      return false;
    }
  }

  /// 开始监听
  ///
  /// [onResult] - 识别结果回调
  /// [onComplete] - 完成回调
  Future<void> startListening({
    required Function(String) onResult,
    Function()? onComplete,
  }) async {
    if (!_isInitialized) {
      final initialized = await initialize();
      if (!initialized) {
        throw Exception('语音识别未初始化');
      }
    }

    _isListening = true;

    await _speech.listen(
      onResult: (result) {
        if (result.finalResult) {
          onResult(result.recognizedWords);
          _isListening = false;
          onComplete?.call();
        }
      },
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
      partialResults: false,
      cancelOnError: true,
    );
  }

  /// 停止监听
  Future<void> stopListening() async {
    if (_isListening) {
      await _speech.stop();
      _isListening = false;
    }
  }

  /// 发送问题到AI服务
  ///
  /// [question] - 用户问题
  /// [artworkId] - 艺术品ID
  /// [context] - 上下文信息
  Future<String> askQuestion({
    required String question,
    String? artworkId,
    String? context,
  }) async {
    try {
      final response = await _dio.post(
        '/api/v1/chat/ask',
        data: {
          'question': question,
          if (artworkId != null) 'artwork_id': artworkId,
          if (context != null) 'context': context,
        },
        options: Options(
          sendTimeout: const Duration(seconds: 30),
          receiveTimeout: const Duration(seconds: 30),
        ),
      );

      if (response.statusCode == 200) {
        return response.data['answer'] as String? ?? '抱歉，无法生成回答';
      } else {
        throw Exception('服务器返回错误: ${response.statusCode}');
      }
    } on DioException catch (e) {
      debugPrint('AI问答请求失败: $e');
      rethrow;
    }
  }

  /// 语音问答（语音输入 + AI回答）
  ///
  /// [artworkId] - 艺术品ID
  /// [context] - 上下文
  /// [onListening] - 开始监听回调
  /// [onProcessing] - 处理中回调
  /// [onAnswer] - 获得答案回调
  /// [onError] - 错误回调
  Future<void> voiceAskQuestion({
    String? artworkId,
    String? context,
    Function()? onListening,
    Function()? onProcessing,
    required Function(String) onAnswer,
    Function(String)? onError,
  }) async {
    try {
      // 1. 开始监听
      onListening?.call();

      await startListening(
        onResult: (recognizedText) async {
          debugPrint('识别到的文字: $recognizedText');

          // 2. 处理中
          onProcessing?.call();

          try {
            // 3. 发送到AI服务
            final answer = await askQuestion(
              question: recognizedText,
              artworkId: artworkId,
              context: context,
            );

            // 4. 返回答案
            onAnswer(answer);
          } catch (e) {
            onError?.call('AI回答失败: $e');
          }
        },
        onComplete: () {
          debugPrint('语音识别完成');
        },
      );
    } catch (e) {
      onError?.call('语音识别失败: $e');
    }
  }

  /// 取消当前问答
  Future<void> cancel() async {
    await stopListening();
  }

  /// 释放资源
  Future<void> dispose() async {
    await stopListening();
  }
}
