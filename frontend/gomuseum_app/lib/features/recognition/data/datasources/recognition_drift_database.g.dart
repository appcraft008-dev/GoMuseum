// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'recognition_drift_database.dart';

// ignore_for_file: type=lint
class $RecognitionResultsTable extends RecognitionResults
    with TableInfo<$RecognitionResultsTable, RecognitionResultData> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $RecognitionResultsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _imageHashMeta =
      const VerificationMeta('imageHash');
  @override
  late final GeneratedColumn<String> imageHash = GeneratedColumn<String>(
      'image_hash', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
      'id', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _artworkNameMeta =
      const VerificationMeta('artworkName');
  @override
  late final GeneratedColumn<String> artworkName = GeneratedColumn<String>(
      'artwork_name', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _artistMeta = const VerificationMeta('artist');
  @override
  late final GeneratedColumn<String> artist = GeneratedColumn<String>(
      'artist', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _periodMeta = const VerificationMeta('period');
  @override
  late final GeneratedColumn<String> period = GeneratedColumn<String>(
      'period', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _descriptionMeta =
      const VerificationMeta('description');
  @override
  late final GeneratedColumn<String> description = GeneratedColumn<String>(
      'description', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _confidenceMeta =
      const VerificationMeta('confidence');
  @override
  late final GeneratedColumn<double> confidence = GeneratedColumn<double>(
      'confidence', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _timestampMeta =
      const VerificationMeta('timestamp');
  @override
  late final GeneratedColumn<DateTime> timestamp = GeneratedColumn<DateTime>(
      'timestamp', aliasedName, false,
      type: DriftSqlType.dateTime, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns => [
        imageHash,
        id,
        artworkName,
        artist,
        period,
        description,
        confidence,
        timestamp
      ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'recognition_results';
  @override
  VerificationContext validateIntegrity(
      Insertable<RecognitionResultData> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('image_hash')) {
      context.handle(_imageHashMeta,
          imageHash.isAcceptableOrUnknown(data['image_hash']!, _imageHashMeta));
    } else if (isInserting) {
      context.missing(_imageHashMeta);
    }
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('artwork_name')) {
      context.handle(
          _artworkNameMeta,
          artworkName.isAcceptableOrUnknown(
              data['artwork_name']!, _artworkNameMeta));
    } else if (isInserting) {
      context.missing(_artworkNameMeta);
    }
    if (data.containsKey('artist')) {
      context.handle(_artistMeta,
          artist.isAcceptableOrUnknown(data['artist']!, _artistMeta));
    } else if (isInserting) {
      context.missing(_artistMeta);
    }
    if (data.containsKey('period')) {
      context.handle(_periodMeta,
          period.isAcceptableOrUnknown(data['period']!, _periodMeta));
    } else if (isInserting) {
      context.missing(_periodMeta);
    }
    if (data.containsKey('description')) {
      context.handle(
          _descriptionMeta,
          description.isAcceptableOrUnknown(
              data['description']!, _descriptionMeta));
    } else if (isInserting) {
      context.missing(_descriptionMeta);
    }
    if (data.containsKey('confidence')) {
      context.handle(
          _confidenceMeta,
          confidence.isAcceptableOrUnknown(
              data['confidence']!, _confidenceMeta));
    } else if (isInserting) {
      context.missing(_confidenceMeta);
    }
    if (data.containsKey('timestamp')) {
      context.handle(_timestampMeta,
          timestamp.isAcceptableOrUnknown(data['timestamp']!, _timestampMeta));
    } else if (isInserting) {
      context.missing(_timestampMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {imageHash};
  @override
  RecognitionResultData map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return RecognitionResultData(
      imageHash: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}image_hash'])!,
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}id'])!,
      artworkName: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}artwork_name'])!,
      artist: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}artist'])!,
      period: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}period'])!,
      description: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}description'])!,
      confidence: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}confidence'])!,
      timestamp: attachedDatabase.typeMapping
          .read(DriftSqlType.dateTime, data['${effectivePrefix}timestamp'])!,
    );
  }

  @override
  $RecognitionResultsTable createAlias(String alias) {
    return $RecognitionResultsTable(attachedDatabase, alias);
  }
}

