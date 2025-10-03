import 'dart:io';
import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

part 'recognition_drift_database.g.dart';

/// 识别结果表定义
@DataClassName('RecognitionResultData')
class RecognitionResults extends Table {
  TextColumn get imageHash => text()();
  TextColumn get id => text()();
  TextColumn get artworkName => text()();
  TextColumn get artist => text()();
  TextColumn get period => text()();
  TextColumn get description => text()();
  RealColumn get confidence => real()();
  DateTimeColumn get timestamp => dateTime()();

  @override
  Set<Column> get primaryKey => {imageHash};
}

/// Drift数据库
@DriftDatabase(tables: [RecognitionResults])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 1;

  /// 根据imageHash查询识别结果
  Future<RecognitionResultData?> getRecognitionByHash(String imageHash) async {
    return (select(recognitionResults)
          ..where((t) => t.imageHash.equals(imageHash)))
        .getSingleOrNull();
  }

  /// 插入或更新识别结果
  Future<void> insertOrUpdateRecognition(
      RecognitionResultsCompanion data) async {
    await into(recognitionResults).insertOnConflictUpdate(data);
  }

  /// 删除所有识别结果
  Future<void> deleteAllRecognitions() async {
    await delete(recognitionResults).go();
  }
}

/// 打开数据库连接
LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'gomuseum.db'));
    return NativeDatabase(file);
  });
}
