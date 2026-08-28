/*
 * Conversion du dump XML Stack Exchange en table colonne partitionnée.
 *
 * Compétence visée : C2 (épreuve E1) — requêtes de collecte, langage Spark SQL
 * Compétence visée : C4 (épreuve E1) — minimisation des données personnelles
 * Compétence visée : C20 (épreuve E5) — optimisation mesurée d'un traitement
 *
 * OBJECTIF DE COLLECTE
 * Transformer un fichier XML monolithique — 123 Mio pour le dump Data Science,
 * 97 Gio pour celui de Stack Overflow — en Parquet partitionné, lisible par
 * requête sans relire l'intégralité du fichier.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * POURQUOI CETTE REQUÊTE A ÉTÉ RÉÉCRITE
 * ─────────────────────────────────────────────────────────────────────────
 * La première version appelait `xpath_string` treize fois par ligne, sur la
 * totalité des lignes du fichier. Elle traitait le dump Data Science en 76
 * secondes. Sur celui de Stack Overflow, elle a traité 32 tâches sur 775 en
 * quatorze heures — soit une projection de trois semaines.
 *
 * Le traitement qui marchait à 123 Mio ne passait pas à l'échelle à 97 Gio, et
 * la cause est mesurable : `xpath_string` construit un arbre XML à chaque
 * appel. Treize appels par ligne, c'est treize analyses complètes du même
 * fragment. Sur 78 926 lignes c'est indolore ; sur une soixantaine de millions,
 * c'est rédhibitoire.
 *
 * Trois optimisations, par ordre de gain attendu.
 *
 * 1. FILTRER AVANT D'ANALYSER
 *    Les prédicats de sélection portent désormais sur le TEXTE BRUT, par
 *    `LIKE` — une recherche de sous-chaîne, sans analyse d'aucune sorte. Une
 *    ligne écartée à ce stade n'est jamais analysée. C'est le gain principal :
 *    l'essentiel du dump ne franchit pas cette étape.
 *
 * 2. AUCUN UDF PYTHON
 *    Il n'y en avait aucun, et il n'y en a toujours aucun. Tout ce fichier
 *    s'exécute dans la JVM. Un UDF Python imposerait un aller-retour et une
 *    sérialisation par ligne, coût qui domine tout le reste — c'est le piège
 *    classique, mais il n'a pas été tendu ici.
 *
 * 3. PLUS AUCUNE ANALYSE XML
 *    L'objectif énoncé était « une analyse par ligne au lieu de treize ». Le
 *    résultat va plus loin : il n'y en a plus aucune. Les attributs sont lus
 *    par expressions régulières ancrées sur leur nom — une recherche de motif
 *    ne construit pas d'arbre et n'alloue pas d'objet par nœud.
 *
 *    Une carte d'attributs bâtie en une seule passe, par `str_to_map`, serait
 *    plus élégante encore. Elle n'a pas été retenue : son découpage clé-valeur
 *    sur des valeurs contenant elles-mêmes le caractère « = », fréquent dans du
 *    code, demande une vérification que la charge actuelle de la machine ne
 *    permet pas. Le gain serait de surcroît secondaire — c'est le filtrage
 *    préalable qui écarte le volume, et la carte n'agirait que sur le reste.
 * ─────────────────────────────────────────────────────────────────────────
 *
 * CHOIX DE SÉLECTION
 * Deux ensembles sont retenus, et l'ordre des étapes compte.
 *
 *   - les QUESTIONS portant l'un des thèmes du corpus ET une réponse acceptée ;
 *   - les RÉPONSES que ces questions ont acceptées, et elles seules.
 *
 * Retenir toutes les réponses aurait conservé la moitié du dump. Les
 * restreindre à celles qui sont effectivement citées suppose de connaître les
 * identifiants attendus : d'où deux balayages du texte brut plutôt qu'un seul.
 * Deux balayages à `LIKE` coûtent moins qu'un seul balayage à treize analyses
 * XML — c'est le calcul qui a décidé.
 *
 * CHOIX DE FILTRAGE — minimisation (C4)
 * Quatre attributs présents dans Posts.xml ne sont volontairement PAS extraits :
 *
 *     OwnerUserId            identifiant persistant de personne
 *     LastEditorUserId       identifiant persistant de personne
 *     OwnerDisplayName       nom d'affichage en clair
 *     LastEditorDisplayName  nom d'affichage en clair
 *
 * Relevés sur le dump Data Science : 78 448, 28 401, 635 et 184 occurrences.
 * Les écarter ici, à la projection, et non après chargement : une donnée non
 * extraite n'a besoin ni de durée de conservation ni de procédure d'effacement.
 * Même raisonnement que pour l'objet `owner` de l'API Stack Exchange en S1.
 *
 * L'attribution exigée par CC BY-SA est assurée par l'URL reconstruite depuis
 * `Id`, qui pointe vers la page où Stack Exchange crédite lui-même l'auteur.
 * Le fichier Users.xml n'est jamais ouvert.
 *
 * OPTIMISATIONS APPLIQUÉES
 * - Prédicats `LIKE` sur le texte brut avant toute extraction.
 * - Extraction par expressions régulières ancrées, sans construction d'arbre.
 * - Typage explicite plutôt qu'inférence : l'inférence imposerait une passe de
 *   lecture supplémentaire sur l'intégralité du dump.
 * - Partitionnement par `annee` à l'écriture : les requêtes aval filtrant sur
 *   une période ne lisent que les répertoires concernés.
 * - Les entités XML sont décodées ici, sur les seules lignes retenues, et non
 *   en Python sur la totalité.
 *
 * GAIN MESURÉ
 * À données identiques et périmètre identique — dump Data Science, 123 Mio :
 *
 *     ancienne version (xpath_string ×13) ....... 75,80 s
 *     nouvelle version (filtre puis regex) ...... 35,03 s   soit x2,2
 *
 * Le facteur est modeste à ce volume : l'amorçage de Spark, une quinzaine de
 * secondes, y pèse davantage que le traitement lui-même.
 *
 * À l'échelle, trois points de mesure sur des sous-ensembles du dump Stack
 * Overflow, machine libre :
 *
 *     volume     conversion   débit        sélection   documents
 *     123 Mio      35,03 s     3,5 Mio/s     10,75 s       4 948
 *     1,9 Gio      76,96 s      25 Mio/s     25,69 s      20 707
 *     9,4 Gio     226,24 s      42 Mio/s     77,34 s      88 799
 *
 * Le débit CROÎT avec le volume : le coût fixe d'amorçage s'amortit.
 *
 * Comparaison à grande échelle : l'ancienne version a traité 6,0 Gio en
 * 14 h 19, soit 0,12 Mio/s, avant d'être arrêtée — projection de trois semaines
 * sur les 97 Gio. La nouvelle tient 42 Mio/s, soit environ 40 min de conversion
 * projetées. Rapport de l'ordre de 350.
 *
 * Ce dernier chiffre est une PROJECTION à partir d'un débit constaté, non la
 * comparaison de deux exécutions achevées : l'ancienne version n'a jamais
 * terminé. Le seul rapport mesuré de bout en bout sur les mêmes données est
 * celui de 2,2 ci-dessus.
 *
 * FIDÉLITÉ VÉRIFIÉE
 * Rejeu sur le dump Data Science à périmètre constant : 4 948 documents des
 * deux côtés, aucun identifiant manquant ni en trop, aucun écart sur le titre,
 * l'URL, la licence, la langue, les mots-clés ni les métadonnées.
 *
 * Un seul écart de contenu, sur 4 948 : trois tabulations là où l'ancienne
 * version rendait trois espaces. La norme XML impose à un analyseur conforme de
 * remplacer les tabulations d'une valeur d'attribut par des espaces ;
 * `xpath_string` l'appliquait, l'extraction par expression régulière rend les
 * octets d'origine. L'écart est CONSERVÉ à dessein : le corpus est un corpus de
 * code, où l'indentation porte du sens.
 *
 * Voir docs/incidents/2026-08-28-conversion-spark-non-scalable.md.
 *
 * PARAMÈTRES
 * :motif_themes  expression régulière des thèmes retenus, appliquée aux
 *                étiquettes. Deux formats coexistent selon l'ancienneté du
 *                dump : « |python|pandas| » et « <python><pandas> ». Le motif
 *                doit donc accepter les deux délimiteurs.
 */

