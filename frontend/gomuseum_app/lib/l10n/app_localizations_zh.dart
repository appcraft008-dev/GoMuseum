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
  String get recCandidatesTitle => '是这件吗？';

  @override
  String get recNoneOfThese => '都不是';

  @override
  String get recNotRecognized => '没认出来这件作品';

  @override
  String recLabelSeen(String text) {
    return '标签上写着 \"$text\"——我们还没收录它的完整讲解，已记下你的需求 ✅';
  }

  @override
  String get recShootLabelBtn => '拍下作品旁的说明牌';

  @override
  String get recShootLabelHint => '博物馆的小标牌上有作品名和作者，拍它我们就能认出来';

  @override
  String get recViewfinderLabelHint => '对准标签文字，占满画面';

  @override
  String get camRecognizeTitle => '识别画作';

  @override
  String get camViewfinderHint => '将画作完整置于取景框内';

  @override
  String get camRecentGallery => '最近图库';

  @override
  String get camAllAlbums => '全部相册';

  @override
  String get camGallery => '图库';

  @override
  String get camSearch => '搜索';

  @override
  String get guideUnavailable => '该藏品资料不足，暂无讲解';

  @override
  String get guideNotGenerated => '讲解暂未生成';

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

/// The translations for Chinese, using the Han script (`zh_Hant`).
class AppLocalizationsZhHant extends AppLocalizationsZh {
  AppLocalizationsZhHant() : super('zh_Hant');

  @override
  String get home => '首頁';

  @override
  String get explore => '探索';

  @override
  String get capture => '拍照';

  @override
  String get footprints => '足跡';

  @override
  String get settings => '設定';

  @override
  String get navScan => '識別';

  @override
  String get artworkRecognition => '藝術品識別';

  @override
  String get takePhoto => '拍照';

  @override
  String get chooseFromGallery => '從相簿選擇';

  @override
  String get selectImagePrompt => '選擇圖片以識別藝術品';

  @override
  String get error => '錯誤';

  @override
  String get comingSoon => '即將推出';

  @override
  String get comingSoonShort => '即將上線';

  @override
  String get language => '語言';

  @override
  String get selectLanguage => '選擇語言';

  @override
  String get retry => '重試';

  @override
  String get cancel => '取消';

  @override
  String get delete => '刪除';

  @override
  String get confirm => '確定';

  @override
  String get gotIt => '知道了';

  @override
  String get loadFailed => '載入失敗';

  @override
  String get loadFailedRetry => '載入失敗，請重試';

  @override
  String get toBeRefined => '待完善';

  @override
  String get viewAll => '檢視全部 →';

  @override
  String get all => '全部';

  @override
  String get homePocketGuide => '隨身博物館導覽手冊';

  @override
  String get homeSlogan => '走近一件作品，\n聽懂它的故事。';

  @override
  String get homeCtaRecognize => '拍照識別講解';

  @override
  String homeFreeLeft(Object count) {
    return '免費識別還剩 $count 次 · 升級暢聽全館';
  }

  @override
  String get homeNearby => '附近博物館';

  @override
  String get statusOpen => '開放中';

  @override
  String get exploreTitle => '探 索';

  @override
  String get searchCityMuseumArtwork => '搜尋城市、博物館或藝術品';

  @override
  String museumCount(Object count) {
    return '$count 家博物館';
  }

  @override
  String get noMuseums => '暫無博物館';

  @override
  String get noMatchedMuseums => '沒有匹配的博物館';

  @override
  String artworkCountLabel(Object count) {
    return '含 $count 件藏品';
  }

  @override
  String recordedCount(Object count) {
    return '$count 件收錄藏品';
  }

  @override
  String get noArtworks => '暫無藏品';

  @override
  String loadingShown(Object shown, Object total) {
    return '正在載入·已顯示 $shown/$total';
  }

  @override
  String allLoaded(Object total) {
    return '已全部載入·共 $total 件';
  }

  @override
  String get guideVoiceGuide => '語音導覽';

  @override
  String get guideGenFailed => '講解生成失敗';

  @override
  String get guideWriting => '正在為你撰寫講解…';

  @override
  String get guideHighlight => '看點';

  @override
  String get guideQa => '問答';

  @override
  String get guideThinking => '思考中…';

  @override
  String get guideQ1 => '這幅畫好在哪裡？';

  @override
  String get guideQ2 => '畫家當時經歷了什麼？';

  @override
  String get guideAskHint => '問問這幅畫……';

