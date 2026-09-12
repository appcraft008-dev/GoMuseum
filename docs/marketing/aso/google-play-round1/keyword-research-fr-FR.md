# GoMuseum · Recherche de mots-clés — Français (Google Play)

**Aucune donnée réelle de volume/difficulté disponible** (pas d'abonnement Appeeky ou équivalent). Les scores Volume/Difficulty/Relevance ci-dessous sont des **jugements directionnels**, basés sur le nombre de résultats de recherche, la densité concurrentielle et la pertinence sémantique — pas des chiffres de recherche réels. Date de recherche : 2026-09-08.

⚠️ Ces mots-clés **ne sont pas des traductions directes** de la version anglaise — recherchés séparément en français natif (voir méthodologie dans `gomuseum-organic-launch-plan.md`).

## Groupes de mots-clés

### Mot de marque
- gomuseum

### Noms de musées
- louvre, musée du louvre, musée d'orsay, musée de l'orangerie, petit palais

### Mots de guide/visite
- guide du louvre, audioguide louvre, guide musée paris, visite guidée louvre, guide audio musée

### Mots de reconnaissance d'œuvre
- reconnaissance œuvre d'art, identifier un tableau, scanner une œuvre d'art, application identification tableau

### Mots de scénario voyage (longue traîne)
- visiter le louvre sans audioguide, louvre sans réserver de guide, guide musée paris gratuit, application musée sans abonnement

## Top Keywords par opportunité (jugement directionnel)

| Mot-clé | Volume(estimé) | Difficulty(estimé) | Relevance | Opportunité | Base |
|---|---|---|---|---|---|
| guide du louvre | 65 | 75 | 90 | Moyen | Concurrents directs identifiés (versions FR probables des apps vusiem/tourblink, à confirmer Phase 3) |
| audioguide louvre | 55 | 70 | 70 | Moyen-faible | Terme "audioguide" en un mot est la forme française native courante — différent de "guide audio" en deux mots, ne pas confondre les deux formes dans la recherche |
| identifier un tableau | 40 | 45 | 85 | Moyen-haut | ArtScan ("Identifier Tableaux") et Smartify ciblent déjà ce terme en FR, mais aucun n'est ancré sur les 4 musées parisiens |
| reconnaissance œuvre d'art | 35 | 40 | 85 | Moyen-haut | Terme plus formel/technique, volume probablement inférieur à "identifier un tableau" mais moins contesté |
| scanner une œuvre d'art louvre | 15 | 10 | 95 | **Haut** | Mot-clé composé longue traîne — aucun concurrent direct trouvé combinant "scanner/identifier" + "Louvre" en français |
| guide musée paris gratuit | 30 | 30 | 50 | Moyen | Terme d'intention "recherche d'info" plutôt que "téléchargement d'app" — mieux capté par la landing page (`deployment/website/fr/`) que par la fiche Store |

## Regroupement stratégique

**Primary (titre/description courte) :**
1. louvre (nom propre, intention la plus forte)
2. scanner / reconnaissance (mot fonctionnel différenciant)
3. audioguide (capter une partie du trafic du terme générique concurrentiel, même si le positionnement n'est pas identique)

**Secondary :**
- musée d'orsay, orangerie, petit palais, identifier, tableau

**Long-tail (description complète, 4000 caractères largement sous-utilisés — voir audit) :**
- scanner une œuvre d'art au louvre, visiter le louvre sans audioguide, application musée paris

**Aspirational :**
- guide musée paris (terme générique, dominé par les grandes plateformes)

## Points d'attention linguistiques (pas une traduction de l'anglais)

- **"Audioguide" (un mot) vs "guide audio" (deux mots)** — les deux formes existent en français, "audioguide" semble être la forme la plus utilisée par les concurrents eux-mêmes (ex. noms d'app "Audio Guide Orsay Museum" en anglais mais probablement "Audioguide" en FR) — à vérifier Phase 3 lors de la rédaction finale, ne pas trancher ici sans donnée
- **"Œuvre" vs "tableau"** — "œuvre" est plus générique (couvre sculptures, objets), "tableau" ne couvre que la peinture ; comme GoMuseum couvre aussi les sculptures, privilégier "œuvre" dans le titre/description courte et réserver "tableau" aux exemples concrets dans la description longue
- **Accents obligatoires** — "musée", "œuvre" perdent en crédibilité perçue si les accents sont omis dans le texte marketing (contrairement au champ de recherche où l'utilisateur tape souvent sans accents)

## Recommendations

1. Le titre doit intégrer "Louvre" + un verbe/nom d'action (scanner/reconnaissance), pas seulement "audioguide" — sinon on se noie dans la même catégorie que les concurrents `vusiem`/`tourblink`
2. Le terme longue traîne "scanner une œuvre d'art au Louvre" est l'opportunité la plus propre trouvée ce round — à intégrer naturellement dans la description complète, pas dans le titre (trop long)
3. Vérifier en Phase 3 si les concurrents `vusiem`/`tourblink` ont des fiches Google Play en français distinctes — si oui, refaire une passe de comparaison directe sur leurs titres/descriptions FR (non fait ce round, WebFetch sur les pages Play a échoué, voir limitation méthodologique dans `competitor-analysis-en-fr.md`)

## Sources
- Recherches WebSearch 2026-09-08 (requêtes en français natif, voir historique de session)
- Concurrents croisés avec `competitor-analysis-en-fr.md`
