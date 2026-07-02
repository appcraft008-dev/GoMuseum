import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_de.dart';
import 'app_localizations_en.dart';
import 'app_localizations_es.dart';
import 'app_localizations_fr.dart';
import 'app_localizations_it.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('de'),
    Locale('en'),
    Locale('es'),
    Locale('fr'),
    Locale('it'),
    Locale('zh')
  ];

  /// No description provided for @home.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get home;

  /// No description provided for @explore.
  ///
  /// In en, this message translates to:
  /// **'Explore'**
  String get explore;

  /// No description provided for @capture.
  ///
  /// In en, this message translates to:
  /// **'Capture'**
  String get capture;

  /// No description provided for @footprints.
  ///
  /// In en, this message translates to:
  /// **'Footprints'**
  String get footprints;

  /// No description provided for @settings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// No description provided for @navScan.
  ///
  /// In en, this message translates to:
  /// **'Scan'**
  String get navScan;

  /// No description provided for @artworkRecognition.
  ///
  /// In en, this message translates to:
  /// **'Artwork Recognition'**
  String get artworkRecognition;

  /// No description provided for @takePhoto.
  ///
  /// In en, this message translates to:
  /// **'Take Photo'**
  String get takePhoto;

  /// No description provided for @chooseFromGallery.
  ///
  /// In en, this message translates to:
  /// **'Choose from Gallery'**
  String get chooseFromGallery;

  /// No description provided for @selectImagePrompt.
  ///
  /// In en, this message translates to:
  /// **'Select an image to recognize artwork'**
  String get selectImagePrompt;

  /// No description provided for @error.
  ///
  /// In en, this message translates to:
  /// **'Error'**
  String get error;

  /// No description provided for @comingSoon.
  ///
  /// In en, this message translates to:
  /// **'Coming Soon'**
  String get comingSoon;

  /// No description provided for @comingSoonShort.
  ///
  /// In en, this message translates to:
  /// **'Coming soon'**
  String get comingSoonShort;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @selectLanguage.
  ///
  /// In en, this message translates to:
  /// **'Select Language'**
  String get selectLanguage;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @delete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// No description provided for @confirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// No description provided for @gotIt.
  ///
  /// In en, this message translates to:
  /// **'Got it'**
  String get gotIt;

  /// No description provided for @loadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load'**
  String get loadFailed;

  /// No description provided for @loadFailedRetry.
  ///
  /// In en, this message translates to:
  /// **'Failed to load, please retry'**
  String get loadFailedRetry;

  /// No description provided for @toBeRefined.
  ///
  /// In en, this message translates to:
  /// **'In progress'**
  String get toBeRefined;

  /// No description provided for @viewAll.
  ///
  /// In en, this message translates to:
  /// **'View all →'**
  String get viewAll;

  /// No description provided for @all.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get all;

  /// No description provided for @homePocketGuide.
  ///
  /// In en, this message translates to:
  /// **'Pocket Museum Guide'**
  String get homePocketGuide;

  /// No description provided for @homeSlogan.
  ///
  /// In en, this message translates to:
  /// **'Step closer to one work,\nhear the story behind it.'**
  String get homeSlogan;

  /// No description provided for @homeCtaRecognize.
  ///
  /// In en, this message translates to:
  /// **'Snap to Recognize & Listen'**
  String get homeCtaRecognize;

  /// No description provided for @homeFreeLeft.
  ///
  /// In en, this message translates to:
  /// **'{count} free scans left · Upgrade for full access'**
  String homeFreeLeft(Object count);

  /// No description provided for @homeNearby.
  ///
  /// In en, this message translates to:
  /// **'Nearby Museums'**
  String get homeNearby;

  /// No description provided for @statusOpen.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get statusOpen;

  /// No description provided for @exploreTitle.
  ///
  /// In en, this message translates to:
  /// **'Explore'**
  String get exploreTitle;

  /// No description provided for @searchCityMuseumArtwork.
  ///
  /// In en, this message translates to:
  /// **'Search cities, museums or artworks'**
  String get searchCityMuseumArtwork;

  /// No description provided for @museumCount.
  ///
  /// In en, this message translates to:
  /// **'{count} museums'**
  String museumCount(Object count);

  /// No description provided for @noMuseums.
  ///
  /// In en, this message translates to:
  /// **'No museums yet'**
  String get noMuseums;

  /// No description provided for @noMatchedMuseums.
  ///
  /// In en, this message translates to:
  /// **'No matching museums'**
  String get noMatchedMuseums;

  /// No description provided for @artworkCountLabel.
  ///
  /// In en, this message translates to:
  /// **'{count} works'**
  String artworkCountLabel(Object count);

  /// No description provided for @recordedCount.
  ///
  /// In en, this message translates to:
  /// **'{count} works in collection'**
  String recordedCount(Object count);

  /// No description provided for @noArtworks.
  ///
  /// In en, this message translates to:
  /// **'No works yet'**
  String get noArtworks;

  /// No description provided for @loadingShown.
  ///
  /// In en, this message translates to:
  /// **'Loading · {shown}/{total} shown'**
  String loadingShown(Object shown, Object total);

  /// No description provided for @allLoaded.
  ///
  /// In en, this message translates to:
  /// **'All loaded · {total} in total'**
  String allLoaded(Object total);

  /// No description provided for @guideVoiceGuide.
  ///
  /// In en, this message translates to:
  /// **'Audio Guide'**
  String get guideVoiceGuide;

  /// No description provided for @guideGenFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to generate explanation'**
  String get guideGenFailed;

  /// No description provided for @guideWriting.
  ///
  /// In en, this message translates to:
  /// **'Writing your explanation…'**
  String get guideWriting;

  /// No description provided for @guideHighlight.
  ///
  /// In en, this message translates to:
  /// **'Highlight'**
  String get guideHighlight;

  /// No description provided for @guideQa.
  ///
  /// In en, this message translates to:
  /// **'Q&A'**
  String get guideQa;

  /// No description provided for @guideThinking.
  ///
  /// In en, this message translates to:
  /// **'Thinking…'**
  String get guideThinking;

  /// No description provided for @guideQ1.
  ///
  /// In en, this message translates to:
  /// **'What makes this painting special?'**
  String get guideQ1;

  /// No description provided for @guideQ2.
  ///
  /// In en, this message translates to:
  /// **'What was the artist going through then?'**
  String get guideQ2;

  /// No description provided for @guideAskHint.
  ///
  /// In en, this message translates to:
  /// **'Ask about this painting…'**
  String get guideAskHint;

  /// No description provided for @guideAskShort.
  ///
  /// In en, this message translates to:
  /// **'Ask about this painting'**
  String get guideAskShort;

  /// No description provided for @guideVoiceComingSoon.
  ///
  /// In en, this message translates to:
  /// **'Voice Q&A is coming soon, type for now'**
  String get guideVoiceComingSoon;

  /// No description provided for @guideGenerating.
  ///
  /// In en, this message translates to:
  /// **'Generating explanation…'**
  String get guideGenerating;

  /// No description provided for @guideEmpty.
  ///
  /// In en, this message translates to:
  /// **'No grounded explanation yet (in progress)'**
  String get guideEmpty;

  /// No description provided for @guideInfo.
  ///
  /// In en, this message translates to:
  /// **'Artwork Info'**
  String get guideInfo;

  /// No description provided for @guideStandardTour.
  ///
  /// In en, this message translates to:
  /// **'Standard tour'**
  String get guideStandardTour;

  /// No description provided for @guideListen.
  ///
  /// In en, this message translates to:
  /// **'Listen'**
  String get guideListen;

  /// No description provided for @guideDiveIn.
  ///
  /// In en, this message translates to:
  /// **'Want more? Tap below'**
  String get guideDiveIn;

  /// No description provided for @guideDeepContent.
  ///
  /// In en, this message translates to:
  /// **'In depth'**
  String get guideDeepContent;

  /// No description provided for @guideAskPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Ask anything…'**
  String get guideAskPlaceholder;

  /// No description provided for @guideArtist.
  ///
  /// In en, this message translates to:
  /// **'Artist'**
  String get guideArtist;

  /// No description provided for @guideArtistTab.
  ///
  /// In en, this message translates to:
  /// **'Artist'**
  String get guideArtistTab;

  /// No description provided for @guideNotableWorks.
  ///
  /// In en, this message translates to:
  /// **'Notable works'**
  String get guideNotableWorks;

  /// No description provided for @guideNoAnswer.
  ///
  /// In en, this message translates to:
  /// **'(no answer returned)'**
  String get guideNoAnswer;

  /// No description provided for @guideAnswerFailed.
  ///
  /// In en, this message translates to:
  /// **'Answer failed, please try again later.'**
  String get guideAnswerFailed;

  /// No description provided for @factInventory.
  ///
  /// In en, this message translates to:
  /// **'Inventory No.'**
  String get factInventory;

  /// No description provided for @factLocation.
  ///
  /// In en, this message translates to:
  /// **'Location'**
  String get factLocation;

  /// No description provided for @factProvenance.
  ///
  /// In en, this message translates to:
  /// **'Provenance'**
  String get factProvenance;

  /// No description provided for @factExhibitions.
  ///
  /// In en, this message translates to:
  /// **'Exhibitions'**
  String get factExhibitions;

  /// No description provided for @factBibliography.
  ///
  /// In en, this message translates to:
  /// **'Bibliography'**
  String get factBibliography;

  /// No description provided for @factArtist.
  ///
  /// In en, this message translates to:
  /// **'Artist'**
  String get factArtist;

  /// No description provided for @factNone.
  ///
  /// In en, this message translates to:
  /// **'No detailed information'**
  String get factNone;

  /// No description provided for @footprintTitle.
  ///
  /// In en, this message translates to:
  /// **'Footprints'**
  String get footprintTitle;

  /// No description provided for @noFootprints.
  ///
  /// In en, this message translates to:
  /// **'No footprints yet'**
  String get noFootprints;

  /// No description provided for @footprintStat.
  ///
  /// In en, this message translates to:
  /// **'{count} works · {days} days'**
  String footprintStat(Object count, Object days);

  /// No description provided for @footprintLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load footprints'**
  String get footprintLoadFailed;

  /// No description provided for @footprintEmptyHint.
  ///
  /// In en, this message translates to:
  /// **'Works you recognize are recorded here automatically'**
  String get footprintEmptyHint;

  /// No description provided for @footprintGoRecognize.
  ///
  /// In en, this message translates to:
  /// **'Recognize your first work'**
  String get footprintGoRecognize;

  /// No description provided for @itemsCount.
  ///
  /// In en, this message translates to:
  /// **'{count} works'**
  String itemsCount(Object count);

  /// No description provided for @today.
  ///
  /// In en, this message translates to:
  /// **'Today'**
  String get today;

  /// No description provided for @yesterday.
  ///
  /// In en, this message translates to:
  /// **'Yesterday'**
  String get yesterday;

  /// No description provided for @dateMonthDay.
  ///
  /// In en, this message translates to:
  /// **'{month}/{day}'**
  String dateMonthDay(Object month, Object day);

  /// No description provided for @deleteFootprintQ.
  ///
  /// In en, this message translates to:
  /// **'Delete this footprint?'**
  String get deleteFootprintQ;

  /// No description provided for @settingsTitle.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settingsTitle;

  /// No description provided for @secGeneral.
  ///
  /// In en, this message translates to:
  /// **'General'**
  String get secGeneral;

  /// No description provided for @guideLanguage.
  ///
  /// In en, this message translates to:
  /// **'Guide language'**
  String get guideLanguage;

  /// No description provided for @offlinePacks.
  ///
  /// In en, this message translates to:
  /// **'Offline museum packs'**
  String get offlinePacks;

  /// No description provided for @autoSavePhoto.
  ///
  /// In en, this message translates to:
  /// **'Auto-save photos'**
  String get autoSavePhoto;

  /// No description provided for @ttsVoice.
  ///
  /// In en, this message translates to:
  /// **'TTS voice'**
  String get ttsVoice;

  /// No description provided for @ttsVoiceValue.
  ///
  /// In en, this message translates to:
  /// **'Calm · Female'**
  String get ttsVoiceValue;

  /// No description provided for @ttsVoiceSelect.
  ///
  /// In en, this message translates to:
  /// **'Choose voice'**
  String get ttsVoiceSelect;

  /// No description provided for @secAccount.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get secAccount;

  /// No description provided for @secSupport.
  ///
  /// In en, this message translates to:
  /// **'Support & Legal'**
  String get secSupport;

  /// No description provided for @encourageUs.
  ///
  /// In en, this message translates to:
  /// **'Encourage us'**
  String get encourageUs;

  /// No description provided for @appStoreRating.
  ///
  /// In en, this message translates to:
  /// **'App Store rating'**
  String get appStoreRating;

  /// No description provided for @privacyPolicy.
  ///
  /// In en, this message translates to:
  /// **'Privacy policy'**
  String get privacyPolicy;

  /// No description provided for @freeQuota.
  ///
  /// In en, this message translates to:
  /// **'Free scan quota'**
  String get freeQuota;

  /// No description provided for @quotaValue.
  ///
  /// In en, this message translates to:
  /// **'{remain} / {total} left'**
  String quotaValue(Object remain, Object total);

  /// No description provided for @upgrade.
  ///
  /// In en, this message translates to:
  /// **'Upgrade'**
  String get upgrade;

  /// No description provided for @loginBind.
  ///
  /// In en, this message translates to:
  /// **'Sign in / Link account'**
  String get loginBind;

  /// No description provided for @notLoggedIn.
  ///
  /// In en, this message translates to:
  /// **'Not signed in'**
  String get notLoggedIn;

  /// No description provided for @userDefault.
  ///
  /// In en, this message translates to:
  /// **'User'**
  String get userDefault;

  /// No description provided for @guestPrefix.
  ///
  /// In en, this message translates to:
  /// **'Guest_'**
  String get guestPrefix;

  /// No description provided for @noEmailBound.
  ///
  /// In en, this message translates to:
  /// **'No email linked'**
  String get noEmailBound;

  /// No description provided for @logout.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get logout;

  /// No description provided for @deleteAccount.
  ///
  /// In en, this message translates to:
  /// **'Delete account'**
  String get deleteAccount;

  /// No description provided for @loadingShort.
  ///
  /// In en, this message translates to:
  /// **'Loading…'**
  String get loadingShort;

  /// No description provided for @appearance.
  ///
  /// In en, this message translates to:
  /// **'Appearance'**
  String get appearance;

  /// No description provided for @themeLight.
  ///
  /// In en, this message translates to:
  /// **'Light'**
  String get themeLight;

  /// No description provided for @themeDark.
  ///
  /// In en, this message translates to:
  /// **'Dark'**
  String get themeDark;

  /// No description provided for @themeSystem.
  ///
  /// In en, this message translates to:
  /// **'System'**
  String get themeSystem;

  /// No description provided for @featureComingSoon.
  ///
  /// In en, this message translates to:
  /// **'{feature} is coming soon'**
  String featureComingSoon(String feature);

  /// No description provided for @privacyBody.
  ///
  /// In en, this message translates to:
  /// **'Original photos are not uploaded by default; recognition data is processed temporarily only. You can delete your account and data anytime. Full terms will be provided at official release.'**
  String get privacyBody;

  /// No description provided for @deleteAccountQ.
  ///
  /// In en, this message translates to:
  /// **'Permanently delete account?'**
  String get deleteAccountQ;

  /// No description provided for @deleteAccountBody.
  ///
  /// In en, this message translates to:
  /// **'This will delete your account profile and remaining quota. This action cannot be undone.'**
  String get deleteAccountBody;

  /// No description provided for @permanentDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete permanently'**
  String get permanentDelete;

  /// No description provided for @deleteFailed.
  ///
  /// In en, this message translates to:
  /// **'Delete failed, please try again later'**
  String get deleteFailed;

  /// No description provided for @confirmLogout.
  ///
  /// In en, this message translates to:
  /// **'Confirm sign out'**
  String get confirmLogout;

  /// No description provided for @confirmLogoutBody.
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to sign out?'**
  String get confirmLogoutBody;

  /// No description provided for @confirmYes.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirmYes;

  /// No description provided for @camNoCamera.
  ///
  /// In en, this message translates to:
  /// **'No available camera found'**
  String get camNoCamera;

  /// No description provided for @camInitFailed.
  ///
  /// In en, this message translates to:
  /// **'Camera initialization failed'**
  String get camInitFailed;

  /// No description provided for @camTagSearch.
  ///
  /// In en, this message translates to:
  /// **'Label lookup'**
  String get camTagSearch;

  /// No description provided for @camTagHint.
  ///
  /// In en, this message translates to:
  /// **'In no-photo areas, enter the label number, title or artist'**
  String get camTagHint;

  /// No description provided for @camTagExample.
  ///
  /// In en, this message translates to:
  /// **'e.g. INV 3692 / The Bedroom'**
  String get camTagExample;

  /// No description provided for @camPackComingSoon.
  ///
  /// In en, this message translates to:
  /// **'Collection lookup opens after offline packs are available'**
  String get camPackComingSoon;

  /// No description provided for @camQuotaUsedUp.
  ///
  /// In en, this message translates to:
  /// **'Free scans used up'**
  String get camQuotaUsedUp;

  /// No description provided for @camUpgradeHint.
  ///
  /// In en, this message translates to:
  /// **'Upgrade to keep listening across the museum'**
  String get camUpgradeHint;

  /// No description provided for @camViewUpgrade.
  ///
  /// In en, this message translates to:
  /// **'View upgrade plans'**
  String get camViewUpgrade;

  /// No description provided for @camCantPhoto.
  ///
  /// In en, this message translates to:
  /// **'Can\'t take a photo? Enter the label number'**
  String get camCantPhoto;

  /// No description provided for @camRecognizing.
  ///
  /// In en, this message translates to:
  /// **'Recognizing…'**
  String get camRecognizing;

  /// No description provided for @camComparing.
  ///
  /// In en, this message translates to:
  /// **'AI is comparing with collections and public art databases'**
  String get camComparing;

  /// No description provided for @camConfirmPrompt.
  ///
  /// In en, this message translates to:
  /// **'Recognition done, please confirm the work'**
  String get camConfirmPrompt;

  /// No description provided for @camConfidence.
  ///
  /// In en, this message translates to:
  /// **'Confidence'**
  String get camConfidence;

  /// No description provided for @camConfirmStart.
  ///
  /// In en, this message translates to:
  /// **'Confirm & start guide'**
  String get camConfirmStart;

  /// No description provided for @camNoneSearch.
  ///
  /// In en, this message translates to:
  /// **'None of these? Search by title or label number →'**
  String get camNoneSearch;

  /// No description provided for @camRecognizeFailed.
  ///
  /// In en, this message translates to:
  /// **'Recognition failed'**
  String get camRecognizeFailed;

  /// No description provided for @camRetake.
  ///
  /// In en, this message translates to:
  /// **'Retake'**
  String get camRetake;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) => <String>[
        'de',
        'en',
        'es',
        'fr',
        'it',
        'zh'
      ].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'de':
      return AppLocalizationsDe();
    case 'en':
      return AppLocalizationsEn();
    case 'es':
      return AppLocalizationsEs();
    case 'fr':
      return AppLocalizationsFr();
    case 'it':
      return AppLocalizationsIt();
    case 'zh':
      return AppLocalizationsZh();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