class RecognitionResultData extends DataClass
    implements Insertable<RecognitionResultData> {
  final String imageHash;
  final String id;
  final String artworkName;
  final String artist;
  final String period;
  final String description;
  final double confidence;
  final DateTime timestamp;
  const RecognitionResultData(
      {required this.imageHash,
      required this.id,
      required this.artworkName,
      required this.artist,
      required this.period,
      required this.description,
      required this.confidence,
      required this.timestamp});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['image_hash'] = Variable<String>(imageHash);
    map['id'] = Variable<String>(id);
    map['artwork_name'] = Variable<String>(artworkName);
    map['artist'] = Variable<String>(artist);
    map['period'] = Variable<String>(period);
    map['description'] = Variable<String>(description);
    map['confidence'] = Variable<double>(confidence);
    map['timestamp'] = Variable<DateTime>(timestamp);
    return map;
  }

  RecognitionResultsCompanion toCompanion(bool nullToAbsent) {
    return RecognitionResultsCompanion(
      imageHash: Value(imageHash),
      id: Value(id),
      artworkName: Value(artworkName),
      artist: Value(artist),
      period: Value(period),
      description: Value(description),
      confidence: Value(confidence),
      timestamp: Value(timestamp),
    );
  }

  factory RecognitionResultData.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return RecognitionResultData(
      imageHash: serializer.fromJson<String>(json['imageHash']),
      id: serializer.fromJson<String>(json['id']),
      artworkName: serializer.fromJson<String>(json['artworkName']),
      artist: serializer.fromJson<String>(json['artist']),
      period: serializer.fromJson<String>(json['period']),
      description: serializer.fromJson<String>(json['description']),
      confidence: serializer.fromJson<double>(json['confidence']),
      timestamp: serializer.fromJson<DateTime>(json['timestamp']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'imageHash': serializer.toJson<String>(imageHash),
      'id': serializer.toJson<String>(id),
      'artworkName': serializer.toJson<String>(artworkName),
      'artist': serializer.toJson<String>(artist),
      'period': serializer.toJson<String>(period),
      'description': serializer.toJson<String>(description),
      'confidence': serializer.toJson<double>(confidence),
      'timestamp': serializer.toJson<DateTime>(timestamp),
    };
  }

  RecognitionResultData copyWith(
          {String? imageHash,
          String? id,
          String? artworkName,
          String? artist,
          String? period,
          String? description,
          double? confidence,
          DateTime? timestamp}) =>
      RecognitionResultData(
        imageHash: imageHash ?? this.imageHash,
        id: id ?? this.id,
        artworkName: artworkName ?? this.artworkName,
        artist: artist ?? this.artist,
        period: period ?? this.period,
        description: description ?? this.description,
        confidence: confidence ?? this.confidence,
        timestamp: timestamp ?? this.timestamp,
      );
  RecognitionResultData copyWithCompanion(RecognitionResultsCompanion data) {
    return RecognitionResultData(
      imageHash: data.imageHash.present ? data.imageHash.value : this.imageHash,
      id: data.id.present ? data.id.value : this.id,
      artworkName:
          data.artworkName.present ? data.artworkName.value : this.artworkName,
      artist: data.artist.present ? data.artist.value : this.artist,
      period: data.period.present ? data.period.value : this.period,
      description:
          data.description.present ? data.description.value : this.description,
      confidence:
          data.confidence.present ? data.confidence.value : this.confidence,
      timestamp: data.timestamp.present ? data.timestamp.value : this.timestamp,
    );
  }

  @override
  String toString() {
    return (StringBuffer('RecognitionResultData(')
          ..write('imageHash: $imageHash, ')
          ..write('id: $id, ')
          ..write('artworkName: $artworkName, ')
          ..write('artist: $artist, ')
          ..write('period: $period, ')
          ..write('description: $description, ')
          ..write('confidence: $confidence, ')
          ..write('timestamp: $timestamp')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(imageHash, id, artworkName, artist, period,
      description, confidence, timestamp);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is RecognitionResultData &&
          other.imageHash == this.imageHash &&
          other.id == this.id &&
          other.artworkName == this.artworkName &&
          other.artist == this.artist &&
          other.period == this.period &&
          other.description == this.description &&
          other.confidence == this.confidence &&
          other.timestamp == this.timestamp);
}

