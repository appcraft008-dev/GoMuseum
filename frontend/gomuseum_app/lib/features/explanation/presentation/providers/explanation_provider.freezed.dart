// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'explanation_provider.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

T _$identity<T>(T value) => value;

final _privateConstructorUsedError = UnsupportedError(
    'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models');

/// @nodoc
mixin _$ExplanationState {
  @optionalTypeArgs
  TResult when<TResult extends Object?>({
    required TResult Function() initial,
    required TResult Function() loading,
    required TResult Function(Explanation explanation) success,
    required TResult Function(String message) error,
  }) =>
      throw _privateConstructorUsedError;
  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>({
    TResult? Function()? initial,
    TResult? Function()? loading,
    TResult? Function(Explanation explanation)? success,
    TResult? Function(String message)? error,
  }) =>
      throw _privateConstructorUsedError;
  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>({
    TResult Function()? initial,
    TResult Function()? loading,
    TResult Function(Explanation explanation)? success,
    TResult Function(String message)? error,
    required TResult orElse(),
  }) =>
      throw _privateConstructorUsedError;
  @optionalTypeArgs
  TResult map<TResult extends Object?>({
    required TResult Function(ExplanationInitial value) initial,
    required TResult Function(ExplanationLoading value) loading,
    required TResult Function(ExplanationSuccess value) success,
    required TResult Function(ExplanationError value) error,
  }) =>
      throw _privateConstructorUsedError;
  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>({
    TResult? Function(ExplanationInitial value)? initial,
    TResult? Function(ExplanationLoading value)? loading,
    TResult? Function(ExplanationSuccess value)? success,
    TResult? Function(ExplanationError value)? error,
  }) =>
      throw _privateConstructorUsedError;
  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>({
    TResult Function(ExplanationInitial value)? initial,
    TResult Function(ExplanationLoading value)? loading,
    TResult Function(ExplanationSuccess value)? success,
    TResult Function(ExplanationError value)? error,
    required TResult orElse(),
  }) =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $ExplanationStateCopyWith<$Res> {
  factory $ExplanationStateCopyWith(
          ExplanationState value, $Res Function(ExplanationState) then) =
      _$ExplanationStateCopyWithImpl<$Res, ExplanationState>;
}

/// @nodoc
class _$ExplanationStateCopyWithImpl<$Res, $Val extends ExplanationState>
    implements $ExplanationStateCopyWith<$Res> {
  _$ExplanationStateCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of ExplanationState
  /// with the given fields replaced by the non-null parameter values.
}

/// @nodoc
abstract class _$$ExplanationInitialImplCopyWith<$Res> {
  factory _$$ExplanationInitialImplCopyWith(_$ExplanationInitialImpl value,
          $Res Function(_$ExplanationInitialImpl) then) =
      __$$ExplanationInitialImplCopyWithImpl<$Res>;
}

/// @nodoc
class __$$ExplanationInitialImplCopyWithImpl<$Res>
    extends _$ExplanationStateCopyWithImpl<$Res, _$ExplanationInitialImpl>
    implements _$$ExplanationInitialImplCopyWith<$Res> {
  __$$ExplanationInitialImplCopyWithImpl(_$ExplanationInitialImpl _value,
      $Res Function(_$ExplanationInitialImpl) _then)
      : super(_value, _then);

  /// Create a copy of ExplanationState
  /// with the given fields replaced by the non-null parameter values.
}

/// @nodoc

class _$ExplanationInitialImpl implements ExplanationInitial {
  const _$ExplanationInitialImpl();

  @override
  String toString() {
    return 'ExplanationState.initial()';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType && other is _$ExplanationInitialImpl);
  }

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  @optionalTypeArgs
  TResult when<TResult extends Object?>({
    required TResult Function() initial,
    required TResult Function() loading,
    required TResult Function(Explanation explanation) success,
    required TResult Function(String message) error,
  }) {
    return initial();
  }

  @override
  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>({
    TResult? Function()? initial,
    TResult? Function()? loading,
    TResult? Function(Explanation explanation)? success,
    TResult? Function(String message)? error,
  }) {
    return initial?.call();
  }

  @override
  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>({
    TResult Function()? initial,
    TResult Function()? loading,
    TResult Function(Explanation explanation)? success,
    TResult Function(String message)? error,
    required TResult orElse(),
  }) {
    if (initial != null) {
      return initial();
    }
    return orElse();
  }

  @override
  @optionalTypeArgs
  TResult map<TResult extends Object?>({
    required TResult Function(ExplanationInitial value) initial,
    required TResult Function(ExplanationLoading value) loading,
    required TResult Function(ExplanationSuccess value) success,
    required TResult Function(ExplanationError value) error,
  }) {
    return initial(this);
  }

  @override
  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>({
    TResult? Function(ExplanationInitial value)? initial,
    TResult? Function(ExplanationLoading value)? loading,
    TResult? Function(ExplanationSuccess value)? success,
    TResult? Function(ExplanationError value)? error,
  }) {
    return initial?.call(this);
  }

  @override
  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>({
    TResult Function(ExplanationInitial value)? initial,
    TResult Function(ExplanationLoading value)? loading,
    TResult Function(ExplanationSuccess value)? success,
    TResult Function(ExplanationError value)? error,
    required TResult orElse(),
  }) {
    if (initial != null) {
      return initial(this);
    }
    return orElse();
  }
}

