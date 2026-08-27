"""
Modèles en lecture seule sur les tables de eduai_data.

Compétence visée : C5 (épreuve E1) — API REST exposant le jeu de données
Compétence visée : C4 (épreuve E1) — séparation des deux bases

Choix : `managed = False` sur tous les modèles. Motivation : le schéma de
`eduai_data` appartient aux scripts de `data_pipeline/load/sql/`, où il est
écrit, commenté et versionné comme une preuve d'évaluation (décision 006). Sans
`managed = False`, `makemigrations` proposerait de recréer les treize tables
sous forme de migrations Django, et le dépôt se retrouverait avec deux
définitions concurrentes du même schéma — dont l'une, la migration, perdrait au
passage les contraintes nommées, les déclencheurs et les commentaires SQL.

Choix : ces modèles décrivent le schéma sans le posséder. Ils sont donc écrits
à partir de la table réelle, colonne par colonne, avec `db_column` explicite
partout où le nom Django diffèrerait. Un modèle qui « devine » les noms de
colonnes se désaligne silencieusement à la première évolution du schéma.
"""

from __future__ import annotations

from django.db import models


class TypeSource(models.Model):
    """
    Les cinq types de sources exigés par le référentiel.

    Compétence visée : C1 (épreuve E1) — couverture des cinq types
    """

    code_type_source = models.CharField(max_length=20, primary_key=True)
    libelle = models.CharField(max_length=100)
    description = models.TextField()

    class Meta:
        managed = False
        db_table = "type_source"
        ordering = ["code_type_source"]
        verbose_name = "type de source"
        verbose_name_plural = "types de source"

    def __str__(self) -> str:
        return f"{self.code_type_source} — {self.libelle}"


class Licence(models.Model):
    """
    Licence d'un document, et droits qu'elle confère.

    Compétence visée : C4 (épreuve E1) — respect des conditions de réutilisation

    `redistribution_autorisee` n'est pas documentaire : c'est le champ sur
    lequel repose le filtrage de l'API. Un document dont la licence l'interdit
    ne sort jamais, quel que soit le point de terminaison interrogé.
    """

    code_licence = models.CharField(max_length=20, primary_key=True)
    libelle = models.CharField(max_length=150)
    url_texte = models.CharField(max_length=255, null=True)
    redistribution_autorisee = models.BooleanField()
    attribution_requise = models.BooleanField()
    mention_copyright = models.CharField(max_length=255, null=True)

    class Meta:
        managed = False
        db_table = "licence"
        ordering = ["code_licence"]

    def __str__(self) -> str:
        return self.code_licence


class Source(models.Model):
    """
    Une des cinq sources du corpus, avec ses contraintes d'accès.

    Compétence visée : C1 (épreuve E1) — contraintes de la source documentées
    Compétence visée : C4 (épreuve E1) — durée de conservation
    """

    code_source = models.CharField(max_length=2, primary_key=True)
    nom = models.CharField(max_length=100, unique=True)
    type_source = models.ForeignKey(
        TypeSource, on_delete=models.DO_NOTHING, db_column="code_type_source",
        related_name="sources",
    )
    url_racine = models.CharField(max_length=255, null=True)
    contraintes_acces = models.TextField()
    duree_conservation_jours = models.SmallIntegerField(null=True)

    class Meta:
        managed = False
        db_table = "source"
        ordering = ["code_source"]

    def __str__(self) -> str:
        return f"{self.code_source} — {self.nom}"


class MotCle(models.Model):
    """
    Mot-clé du corpus : étiquette de source ou module pédagogique.

    Compétence visée : C3 (épreuve E1) — vocabulaire homogénéisé
    """

    code_mot_cle = models.CharField(max_length=60, primary_key=True)
    categorie = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = "mot_cle"
        ordering = ["code_mot_cle"]
        verbose_name = "mot-clé"
        verbose_name_plural = "mots-clés"

    def __str__(self) -> str:
        return self.code_mot_cle


def condition_exposable_depuis_source() -> models.Q:
    """
    Les deux critères d'exposition d'un document, vus depuis Source.

    Compétence visée : C4 (épreuve E1)

    Choix : cette condition vit à côté du gestionnaire qui porte les mêmes
    règles, et non dans le fichier des vues. Motivation : les agrégations
    traversant la relation inverse `source -> documents` n'appliquent pas le
    gestionnaire du modèle lié ; il faut donc réécrire les règles. Les placer
    ici rend les deux formulations voisines et leur divergence visible — sans
    quoi l'API annoncerait un décompte que sa propre liste ne servirait pas.

    Le second critère vient d'un écart constaté : `/sources/` annonçait 235
    documents pour la documentation Python quand la source n'en fournissait plus
    que 234, une section ayant disparu entre deux scrapings.
    """
    return models.Q(
        documents__licence__redistribution_autorisee=True,
        documents__retire_le__isnull=True,
    )


