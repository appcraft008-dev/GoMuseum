// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Japanese (`ja`).
class AppLocalizationsJa extends AppLocalizations {
  AppLocalizationsJa([String locale = 'ja']) : super(locale);

  @override
  String get home => 'ホーム';

  @override
  String get explore => '探す';

  @override
  String get capture => 'カメラ';

  @override
  String get footprints => '足跡';

  @override
  String get settings => '設定';

  @override
  String get navScan => 'スキャン';

  @override
  String get artworkRecognition => '作品認識';

  @override
  String get takePhoto => '写真を撮る';

  @override
  String get chooseFromGallery => 'ギャラリーから選択';

  @override
  String get selectImagePrompt => '作品を認識する画像を選択';

  @override
  String get error => 'エラー';

  @override
  String get comingSoon => '近日公開';

  @override
  String get comingSoonShort => '近日公開';

  @override
  String get language => '言語';

  @override
  String get selectLanguage => '言語を選択';

  @override
  String get retry => '再試行';

  @override
  String get cancel => 'キャンセル';

  @override
  String get delete => '削除';

  @override
  String get confirm => '確認';

  @override
  String get gotIt => 'OK';

  @override
  String get loadFailed => '読み込みに失敗しました';

  @override
  String get loadFailedRetry => '読み込みに失敗しました。再試行してください';

  @override
  String get toBeRefined => '準備中';

  @override
  String get viewAll => 'すべて見る →';

  @override
  String get all => 'すべて';

  @override
  String get homePocketGuide => 'ポケット美術館ガイド';

  @override
  String get homeSlogan => '一つの作品に近づいて、\nその物語を聴こう。';

  @override
  String get homeCtaRecognize => '撮影して認識・再生';

  @override
  String homeFreeLeft(Object count) {
    return '無料スキャン残り$count回 · アップグレードで全機能';
  }

  @override
  String get homeNearby => '近くの美術館';

  @override
  String get statusOpen => '開館中';

  @override
  String get exploreTitle => '探す';

  @override
  String get searchCityMuseumArtwork => '都市・美術館・作品を検索';

  @override
  String museumCount(Object count) {
    return '$count館';
  }

  @override
  String get noMuseums => '美術館がありません';

  @override
  String get noMatchedMuseums => '一致する美術館がありません';

  @override
  String artworkCountLabel(Object count) {
    return '$count点';
  }

  @override
  String recordedCount(Object count) {
    return '所蔵$count点';
  }

  @override
  String get noArtworks => '作品がありません';

  @override
  String loadingShown(Object shown, Object total) {
    return '読み込み中 · $shown/$total件表示';
  }

  @override
  String allLoaded(Object total) {
    return 'すべて読み込み済み · 合計$total件';
  }

  @override
  String get guideVoiceGuide => '音声ガイド';

  @override
  String get guideGenFailed => '解説の生成に失敗しました';

  @override
  String get guideWriting => '解説を作成中…';

  @override
  String get guideHighlight => '見どころ';

  @override
  String get guideQa => 'Q&A';

  @override
  String get guideThinking => '考え中…';

  @override
  String get guideQ1 => 'この絵の特別なところは？';

  @override
  String get guideQ2 => 'その頃、画家は何を経験していましたか？';

  @override
  String get guideAskHint => 'この絵について質問…';

  @override
  String get guideAskShort => 'この絵について質問';

  @override
  String get guideVoiceComingSoon => '音声Q&Aは近日公開、今は入力してください';

  @override
  String get guideGenerating => 'コンテンツ生成中 · 約1〜3分';

  @override
  String get guideEmpty => '根拠のある解説はまだありません（準備中）';

  @override
  String get guideInfo => '作品情報';

  @override
  String get guideStandardTour => '標準ツアー';

  @override
  String get guideListen => '聴く';

  @override
  String get guideDiveIn => 'もっと知りたい？下をタップ';

  @override
  String get guideDeepContent => '詳しく';

  @override
  String get guideAskPlaceholder => '何でも質問…';

  @override
  String get guideArtist => '作家';

  @override
  String get guideArtistTab => '作家';

  @override
  String get guideNotableWorks => '代表作';

  @override
  String get guideNoAnswer => '（回答なし）';

  @override
  String get guideAnswerFailed => '回答に失敗しました。後でもう一度お試しください。';

  @override
  String get factInventory => '目録番号';

  @override
  String get factLocation => '所在地';

