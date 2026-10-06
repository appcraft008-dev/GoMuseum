import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';

void main() {
  test('RecognizedItem reads image + credit', () {
    final c = RecognizedItem.fromJson(const {
      'qid': 'Q1',
      'museum': 'orsay',
      'thumbnail': 't.jpg',
      'image': 'L.jpg',
      'credit': 'Studio X',
    });
    expect(c.image, 'L.jpg');
    expect(c.credit, 'Studio X');
  });

  test('RecognizedItem falls back to thumbnail when image missing (old cache)',
      () {
    final c = RecognizedItem.fromJson(
        const {'qid': 'Q1', 'museum': 'orsay', 'thumbnail': 't.jpg'});
    expect(c.image, 't.jpg');
    expect(c.credit, isNull);
  });
}