  @override
  String get guideAskShort => '問問這幅畫';

  @override
  String get guideVoiceComingSoon => '語音問答即將開放，先打字問問吧';

  @override
  String get guideGenerating => '內容生成中，約 1–3 分鐘';

  @override
  String get guideEmpty => '該作品暫無可接地講解（待完善）';

  @override
  String get guideInfo => '作品資訊';

  @override
  String get guideStandardTour => '標準導覽';

  @override
  String get guideListen => '聽講解';

  @override
  String get guideDiveIn => '想深入？點一下';

  @override
  String get guideDeepContent => '深度內容';

  @override
  String get guideAskPlaceholder => '問點什麼…';

  @override
  String get guideArtist => '作者';

  @override
  String get guideArtistTab => '作者介紹';

  @override
  String get guideNotableWorks => '代表作';

  @override
  String get guideNoAnswer => '（未返回回答）';

  @override
  String get guideAnswerFailed => '回答失敗，請稍後再試。';

  @override
  String get factInventory => '館藏編號';

  @override
  String get factLocation => '現藏地';

  @override
  String get factProvenance => '來源流轉';

  @override
  String get factExhibitions => '展覽史';

  @override
  String get factBibliography => '參考文獻';

  @override
  String get factArtist => '作者';

  @override
  String get factNone => '暫無詳細資訊';

  @override
  String get footprintTitle => '足 跡';

  @override
  String get noFootprints => '還沒有足跡';

  @override
  String footprintStat(Object count, Object days) {
    return '$count 件作品 · $days 天';
  }

  @override
  String get footprintLoadFailed => '足跡載入失敗';

  @override
  String get footprintEmptyHint => '識別過的展品會自動記錄在這裡';

  @override
  String get footprintGoRecognize => '去識別第一件作品';

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
  String get deleteFootprintQ => '刪除這條足跡？';

  @override
  String get settingsTitle => '設 置';

  @override
  String get secGeneral => '通用';

  @override
  String get guideLanguage => '講解語言';

  @override
  String get offlinePacks => '離線館包';

  @override
  String get autoSavePhoto => '自動儲存照片';

  @override
  String get ttsVoice => 'TTS 音色';

  @override
  String get ttsVoiceValue => '沉穩 · 女聲';

  @override
  String get ttsVoiceSelect => '音色選擇';

  @override
  String get secAccount => '賬戶';

  @override
  String get secSupport => '支援與法律';

  @override
  String get encourageUs => '鼓勵我們';

  @override
  String get appStoreRating => '應用商店評分';

  @override
  String get privacyPolicy => '隱私政策';

  @override
  String get freeQuota => '免費識別額度';

  @override
  String quotaValue(Object remain, Object total) {
    return '剩餘 $remain/$total 次';
  }

  @override
  String get upgrade => '升級';

  @override
  String get loginBind => '登入 / 繫結賬號';

  @override
  String get notLoggedIn => '未登入';

  @override
  String get userDefault => '使用者';

  @override
  String get guestPrefix => '遊客_';

  @override
  String get noEmailBound => '未繫結郵箱';

  @override
  String get logout => '登出';

  @override
  String get deleteAccount => '刪除賬號';

  @override
  String get loadingShort => '載入中…';

  @override
  String get appearance => '外觀';

  @override
  String get themeLight => '淺色';

  @override
  String get themeDark => '深色';

  @override
  String get themeSystem => '跟隨系統';

  @override
  String featureComingSoon(String feature) {
    return '$feature即將開放';
  }

  @override
  String get privacyBody => '照片預設不上傳原圖，識別資料僅作臨時處理；你可以隨時刪除賬戶與資料。完整條款將在正式釋出時提供。';

  @override
  String get deleteAccountQ => '永久刪除賬號？';

  @override
  String get deleteAccountBody => '將刪除你的賬號資料與剩餘額度，此操作不可恢復。';

  @override
  String get permanentDelete => '永久刪除';

  @override
  String get deleteFailed => '刪除失敗，請稍後再試';

  @override
  String get confirmLogout => '確認登出';

  @override
  String get confirmLogoutBody => '確定要登出嗎？';

  @override
  String get confirmYes => '確定';

  @override
  String get authEmailHint => '郵箱';

  @override
  String get authEmailRequired => '請輸入郵箱';

  @override
  String get authEmailInvalid => '請輸入有效的郵箱地址';

  @override
  String get authPasswordHint => '密碼';

  @override
  String get authPasswordRequired => '請輸入密碼';

