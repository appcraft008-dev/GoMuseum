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

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'GoMuseum'**
  String get appTitle;

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

  /// No description provided for @settings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @about.
  ///
  /// In en, this message translates to:
  /// **'About'**
  String get about;

  /// No description provided for @version.
  ///
  /// In en, this message translates to:
  /// **'Version'**
  String get version;

  /// No description provided for @getDetailedExplanation.
  ///
  /// In en, this message translates to:
  /// **'Get Detailed Explanation'**
  String get getDetailedExplanation;

  /// No description provided for @detailLevel.
  ///
  /// In en, this message translates to:
  /// **'Detail Level'**
  String get detailLevel;

  /// No description provided for @brief.
  ///
  /// In en, this message translates to:
  /// **'Brief'**
  String get brief;

  /// No description provided for @standard.
  ///
  /// In en, this message translates to:
  /// **'Standard'**
  String get standard;

  /// No description provided for @detailed.
  ///
  /// In en, this message translates to:
  /// **'Detailed'**
  String get detailed;

  /// No description provided for @includeAudioNarration.
  ///
  /// In en, this message translates to:
  /// **'Include Audio Narration'**
  String get includeAudioNarration;

  /// No description provided for @generateAudioVersion.
  ///
  /// In en, this message translates to:
  /// **'Generate audio version of explanation'**
  String get generateAudioVersion;

  /// No description provided for @regenerateExplanation.
  ///
  /// In en, this message translates to:
  /// **'Regenerate explanation'**
  String get regenerateExplanation;

  /// No description provided for @preparingExplanation.
  ///
  /// In en, this message translates to:
  /// **'Preparing explanation for {artworkName}...'**
  String preparingExplanation(Object artworkName);

  /// No description provided for @generatingExplanation.
  ///
  /// In en, this message translates to:
  /// **'Generating explanation...'**
  String get generatingExplanation;

  /// No description provided for @thisIsTakingLonger.
  ///
  /// In en, this message translates to:
  /// **'This may take a moment with audio...'**
  String get thisIsTakingLonger;

  /// No description provided for @failedToGenerate.
  ///
  /// In en, this message translates to:
  /// **'Failed to generate explanation'**
  String get failedToGenerate;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @audioNarration.
  ///
  /// In en, this message translates to:
  /// **'Audio Narration'**
  String get audioNarration;

  /// No description provided for @languageHint.
  ///
  /// In en, this message translates to:
  /// **'Language: {languageName}'**
  String languageHint(Object languageName);

  /// No description provided for @changeInSettings.
  ///
  /// In en, this message translates to:
  /// **'Change in Settings'**
  String get changeInSettings;

  /// No description provided for @artist.
  ///
  /// In en, this message translates to:
  /// **'Artist'**
  String get artist;

  /// No description provided for @period.
  ///
  /// In en, this message translates to:
  /// **'Period'**
  String get period;

  /// No description provided for @confidence.
  ///
  /// In en, this message translates to:
  /// **'Confidence'**
  String get confidence;

  /// No description provided for @recognizedAt.
  ///
  /// In en, this message translates to:
  /// **'Recognized at'**
  String get recognizedAt;

  /// No description provided for @description.
  ///
  /// In en, this message translates to:
  /// **'Description'**
  String get description;
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
