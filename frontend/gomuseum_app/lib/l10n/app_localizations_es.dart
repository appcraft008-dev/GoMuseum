// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Spanish Castilian (`es`).
class AppLocalizationsEs extends AppLocalizations {
  AppLocalizationsEs([String locale = 'es']) : super(locale);

  @override
  String get appTitle => 'GoMuseum';

  @override
  String get artworkRecognition => 'Reconocimiento de obras de arte';

  @override
  String get takePhoto => 'Tomar foto';

  @override
  String get chooseFromGallery => 'Elegir de la galería';

  @override
  String get selectImagePrompt =>
      'Seleccione una imagen para reconocer la obra de arte';

  @override
  String get error => 'Error';

  @override
  String get settings => 'Configuración';

  @override
  String get language => 'Idioma';

  @override
  String get about => 'Acerca de';

  @override
  String get version => 'Versión';

  @override
  String get getDetailedExplanation => 'Obtener explicación detallada';

  @override
  String get detailLevel => 'Nivel de detalle';

  @override
  String get brief => 'Breve';

  @override
  String get standard => 'Estándar';

  @override
  String get detailed => 'Detallado';

  @override
  String get includeAudioNarration => 'Incluir narración de audio';

  @override
  String get generateAudioVersion =>
      'Generar versión de audio de la explicación';

  @override
  String get regenerateExplanation => 'Regenerar explicación';

  @override
  String preparingExplanation(Object artworkName) {
    return 'Preparando explicación para $artworkName...';
  }

  @override
  String get generatingExplanation => 'Generando explicación...';

  @override
  String get thisIsTakingLonger => 'Esto puede tardar un momento con audio...';

  @override
  String get failedToGenerate => 'Error al generar la explicación';

  @override
  String get retry => 'Reintentar';

  @override
  String get audioNarration => 'Narración de audio';

  @override
  String languageHint(Object languageName) {
    return 'Idioma: $languageName';
  }

  @override
  String get changeInSettings => 'Cambiar en configuración';

  @override
  String get artist => 'Artista';

  @override
  String get period => 'Período';

  @override
  String get confidence => 'Confianza';

  @override
  String get recognizedAt => 'Reconocido en';

  @override
  String get description => 'Descripción';
}
