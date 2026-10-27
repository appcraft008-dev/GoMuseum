// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Korean (`ko`).
class AppLocalizationsKo extends AppLocalizations {
  AppLocalizationsKo([String locale = 'ko']) : super(locale);

  @override
  String get home => '홈';

  @override
  String get explore => '탐⁠색';

  @override
  String get capture => '카⁠메⁠라';

  @override
  String get footprints => '발⁠자⁠취';

  @override
  String get settings => '설⁠정';

  @override
  String get navScan => '스⁠캔';

  @override
  String get artworkRecognition => '작⁠품 인⁠식';

  @override
  String get takePhoto => '사⁠진 촬⁠영';

  @override
  String get chooseFromGallery => '갤⁠러⁠리⁠에⁠서 선⁠택';

  @override
  String get selectImagePrompt => '작⁠품⁠을 인⁠식⁠할 이⁠미⁠지⁠를 선⁠택⁠하⁠세⁠요';

  @override
  String get error => '오⁠류';

  @override
  String get comingSoon => '곧 제⁠공';

  @override
  String get comingSoonShort => '곧 제⁠공';

  @override
  String get language => '언⁠어';

  @override
  String get languageFollowSystem => '시⁠스⁠템 설⁠정 따⁠름';

  @override
  String get selectLanguage => '언⁠어 선⁠택';

  @override
  String get retry => '다⁠시 시⁠도';

  @override
  String get cancel => '취⁠소';

  @override
  String get delete => '삭⁠제';

  @override
  String get confirm => '확⁠인';

  @override
  String get loadFailed => '불⁠러⁠오⁠기 실⁠패';

  @override
  String get loadFailedRetry => '불⁠러⁠오⁠기 실⁠패, 다⁠시 시⁠도⁠하⁠세⁠요';

  @override
  String get toBeRefined => '준⁠비 중';

  @override
  String get viewAll => '모⁠두 보⁠기 →';

  @override
  String get all => '전⁠체';

  @override
  String get homePocketGuide => '포⁠켓 미⁠술⁠관 가⁠이⁠드';

  @override
  String get homeSlogan => '한 작⁠품⁠에 다⁠가⁠가\n그 이⁠야⁠기⁠를 들⁠어⁠보⁠세⁠요.';

  @override
  String get homeCtaRecognize => '촬⁠영⁠해 인⁠식⁠하⁠고 감⁠상';

  @override
  String homeFreeLeft(Object count) {
    return '무⁠료 스⁠캔 $count⁠회 남⁠음 · 업⁠그⁠레⁠이⁠드⁠로 전⁠체 이⁠용';
  }

  @override
  String get homePassActive => '패⁠스 이⁠용 중 · 전⁠체 이⁠용 가⁠능';

  @override
  String get homePassPending => '패⁠스 구⁠매 완⁠료 · 탭⁠하⁠여 활⁠성⁠화';

  @override
  String homePassActiveNamed(String name) {
    return '$name 이⁠용 중';
  }

  @override
  String homePassPendingNamed(String name) {
    return '$name 구⁠매 완⁠료 · 탭⁠하⁠여 활⁠성⁠화';
  }

  @override
  String homePassActiveCount(int count) {
    return '패⁠스 $count⁠개 이⁠용 중';
  }

  @override
  String homePassPendingCount(int count) {
    return '패⁠스 $count⁠개 구⁠매 완⁠료 · 탭⁠하⁠여 활⁠성⁠화';
  }

  @override
  String get homeNearby => '근⁠처 미⁠술⁠관';

  @override
  String get homeMuseums => '박⁠물⁠관·미⁠술⁠관';

  @override
  String get homeEnableLocation => '위⁠치⁠를 켜⁠면 가⁠까⁠운 미⁠술⁠관⁠을 보⁠여 드⁠려⁠요';

  @override
  String get homeNoMuseumNearby => '근⁠처⁠에 아⁠직 수⁠록⁠된 미⁠술⁠관⁠이 없⁠어⁠요';

  @override
  String get homeContinue => '이⁠어⁠서 보⁠기';

  @override
  String get statusOpen => '개⁠관 중';

  @override
  String get exploreTitle => '탐⁠색';

  @override
  String get searchCityMuseumArtwork => '도⁠시, 미⁠술⁠관 또⁠는 작⁠품 검⁠색';

  @override
  String get searchMuseumsSection => '박⁠물⁠관';

  @override
  String get searchArtworksSection => '작⁠품';

  @override
  String get searchNoResults => '결⁠과 없⁠음';

  @override
  String museumCount(Object count) {
    return '미⁠술⁠관 $count⁠곳';
  }

  @override
  String get noMuseums => '미⁠술⁠관⁠이 없⁠습⁠니⁠다';

  @override
  String get noMatchedMuseums => '일⁠치⁠하⁠는 미⁠술⁠관⁠이 없⁠습⁠니⁠다';

  @override
  String artworkCountLabel(Object count) {
    return '작⁠품 $count⁠점';
  }

  @override
  String recordedCount(Object count) {
    return '소⁠장 $count⁠점';
  }

  @override
  String museumCatalogNumbers(Object catalog, Object archive) {
    return '온⁠라⁠인 도⁠록 $catalog⁠점 · 아⁠카⁠이⁠브 $archive⁠건 (인⁠식/검⁠색 가⁠능)';
  }

  @override
  String get noArtworks => '작⁠품⁠이 없⁠습⁠니⁠다';

  @override
  String loadingShown(Object shown, Object total) {
    return '불⁠러⁠오⁠는 중 · $shown/$total 표⁠시';
  }

  @override
  String allLoaded(Object total) {
    return '모⁠두 불⁠러⁠옴 · 총 $total⁠점';
  }

  @override
  String get guideVoiceGuide => '오⁠디⁠오 가⁠이⁠드';

  @override
  String get guideGenFailed => '해⁠설 생⁠성 실⁠패';

  @override
  String get guideWriting => '해⁠설⁠을 작⁠성 중…';

  @override
  String get guideHighlight => '감⁠상 포⁠인⁠트';

  @override
  String get guideQa => 'Q&A';

  @override
  String get guideThinking => '생⁠각 중…';

  @override
  String get guideQ1 => '이 그⁠림⁠의 특⁠별⁠한 점⁠은?';