  @override
  String get factProvenance => '来歴';

  @override
  String get factExhibitions => '展覧会';

  @override
  String get factBibliography => '参考文献';

  @override
  String get factArtist => '作家';

  @override
  String get factNone => '詳細情報なし';

  @override
  String get footprintTitle => '足跡';

  @override
  String get noFootprints => '足跡がありません';

  @override
  String footprintStat(Object count, Object days) {
    return '$count点 · $days日';
  }

  @override
  String get footprintLoadFailed => '足跡の読み込みに失敗しました';

  @override
  String get footprintEmptyHint => '認識した作品はここに自動で記録されます';

  @override
  String get footprintGoRecognize => '最初の作品を認識';

  @override
  String itemsCount(Object count) {
    return '$count点';
  }

  @override
  String get today => '今日';

  @override
  String get yesterday => '昨日';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$month/$day';
  }

  @override
  String get deleteFootprintQ => 'この足跡を削除しますか？';

  @override
  String get settingsTitle => '設定';

  @override
  String get secGeneral => '一般';

  @override
  String get guideLanguage => 'ガイドの言語';

  @override
  String get offlinePacks => 'オフライン美術館パック';

  @override
  String get autoSavePhoto => '写真を自動保存';

  @override
  String get ttsVoice => 'TTS音声';

  @override
  String get ttsVoiceValue => '落ち着いた · 女性';

  @override
  String get ttsVoiceSelect => '音声を選択';

  @override
  String get secAccount => 'アカウント';

  @override
  String get secSupport => 'サポートと法的情報';

  @override
  String get encourageUs => '応援する';

  @override
  String get appStoreRating => 'App Storeで評価';

  @override
  String get privacyPolicy => 'プライバシーポリシー';

  @override
  String get freeQuota => '無料スキャン枠';

  @override
  String quotaValue(Object remain, Object total) {
    return '残り$remain / $total';
  }

  @override
  String get upgrade => 'アップグレード';

  @override
  String get loginBind => 'ログイン / アカウント連携';

  @override
  String get notLoggedIn => '未ログイン';

  @override
  String get userDefault => 'ユーザー';

  @override
  String get guestPrefix => 'ゲスト_';

  @override
  String get noEmailBound => 'メール未連携';

  @override
  String get logout => 'ログアウト';

  @override
  String get deleteAccount => 'アカウント削除';

  @override
  String get loadingShort => '読み込み中…';

  @override
  String get appearance => '外観';

  @override
  String get themeLight => 'ライト';

  @override
  String get themeDark => 'ダーク';

  @override
  String get themeSystem => 'システム';

  @override
  String featureComingSoon(String feature) {
    return '$featureは近日公開';
  }

  @override
  String get privacyBody =>
      '元の写真はデフォルトでアップロードされません。認識データは一時的にのみ処理されます。アカウントとデータはいつでも削除できます。正式リリース時に完全な規約を提供します。';

  @override
  String get deleteAccountQ => 'アカウントを完全に削除しますか？';

  @override
  String get deleteAccountBody => 'アカウントのプロフィールと残りの枠が削除されます。この操作は取り消せません。';

  @override
  String get permanentDelete => '完全に削除';

  @override
  String get deleteFailed => '削除に失敗しました。後でもう一度お試しください';

  @override
  String get confirmLogout => 'ログアウトの確認';

  @override
  String get confirmLogoutBody => '本当にログアウトしますか？';

  @override
  String get confirmYes => '確認';

  @override
  String get authEmailHint => 'メールアドレス';

  @override
  String get authEmailRequired => 'メールアドレスを入力してください';

  @override
  String get authEmailInvalid => '有効なメールアドレスを入力してください';

  @override
  String get authPasswordHint => 'パスワード';

  @override
  String get authPasswordRequired => 'パスワードを入力してください';

  @override
  String get authPasswordMin6 => 'パスワードは6文字以上必要です';

  @override
  String get authConfirmPasswordHint => 'パスワードを確認';

  @override
  String get authPasswordMismatch => 'パスワードが一致しません';

  @override
  String get authUsernameOptionalHint => 'ユーザー名（任意）';

  @override
  String get authLoginButton => 'ログイン';

  @override
  String get authRegisterButton => '登録';

  @override
  String get authNoAccount => 'アカウントがない？登録';

  @override
  String get authHaveAccount => 'アカウントがある？ログイン';

  @override
  String get authCreateAccount => 'アカウント作成';

  @override
  String get authOrLoginWith => 'または次でログイン';

  @override
  String get authGoogleLogin => 'Googleでログイン';

  @override
  String get authAppleLogin => 'Appleでログイン';

  @override
  String get authOr => 'または';

  @override
  String get authGuestLogin => 'ゲストとして続行';

  @override
  String get authLoginFailed => 'ログインに失敗しました。メールとパスワードを確認してください';

  @override
  String get authRegisterFailed => '登録に失敗しました。メールは既に使用されている可能性があります';

  @override
  String get authGoogleCancelled => 'Googleログインをキャンセルしました';

  @override
  String get authGoogleFailed => 'Googleログインに失敗しました。もう一度お試しください';

  @override
  String get authGoogleError => 'Googleログインエラー';

  @override
  String get authGoogleNotConfigured => 'Googleログインが未設定です。管理者に連絡してください';

  @override
  String get authGoogleNetworkError => 'Googleログインのネットワークエラー。接続を確認してください';

  @override
  String get authAppleOnlyApple => 'AppleログインはiOSとmacOSのみ対応';

  @override
  String get authAppleCancelled => 'Appleログインをキャンセルしました';

  @override
  String get authAppleFailed => 'Appleログインに失敗しました。もう一度お試しください';

  @override
  String get authAppleError => 'Appleログインエラー';

  @override
  String get authAppleNotConfigured => 'Appleログインが未設定です';

  @override
  String get authGuestFailed => 'ゲストログインに失敗しました。もう一度お試しください';

  @override
  String get authGuestError => 'ゲストログインエラー';

  @override
  String get recCandidatesTitle => 'これですか？';

  @override
  String get recNoneOfThese => 'どれも違う';

  @override
  String get recNotRecognized => 'この作品を認識できませんでした';

  @override
  String recLabelSeen(String text) {
    return 'ラベルには「$text」とあります — まだ完全なガイドはありませんが、ご要望を記録しました ✅';
  }

  @override
  String get recShootLabelBtn => '解説プレートを撮影';

  @override
  String get recShootLabelHint => '美術館のプレートには題名と作家が書かれています。撮影すれば作品を特定できます';

  @override
  String get recViewfinderLabelHint => 'プレートの文字を画面いっぱいに写してください';

  @override
  String get camRecognizeTitle => '作品を識別';

  @override
  String get camViewfinderHint => '作品全体を枠内に収めてください';

  @override
  String get camRecentGallery => '最近';

  @override
  String get camAllAlbums => 'すべてのアルバム';

  @override
  String get camGallery => 'ギャラリー';

  @override
  String get camSearch => '検索';

  @override
  String get guideUnavailable => 'この作品はガイド用の資料が不足しています';

  @override
  String get guideNotGenerated => 'ガイドはまだ生成されていません';

  @override
  String get audioNotReady => '解説の生成後に再生できます';

  @override
  String get audioFailed => '音声を利用できません。再試行してください';

  @override
  String get deepGenerating => '詳細コンテンツを生成中…';

  @override
  String get camNoCamera => '利用可能なカメラが見つかりません';

  @override
  String get camInitFailed => 'カメラの初期化に失敗しました';

  @override
  String get camTagSearch => 'プレート検索';

  @override
  String get camTagHint => '撮影不可の場所ではプレート番号・題名・作家を入力';

  @override
  String get camTagExample => '例：INV 3692 / 寝室';

  @override
  String get camPackComingSoon => 'コレクション検索はオフラインパック提供後に利用可能';

  @override
  String get camQuotaUsedUp => '無料スキャンを使い切りました';

  @override
  String get camUpgradeHint => 'アップグレードして館内で聴き続ける';

  @override
  String get camViewUpgrade => 'プランを見る';

  @override
  String get camCantPhoto => '撮影できない？プレート番号を入力';

  @override
  String get camRecognizing => '認識中…';

  @override
  String get camComparing => 'AIがコレクションと公開美術データベースと照合中';

  @override
  String get camConfirmPrompt => '認識完了。作品を確認してください';

  @override
  String get camConfidence => '信頼度';

  @override
  String get camConfirmStart => '確認してガイド開始';

  @override
  String get camNoneSearch => '該当なし？題名またはプレート番号で検索 →';

  @override
  String get camRecognizeFailed => '認識に失敗しました';

  @override
  String get camRetake => '撮り直す';
}
