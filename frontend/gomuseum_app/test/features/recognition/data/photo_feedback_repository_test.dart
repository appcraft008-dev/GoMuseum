import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/data/photo_feedback_repository.dart';
import 'package:mocktail/mocktail.dart';

class _Dio extends Mock implements Dio {}

void main() {
  setUpAll(() => registerFallbackValue(Options()));
  final img = XFile.fromData(Uint8List.fromList(const [1, 2, 3]),
      name: 'a.jpg', mimeType: 'image/jpeg');

  test('posts multipart with trigger/phash/answer to the photo endpoint',
      () async {
    final dio = _Dio();
    when(() => dio.post(any(), data: any(named: 'data'))).thenAnswer(
        (_) async => Response(
            requestOptions: RequestOptions(path: ''), statusCode: 204));
    await PhotoFeedbackRepository(dio).send(
        image: img, trigger: 'found', phash: 'ph', answerQid: 'Q1', text: 'x');
    final cap =
        verify(() => dio.post(captureAny(), data: captureAny(named: 'data')))
            .captured;
    expect(cap[0], '/api/v1/feedback/recognition-photo');
    final form = cap[1] as FormData;
    final fields = Map.fromEntries(form.fields);
    expect(fields['trigger'], 'found');
    expect(fields['phash'], 'ph');
    expect(fields['answer_qid'], 'Q1');
    expect(form.files.single.key, 'image');
  });

  test('upload retries once then gives up silently', () async {
    final dio = _Dio();
    when(() => dio.post(any(), data: any(named: 'data')))
        .thenThrow(DioException(requestOptions: RequestOptions(path: '')));
    await PhotoFeedbackRepository(dio, retryDelay: Duration.zero)
        .send(image: img, trigger: 'not_found', phash: 'ph');
    verify(() => dio.post(any(), data: any(named: 'data'))).called(2);
  });
}
