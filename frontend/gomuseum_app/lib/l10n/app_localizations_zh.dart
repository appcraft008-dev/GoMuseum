// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class AppLocalizationsZh extends AppLocalizations {
  AppLocalizationsZh([String locale = 'zh']) : super(locale);

  @override
  String get home => '首页';

  @override
  String get explore => '探索';

  @override
  String get capture => '拍照';

  @override
  String get footprints => '足迹';

  @override
  String get settings => '设置';

  @override
  String get navScan => '识别';

  @override
  String get artworkRecognition => '艺术品识别';

  @override
  String get takePhoto => '拍照';

  @override
  String get chooseFromGallery => '从相册选择';

  @override
  String get selectImagePrompt => '选择图片以识别艺术品';

  @override
  String get error => '错误';

  @override
  String get comingSoon => '即将推出';

  @override
  String get comingSoonShort => '即将上线';

  @override
  String get language => '语言';

  @override
  String get selectLanguage => '选择语言';

  @override
  String get retry => '重试';

  @override
  String get cancel => '取消';

  @override
  String get delete => '删除';

  @override
  String get confirm => '确定';

  @override
  String get gotIt => '知道了';

  @override
  String get loadFailed => '加载失败';

  @override
  String get loadFailedRetry => '加载失败，请重试';

  @override
  String get toBeRefined => '待完善';

  @override
  String get viewAll => '查看全部 →';

  @override
  String get all => '全部';

  @override
  String get homePocketGuide => '随身博物馆导览手册';

  @override
  String get homeSlogan => '走近一件作品，\n听懂它的故事。';

  @override
  String get homeCtaRecognize => '拍照识别讲解';

  @override
  String homeFreeLeft(Object count) {
    return '免费识别还剩 $count 次 · 升级畅听全馆';
  }

  @override
  String get homeNearby => '附近博物馆';

  @override
  String get statusOpen => '开放中';

  @override
  String get exploreTitle => '探 索';

  @override
  String get searchCityMuseumArtwork => '搜索城市、博物馆或艺术品';

  @override
  String museumCount(Object count) {
    return '$count 家博物馆';
  }

  @override
  String get noMuseums => '暂无博物馆';

  @override
  String get noMatchedMuseums => '没有匹配的博物馆';

  @override
  String artworkCountLabel(Object count) {
    return '含 $count 件藏品';
  }

  @override
  String recordedCount(Object count) {
    return '$count 件收录藏品';
  }

  @override
  String get noArtworks => '暂无藏品';

  @override
  String loadingShown(Object shown, Object total) {
    return '正在加载·已显示 $shown/$total';
  }

  @override
  String allLoaded(Object total) {
    return '已全部加载·共 $total 件';
  }

  @override
  String get guideVoiceGuide => '语音导览';

  @override
  String get guideGenFailed => '讲解生成失败';

  @override
  String get guideWriting => '正在为你撰写讲解…';

  @override
  String get guideHighlight => '看点';

  @override
  String get guideQa => '问答';

  @override
  String get guideThinking => '思考中…';

  @override
  String get guideQ1 => '这幅画好在哪里？';

  @override
  String get guideQ2 => '画家当时经历了什么？';

  @override
  String get guideAskHint => '问问这幅画……';

  @override
  String get guideAskShort => '问问这幅画';

  @override
  String get guideVoiceComingSoon => '语音问答即将开放，先打字问问吧';

  @override
  String get guideGenerating => '内容生成中，约 1–3 分钟';

  @override
  String get guideEmpty => '该作品暂无可接地讲解（待完善）';

  @override
  String get guideInfo => '作品信息';

  @override
  String get guideStandardTour => '标准导览';

  @override
  String get guideListen => '听讲解';

  @override
  String get guideDiveIn => '想深入？点一下';

  @override
  String get guideDeepContent => '深度内容';

  @override
  String get guideAskPlaceholder => '问点什么…';

  @override
  String get guideArtist => '作者';

  @override
  String get guideArtistTab => '作者介绍';

  @override
  String get guideNotableWorks => '代表作';

  @override
  String get guideNoAnswer => '（未返回回答）';

  @override
  String get guideAnswerFailed => '回答失败，请稍后再试。';

  @override
  String get factInventory => '馆藏编号';

  @override
  String get factLocation => '现藏地';

  @override
  String get factProvenance => '来源流转';

  @override
  String get factExhibitions => '展览史';

  @override
  String get factBibliography => '参考文献';

  @override
  String get factArtist => '作者';

  @override
  String get factNone => '暂无详细信息';

  @override
  String get footprintTitle => '足 迹';

  @override
  String get noFootprints => '还没有足迹';

  @override
  String footprintStat(Object count, Object days) {
    return '$count 件作品 · $days 天';
  }

  @override
  String get footprintLoadFailed => '足迹加载失败';

  @override
  String get footprintEmptyHint => '识别过的展品会自动记录在这里';

  @override
  String get footprintGoRecognize => '去识别第一件作品';

  @override
  String itemsCount(Object count) {
    return '$count 件';
  }

  @override
  String get today => '今天';

  @override
  String get yesterday => '昨天';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$month月$day日';
  }

  @override
  String get deleteFootprintQ => '删除这条足迹？';

  @override
  String get settingsTitle => '设 置';

  @override
  String get secGeneral => '通用';

  @override
  String get guideLanguage => '讲解语言';

  @override
  String get offlinePacks => '离线馆包';

  @override
  String get autoSavePhoto => '自动保存照片';

  @override
  String get ttsVoice => 'TTS 音色';

  @override
  String get ttsVoiceValue => '沉稳 · 女声';

  @override
  String get ttsVoiceSelect => '音色选择';

  @override
  String get secAccount => '账户';

  @override
  String get secSupport => '支持与法律';

  @override
  String get encourageUs => '鼓励我们';

  @override
  String get appStoreRating => '应用商店评分';

  @override
  String get privacyPolicy => '隐私政策';

  @override
  String get freeQuota => '免费识别额度';

  @override
  String quotaValue(Object remain, Object total) {
    return '剩余 $remain/$total 次';
  }

  @override
  String get upgrade => '升级';

  @override
  String get loginBind => '登录 / 绑定账号';

  @override
  String get notLoggedIn => '未登录';

  @override
  String get userDefault => '用户';

  @override
  String get guestPrefix => '游客_';

  @override
  String get noEmailBound => '未绑定邮箱';

  @override
  String get logout => '登出';

  @override
  String get deleteAccount => '删除账号';

  @override
  String get loadingShort => '加载中…';

  @override
  String get appearance => '外观';

  @override
  String get themeLight => '浅色';

  @override
  String get themeDark => '深色';

  @override
  String get themeSystem => '跟随系统';

  @override
  String featureComingSoon(String feature) {
    return '$feature即将开放';
  }

  @override
  String get privacyBody => '照片默认不上传原图，识别数据仅作临时处理；你可以随时删除账户与数据。完整条款将在正式发布时提供。';

  @override
  String get deleteAccountQ => '永久删除账号？';

  @override
  String get deleteAccountBody => '将删除你的账号资料与剩余额度，此操作不可恢复。';

  @override
  String get permanentDelete => '永久删除';

  @override
  String get deleteFailed => '删除失败，请稍后再试';

  @override
  String get confirmLogout => '确认登出';

  @override
  String get confirmLogoutBody => '确定要登出吗？';

  @override
  String get confirmYes => '确定';

  @override
  String get authEmailHint => '邮箱';

  @override
  String get authEmailRequired => '请输入邮箱';

  @override
  String get authEmailInvalid => '请输入有效的邮箱地址';

  @override
  String get authPasswordHint => '密码';

  @override
  String get authPasswordRequired => '请输入密码';

  @override
  String get authPasswordMin6 => '密码至少 6 位';

  @override
  String get authConfirmPasswordHint => '确认密码';

  @override
  String get authPasswordMismatch => '两次密码不一致';

  @override
  String get authUsernameOptionalHint => '用户名（可选）';

  @override
  String get authLoginButton => '登 录';

  @override
  String get authRegisterButton => '注 册';

  @override
  String get authNoAccount => '还没有账号？注册';

  @override
  String get authHaveAccount => '已有账号？登录';

  @override
  String get authCreateAccount => '创建账号';

  @override
  String get authOrLoginWith => '或使用以下方式登录';

  @override
  String get authGoogleLogin => '使用 Google 登录';

  @override
  String get authAppleLogin => '使用 Apple 登录';

  @override
  String get authOr => '或';

  @override
  String get authGuestLogin => '游客登录';

  @override
  String get authLoginFailed => '登录失败，请检查邮箱和密码';

  @override
  String get authRegisterFailed => '注册失败，邮箱可能已被使用';

  @override
  String get authGoogleCancelled => 'Google 登录已取消';

  @override
  String get authGoogleFailed => 'Google 登录失败，请重试';

  @override
  String get authGoogleError => 'Google 登录错误';

  @override
  String get authGoogleNotConfigured => 'Google 登录未配置，请联系管理员';

  @override
  String get authGoogleNetworkError => 'Google 登录网络错误，请检查网络连接';

  @override
  String get authAppleOnlyApple => 'Apple 登录仅支持 iOS 和 macOS 设备';

  @override
  String get authAppleCancelled => 'Apple 登录已取消';

  @override
  String get authAppleFailed => 'Apple 登录失败，请重试';

  @override
  String get authAppleError => 'Apple 登录错误';

  @override
  String get authAppleNotConfigured => 'Apple 登录未配置';

  @override
  String get authGuestFailed => '游客登录失败，请重试';

  @override
  String get authGuestError => '游客登录错误';

  @override
  String get camNoCamera => '未找到可用相机';

  @override
  String get camInitFailed => '相机初始化失败';

  @override
  String get camTagSearch => '展签检索';

  @override
  String get camTagHint => '禁拍照展区可输入展签编号、作品名或作者名';

  @override
  String get camTagExample => '如：INV 3692 / 在阿尔的卧室';

  @override
  String get camPackComingSoon => '馆藏检索将在离线馆包接入后开放';

  @override
  String get camQuotaUsedUp => '免费识别次数已用尽';

  @override
  String get camUpgradeHint => '升级后可继续畅听全馆讲解';

  @override
  String get camViewUpgrade => '查看升级方案';

  @override
  String get camCantPhoto => '不能拍照？输入展签编号';

  @override
  String get camRecognizing => '正在识别…';

  @override
  String get camComparing => 'AI 正在比对馆藏与公开艺术数据库';

  @override
  String get camConfirmPrompt => '识别完成，请确认展品';

  @override
  String get camConfidence => '置信度';

  @override
  String get camConfirmStart => '确认，开始讲解';

  @override
  String get camNoneSearch => '都不是？搜索作品名或展签编号 →';

  @override
  String get camRecognizeFailed => '识别失败';

  @override
  String get camRetake => '重新拍摄';
}
