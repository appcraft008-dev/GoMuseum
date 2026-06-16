import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:gomuseum_app/features/content/data/datasources/content_remote_datasource.dart';

class MockDio extends Mock implements Dio {}

void main() {
  late MockDio dio;
  late ContentRemoteDataSourceImpl ds;

  setUp(() {
    dio = MockDio();
    ds = ContentRemoteDataSourceImpl(dio: dio);
  });

  test('section 模式解析 JSON 的 audio_url', () async {
    when(() => dio.post(
          any(),
          data: any(named: 'data'),
          options: any(named: 'options'),
        )).thenAnswer((_) async => Response(
          data: {'audio_url': 'https://cdn.test/x.mp3', 'cached': false},
          statusCode: 200,
          requestOptions: RequestOptions(path: '/api/v1/content/tts/generate'),
        ));

    final url = await ds.generateTtsAudio(
      text: 't',
      language: 'en',
      qid: 'Q1',
      sectionCode: 'overview',
    );

    expect(url, 'https://cdn.test/x.mp3');
  });
}