  @override
  String get guideQ2 => '그⁠때 작⁠가⁠는 무⁠엇⁠을 겪⁠고 있⁠었⁠나⁠요?';

  @override
  String get guideAskHint => '이 그⁠림⁠에 대⁠해 질⁠문…';

  @override
  String get guideAskShort => '이 그⁠림⁠에 대⁠해 질⁠문';

  @override
  String get guideVoiceComingSoon => '음⁠성 Q&A⁠는 곧 제⁠공⁠됩⁠니⁠다. 지⁠금⁠은 입⁠력⁠하⁠세⁠요';

  @override
  String get guideGenerating => '콘⁠텐⁠츠 생⁠성 중 · 약 1~3⁠분';

  @override
  String get guideEmpty => '아⁠직 근⁠거 있⁠는 해⁠설⁠이 없⁠습⁠니⁠다 (준⁠비 중)';

  @override
  String get guideInfo => '작⁠품 정⁠보';

  @override
  String get guideStandardTour => '표⁠준 투⁠어';

  @override
  String get guideListen => '듣⁠기';

  @override
  String get guideDiveIn => '더 알⁠고 싶⁠나⁠요? 아⁠래⁠를 탭';

  @override
  String get guideDeepContent => '자⁠세⁠히';

  @override
  String get guideAskPlaceholder => '무⁠엇⁠이⁠든 질⁠문…';

  @override
  String get guideArtist => '작⁠가';

  @override
  String get guideArtistTab => '작⁠가';

  @override
  String get guideNotableWorks => '대⁠표⁠작';

  @override
  String get guideNoAnswer => '(답⁠변 없⁠음)';

  @override
  String get guideAnswerFailed => '답⁠변 실⁠패, 나⁠중⁠에 다⁠시 시⁠도⁠하⁠세⁠요.';

  @override
  String get factInventory => '소⁠장 번⁠호';

  @override
  String get factLocation => '위⁠치';

  @override
  String get factProvenance => '출⁠처';

  @override
  String get factExhibitions => '전⁠시';

  @override
  String get factBibliography => '참⁠고 문⁠헌';

  @override
  String get factArtist => '작⁠가';

  @override
  String get factNone => '상⁠세 정⁠보 없⁠음';

  @override
  String get footprintTitle => '발⁠자⁠취';

  @override
  String get footprintNoMuseum => '장⁠소 미⁠상';

  @override
  String get noFootprints => '발⁠자⁠취⁠가 없⁠습⁠니⁠다';

  @override
  String footprintStat(Object count, Object days) {
    return '작⁠품 $count⁠점 · $days⁠일';
  }

  @override
  String get footprintLoadFailed => '발⁠자⁠취 불⁠러⁠오⁠기 실⁠패';

  @override
  String get footprintEmptyHint => '인⁠식⁠한 작⁠품⁠은 여⁠기⁠에 자⁠동⁠으⁠로 기⁠록⁠됩⁠니⁠다';

  @override
  String get footprintGoRecognize => '첫 작⁠품⁠을 인⁠식⁠하⁠세⁠요';

  @override
  String itemsCount(Object count) {
    return '작⁠품 $count⁠점';
  }

  @override
  String ticketDurationDays(String days) {
    return '$days⁠일';
  }

  @override
  String yearBefore(String year) {
    return '$year⁠년 이⁠전';
  }

  @override
  String yearAfter(String year) {
    return '$year⁠년 이⁠후';
  }

  @override
  String yearBce(String year) {
    return '기⁠원⁠전 $year⁠년';
  }

  @override
  String get today => '오⁠늘';

