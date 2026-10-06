import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/search/data/search_api.dart';

void main() {
  test('SearchObject reads inventory, tolerates absence', () {
    expect(
        SearchObject.fromJson(const {'qid': 'Q1', 'inventory': 'INV 779'})
            .inventory,
        'INV 779');
    expect(SearchObject.fromJson(const {'qid': 'Q1'}).inventory, isNull);
  });
}
