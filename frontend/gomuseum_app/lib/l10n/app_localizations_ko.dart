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
  String get explore => '탐색';

  @override
  String get capture => '카메라';

  @override
  String get footprints => '발자취';

  @override
  String get settings => '설정';

  @override
  String get navScan => '스캔';

  @override
  String get artworkRecognition => '작품 인식';

  @override
  String get takePhoto => '사진 촬영';

  @override
  String get chooseFromGallery => '갤러리에서 선택';

  @override
  String get selectImagePrompt => '작품을 인식할 이미지를 선택하세요';

  @override
  String get error => '오류';

  @override
  String get comingSoon => '곧 제공';

  @override
  String get comingSoonShort => '곧 제공';

  @override
  String get language => '언어';

  @override
  String get selectLanguage => '언어 선택';

  @override
  String get retry => '다시 시도';

  @override
  String get cancel => '취소';

  @override
  String get delete => '삭제';

  @override
  String get confirm => '확인';

  @override
  String get gotIt => '확인';

  @override
  String get loadFailed => '불러오기 실패';

  @override
  String get loadFailedRetry => '불러오기 실패, 다시 시도하세요';

  @override
  String get toBeRefined => '준비 중';

  @override
  String get viewAll => '모두 보기 →';

  @override
  String get all => '전체';

  @override
  String get homePocketGuide => '포켓 미술관 가이드';

  @override
  String get homeSlogan => '한 작품에 다가가\n그 이야기를 들어보세요.';

  @override
  String get homeCtaRecognize => '촬영해 인식하고 감상';

  @override
  String homeFreeLeft(Object count) {
    return '무료 스캔 $count회 남음 · 업그레이드로 전체 이용';
  }

  @override
  String get homeNearby => '근처 미술관';

  @override
  String get statusOpen => '개관 중';

  @override
  String get exploreTitle => '탐색';

  @override
  String get searchCityMuseumArtwork => '도시, 미술관 또는 작품 검색';

  @override
  String get searchMuseumsSection => '박물관';

  @override
  String get searchArtworksSection => '작품';

  @override
  String get searchNoResults => '결과 없음';

  @override
  String museumCount(Object count) {
    return '미술관 $count곳';
  }

  @override
  String get noMuseums => '미술관이 없습니다';

  @override
  String get noMatchedMuseums => '일치하는 미술관이 없습니다';

  @override
  String artworkCountLabel(Object count) {
    return '작품 $count점';
  }

  @override
  String recordedCount(Object count) {
    return '소장 $count점';
  }

  @override
  String museumCatalogNumbers(Object catalog, Object archive) {
    return '온라인 도록 $catalog점 · 아카이브 $archive건 (인식/검색 가능)';
  }

  @override
  String get noArtworks => '작품이 없습니다';

  @override
  String loadingShown(Object shown, Object total) {
    return '불러오는 중 · $shown/$total 표시';
  }

  @override
  String allLoaded(Object total) {
    return '모두 불러옴 · 총 $total점';
  }

  @override
  String get guideVoiceGuide => '오디오 가이드';

  @override
  String get guideGenFailed => '해설 생성 실패';

  @override
  String get guideWriting => '해설을 작성 중…';

  @override
  String get guideHighlight => '감상 포인트';

  @override
  String get guideQa => 'Q&A';

  @override
  String get guideThinking => '생각 중…';

  @override
  String get guideQ1 => '이 그림의 특별한 점은?';

  @override
  String get guideQ2 => '그때 작가는 무엇을 겪고 있었나요?';

  @override
  String get guideAskHint => '이 그림에 대해 질문…';

  @override
  String get guideAskShort => '이 그림에 대해 질문';

  @override
  String get guideVoiceComingSoon => '음성 Q&A는 곧 제공됩니다. 지금은 입력하세요';

  @override
  String get guideGenerating => '콘텐츠 생성 중 · 약 1~3분';

  @override
  String get guideEmpty => '아직 근거 있는 해설이 없습니다 (준비 중)';

  @override
  String get guideInfo => '작품 정보';

  @override
  String get guideStandardTour => '표준 투어';

  @override
  String get guideListen => '듣기';

  @override
  String get guideDiveIn => '더 알고 싶나요? 아래를 탭';

  @override
  String get guideDeepContent => '자세히';

  @override
  String get guideAskPlaceholder => '무엇이든 질문…';

  @override
  String get guideArtist => '작가';

  @override
  String get guideArtistTab => '작가';

  @override
  String get guideNotableWorks => '대표작';

  @override
  String get guideNoAnswer => '(답변 없음)';

  @override
  String get guideAnswerFailed => '답변 실패, 나중에 다시 시도하세요.';

  @override
  String get factInventory => '소장 번호';

  @override
  String get factLocation => '위치';

  @override
  String get factProvenance => '출처';

  @override
  String get factExhibitions => '전시';

  @override
  String get factBibliography => '참고 문헌';

  @override
  String get factArtist => '작가';

  @override
  String get factNone => '상세 정보 없음';

  @override
  String get footprintTitle => '발자취';

  @override
  String get noFootprints => '발자취가 없습니다';

  @override
  String footprintStat(Object count, Object days) {
    return '작품 $count점 · $days일';
  }

  @override
  String get footprintLoadFailed => '발자취 불러오기 실패';

  @override
  String get footprintEmptyHint => '인식한 작품은 여기에 자동으로 기록됩니다';

  @override
  String get footprintGoRecognize => '첫 작품을 인식하세요';

  @override
  String itemsCount(Object count) {
    return '작품 $count점';
  }

  @override
  String get today => '오늘';

  @override
  String get yesterday => '어제';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$month/$day';
  }

  @override
  String get deleteFootprintQ => '이 발자취를 삭제할까요?';

  @override
  String get settingsTitle => '설정';

  @override
  String get secGeneral => '일반';

  @override
  String get guideLanguage => '가이드 언어';

  @override
  String get offlinePacks => '오프라인 미술관 팩';

  @override
  String get autoSavePhoto => '사진 자동 저장';

  @override
  String get ttsVoice => 'TTS 음성';

  @override
  String get ttsVoiceValue => '차분함 · 여성';

  @override
  String get ttsVoiceSelect => '음성 선택';

  @override
  String get secAccount => '계정';

  @override
  String get secSupport => '지원 및 법적 고지';

  @override
  String get encourageUs => '응원하기';

  @override
  String get appStoreRating => 'App Store 평가';

  @override
  String get privacyPolicy => '개인정보 처리방침';

  @override
  String get freeQuota => '무료 스캔 한도';

  @override
  String quotaValue(Object remain, Object total) {
    return '$remain / $total 남음';
  }

  @override
  String get upgrade => '업그레이드';

  @override
  String get loginBind => '로그인 / 계정 연결';

  @override
  String get notLoggedIn => '로그인되지 않음';

  @override
  String get userDefault => '사용자';

  @override
  String get guestPrefix => '게스트_';

  @override
  String get noEmailBound => '연결된 이메일 없음';

  @override
  String get logout => '로그아웃';

  @override
  String get deleteAccount => '계정 삭제';

  @override
  String get loadingShort => '불러오는 중…';

  @override
  String get appearance => '화면';

  @override
  String get themeLight => '라이트';

  @override
  String get themeDark => '다크';

  @override
  String get themeSystem => '시스템';

  @override
  String featureComingSoon(String feature) {
    return '$feature 곧 제공';
  }

  @override
  String get privacyBody =>
      '원본 사진은 기본적으로 업로드되지 않으며, 인식 데이터는 임시로만 처리됩니다. 언제든지 계정과 데이터를 삭제할 수 있습니다. 정식 출시 시 전체 약관을 제공합니다.';

  @override
  String get deleteAccountQ => '계정을 영구 삭제할까요?';

  @override
  String get deleteAccountBody => '계정 프로필과 남은 한도가 삭제됩니다. 이 작업은 되돌릴 수 없습니다.';

  @override
  String get permanentDelete => '영구 삭제';

  @override
  String get deleteFailed => '삭제 실패, 나중에 다시 시도하세요';

  @override
  String get confirmLogout => '로그아웃 확인';

  @override
  String get confirmLogoutBody => '정말 로그아웃하시겠습니까?';

  @override
  String get confirmYes => '확인';

  @override
  String get authEmailHint => '이메일';

  @override
  String get authEmailRequired => '이메일을 입력하세요';

  @override
  String get authEmailInvalid => '유효한 이메일을 입력하세요';

  @override
  String get authPasswordHint => '비밀번호';

  @override
  String get authPasswordRequired => '비밀번호를 입력하세요';

  @override
  String get authPasswordMin6 => '비밀번호는 6자 이상이어야 합니다';

  @override
  String get authConfirmPasswordHint => '비밀번호 확인';

  @override
  String get authPasswordMismatch => '비밀번호가 일치하지 않습니다';

  @override
  String get authUsernameOptionalHint => '사용자 이름 (선택)';

  @override
  String get authLoginButton => '로그인';

  @override
  String get authRegisterButton => '가입';

  @override
  String get authNoAccount => '계정이 없나요? 가입';

  @override
  String get authHaveAccount => '계정이 있나요? 로그인';

  @override
  String get authCreateAccount => '계정 만들기';

  @override
  String get authOrLoginWith => '또는 다음으로 로그인';

  @override
  String get authGoogleLogin => 'Google로 로그인';

  @override
  String get authAppleLogin => 'Apple로 로그인';

  @override
  String get authOr => '또는';

  @override
  String get authGuestLogin => '게스트로 계속';

  @override
  String get authLoginFailed => '로그인 실패, 이메일과 비밀번호를 확인하세요';

  @override
  String get authRegisterFailed => '가입 실패, 이메일이 이미 사용 중일 수 있습니다';

  @override
  String get authGoogleCancelled => 'Google 로그인이 취소되었습니다';

  @override
  String get authGoogleFailed => 'Google 로그인 실패, 다시 시도하세요';

  @override
  String get authGoogleError => 'Google 로그인 오류';

  @override
  String get authGoogleNotConfigured => 'Google 로그인이 설정되지 않았습니다. 관리자에게 문의하세요';

  @override
  String get authGoogleNetworkError => 'Google 로그인 네트워크 오류, 연결을 확인하세요';

  @override
  String get authAppleOnlyApple => 'Apple 로그인은 iOS와 macOS에서만 지원됩니다';

  @override
  String get authAppleCancelled => 'Apple 로그인이 취소되었습니다';

  @override
  String get authAppleFailed => 'Apple 로그인 실패, 다시 시도하세요';

  @override
  String get authAppleError => 'Apple 로그인 오류';

  @override
  String get authAppleNotConfigured => 'Apple 로그인이 설정되지 않았습니다';

  @override
  String get authGuestFailed => '게스트 로그인 실패, 다시 시도하세요';

  @override
  String get authGuestError => '게스트 로그인 오류';

  @override
  String get recCandidatesTitle => '이 작품인가요?';

  @override
  String get recNoneOfThese => '모두 아님';

  @override
  String get recNotRecognized => '이 작품을 인식하지 못했습니다';

  @override
  String recLabelSeen(String text) {
    return '라벨에 \"$text\"라고 적혀 있습니다 — 아직 전체 가이드는 없지만 요청을 기록했습니다 ✅';
  }

  @override
  String get recShootLabelBtn => '설명판 촬영';

  @override
  String get recShootLabelHint => '미술관 설명판에는 제목과 작가가 있습니다. 촬영하면 작품을 식별할 수 있습니다';

  @override
  String get recViewfinderLabelHint => '설명판 글자를 화면에 가득 채우세요';

  @override
  String get camRecognizeTitle => '작품 식별';

  @override
  String get camViewfinderHint => '작품 전체를 화면에 담으세요';

  @override
  String get camRecentGallery => '최근';

  @override
  String get camAllAlbums => '모든 앨범';

  @override
  String get camGallery => '갤러리';

  @override
  String get camSearch => '검색';

  @override
  String get guideUnavailable => '이 작품은 가이드를 만들 자료가 부족합니다';

  @override
  String get guideNotGenerated => '아직 가이드가 생성되지 않았습니다';

  @override
  String get audioNotReady => '해설 생성 후 들을 수 있습니다';

  @override
  String get audioFailed => '오디오를 사용할 수 없습니다. 다시 시도하세요';

  @override
  String get deepGenerating => '심층 콘텐츠 생성 중…';

  @override
  String get camNoCamera => '사용 가능한 카메라가 없습니다';

  @override
  String get camInitFailed => '카메라 초기화 실패';

  @override
  String get camTagSearch => '설명판 검색';

  @override
  String get camTagHint => '촬영 불가 구역에서는 설명판 번호, 제목 또는 작가를 입력하세요';

  @override
  String get camTagExample => '예: INV 3692 / 침실';

  @override
  String get camPackComingSoon => '컬렉션 검색은 오프라인 팩 제공 후 이용 가능';

  @override
  String get camQuotaUsedUp => '무료 스캔을 모두 사용했습니다';

  @override
  String get camUpgradeHint => '업그레이드하여 미술관 전체에서 계속 감상하세요';

  @override
  String get camViewUpgrade => '요금제 보기';

  @override
  String get camCantPhoto => '촬영할 수 없나요? 설명판 번호를 입력하세요';

  @override
  String get camRecognizing => '인식 중…';

  @override
  String get camComparing => 'AI가 컬렉션 및 공개 미술 데이터베이스와 대조 중';

  @override
  String get camConfirmPrompt => '인식 완료, 작품을 확인하세요';

  @override
  String get camConfidence => '신뢰도';

  @override
  String get camConfirmStart => '확인하고 가이드 시작';

  @override
  String get camNoneSearch => '해당 없음? 제목이나 설명판 번호로 검색 →';

  @override
  String get camRecognizeFailed => '인식 실패';

  @override
  String get camRetake => '다시 촬영';
}