  @override
  String get yesterday => '어⁠제';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$month/$day';
  }

  @override
  String dateYearMonthDay(Object day, Object month, Object year) {
    return '$year/$month/$day';
  }

  @override
  String get deleteFootprintQ => '이 발⁠자⁠취⁠를 삭⁠제⁠할⁠까⁠요?';

  @override
  String get settingsTitle => '설⁠정';

  @override
  String get secGeneral => '일⁠반';

  @override
  String get guideLanguage => '가⁠이⁠드 언⁠어';

  @override
  String get offlinePacks => '오⁠프⁠라⁠인 미⁠술⁠관 팩';

  @override
  String get autoSavePhoto => '사⁠진 자⁠동 저⁠장';

  @override
  String get autoSavePhotoNeedsAccess =>
      '사⁠진⁠을 저⁠장⁠하⁠려⁠면 사⁠진 보⁠관⁠함 접⁠근 권⁠한⁠이 필⁠요⁠합⁠니⁠다';

  @override
  String get secAccount => '계⁠정';

  @override
  String get secSupport => '지⁠원 및 법⁠적 고⁠지';

  @override
  String get encourageUs => '응⁠원⁠하⁠기';

  @override
  String get appStoreRating => 'App Store 평⁠가';

  @override
  String get privacyPolicy => '개⁠인⁠정⁠보 처⁠리⁠방⁠침';

  @override
  String get freeQuota => '무⁠료 스⁠캔 한⁠도';

  @override
  String quotaValue(Object remain, Object total) {
    return '$remain / $total 남⁠음';
  }

  @override
  String get upgrade => '업⁠그⁠레⁠이⁠드';

  @override
  String get loginBind => '로⁠그⁠인 / 계⁠정 연⁠결';

  @override
  String get notLoggedIn => '로⁠그⁠인⁠되⁠지 않⁠음';

  @override
  String get userDefault => '사⁠용⁠자';

  @override
  String get guestPrefix => '게⁠스⁠트_';

  @override
  String get noEmailBound => '연⁠결⁠된 이⁠메⁠일 없⁠음';

  @override
  String get logout => '로⁠그⁠아⁠웃';

  @override
  String get deleteAccount => '계⁠정 삭⁠제';

  @override
  String get loadingShort => '불⁠러⁠오⁠는 중…';

  @override
  String get appearance => '화⁠면';

  @override
  String get themeLight => '라⁠이⁠트';

  @override
  String get themeDark => '다⁠크';

  @override
  String get themeSystem => '시⁠스⁠템';

  @override
  String featureComingSoon(String feature) {
    return '$feature 곧 제⁠공';
  }

  @override
  String get privacyLinkCopied => '링⁠크⁠가 복⁠사⁠되⁠었⁠습⁠니⁠다';

  @override
  String get deleteAccountQ => '계⁠정⁠을 영⁠구 삭⁠제⁠할⁠까⁠요?';

  @override
  String get deleteAccountBody =>
      '계⁠정 프⁠로⁠필⁠과 남⁠은 한⁠도⁠가 삭⁠제⁠됩⁠니⁠다. 이 작⁠업⁠은 되⁠돌⁠릴 수 없⁠습⁠니⁠다.';

  @override
  String get deleteAccountBodyPass =>
      '구⁠매⁠한 패⁠스⁠는 즉⁠시 무⁠효⁠가 되⁠며 복⁠원⁠할 수 없⁠습⁠니⁠다. 다⁠시 가⁠입⁠해⁠도 돌⁠아⁠오⁠지 않⁠으⁠므⁠로 새⁠로 구⁠매⁠해⁠야 합⁠니⁠다.';

  @override
  String get permanentDelete => '영⁠구 삭⁠제';

  @override
  String get deleteFailed => '삭⁠제 실⁠패, 나⁠중⁠에 다⁠시 시⁠도⁠하⁠세⁠요';

  @override
  String get confirmLogout => '로⁠그⁠아⁠웃 확⁠인';

  @override
  String get confirmLogoutBody => '정⁠말 로⁠그⁠아⁠웃⁠하⁠시⁠겠⁠습⁠니⁠까?';

  @override
  String get confirmYes => '확⁠인';

  @override
  String get authEmailHint => '이⁠메⁠일';

  @override
  String get authEmailRequired => '이⁠메⁠일⁠을 입⁠력⁠하⁠세⁠요';

  @override
  String get authEmailInvalid => '유⁠효⁠한 이⁠메⁠일⁠을 입⁠력⁠하⁠세⁠요';

  @override
  String get authPasswordHint => '비⁠밀⁠번⁠호';

  @override
  String get authPasswordRequired => '비⁠밀⁠번⁠호⁠를 입⁠력⁠하⁠세⁠요';

  @override
  String get authPasswordMin8 => '비⁠밀⁠번⁠호⁠는 8⁠자 이⁠상⁠이⁠어⁠야 합⁠니⁠다';

  @override
  String get authConfirmPasswordHint => '비⁠밀⁠번⁠호 확⁠인';

  @override
  String get authPasswordMismatch => '비⁠밀⁠번⁠호⁠가 일⁠치⁠하⁠지 않⁠습⁠니⁠다';

  @override
  String get authUsernameOptionalHint => '사⁠용⁠자 이⁠름 (선⁠택)';

  @override
  String get authLoginButton => '로⁠그⁠인';

  @override
  String get authRegisterButton => '가⁠입';

  @override
  String get authForgotPassword => '비⁠밀⁠번⁠호⁠를 잊⁠으⁠셨⁠나⁠요?';

  @override
  String get authResetTitle => '비⁠밀⁠번⁠호 재⁠설⁠정';

  @override
  String get authResetPrompt =>
      '가⁠입⁠할 때 사⁠용⁠한 이⁠메⁠일⁠을 입⁠력⁠하⁠세⁠요. 새 비⁠밀⁠번⁠호⁠를 설⁠정⁠할 수 있⁠는 링⁠크⁠를 보⁠내⁠드⁠립⁠니⁠다.';

  @override
  String get authResetSend => '링⁠크 보⁠내⁠기';

  @override
  String get authResetSent =>
      '해⁠당 이⁠메⁠일⁠이 등⁠록⁠되⁠어 있⁠다⁠면 링⁠크⁠가 발⁠송⁠되⁠었⁠습⁠니⁠다. 스⁠팸⁠함⁠도 확⁠인⁠해 보⁠세⁠요.';

  @override
  String get authResetFailed =>
      '이⁠메⁠일⁠을 보⁠내⁠지 못⁠했⁠습⁠니⁠다. 잠⁠시 후 다⁠시 시⁠도⁠해 주⁠세⁠요.';

  @override
  String get authNoAccount => '계⁠정⁠이 없⁠나⁠요? 가⁠입';

  @override
  String get authHaveAccount => '계⁠정⁠이 있⁠나⁠요? 로⁠그⁠인';

  @override
  String get authCreateAccount => '계⁠정 만⁠들⁠기';

  @override
  String get authGoogleLogin => 'Google⁠로 로⁠그⁠인';

  @override
  String get authAppleLogin => 'Apple⁠로 로⁠그⁠인';

  @override
  String get authOr => '또⁠는';

  @override
  String get authGuestLogin => '게⁠스⁠트⁠로 계⁠속';

  @override
  String get authLoginFailed => '로⁠그⁠인 실⁠패, 이⁠메⁠일⁠과 비⁠밀⁠번⁠호⁠를 확⁠인⁠하⁠세⁠요';

  @override
  String get authRegisterFailed => '가⁠입 실⁠패, 이⁠메⁠일⁠이 이⁠미 사⁠용 중⁠일 수 있⁠습⁠니⁠다';

  @override
  String get authGoogleCancelled => 'Google 로⁠그⁠인⁠이 취⁠소⁠되⁠었⁠습⁠니⁠다';

  @override
  String get authGoogleFailed => 'Google 로⁠그⁠인 실⁠패, 다⁠시 시⁠도⁠하⁠세⁠요';

  @override
  String get authGoogleError => 'Google 로⁠그⁠인 오⁠류';

  @override
  String get authGoogleNotConfigured =>
      'Google 로⁠그⁠인⁠이 설⁠정⁠되⁠지 않⁠았⁠습⁠니⁠다. 관⁠리⁠자⁠에⁠게 문⁠의⁠하⁠세⁠요';

  @override
  String get authGoogleNetworkError =>
      'Google 로⁠그⁠인 네⁠트⁠워⁠크 오⁠류, 연⁠결⁠을 확⁠인⁠하⁠세⁠요';

  @override
  String get authAppleOnlyApple => 'Apple 로⁠그⁠인⁠은 iOS⁠와 macOS⁠에⁠서⁠만 지⁠원⁠됩⁠니⁠다';

  @override
  String get authAppleCancelled => 'Apple 로⁠그⁠인⁠이 취⁠소⁠되⁠었⁠습⁠니⁠다';

  @override
  String get authAppleFailed => 'Apple 로⁠그⁠인 실⁠패, 다⁠시 시⁠도⁠하⁠세⁠요';

  @override
  String get authAppleError => 'Apple 로⁠그⁠인 오⁠류';

  @override
  String get authAppleNotConfigured => 'Apple 로⁠그⁠인⁠이 설⁠정⁠되⁠지 않⁠았⁠습⁠니⁠다';

  @override
  String get authGuestFailed => '게⁠스⁠트 로⁠그⁠인 실⁠패, 다⁠시 시⁠도⁠하⁠세⁠요';

  @override
  String get authGuestError => '게⁠스⁠트 로⁠그⁠인 오⁠류';

  @override
  String get recCandidatesTitle => '이 작⁠품⁠인⁠가⁠요?';

  @override
  String get recNoneOfThese => '모⁠두 아⁠님';

  @override
  String get recThisIsIt => '이 작⁠품⁠이⁠에⁠요';

  @override
  String get recNotRecognized => '인⁠식⁠하⁠지 못⁠했⁠습⁠니⁠다';

  @override
  String get recNotInCatalog => '작⁠품⁠을 찾⁠지 못⁠했⁠습⁠니⁠다';

  @override
  String get recShootLabelBtn => '설⁠명⁠판 촬⁠영';

  @override
  String get recTypeNumberOrName => '번⁠호·작⁠품⁠명';

  @override
  String get photoFbTitle => '이 사⁠진⁠을 보⁠내 주⁠시⁠겠⁠어⁠요?';

  @override
  String get photoFbBody =>
      '빠⁠진 작⁠품 추⁠가⁠와 인⁠식 개⁠선⁠에⁠만 써⁠요. 최⁠대 90⁠일 보⁠관⁠하⁠며 공⁠개⁠하⁠지 않⁠아⁠요.';

  @override
  String get photoFbConsent => '이 사⁠진 보⁠내⁠기';

  @override
  String get photoFbNoteHint => '메⁠모 추⁠가(선⁠택)';

  @override
  String get photoFbContinue => '계⁠속';

  @override
  String get recSearchWithLabel => '이 텍⁠스⁠트⁠로 검⁠색';

  @override
  String get recViewfinderLabelHint => '설⁠명⁠판 글⁠자⁠를 화⁠면⁠에 가⁠득 채⁠우⁠세⁠요';

  @override
  String get camRecognizeTitle => '작⁠품 식⁠별';

  @override
  String get camViewfinderHint =>
      '작⁠품 전⁠체⁠를 화⁠면⁠에 담⁠으⁠세⁠요\n넓⁠은 작⁠품⁠은 가⁠로⁠로 찍⁠으⁠세⁠요';

  @override
  String get camRecentGallery => '최⁠근';

  @override
  String get camAllAlbums => '모⁠든 앨⁠범';

  @override
  String get camGallery => '갤⁠러⁠리';

  @override
  String get camSearch => '검⁠색';

  @override
  String get guideUnavailable => '이 작⁠품⁠은 아⁠직 이 언⁠어⁠로 된 가⁠이⁠드⁠가 없⁠습⁠니⁠다';

  @override
  String get guideNotGenerated => '아⁠직 가⁠이⁠드⁠가 생⁠성⁠되⁠지 않⁠았⁠습⁠니⁠다';

  @override
  String get guideDailyCap =>
      '오⁠늘⁠의 가⁠이⁠드 생⁠성 한⁠도⁠에 도⁠달⁠했⁠습⁠니⁠다. 내⁠일 다⁠시 확⁠인⁠해 주⁠세⁠요';

  @override
  String get audioNotReady => '해⁠설 생⁠성 후 들⁠을 수 있⁠습⁠니⁠다';

  @override
  String get audioFailed => '오⁠디⁠오⁠를 사⁠용⁠할 수 없⁠습⁠니⁠다. 다⁠시 시⁠도⁠하⁠세⁠요';

  @override
  String get deepGenerating => '심⁠층 콘⁠텐⁠츠 생⁠성 중…';

  @override
  String get camNoCamera => '사⁠용 가⁠능⁠한 카⁠메⁠라⁠가 없⁠습⁠니⁠다';

  @override
  String get camInitFailed => '카⁠메⁠라 초⁠기⁠화 실⁠패';

  @override
  String get camTagSearch => '설⁠명⁠판 검⁠색';

  @override
  String get camTagHint =>
      '촬⁠영 불⁠가 구⁠역⁠에⁠서⁠는 설⁠명⁠판 번⁠호, 제⁠목 또⁠는 작⁠가⁠를 입⁠력⁠하⁠세⁠요';

  @override
  String get camTagExample => '예: INV 3692 / 침⁠실';

  @override
  String get camPackComingSoon => '컬⁠렉⁠션 검⁠색⁠은 오⁠프⁠라⁠인 팩 제⁠공 후 이⁠용 가⁠능';

  @override
  String get camQuotaUsedUp => '무⁠료 스⁠캔⁠을 모⁠두 사⁠용⁠했⁠습⁠니⁠다';

  @override
  String get camUpgradeHint => '업⁠그⁠레⁠이⁠드⁠하⁠여 미⁠술⁠관 전⁠체⁠에⁠서 계⁠속 감⁠상⁠하⁠세⁠요';

  @override
  String get camViewUpgrade => '요⁠금⁠제 보⁠기';

  @override
  String get camCantPhoto => '촬⁠영⁠할 수 없⁠나⁠요? 설⁠명⁠판 번⁠호⁠를 입⁠력⁠하⁠세⁠요';

  @override
  String get camRecognizing => '인⁠식 중…';

  @override
  String get camComparing => 'AI⁠가 소⁠장⁠품·미⁠술 DB⁠와 대⁠조 중';

  @override
  String get recWaitSlow => '평⁠소⁠보⁠다 오⁠래 걸⁠려⁠요. 계⁠속 찾⁠는 중';

  @override
  String get recWaitSwitchApp =>
      '다⁠른 앱⁠으⁠로 전⁠환⁠해⁠도 괜⁠찮⁠아⁠요. 돌⁠아⁠오⁠면 결⁠과⁠가 그⁠대⁠로 있⁠어⁠요';

  @override
  String get camConfirmPrompt => '인⁠식 완⁠료, 작⁠품⁠을 확⁠인⁠하⁠세⁠요';

  @override
  String get camConfidence => '신⁠뢰⁠도';

  @override
  String get camConfirmStart => '확⁠인⁠하⁠고 가⁠이⁠드 시⁠작';

  @override
  String get camNoneSearch => '해⁠당 없⁠음? 제⁠목⁠이⁠나 설⁠명⁠판 번⁠호⁠로 검⁠색 →';

  @override
  String get camRecognizeFailed => '인⁠식 실⁠패';

  @override
  String get camRetake => '다⁠시 촬⁠영';

  @override
  String get museumCoverTab => '표⁠지';

  @override
  String get museumCollectionTab => '컬⁠렉⁠션';

  @override
  String get museumTabMustSee => '필⁠수 작⁠품';

  @override
  String passportTitle(String museum) {
    return '$museum · 필⁠수 작⁠품';
  }

  @override
  String passportStamped(int done, int total) {
    return '도⁠장 $done / $total';
  }

  @override
  String passportRoundSince(String date) {
    return '$date⁠부⁠터';
  }

  @override
  String get passportRoundDone => '이⁠번⁠엔 모⁠두 봤⁠어⁠요 ✓';

  @override
  String get passportSealTitle => '완⁠주';

  @override
  String get passportShare => '이 페⁠이⁠지 공⁠유';

  @override
  String get passportMedals => '내 메⁠달';

  @override
  String get passportNoLocation => '전⁠시⁠실 정⁠보 없⁠음';

  @override
  String get passportSignInHint => '로⁠그⁠인⁠하⁠고 현⁠장⁠에⁠서 작⁠품⁠을 찍⁠으⁠면 도⁠장⁠이 찍⁠혀⁠요';

  @override
  String passportLevel(int level) {
    return '$level⁠층';
  }

  @override
  String passportBasement(int n) {
    return '지⁠하 $n⁠층';
  }

  @override
  String passportRoom(String room) {
    return '$room 전⁠시⁠실';
  }

  @override
  String mustSeeToastStamped(int done, int total) {
    return '도⁠장 쾅! 필⁠수 작⁠품 $done / $total';
  }

  @override
  String mustSeeToastDone(int total) {
    return '필⁠수 작⁠품 완⁠주 $total / $total';
  }

  @override
  String passportShareText(String museum, int total, String date) {
    return '$museum⁠의 필⁠수 작⁠품 $total⁠점⁠을 모⁠두 봤⁠어⁠요($date). GoMuseum⁠으⁠로 완⁠주.';
  }

  @override
  String get museumOpeningHours => '운⁠영 시⁠간';

  @override
  String get museumOfficialSite => '공⁠식 웹⁠사⁠이⁠트';

  @override
  String get museumIntroComingSoon => '박⁠물⁠관 소⁠개 준⁠비 중⁠입⁠니⁠다';

  @override
  String paywallTitle(String label, String days) {
    return '$label $days⁠일 패⁠스';
  }

  @override
  String paywallPitch(String museums) {
    return '사⁠진 인⁠식 무⁠제⁠한, $museums⁠의 음⁠성 해⁠설⁠을 들⁠을 수 있⁠습⁠니⁠다.';
  }

  @override
  String get paywallPitchGeneric => '사⁠진 인⁠식 무⁠제⁠한, 음⁠성 해⁠설⁠을 들⁠을 수 있⁠습⁠니⁠다.';

  @override
  String get passNotOnSale => '이 미⁠술⁠관⁠의 패⁠스⁠는 아⁠직 판⁠매⁠하⁠지 않⁠습⁠니⁠다.';

  @override
  String get paywallFreeAlways =>
      '둘⁠러⁠보⁠기, 검⁠색, 전⁠체 텍⁠스⁠트 해⁠설⁠은 언⁠제⁠나 무⁠료⁠입⁠니⁠다.';

  @override
  String get paywallBuy => '패⁠스 구⁠매';

  @override
  String get paywallRestore => '결⁠제⁠했⁠는⁠데 패⁠스⁠가 없⁠나⁠요?';

  @override
  String get restoreInProgress => '복⁠원 중…';

  @override
  String get restoreNothingFound => '미⁠완⁠료 결⁠제⁠를 찾⁠지 못⁠했⁠습⁠니⁠다';

  @override
  String get restoreSucceeded => '패⁠스⁠를 복⁠원⁠했⁠습⁠니⁠다';

  @override
  String get audioFreePreview => '무⁠료 체⁠험';

  @override
  String audioLockedHint(String days) {
    return '음⁠성 해⁠설⁠은 패⁠스⁠가 필⁠요⁠합⁠니⁠다. 사⁠진⁠으⁠로 인⁠식⁠한 작⁠품⁠은 $days⁠일 동⁠안 무⁠료⁠로 들⁠을 수 있⁠습⁠니⁠다.';
  }

  @override
  String audioFreePreviewDays(String days) {
    return '무⁠료 청⁠취 · $days⁠일 남⁠음';
  }

  @override
  String get audioFreeExpiredHint =>
      '이 작⁠품⁠의 무⁠료 청⁠취⁠가 끝⁠났⁠습⁠니⁠다. 계⁠속 들⁠으⁠려⁠면 패⁠스⁠가 필⁠요⁠합⁠니⁠다.';

  @override
  String get audioPassExpiredHint =>
      '패⁠스⁠가 만⁠료⁠되⁠었⁠습⁠니⁠다. 계⁠속 들⁠으⁠려⁠면 새 패⁠스⁠를 구⁠매⁠하⁠세⁠요.';

  @override
  String get quotaExhausted => '무⁠료 인⁠식 횟⁠수⁠를 모⁠두 사⁠용⁠했⁠습⁠니⁠다.';

  @override
  String get activateLater => '나⁠중⁠에';

  @override
  String get paywallLoginToBuy => '로⁠그⁠인 후 구⁠매';

  @override
  String get paywallLoginWhy => '패⁠스⁠는 계⁠정⁠에 연⁠결⁠되⁠어 새 휴⁠대⁠폰⁠에⁠서⁠도 유⁠지⁠됩⁠니⁠다.';

  @override
  String get passActive => '패⁠스 사⁠용 중';

  @override
  String passExpiresOn(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return '$dateString 만⁠료';
  }

  @override
  String get passPendingActivation => '구⁠매⁠함 · 미⁠활⁠성⁠화';

  @override
  String get passActivateHint => '첫 재⁠생 시 시⁠작⁠됩⁠니⁠다';

  @override
  String get viewBenefits => '혜⁠택 보⁠기';

  @override
  String get unlimited => '무⁠제⁠한';

  @override
  String get paywallPriceNote => '1⁠회 결⁠제 · 구⁠독 아⁠님';

  @override
  String get paywallClockHead => '구⁠매 시⁠점⁠에⁠는 시⁠간⁠이 흐⁠르⁠지 않⁠습⁠니⁠다';

  @override
  String paywallClockBody(String days) {
    return '프⁠리⁠미⁠엄 기⁠능⁠을 처⁠음 사⁠용⁠하⁠고 확⁠인⁠한 때⁠부⁠터 $days⁠일⁠이 시⁠작⁠됩⁠니⁠다. 미⁠리 사 두⁠고 미⁠술⁠관⁠에⁠서 시⁠작⁠하⁠세⁠요.';
  }

  @override
  String get paywallLapseNote =>
      '활⁠성⁠화⁠하⁠지 않⁠은 패⁠스⁠는 구⁠매 후 30⁠일⁠이 지⁠나⁠면 만⁠료⁠됩⁠니⁠다.';

  @override
  String get ticketStub => '반⁠권';

  @override
  String get ticketStubPending => '만⁠료⁠일 미⁠기⁠재';

  @override
  String get ticketStubUntorn => '미⁠사⁠용';

  @override
  String get ticketValidUntil => '유⁠효 기⁠간';

  @override
  String ticketDateTime(DateTime date, DateTime time) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);
    final intl.DateFormat timeDateFormat = intl.DateFormat.Hm(localeName);
    final String timeString = timeDateFormat.format(time);

    return '$dateString $timeString';
  }

  @override
  String ticketDaysLeft(int days) {
    return '$days⁠일 남⁠음';
  }

  @override
  String activateSheetTitle(String days) {
    return '지⁠금 $days⁠일⁠을 시⁠작⁠할⁠까⁠요?';
  }

  @override
  String activateSheetBody(DateTime date, DateTime time) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);
    final intl.DateFormat timeDateFormat = intl.DateFormat.Hm(localeName);
    final String timeString = timeDateFormat.format(time);

    return '확⁠인⁠하⁠면 시⁠간⁠이 시⁠작⁠되⁠어 $dateString $timeString⁠에 종⁠료⁠됩⁠니⁠다. 되⁠돌⁠릴 수 없⁠습⁠니⁠다.';
  }

  @override
  String get activateTear => '뜯⁠고 시⁠작⁠하⁠기';

  @override
  String get activateWaiting => '확⁠인⁠하⁠는 중…';

  @override
  String get activateWaitingNote =>
      '티⁠켓⁠은 아⁠직 뜯⁠지 않⁠았⁠습⁠니⁠다. 확⁠인⁠된 뒤⁠에 시⁠작⁠됩⁠니⁠다';

  @override
  String get activateDoneTitle => '패⁠스⁠가 시⁠작⁠되⁠었⁠습⁠니⁠다';

  @override
  String get activateDoneBody => '음⁠성 해⁠설⁠과 무⁠제⁠한 인⁠식⁠이 열⁠렸⁠습⁠니⁠다.';

  @override
  String get activateDoneCta => '계⁠속';

  @override
  String get activateFailTitle => '확⁠인⁠하⁠지 못⁠했⁠습⁠니⁠다. 티⁠켓⁠은 사⁠용⁠되⁠지 않⁠았⁠습⁠니⁠다';

  @override
  String activateFailBody(String days) {
    return '연⁠결⁠되⁠지 않⁠아 $days⁠일⁠이 시⁠작⁠되⁠지 않⁠았⁠습⁠니⁠다. 패⁠스⁠는 그⁠대⁠로⁠입⁠니⁠다. 다⁠시 시⁠도⁠하⁠세⁠요.';
  }

  @override
  String get activateRetry => '다⁠시 시⁠도';

  @override
  String get benefitsMyPass => '내 패⁠스';

  @override
  String get benefitsSecFreeQuota => '무⁠료 이⁠용⁠량';

  @override
  String get benefitsSecFeatures => '기⁠능';

  @override
  String get benefitsSecBuyable => '구⁠매 가⁠능';

  @override
  String get benefitsSecIncluded => '포⁠함 사⁠항';

  @override
  String get benefitsSecUnlocked => '잠⁠금 해⁠제⁠됨';

  @override
  String get benefitsSecPurchases => '구⁠매 내⁠역';

  @override
  String get benefitsSecCurrentQuota => '현⁠재 이⁠용⁠량';

  @override
  String get benefitsSecBuyAnother => '한 장 더';

  @override
  String benefitsOtherCities(int count) {
    return '다⁠른 도⁠시 ($count)';
  }

  @override
  String get passExchangeLink => '도⁠시⁠를 잘⁠못 골⁠랐⁠나⁠요? 교⁠환⁠하⁠기';

  @override
  String get passExchangeSheetTitle => '다⁠른 도⁠시 패⁠스⁠로 교⁠환';

  @override
  String get passExchangeSheetBody =>
      '아⁠직 시⁠작⁠하⁠지 않⁠은 패⁠스⁠는 같⁠은 가⁠격⁠의 다⁠른 도⁠시 패⁠스⁠로 무⁠료 교⁠환⁠할 수 있⁠습⁠니⁠다. 활⁠성⁠화 기⁠한⁠은 그⁠대⁠로⁠입⁠니⁠다.';

  @override
  String passExchangeTo(String title) {
    return '$title(으)로 교⁠환';
  }

  @override
  String passExchangeDone(String title) {
    return '$title(으)로 교⁠환⁠했⁠습⁠니⁠다';
  }

  @override
  String get passExchangeFailed =>
      '교⁠환⁠하⁠지 못⁠했⁠습⁠니⁠다. 패⁠스⁠는 그⁠대⁠로⁠입⁠니⁠다. 잠⁠시 후 다⁠시 시⁠도⁠해 주⁠세⁠요';

  @override
  String get benefitsRecognition => '사⁠진 인⁠식';

  @override
  String get benefitsFreeAudioNote =>
      '촬⁠영⁠해⁠서 인⁠식⁠한 작⁠품⁠은 주⁠요 음⁠성 해⁠설⁠을 무⁠료⁠로 들⁠을 수 있⁠습⁠니⁠다. 그 밖⁠의 작⁠품⁠도 무⁠료 횟⁠수 1⁠회⁠로 잠⁠금 해⁠제⁠할 수 있⁠습⁠니⁠다.';

  @override
  String get benefitsFeatBrowse => '둘⁠러⁠보⁠기, 검⁠색, 텍⁠스⁠트 해⁠설 전⁠문';

  @override
  String get benefitsFeatPresetQa => '추⁠천 질⁠문⁠에 대⁠한 답⁠변';

  @override
  String get benefitsFeatRecognition => '무⁠제⁠한 사⁠진 인⁠식';

  @override
  String get benefitsFeatAllAudio => '패⁠스⁠에 포⁠함⁠된 미⁠술⁠관⁠의 음⁠성 해⁠설';

  @override
  String get benefitsFeatDeepAudio => '심⁠화 콘⁠텐⁠츠 음⁠성';

  @override
  String get benefitsNeedsPass => '패⁠스 필⁠요';

  @override
  String get benefitsNotStartedHead => '아⁠직 시⁠간⁠이 시⁠작⁠되⁠지 않⁠았⁠습⁠니⁠다';

  @override
  String get benefitsPassNotActivated => '미⁠활⁠성';

  @override
  String get benefitsPassStartsOnFirstUse => '박⁠물⁠관⁠에⁠서 처⁠음 사⁠용⁠할 때 시⁠작⁠됩⁠니⁠다';

  @override
  String benefitsPassVoidAfter(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return '$dateString⁠까⁠지 활⁠성⁠화⁠하⁠지 않⁠으⁠면 만⁠료⁠됩⁠니⁠다';
  }

  @override
  String get benefitsOtherMuseumsRecognition => '다⁠른 박⁠물⁠관 사⁠진 인⁠식';

  @override
  String benefitsNotStartedBody(String days) {
    return '미⁠술⁠관⁠에⁠서 음⁠성 해⁠설⁠이⁠나 인⁠식⁠을 처⁠음 사⁠용⁠할 때 한 번 확⁠인⁠을 요⁠청⁠합⁠니⁠다. $days⁠일⁠은 그 순⁠간⁠부⁠터 시⁠작⁠됩⁠니⁠다.';
  }

  @override
  String benefitsStartNow(String days) {
    return '지⁠금 $days⁠일 시⁠작⁠하⁠기';
  }

  @override
  String get benefitsStartNowNote =>
      '아⁠직 미⁠술⁠관⁠이 아⁠니⁠라⁠면 도⁠착⁠한 뒤⁠에 시⁠작⁠하⁠는 편⁠이 좋⁠습⁠니⁠다';

  @override
  String benefitsExpiredBody(String days) {
    return '$days⁠일⁠이 모⁠두 지⁠났⁠습⁠니⁠다. 무⁠료 이⁠용⁠량⁠은 복⁠구⁠되⁠었⁠고 텍⁠스⁠트 해⁠설⁠은 그⁠대⁠로 전⁠부 볼 수 있⁠습⁠니⁠다.';
  }

  @override
  String benefitsPrevPass(DateTime start, DateTime end) {
    final intl.DateFormat startDateFormat = intl.DateFormat.yMMMd(localeName);
    final String startString = startDateFormat.format(start);
    final intl.DateFormat endDateFormat = intl.DateFormat.yMMMd(localeName);
    final String endString = endDateFormat.format(end);

    return '이⁠전 패⁠스 사⁠용 완⁠료 · $startString – $endString';
  }

  @override
  String get benefitsEndedAt => '종⁠료⁠일';

  @override
  String get benefitsLapsedHead => '이 패⁠스⁠는 사⁠용⁠이 시⁠작⁠되⁠지 않⁠았⁠습⁠니⁠다';

  @override
  String get benefitsLapsedBody =>
      '구⁠매 후 30⁠일 이⁠내⁠에 사⁠용⁠하⁠지 않⁠아 만⁠료⁠되⁠었⁠습⁠니⁠다. 무⁠료 횟⁠수⁠는 복⁠구⁠되⁠었⁠고, 텍⁠스⁠트 해⁠설⁠은 그⁠대⁠로 이⁠용⁠할 수 있⁠습⁠니⁠다.';

  @override
  String get benefitsBoughtOn => '구⁠매⁠일';

  @override
  String benefitsDateOnly(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return '$dateString';
  }

  @override
  String get edgeUnknownHead => '지⁠금⁠은 권⁠한⁠을 확⁠인⁠할 수 없⁠습⁠니⁠다';

  @override
  String get edgeUnknownBody =>
      '연⁠결⁠이 없⁠어 이⁠미 패⁠스⁠가 있⁠는⁠지 확⁠인⁠할 수 없⁠고, 구⁠매⁠도 안⁠전⁠하⁠게 시⁠작⁠할 수 없⁠습⁠니⁠다.';

  @override
  String get edgeUnknownNote =>
      '이⁠미 구⁠매⁠하⁠셨⁠다⁠면 온⁠라⁠인⁠에 연⁠결⁠되⁠는 즉⁠시 자⁠동⁠으⁠로 복⁠구⁠됩⁠니⁠다. 이⁠중⁠으⁠로 청⁠구⁠되⁠지 않⁠습⁠니⁠다.';

  @override
  String get edgeSignedOutHead => '패⁠스⁠는 계⁠정⁠에 연⁠결⁠됩⁠니⁠다';

  @override
  String get edgeSignedOutBody =>
      '로⁠그⁠인⁠한 뒤 구⁠매⁠하⁠면 기⁠기⁠를 바⁠꾸⁠거⁠나 재⁠설⁠치⁠해⁠도 잃⁠지 않⁠습⁠니⁠다.';

  @override
  String get edgeConflictTitle => '이 패⁠스⁠는 다⁠른 계⁠정⁠에 연⁠결⁠되⁠어 있⁠습⁠니⁠다';

  @override
  String get edgeConflictBody =>
      '이 구⁠매⁠는 다⁠른 GoMuseum 계⁠정⁠의 것⁠입⁠니⁠다. 하⁠나⁠의 패⁠스⁠를 두 계⁠정⁠이 함⁠께 쓸 수 없⁠어 여⁠기⁠서⁠는 복⁠구⁠할 수 없⁠습⁠니⁠다.';

  @override
  String get edgeConflictBound => '연⁠결⁠된 계⁠정';

  @override
  String get edgeConflictOther => '다⁠른 계⁠정';

  @override
  String get edgeConflictHelp =>
      '구⁠매⁠할 때 사⁠용⁠한 계⁠정⁠으⁠로 로⁠그⁠인⁠해 주⁠세⁠요. 어⁠떤 계⁠정⁠인⁠지 모⁠르⁠겠⁠거⁠나 잘⁠못⁠된 것 같⁠다⁠면 문⁠의⁠해 주⁠시⁠면 저⁠희⁠가 확⁠인⁠해 드⁠립⁠니⁠다.';

  @override
  String get edgeSwitchAccount => '계⁠정 전⁠환';

  @override
  String get edgeContactSupport => '문⁠의⁠하⁠기';

  @override
  String get drawerLockedHint =>
      '심⁠화 콘⁠텐⁠츠⁠의 음⁠성⁠에⁠는 패⁠스⁠가 필⁠요⁠합⁠니⁠다. 텍⁠스⁠트⁠는 모⁠두 무⁠료⁠입⁠니⁠다.';

  @override
  String get drawerLockedCta => '패⁠스 보⁠기';

  @override
  String get purchaseSuccess => '구⁠매⁠가 완⁠료⁠되⁠어 패⁠스⁠가 준⁠비⁠되⁠었⁠습⁠니⁠다.';

  @override
  String get purchaseVerifyPending =>
      '아⁠직 구⁠매⁠를 확⁠인⁠하⁠지 못⁠했⁠습⁠니⁠다. 앱⁠을 다⁠시 열⁠면 재⁠시⁠도⁠합⁠니⁠다.';

  @override
  String get purchaseFailed => '구⁠매⁠가 완⁠료⁠되⁠지 않⁠았⁠습⁠니⁠다. 다⁠시 시⁠도⁠해 주⁠세⁠요.';

  @override
  String get ticketPaid => '결⁠제 완⁠료';

  @override
  String get ticketVoid => '종⁠료⁠됨';

  @override
  String edgeSupportCopied(String email) {
    return '지⁠원 이⁠메⁠일⁠을 복⁠사⁠했⁠습⁠니⁠다: $email';
  }

  @override
  String get fbTitleObject => '내⁠용 신⁠고';

  @override
  String get fbTitleApp => '의⁠견 보⁠내⁠기';

  @override
  String get fbContentWrong => '내⁠용 오⁠류';

  @override
  String get fbAudioBad => '발⁠음⁠이 이⁠상⁠함';

  @override
  String get fbAudioMissing => '음⁠성 없⁠음';

  @override
  String get fbAppCrash => '앱 튕⁠김·버⁠벅⁠임';

  @override
  String get fbRecognitionBad => '인⁠식 부⁠정⁠확';

  @override
  String get fbFeatureRequest => '기⁠능 제⁠안';

  @override
  String get fbOther => '기⁠타';

  @override
  String get fbTextHint =>
      '더 알⁠려⁠주⁠실 내⁠용⁠이 있⁠나⁠요? (선⁠택 · 개⁠인⁠정⁠보⁠는 입⁠력⁠하⁠지 마⁠세⁠요)';

  @override
  String get fbSubmit => '보⁠내⁠기';

  @override
  String get fbThanks => '접⁠수⁠되⁠었⁠습⁠니⁠다. 감⁠사⁠합⁠니⁠다';

  @override
  String get fbFailed => '보⁠내⁠지 못⁠했⁠습⁠니⁠다. 연⁠결⁠을 확⁠인⁠해 주⁠세⁠요';

  @override
  String get fbRetry => '다⁠시 시⁠도';

  @override
  String get unlockAudioTitle => '무⁠료 횟⁠수⁠를 1⁠회 사⁠용⁠할⁠까⁠요?';

  @override
  String unlockAudioBody(int left) {
    return '이 작⁠품⁠의 음⁠성 해⁠설⁠을 잠⁠금 해⁠제⁠합⁠니⁠다. $left⁠회 남⁠게 됩⁠니⁠다.';
  }

  @override
  String get unlockAudioCta => '잠⁠금 해⁠제⁠하⁠고 재⁠생';

  @override
  String get guideShare => '공⁠유';

  @override
  String get authUseEmail => '이⁠메⁠일⁠로 로⁠그⁠인 / 가⁠입';

  @override
  String authConsent(String terms, String privacy) {
    return '계⁠속⁠하⁠면 $terms 및 $privacy⁠에 동⁠의⁠하⁠는 것⁠으⁠로 간⁠주⁠됩⁠니⁠다';
  }

  @override
  String get authTermsOfService => '서⁠비⁠스 약⁠관';

  @override
  String get authConsentPrivacy => '개⁠인⁠정⁠보 처⁠리⁠방⁠침';

  @override
  String get updateReady => '새 버⁠전⁠이 준⁠비⁠되⁠었⁠습⁠니⁠다';

  @override
  String get updateRestart => '다⁠시 시⁠작';

  @override
  String get collectionViewGrid => '큰 이⁠미⁠지⁠로 보⁠기';

  @override
  String get collectionViewList => '목⁠록⁠으⁠로 보⁠기';

  @override
  String get guideNotThisOne => '이 작⁠품⁠이 아⁠닌⁠가⁠요?';

  @override
  String get guideNotThisOneNoted =>
      '기⁠록⁠했⁠습⁠니⁠다. 다⁠른 각⁠도⁠로 다⁠시 찍⁠거⁠나 검⁠색⁠으⁠로 찾⁠아⁠보⁠세⁠요.';

  @override
  String get recMaybeNotCollected =>
      '특⁠별⁠전⁠이⁠거⁠나 미⁠수⁠록 작⁠품⁠일 수 있⁠어⁠요. 옆 설⁠명⁠판⁠을 찍⁠으⁠면 더 잘 인⁠식⁠돼⁠요.';

  @override
  String get recLabelNoMatch =>
      '특⁠별⁠전⁠이⁠거⁠나 미⁠수⁠록 작⁠품⁠일 수 있⁠어⁠요. 다⁠른 이⁠름⁠이⁠나 번⁠호⁠로 찾⁠아⁠보⁠세⁠요.';
}
