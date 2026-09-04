/// **「连不上服务器」不等于「没登录」。**
///
/// 真机反馈(2026-09-04):飞行模式下冷启动直接落在登录页 —— `getCurrentUser`
/// 把所有异常都吞成 null,路由据此判定未登录。令牌其实好好地存着。
/// 对一个馆内常常没信号的导览 App,用户会把登录页读成"我被登出了",
/// 进而担心刚买的通票、甚至重新购买。
library;

import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';

const _userJson = {
  'id': 'u-1',
  'email': 'someone@example.com',
  'username': 'Someone',
  'is_active': true,
  'is_verified': true,
  'created_at': '2026-01-01T00:00:00Z',
};

/// 一个只会以指定方式失败的 Dio。
Dio _failingDio(DioException Function(RequestOptions o) make) => Dio()
  ..interceptors.add(InterceptorsWrapper(
    onRequest: (o, h) => h.reject(make(o)),
  ));

DioException _offline(RequestOptions o) =>
    DioException.connectionError(requestOptions: o, reason: 'airplane mode');

DioException _status(RequestOptions o, int code) => DioException.badResponse(
      statusCode: code,
      requestOptions: o,
      response: Response<dynamic>(requestOptions: o, statusCode: code),
    );

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({
      'access_token': 'tok',
      'user_profile': jsonEncode(_userJson),
    });
  });

  test('断网时保住上次的身份,不把人当成登出', () async {
    final repo = AuthRepository(_failingDio(_offline));
    final user = await repo.getCurrentUser();

    expect(user, isNotNull, reason: '返回 null 会让路由把人踢到登录页');
    expect(user!.id, 'u-1');
  });

  test('5xx 也保住身份 —— 服务端坏了不代表令牌失效', () async {
    final repo = AuthRepository(_failingDio((o) => _status(o, 500)));
    expect((await repo.getCurrentUser())?.id, 'u-1');
  });

  test('401 才真的按未登录处理', () async {
    final repo = AuthRepository(_failingDio((o) => _status(o, 401)));
    expect(await repo.getCurrentUser(), isNull,
        reason: '服务器明确不认这个令牌(刷新也已失败),这时候留着身份才是错的');
  });

  test('没有缓存过身份时,断网仍是未登录 —— 不凭空编一个用户', () async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'tok'});
    final repo = AuthRepository(_failingDio(_offline));
    expect(await repo.getCurrentUser(), isNull);
  });

  test('脏缓存不把 App 卡住 —— 解析不了就当没有', () async {
    FlutterSecureStorage.setMockInitialValues({
      'access_token': 'tok',
      'user_profile': '{"这不是一个用户": true}',
    });
    final repo = AuthRepository(_failingDio(_offline));
    expect(await repo.getCurrentUser(), isNull);
  });

  test('压根没有令牌时不去碰网络', () async {
    FlutterSecureStorage.setMockInitialValues({});
    var hit = false;
    final repo = AuthRepository(_failingDio((o) {
      hit = true;
      return _offline(o);
    }));
    expect(await repo.getCurrentUser(), isNull);
    expect(hit, isFalse);
  });
}