abstract class ExplanationInitial implements ExplanationState {
  const factory ExplanationInitial() = _$ExplanationInitialImpl;
}

/// @nodoc
abstract class _$$ExplanationLoadingImplCopyWith<$Res> {
  factory _$$ExplanationLoadingImplCopyWith(_$ExplanationLoadingImpl value,
          $Res Function(_$ExplanationLoadingImpl) then) =
      __$$ExplanationLoadingImplCopyWithImpl<$Res>;
}

/// @nodoc
class __$$ExplanationLoadingImplCopyWithImpl<$Res>
    extends _$ExplanationStateCopyWithImpl<$Res, _$ExplanationLoadingImpl>
    implements _$$ExplanationLoadingImplCopyWith<$Res> {
  __$$ExplanationLoadingImplCopyWithImpl(_$ExplanationLoadingImpl _value,
      $Res Function(_$ExplanationLoadingImpl) _then)
      : super(_value, _then);

  /// Create a copy of ExplanationState
  /// with the given fields replaced by the non-null parameter values.
}

/// @nodoc

class _$ExplanationLoadingImpl implements ExplanationLoading {
  const _$ExplanationLoadingImpl();

  @override
  String toString() {
    return 'ExplanationState.loading()';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType && other is _$ExplanationLoadingImpl);
  }

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  @optionalTypeArgs
  TResult when<TResult extends Object?>({
    required TResult Function() initial,
    required TResult Function() loading,
    required TResult Function(Explanation explanation) success,
    required TResult Function(String message) error,
  }) {
    return loading();
  }

  @override
  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>({
    TResult? Function()? initial,
    TResult? Function()? loading,
    TResult? Function(Explanation explanation)? success,
    TResult? Function(String message)? error,
  }) {
    return loading?.call();
  }

  @override
  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>({
    TResult Function()? initial,
    TResult Function()? loading,
    TResult Function(Explanation explanation)? success,
    TResult Function(String message)? error,
    required TResult orElse(),
  }) {
    if (loading != null) {
      return loading();
    }
    return orElse();
  }

  @override
  @optionalTypeArgs
  TResult map<TResult extends Object?>({
    required TResult Function(ExplanationInitial value) initial,
    required TResult Function(ExplanationLoading value) loading,
    required TResult Function(ExplanationSuccess value) success,
    required TResult Function(ExplanationError value) error,
  }) {
    return loading(this);
  }

  @override
  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>({
    TResult? Function(ExplanationInitial value)? initial,
    TResult? Function(ExplanationLoading value)? loading,
    TResult? Function(ExplanationSuccess value)? success,
    TResult? Function(ExplanationError value)? error,
  }) {
    return loading?.call(this);
  }

  @override
  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>({
    TResult Function(ExplanationInitial value)? initial,
    TResult Function(ExplanationLoading value)? loading,
    TResult Function(ExplanationSuccess value)? success,
    TResult Function(ExplanationError value)? error,
    required TResult orElse(),
  }) {
    if (loading != null) {
      return loading(this);
    }
    return orElse();
  }
}