class DocumentExposableManager(models.Manager):
    """
    Gestionnaire n'exposant que les documents diffusables et toujours observés.

    Compétence visée : C4 (épreuve E1) — respect des conditions de licence
    Compétence visée : C5 (épreuve E1) — API du jeu de données

    Choix : le filtre est porté par le gestionnaire par défaut, et non par
    chaque vue. Motivation : une exigence qu'on peut oublier point de
    terminaison par point de terminaison n'est pas une garantie, c'est une
    consigne. Placé ici, le filtre s'applique à toute requête écrite un jour
    sur ce modèle — liste, détail, statistiques, filtre, recherche — y compris
    celles qui n'existent pas encore.

    Deux ensembles sont concernés aujourd'hui : les 82 documents du corpus
    local dont l'origine n'est pas tranchée, chargés sous la licence
    `A_VERIFIER`, et les productions d'apprenants de la source S4, dont la
    licence `PRODUCTION-APPRENANT` réserve l'usage à l'organisme de formation.

    **Second critère : les documents retirés sont exclus.** Un document dont
    `retire_le` est renseigné a disparu de sa source entre deux extractions. Il
    reste en base, avec ses lignes de `collecte` qui attestent qu'il a bien été
    collecté un jour — sa disparition est une information sur la source, pas
    une erreur à effacer. Mais l'API ne le sert plus : il ne fait plus partie du
    corpus que la source fournit aujourd'hui.

    Choix : aucun gestionnaire non filtré n'est fourni. Motivation : en ajouter
    un « pour les cas particuliers » rendrait le contournement disponible, donc
    tôt ou tard utilisé. Le pipeline, qui a besoin de tout voir, n'utilise pas
    l'ORM.
    """

    def get_queryset(self):
        return (
            super().get_queryset()
            .filter(licence__redistribution_autorisee=True)
            .filter(retire_le__isnull=True)
        )


class Document(models.Model):
    """
    Un document du corpus, quelle que soit sa source.

    Compétence visée : C5 (épreuve E1)

    La spécialisation par type de source vit dans cinq tables filles, une par
    type, reliées en un-à-un. Le détail d'un document expose celle qui le
    concerne — voir `apps/api_data/serializers.py`.
    """

    LANGUES = [("fr", "Français"), ("en", "Anglais")]

    id_document = models.AutoField(primary_key=True)
    source = models.ForeignKey(
        Source, on_delete=models.DO_NOTHING, db_column="code_source",
        related_name="documents",
    )
    # Colonne dénormalisée à dessein : elle porte la clé étrangère composite
    # (code_source, code_type_source) vers `source`, qui interdit toute
    # divergence entre les deux. Django ne sait pas décrire une clé composite ;
    # le champ est donc exposé simplement, la contrainte restant tenue par le
    # moteur.
    code_type_source = models.CharField(max_length=20)
    identifiant_source = models.CharField(max_length=120)
    licence = models.ForeignKey(
        Licence, on_delete=models.DO_NOTHING, db_column="code_licence",
        related_name="documents",
    )
    attribution_requise = models.BooleanField()
    titre = models.CharField(max_length=255)
    contenu = models.TextField()
    url_source = models.CharField(max_length=500, null=True)
    langue = models.CharField(max_length=2, choices=LANGUES)
    extrait_le = models.DateTimeField()

    #: Dernier chargement ayant retrouvé ce document dans le corpus.
    dernier_vu_le = models.DateTimeField()

    #: Date à laquelle le chargeur a constaté sa disparition de la source,
    #: ou None s'il est toujours observé. Un document retiré reste en base —
    #: sa disparition est une information sur la source, pas une erreur — mais
    #: il sort du corpus servi par l'API.
    retire_le = models.DateTimeField(null=True)

    mots_cles = models.ManyToManyField(
        MotCle, through="Description", related_name="documents",
    )

    objects = DocumentExposableManager()

    class Meta:
        managed = False
        db_table = "document"
        ordering = ["-extrait_le", "id_document"]

    def __str__(self) -> str:
        return f"[{self.source_id}] {self.titre}"


