# 识别计费身份串号修复（device_id 撞到别人配额行）

> 2026-07-14。prod 实证:用户登录 appcraft008(999999 额度)却识别报 402。根因诊断见下。
> 与 [[recognition-mechanism]] 计费链相关。

## 现象（prod 实证）

- 用户登录 appcraft008@gmail.com(`recognition_quota=999999`,首页显示 999999),`/payment/benefits`、`/payment/consume` 都正确解析成该账号。
- 但 `/api/v1/recognize`(带 `device_id=AQ3A.250226.002`)**一律 402 Payment Required**。
- 该 device_id 底下挂了 **5 个 user_benefits 行**(用户 5 个测试账号各一行,含两条 `quota=0/used=10` 耗尽行)。

## 根因（两个 bug 叠加）

### Bug ①（前端）：multipart 令牌抽风 → 掉到 device 计费

识别是 multipart 图片上传(FormData 单次性)。`AuthInterceptor` 在 401 时刷新+重发,但 **FormData 无法重放** → 令牌过期那次 `/recognize` 实际没带有效令牌 → 后端 `run_recognition` 里 `user_id=None` → **降级到 device_id 计费**。datasource 已有注释点破此坑("令牌抽风")。

### Bug ②（后端·串号本体）：匿名查询命中账号所有的配额行

`benefits_service.get_or_create_benefits(user_id=None, device_id=D)`:
```python
else:  # user_id 为空
    benefits = query.filter(UserBenefits.device_id == device_id).first()
```
`.first()` **无排序**,且**不限 `user_id IS NULL`** → 在同 device 的多行里随机挑一行,**可能挑到某个账号(user_id 非空)的耗尽行** → `has_access=False` → 402。
**匿名请求 billing 到某个登录账号的配额行,本身就是数据模型缺陷。**

## 修复

### 后端（根治 Bug ②,本 PR 主体）

`get_or_create_benefits` 的匿名分支**只匹配匿名行**并确定排序:
```python
else:
    benefits = (
        query.filter(
            UserBenefits.device_id == device_id,
            UserBenefits.user_id.is_(None),
        )
        .order_by(UserBenefits.created_at)
        .first()
    )
```
效果:匿名/令牌失败的请求**绝不再动任何账号的配额行**(串号根除);找不到匿名行就按老逻辑建一条匿名行(user_id=NULL)。已登录账号的行只经 `user_id` 分支命中,不受影响。

### 前端（Bug ① 配套,后续/同 PR 视工作量）

识别前**主动确保有效令牌**(pre-flight refresh),让 multipart 请求一定带上当前账号令牌 → 已登录用户永远计费到自己账号,不再降级 device。

## 测试（TDD）

后端(sqlite,抄 `test_quota_abuse.py`):
- **串号复现**:建账号行(user_id=A, device=D, quota 耗尽)→ `check_access(user_id=None, device_id=D)` **不得**命中 A 的行(修前 has_access=False,修后=True,走匿名行)。
- 匿名行存在时复用该匿名行(不重复建)。
- 已登录:`check_access(user_id=A, device_id=D)` 仍命中 A 自己的行(回归)。
- `consume_recognition` 同链路一并受益(共用 get_or_create)。

## 数据侧（已做）

prod 该测试设备 5 行已全部放开 999999 解眼前测试堵(非破坏,保留 used)。

## 不做（YAGNI）

- 不重构 guest-login/身份模型(超范围;本 PR 只堵串号 + 令牌降级)。
- 不做"同设备多账号合并/去重"(各账号独立合理;只保证匿名请求不碰账号行)。