abstract class ExplanationLoading implements ExplanationState {
  const factory ExplanationLoading() = _$ExplanationLoadingImpl;
}

/// @nodoc
abstract class _$$ExplanationSuccessImplCopyWith<$Res> {
  factory _$$ExplanationSuccessImplCopyWith(_$ExplanationSuccessImpl value,
          $Res Function(_$ExplanationSuccessImpl) then) =
      __$$ExplanationSuccessImplCopyWithImpl<$Res>;
  @useResult
  $Res call({Explanation explanation});
}

/// @nodoc
class __$$ExplanationSuccessImplCopyWithImpl<$Res>
    extends _$ExplanationStateCopyWithImpl<$Res, _$ExplanationSuccessImpl>
    implements _$$ExplanationSuccessImplCopyWith<$Res> {
  __$$ExplanationSuccessImplCopyWithImpl(_$ExplanationSuccessImpl _value,
      $Res Function(_$ExplanationSuccessImpl) _then)
      : super(_value, _then);

  /// Create a copy of ExplanationState
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? explanation = null,
  }) {
    return _then(_$ExplanationSuccessImpl(
      null == explanation
          ? _value.explanation
          : explanation // ignore: cast_nullable_to_non_nullable
              as Explanation,
    ));
  }
}

/// @nodoc

class _$ExplanationSuccessImpl implements ExplanationSuccess {
  const _$ExplanationSuccessImpl(this.explanation);

  @override
  final Explanation explanation;

  @override
  String toString() {
    return 'ExplanationState.success(explanation: $explanation)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$ExplanationSuccessImpl &&
            (identical(other.explanation, explanation) ||
                other.explanation == explanation));
  }

  @override
  int get hashCode => Object.hash(runtimeType, explanation);

  /// Create a copy of ExplanationState
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$ExplanationSuccessImplCopyWith<_$ExplanationSuccessImpl> get copyWith =>
      __$$ExplanationSuccessImplCopyWithImpl<_$ExplanationSuccessImpl>(
          this, _$identity);

  @override
  @optionalTypeArgs
  TResult when<TResult extends Object?>({
    required TResult Function() initial,
    required TResult Function() loading,
    required TResult Function(Explanation explanation) success,
    required TResult Function(String message) error,
  }) {
    return success(explanation);
  }

  @override
  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>({
    TResult? Function()? initial,
    TResult? Function()? loading,
    TResult? Function(Explanation explanation)? success,
    TResult? Function(String message)? error,
  }) {
    return success?.call(explanation);
  }

  @override
  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>({
    TResult Function()? initial,
    TResult Function()? loading,
    TResult Function(Explanation explanation)? success,
    TResult Function(String message)? error,
    required TResult orElse(),
  }) {
    if (success != null) {
      return success(explanation);
    }
    return orElse();
  }

  @override
  @optionalTypeArgs
  TResult map<TResult extends Object?>({
    required TResult Function(ExplanationInitial value) initial,
    required TResult Function(ExplanationLoading value) loading,
    required TResult Function(ExplanationSuccess value) success,
    required TResult Function(ExplanationError value) error,
  }) {
    return success(this);
  }

  @override
  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>({
    TResult? Function(ExplanationInitial value)? initial,
    TResult? Function(ExplanationLoading value)? loading,
    TResult? Function(ExplanationSuccess value)? success,
    TResult? Function(ExplanationError value)? error,
  }) {
    return success?.call(this);
  }

  @override
  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>({
    TResult Function(ExplanationInitial value)? initial,
    TResult Function(ExplanationLoading value)? loading,
    TResult Function(ExplanationSuccess value)? success,
    TResult Function(ExplanationError value)? error,
    required TResult orElse(),
  }) {
    if (success != null) {
      return success(this);
    }
    return orElse();
  }
}