class Description(models.Model):
    """
    Association entre un document et un mot-clé.

    Compétence visée : C5 (épreuve E1)

    Choix : `CompositePrimaryKey`, apparue dans Django 5.2. Motivation : la
    table a pour clé primaire le couple (document, mot-clé), et aucune colonne
    technique. Déclarer arbitrairement `id_document` comme clé primaire ferait
    croire à Django qu'un document n'a qu'un seul mot-clé, et la moitié des
    associations disparaîtrait des résultats sans erreur.
    """

    # Les noms attendus sont ceux des CHAMPS Django, non ceux des colonnes :
    # « document » et « mot_cle », dont les db_column valent id_document et
    # code_mot_cle.
    pk = models.CompositePrimaryKey("document", "mot_cle")
    document = models.ForeignKey(
        Document, on_delete=models.DO_NOTHING, db_column="id_document",
    )
    mot_cle = models.ForeignKey(
        MotCle, on_delete=models.DO_NOTHING, db_column="code_mot_cle",
    )

    class Meta:
        managed = False
        db_table = "description"


class DocumentApiRest(models.Model):
    """
    Attributs propres aux documents issus d'un service web (S1).

    Compétence visée : C5 (épreuve E1)
    """

    document = models.OneToOneField(
        Document, on_delete=models.DO_NOTHING, db_column="id_document",
        primary_key=True, related_name="detail_api_rest",
    )
    code_type_source = models.CharField(max_length=20)
    score = models.IntegerField()
    nombre_reponses = models.SmallIntegerField()
    nombre_vues = models.IntegerField()
    cree_le = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "document_api_rest"


class DocumentWeb(models.Model):
    """
    Attributs propres aux documents issus du scraping (S2).

    Compétence visée : C5 (épreuve E1)
    """

    document = models.OneToOneField(
        Document, on_delete=models.DO_NOTHING, db_column="id_document",
        primary_key=True, related_name="detail_web",
    )
    code_type_source = models.CharField(max_length=20)
    page = models.CharField(max_length=255)
    ancre_section = models.CharField(max_length=255, null=True)

    class Meta:
        managed = False
        db_table = "document_web"


class DocumentFichier(models.Model):
    """
    Attributs propres aux documents issus d'un fichier local (S3).

    Compétence visée : C5 (épreuve E1)
    """

    document = models.OneToOneField(
        Document, on_delete=models.DO_NOTHING, db_column="id_document",
        primary_key=True, related_name="detail_fichier",
    )
    code_type_source = models.CharField(max_length=20)
    chemin_fichier = models.CharField(max_length=255)
    format = models.CharField(max_length=10)
    module_pedagogique = models.CharField(max_length=50)
    index_section = models.SmallIntegerField()
    origine_declaree = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "document_fichier"


class DocumentBigData(models.Model):
    """
    Rattachement des documents issus du système big data (S5).

    Compétence visée : C5 (épreuve E1)

    La table ne porte aucun attribut propre : elle existe parce que la
    spécialisation du modèle est totale — un document appartient à exactement
    une table fille, ce qu'un déclencheur vérifie à chaque validation.
    """

    document = models.OneToOneField(
        Document, on_delete=models.DO_NOTHING, db_column="id_document",
        primary_key=True, related_name="detail_big_data",
    )
    code_type_source = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = "document_big_data"


class DocumentBaseDonnees(models.Model):
    """
    Rattachement des documents issus de la base applicative (S4).

    Compétence visée : C5 (épreuve E1)
    """

    document = models.OneToOneField(
        Document, on_delete=models.DO_NOTHING, db_column="id_document",
        primary_key=True, related_name="detail_base_donnees",
    )
    code_type_source = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = "document_base_donnees"


class Extraction(models.Model):
    """
    Une campagne d'extraction, telle que l'extracteur l'a rapportée.

    Compétence visée : C1 (épreuve E1) — traçabilité de la collecte
    Compétence visée : C20 (épreuve E5) — suivi d'un traitement

    L'historique de cette table est ce qui permet de voir une source se
    dégrader : un volume qui s'effondre, une durée qui dérive, un taux d'erreur
    qui monte. Le statut `vide` s'y distingue de `succes` et de `echec` — une
    base applicative sans production d'apprenant n'est pas une panne.
    """

    id_extraction = models.AutoField(primary_key=True)
    source = models.ForeignKey(
        Source, on_delete=models.DO_NOTHING, db_column="code_source",
        related_name="extractions",
    )
    horodatage_debut = models.DateTimeField()
    duree_secondes = models.DecimalField(max_digits=10, decimal_places=2)
    statut = models.CharField(max_length=10)
    nb_enregistrements = models.IntegerField()
    nb_erreurs = models.IntegerField()
    fichier_sortie = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "extraction"
        ordering = ["-horodatage_debut"]

    def __str__(self) -> str:
        return f"{self.source_id} {self.horodatage_debut:%Y-%m-%d %H:%M} ({self.statut})"