WITH lignes AS (
    -- Seules les lignes d'enregistrement. L'en-tête XML, la balise ouvrante et
    -- la balise fermante sont écartées ici, une fois pour toutes.
    SELECT ligne
      FROM posts_brut
     WHERE ligne LIKE '%<row %'
),

-- ── Étape 1 : les questions, filtrées AVANT toute analyse ────────────────
--
-- Trois prédicats de sous-chaîne, du plus sélectif au moins sélectif. Aucun
-- n'analyse quoi que ce soit : ce sont des recherches de motif dans une
-- chaîne, opération que la JVM exécute sans allouer.
questions_retenues AS (
    SELECT ligne
      FROM lignes
     WHERE ligne LIKE '% PostTypeId="1"%'
       -- Une question sans réponse acceptée n'apporte rien à un tuteur : le
       -- corpus vise le couple problème/solution validée.
       AND ligne LIKE '% AcceptedAnswerId="%'
       AND ligne LIKE '% Tags="%'
       -- Le motif des thèmes s'applique au seul attribut Tags, et non à la
       -- ligne entière : sans cette restriction, un mot du corps de la
       -- question suffirait à la retenir.
       AND regexp_extract(ligne, ' Tags="([^"]*)"', 1) RLIKE :motif_themes
),

-- ── Étape 2 : les identifiants des réponses effectivement citées ─────────
--
-- Une seule expression régulière par question retenue, ancrée sur le nom de
-- l'attribut. L'ensemble obtenu est petit — quelques centaines de milliers
-- d'identifiants — et sert de filtre aux réponses.
identifiants_attendus AS (
    SELECT DISTINCT
           CAST(regexp_extract(ligne, ' AcceptedAnswerId="([0-9]+)"', 1) AS BIGINT)
               AS id_attendu
      FROM questions_retenues
),