class RecognitionResultsCompanion
    extends UpdateCompanion<RecognitionResultData> {
  final Value<String> imageHash;
  final Value<String> id;
  final Value<String> artworkName;
  final Value<String> artist;
  final Value<String> period;
  final Value<String> description;
  final Value<double> confidence;
  final Value<DateTime> timestamp;
  final Value<int> rowid;
  const RecognitionResultsCompanion({
    this.imageHash = const Value.absent(),
    this.id = const Value.absent(),
    this.artworkName = const Value.absent(),
    this.artist = const Value.absent(),
    this.period = const Value.absent(),
    this.description = const Value.absent(),
    this.confidence = const Value.absent(),
    this.timestamp = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  RecognitionResultsCompanion.insert({
    required String imageHash,
    required String id,
    required String artworkName,
    required String artist,
    required String period,
    required String description,
    required double confidence,
    required DateTime timestamp,
    this.rowid = const Value.absent(),
  })  : imageHash = Value(imageHash),
        id = Value(id),
        artworkName = Value(artworkName),
        artist = Value(artist),
        period = Value(period),
        description = Value(description),
        confidence = Value(confidence),
        timestamp = Value(timestamp);
  static Insertable<RecognitionResultData> custom({
    Expression<String>? imageHash,
    Expression<String>? id,
    Expression<String>? artworkName,
    Expression<String>? artist,
    Expression<String>? period,
    Expression<String>? description,
    Expression<double>? confidence,
    Expression<DateTime>? timestamp,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (imageHash != null) 'image_hash': imageHash,
      if (id != null) 'id': id,
      if (artworkName != null) 'artwork_name': artworkName,
      if (artist != null) 'artist': artist,
      if (period != null) 'period': period,
      if (description != null) 'description': description,
      if (confidence != null) 'confidence': confidence,
      if (timestamp != null) 'timestamp': timestamp,
      if (rowid != null) 'rowid': rowid,
    });
  }

  RecognitionResultsCompanion copyWith(
      {Value<String>? imageHash,
      Value<String>? id,
      Value<String>? artworkName,
      Value<String>? artist,
      Value<String>? period,
      Value<String>? description,
      Value<double>? confidence,
      Value<DateTime>? timestamp,
      Value<int>? rowid}) {
    return RecognitionResultsCompanion(
      imageHash: imageHash ?? this.imageHash,
      id: id ?? this.id,
      artworkName: artworkName ?? this.artworkName,
      artist: artist ?? this.artist,
      period: period ?? this.period,
      description: description ?? this.description,
      confidence: confidence ?? this.confidence,
      timestamp: timestamp ?? this.timestamp,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (imageHash.present) {
      map['image_hash'] = Variable<String>(imageHash.value);
    }
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (artworkName.present) {
      map['artwork_name'] = Variable<String>(artworkName.value);
    }
    if (artist.present) {
      map['artist'] = Variable<String>(artist.value);
    }
    if (period.present) {
      map['period'] = Variable<String>(period.value);
    }
    if (description.present) {
      map['description'] = Variable<String>(description.value);
    }
    if (confidence.present) {
      map['confidence'] = Variable<double>(confidence.value);
    }
    if (timestamp.present) {
      map['timestamp'] = Variable<DateTime>(timestamp.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('RecognitionResultsCompanion(')
          ..write('imageHash: $imageHash, ')
          ..write('id: $id, ')
          ..write('artworkName: $artworkName, ')
          ..write('artist: $artist, ')
          ..write('period: $period, ')
          ..write('description: $description, ')
          ..write('confidence: $confidence, ')
          ..write('timestamp: $timestamp, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$AppDatabase extends GeneratedDatabase {
  _$AppDatabase(QueryExecutor e) : super(e);
  $AppDatabaseManager get managers => $AppDatabaseManager(this);
  late final $RecognitionResultsTable recognitionResults =
      $RecognitionResultsTable(this);
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [recognitionResults];
}

typedef $$RecognitionResultsTableCreateCompanionBuilder
    = RecognitionResultsCompanion Function({
  required String imageHash,
  required String id,
  required String artworkName,
  required String artist,
  required String period,
  required String description,
  required double confidence,
  required DateTime timestamp,
  Value<int> rowid,
});
typedef $$RecognitionResultsTableUpdateCompanionBuilder
    = RecognitionResultsCompanion Function({
  Value<String> imageHash,
  Value<String> id,
  Value<String> artworkName,
  Value<String> artist,
  Value<String> period,
  Value<String> description,
  Value<double> confidence,
  Value<DateTime> timestamp,
  Value<int> rowid,
});

class $$RecognitionResultsTableFilterComposer
    extends Composer<_$AppDatabase, $RecognitionResultsTable> {
  $$RecognitionResultsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get imageHash => $composableBuilder(
      column: $table.imageHash, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get artworkName => $composableBuilder(
      column: $table.artworkName, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get artist => $composableBuilder(
      column: $table.artist, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get period => $composableBuilder(
      column: $table.period, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get description => $composableBuilder(
      column: $table.description, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get confidence => $composableBuilder(
      column: $table.confidence, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get timestamp => $composableBuilder(
      column: $table.timestamp, builder: (column) => ColumnFilters(column));
}

class $$RecognitionResultsTableOrderingComposer
    extends Composer<_$AppDatabase, $RecognitionResultsTable> {
  $$RecognitionResultsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get imageHash => $composableBuilder(
      column: $table.imageHash, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get artworkName => $composableBuilder(
      column: $table.artworkName, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get artist => $composableBuilder(
      column: $table.artist, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get period => $composableBuilder(
      column: $table.period, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get description => $composableBuilder(
      column: $table.description, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get confidence => $composableBuilder(
      column: $table.confidence, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get timestamp => $composableBuilder(
      column: $table.timestamp, builder: (column) => ColumnOrderings(column));
}

class $$RecognitionResultsTableAnnotationComposer
    extends Composer<_$AppDatabase, $RecognitionResultsTable> {
  $$RecognitionResultsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get imageHash =>
      $composableBuilder(column: $table.imageHash, builder: (column) => column);

  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get artworkName => $composableBuilder(
      column: $table.artworkName, builder: (column) => column);

  GeneratedColumn<String> get artist =>
      $composableBuilder(column: $table.artist, builder: (column) => column);

  GeneratedColumn<String> get period =>
      $composableBuilder(column: $table.period, builder: (column) => column);

  GeneratedColumn<String> get description => $composableBuilder(
      column: $table.description, builder: (column) => column);

  GeneratedColumn<double> get confidence => $composableBuilder(
      column: $table.confidence, builder: (column) => column);

  GeneratedColumn<DateTime> get timestamp =>
      $composableBuilder(column: $table.timestamp, builder: (column) => column);
}

class $$RecognitionResultsTableTableManager extends RootTableManager<
    _$AppDatabase,
    $RecognitionResultsTable,
    RecognitionResultData,
    $$RecognitionResultsTableFilterComposer,
    $$RecognitionResultsTableOrderingComposer,
    $$RecognitionResultsTableAnnotationComposer,
    $$RecognitionResultsTableCreateCompanionBuilder,
    $$RecognitionResultsTableUpdateCompanionBuilder,
    (
      RecognitionResultData,
      BaseReferences<_$AppDatabase, $RecognitionResultsTable,
          RecognitionResultData>
    ),
    RecognitionResultData,
    PrefetchHooks Function()> {
  $$RecognitionResultsTableTableManager(
      _$AppDatabase db, $RecognitionResultsTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$RecognitionResultsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$RecognitionResultsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$RecognitionResultsTableAnnotationComposer(
                  $db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> imageHash = const Value.absent(),
            Value<String> id = const Value.absent(),
            Value<String> artworkName = const Value.absent(),
            Value<String> artist = const Value.absent(),
            Value<String> period = const Value.absent(),
            Value<String> description = const Value.absent(),
            Value<double> confidence = const Value.absent(),
            Value<DateTime> timestamp = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              RecognitionResultsCompanion(
            imageHash: imageHash,
            id: id,
            artworkName: artworkName,
            artist: artist,
            period: period,
            description: description,
            confidence: confidence,
            timestamp: timestamp,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String imageHash,
            required String id,
            required String artworkName,
            required String artist,
            required String period,
            required String description,
            required double confidence,
            required DateTime timestamp,
            Value<int> rowid = const Value.absent(),
          }) =>
              RecognitionResultsCompanion.insert(
            imageHash: imageHash,
            id: id,
            artworkName: artworkName,
            artist: artist,
            period: period,
            description: description,
            confidence: confidence,
            timestamp: timestamp,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ));
}

typedef $$RecognitionResultsTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $RecognitionResultsTable,
    RecognitionResultData,
    $$RecognitionResultsTableFilterComposer,
    $$RecognitionResultsTableOrderingComposer,
    $$RecognitionResultsTableAnnotationComposer,
    $$RecognitionResultsTableCreateCompanionBuilder,
    $$RecognitionResultsTableUpdateCompanionBuilder,
    (
      RecognitionResultData,
      BaseReferences<_$AppDatabase, $RecognitionResultsTable,
          RecognitionResultData>
    ),
    RecognitionResultData,
    PrefetchHooks Function()>;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$RecognitionResultsTableTableManager get recognitionResults =>
      $$RecognitionResultsTableTableManager(_db, _db.recognitionResults);
}