  @override
  String get authPasswordMin6 => '密碼至少 6 位';

  @override
  String get authConfirmPasswordHint => '確認密碼';

  @override
  String get authPasswordMismatch => '兩次密碼不一致';

  @override
  String get authUsernameOptionalHint => '使用者名稱（可選）';

  @override
  String get authLoginButton => '登 錄';

  @override
  String get authRegisterButton => '注 冊';

  @override
  String get authNoAccount => '還沒有賬號？註冊';

  @override
  String get authHaveAccount => '已有賬號？登入';

  @override
  String get authCreateAccount => '建立賬號';

  @override
  String get authOrLoginWith => '或使用以下方式登入';

  @override
  String get authGoogleLogin => '使用 Google 登入';

  @override
  String get authAppleLogin => '使用 Apple 登入';

  @override
  String get authOr => '或';

  @override
  String get authGuestLogin => '遊客登入';

  @override
  String get authLoginFailed => '登入失敗，請檢查郵箱和密碼';

  @override
  String get authRegisterFailed => '註冊失敗，郵箱可能已被使用';

  @override
  String get authGoogleCancelled => 'Google 登入已取消';

  @override
  String get authGoogleFailed => 'Google 登入失敗，請重試';

  @override
  String get authGoogleError => 'Google 登入錯誤';

  @override
  String get authGoogleNotConfigured => 'Google 登入未配置，請聯絡管理員';

  @override
  String get authGoogleNetworkError => 'Google 登入網路錯誤，請檢查網路連線';

  @override
  String get authAppleOnlyApple => 'Apple 登入僅支援 iOS 和 macOS 裝置';

  @override
  String get authAppleCancelled => 'Apple 登入已取消';

  @override
  String get authAppleFailed => 'Apple 登入失敗，請重試';

  @override
  String get authAppleError => 'Apple 登入錯誤';

  @override
  String get authAppleNotConfigured => 'Apple 登入未配置';

  @override
  String get authGuestFailed => '遊客登入失敗，請重試';

  @override
  String get authGuestError => '遊客登入錯誤';

  @override
  String get recCandidatesTitle => '是這件嗎？';

  @override
  String get recNoneOfThese => '都不是';

  @override
  String get recNotRecognized => '沒認出來這件作品';

  @override
  String recLabelSeen(String text) {
    return '標籤上寫著 \"$text\"——我們還沒收錄它的完整講解，已記下你的需求 ✅';
  }

  @override
  String get recShootLabelBtn => '拍下作品旁的說明牌';

  @override
  String get recShootLabelHint => '博物館的小標牌上有作品名和作者，拍它我們就能認出來';

  @override
  String get recViewfinderLabelHint => '對準標籤文字，佔滿畫面';

  @override
  String get camRecognizeTitle => '識別畫作';

  @override
  String get camViewfinderHint => '將畫作完整置於取景框內';

  @override
  String get camRecentGallery => '最近相簿';

  @override
  String get camAllAlbums => '全部相簿';

  @override
  String get camGallery => '相簿';

  @override
  String get camSearch => '搜尋';

  @override
  String get guideUnavailable => '該藏品資料不足，暫無講解';

  @override
  String get guideNotGenerated => '講解暫未生成';

  @override
  String get camNoCamera => '未找到可用相機';

  @override
  String get camInitFailed => '相機初始化失敗';

  @override
  String get camTagSearch => '展籤檢索';

  @override
  String get camTagHint => '禁拍照展區可輸入展籤編號、作品名或作者名';

  @override
  String get camTagExample => '如：INV 3692 / 在阿爾的臥室';

  @override
  String get camPackComingSoon => '館藏檢索將在離線館包接入後開放';

  @override
  String get camQuotaUsedUp => '免費識別次數已用盡';

  @override
  String get camUpgradeHint => '升級後可繼續暢聽全館講解';

  @override
  String get camViewUpgrade => '檢視升級方案';

  @override
  String get camCantPhoto => '不能拍照？輸入展籤編號';

  @override
  String get camRecognizing => '正在識別…';

  @override
  String get camComparing => 'AI 正在比對館藏與公開藝術資料庫';

  @override
  String get camConfirmPrompt => '識別完成，請確認展品';

  @override
  String get camConfidence => '置信度';

  @override
  String get camConfirmStart => '確認，開始講解';

  @override
  String get camNoneSearch => '都不是？搜尋作品名或展籤編號 →';

  @override
  String get camRecognizeFailed => '識別失敗';

  @override
  String get camRetake => '重新拍攝';
}