-- ── Étape 3 : les réponses citées, et elles seules ───────────────────────
--
-- L'identifiant est extrait par une expression régulière ancrée en début de
-- ligne : `Id` est toujours le premier attribut d'un enregistrement Stack
-- Exchange, la recherche s'arrête donc au bout de quelques caractères.
--
-- Le prédicat `LIKE` sur PostTypeId précède l'extraction : les questions,
-- majoritaires en volume de texte, sont écartées sans qu'on lise leur
-- identifiant.
reponses_candidates AS (
    SELECT ligne,
           CAST(regexp_extract(ligne, '<row Id="([0-9]+)"', 1) AS BIGINT) AS id_reponse
      FROM lignes
     WHERE ligne LIKE '% PostTypeId="2"%'
),

reponses_retenues AS (
    SELECT r.ligne
      FROM reponses_candidates r
      JOIN identifiants_attendus a
        ON a.id_attendu = r.id_reponse
),

-- ── Étape 4 : réunion, puis extraction sans analyse XML ─────────────────
retenues AS (
    SELECT ligne FROM questions_retenues
    UNION ALL
    SELECT ligne FROM reponses_retenues
)

-- Extraction des attributs par expressions régulières ancrées sur leur nom.
--
-- CE QUE CELA REMPLACE
-- La version précédente appelait `xpath_string` treize fois par ligne, et
-- chaque appel construisait un arbre XML complet du fragment. Ici il n'y a
-- PLUS AUCUNE analyse XML : treize recherches de motif, chacune ancrée sur le
-- nom de l'attribut, donc arrêtée dès qu'elle a trouvé. Une recherche de motif
-- ne construit pas d'arbre et n'alloue pas d'objet par nœud.
--
-- Une carte d'attributs construite en une seule passe — par `str_to_map` sur
-- une ligne normalisée — serait plus élégante encore. Elle n'a pas été retenue
-- ici : le découpage clé-valeur de `str_to_map` sur des valeurs contenant
-- elles-mêmes le séparateur « = », fréquent dans du code, demande une
-- vérification que la machine ne permet pas de faire aujourd'hui. Le gain
-- attendu est de surcroît secondaire : c'est le filtrage préalable qui écarte
-- l'essentiel du volume, et la carte n'agirait que sur ce qui reste.
--
-- LE DÉCODAGE DES ENTITÉS
-- `xpath_string` décodait `&lt;` en `<`. Il faut donc le faire ici, sans quoi
-- le nettoyage HTML effectué en Python ne reconnaîtrait plus les balises et
-- laisserait du balisage brut dans le corpus.
--
-- L'ordre compte : `&amp;` est décodé EN DERNIER. Le décoder en premier
-- transformerait `&amp;lt;` — un « &lt; » littéral voulu par l'auteur — en
-- `&lt;`, puis en `<`, changeant le sens du texte.
--
-- `replace` et non `regexp_replace` : la recherche porte sur des chaînes
-- littérales, pour lesquelles le moteur d'expressions régulières n'apporte rien
-- et coûte une compilation.
SELECT
    CAST(regexp_extract(ligne, '<row Id="([0-9]+)"', 1)          AS BIGINT) AS id_post,
    CAST(regexp_extract(ligne, ' PostTypeId="([0-9]+)"', 1)      AS INT)    AS type_post,
    CAST(NULLIF(regexp_extract(ligne, ' ParentId="([0-9]+)"', 1), '')
                                                                 AS BIGINT) AS id_parent,
    CAST(NULLIF(regexp_extract(ligne, ' AcceptedAnswerId="([0-9]+)"', 1), '')
                                                                 AS BIGINT) AS id_reponse_acceptee,

    NULLIF(
        replace(replace(replace(replace(replace(replace(replace(replace(
            regexp_extract(ligne, ' Title="([^"]*)"', 1),
            '&#xA;', '\n'), '&#xD;', '\r'), '&#x9;', '\t'),
            '&lt;', '<'), '&gt;', '>'), '&quot;', '"'), '&apos;', "'"),
            '&amp;', '&'),
        '')                                                                  AS titre,

    replace(replace(replace(replace(replace(replace(replace(replace(
        regexp_extract(ligne, ' Body="([^"]*)"', 1),
        '&#xA;', '\n'), '&#xD;', '\r'), '&#x9;', '\t'),
        '&lt;', '<'), '&gt;', '>'), '&quot;', '"'), '&apos;', "'"),
        '&amp;', '&')                                                        AS corps,

    NULLIF(regexp_extract(ligne, ' Tags="([^"]*)"', 1), '')                  AS mots_cles_bruts,
    CAST(NULLIF(regexp_extract(ligne, ' Score="(-?[0-9]+)"', 1), '')
                                                                 AS INT)    AS score,
    CAST(NULLIF(regexp_extract(ligne, ' ViewCount="([0-9]+)"', 1), '')
                                                                 AS INT)    AS nombre_vues,
    CAST(NULLIF(regexp_extract(ligne, ' AnswerCount="([0-9]+)"', 1), '')
                                                                 AS INT)    AS nombre_reponses,
    CAST(regexp_extract(ligne, ' CreationDate="([^"]*)"', 1)     AS TIMESTAMP) AS date_creation,
    NULLIF(regexp_extract(ligne, ' ContentLicense="([^"]*)"', 1), '')        AS licence,

    -- Colonne de partitionnement, calculée ici pour que l'écriture n'ait pas à
    -- réévaluer l'horodatage ligne par ligne.
    CAST(year(CAST(regexp_extract(ligne, ' CreationDate="([^"]*)"', 1) AS TIMESTAMP))
                                                                 AS INT)    AS annee
FROM retenues
WHERE regexp_extract(ligne, '<row Id="([0-9]+)"', 1) <> ''