abstract class ExplanationSuccess implements ExplanationState {
  const factory ExplanationSuccess(final Explanation explanation) =
      _$ExplanationSuccessImpl;

  Explanation get explanation;

  /// Create a copy of ExplanationState
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$ExplanationSuccessImplCopyWith<_$ExplanationSuccessImpl> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class _$$ExplanationErrorImplCopyWith<$Res> {
  factory _$$ExplanationErrorImplCopyWith(_$ExplanationErrorImpl value,
          $Res Function(_$ExplanationErrorImpl) then) =
      __$$ExplanationErrorImplCopyWithImpl<$Res>;
  @useResult
  $Res call({String message});
}

/// @nodoc
class __$$ExplanationErrorImplCopyWithImpl<$Res>
    extends _$ExplanationStateCopyWithImpl<$Res, _$ExplanationErrorImpl>
    implements _$$ExplanationErrorImplCopyWith<$Res> {
  __$$ExplanationErrorImplCopyWithImpl(_$ExplanationErrorImpl _value,
      $Res Function(_$ExplanationErrorImpl) _then)
      : super(_value, _then);

  /// Create a copy of ExplanationState
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? message = null,
  }) {
    return _then(_$ExplanationErrorImpl(
      null == message
          ? _value.message
          : message // ignore: cast_nullable_to_non_nullable
              as String,
    ));
  }
}

/// @nodoc

class _$ExplanationErrorImpl implements ExplanationError {
  const _$ExplanationErrorImpl(this.message);

  @override
  final String message;

  @override
  String toString() {
    return 'ExplanationState.error(message: $message)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$ExplanationErrorImpl &&
            (identical(other.message, message) || other.message == message));
  }

  @override
  int get hashCode => Object.hash(runtimeType, message);

  /// Create a copy of ExplanationState
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$ExplanationErrorImplCopyWith<_$ExplanationErrorImpl> get copyWith =>
      __$$ExplanationErrorImplCopyWithImpl<_$ExplanationErrorImpl>(
          this, _$identity);

  @override
  @optionalTypeArgs
  TResult when<TResult extends Object?>({
    required TResult Function() initial,
    required TResult Function() loading,
    required TResult Function(Explanation explanation) success,
    required TResult Function(String message) error,
  }) {
    return error(message);
  }

  @override
  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>({
    TResult? Function()? initial,
    TResult? Function()? loading,
    TResult? Function(Explanation explanation)? success,
    TResult? Function(String message)? error,
  }) {
    return error?.call(message);
  }

  @override
  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>({
    TResult Function()? initial,
    TResult Function()? loading,
    TResult Function(Explanation explanation)? success,
    TResult Function(String message)? error,
    required TResult orElse(),
  }) {
    if (error != null) {
      return error(message);
    }
    return orElse();
  }

  @override
  @optionalTypeArgs
  TResult map<TResult extends Object?>({
    required TResult Function(ExplanationInitial value) initial,
    required TResult Function(ExplanationLoading value) loading,
    required TResult Function(ExplanationSuccess value) success,
    required TResult Function(ExplanationError value) error,
  }) {
    return error(this);
  }

  @override
  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>({
    TResult? Function(ExplanationInitial value)? initial,
    TResult? Function(ExplanationLoading value)? loading,
    TResult? Function(ExplanationSuccess value)? success,
    TResult? Function(ExplanationError value)? error,
  }) {
    return error?.call(this);
  }

  @override
  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>({
    TResult Function(ExplanationInitial value)? initial,
    TResult Function(ExplanationLoading value)? loading,
    TResult Function(ExplanationSuccess value)? success,
    TResult Function(ExplanationError value)? error,
    required TResult orElse(),
  }) {
    if (error != null) {
      return error(this);
    }
    return orElse();
  }
}

abstract class ExplanationError implements ExplanationState {
  const factory ExplanationError(final String message) = _$ExplanationErrorImpl;

  String get message;

  /// Create a copy of ExplanationState
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$ExplanationErrorImplCopyWith<_$ExplanationErrorImpl> get copyWith =>
      throw _privateConstructorUsedError;
}
