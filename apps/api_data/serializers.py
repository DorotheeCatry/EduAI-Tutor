"""
Sérialiseurs de l'API du jeu de données.

Compétence visée : C5 (épreuve E1) — API REST exposant le jeu de données

Choix : deux sérialiseurs distincts pour la liste et le détail. Motivation :
le champ `contenu` pèse en moyenne 2 900 caractères et culmine à 33 000. Le
renvoyer intégralement sur une page de vingt documents produirait une réponse
de plusieurs centaines de kilooctets pour un appel dont l'objet est de
parcourir, pas de lire. La liste en donne un extrait, le détail le texte
entier.

Choix : aucun sérialiseur d'écriture. Motivation : l'API est en lecture seule
(décision 012). Un `ModelSerializer` complet exposerait des champs
modifiables dans la documentation OpenAPI, laissant croire à des opérations
qui n'existent pas.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import (
    Document,
    Extraction,
    Licence,
    MotCle,
    Source,
    TypeSource,
)

#: Longueur de l'extrait de contenu renvoyé en liste.
LONGUEUR_EXTRAIT = 400


class TypeSourceSerializer(serializers.ModelSerializer):
    """
    Un des cinq types de sources du référentiel.

    Compétence visée : C5 (épreuve E1)
    """

    class Meta:
        model = TypeSource
        fields = ["code_type_source", "libelle", "description"]


class LicenceSerializer(serializers.ModelSerializer):
    """
    Licence d'un document et droits qu'elle confère.

    Compétence visée : C4 (épreuve E1) — conditions de réutilisation exposées

    `attribution_requise` est renvoyée avec la licence : un client qui
    réutilise un document doit savoir s'il lui faut créditer l'auteur, et
    `url_source` lui dit où. Documenter la licence sans dire ce qu'elle exige
    reviendrait à la mentionner pour la forme.
    """

    class Meta:
        model = Licence
        fields = [
            "code_licence", "libelle", "url_texte",
            "attribution_requise", "mention_copyright",
        ]


class MotCleSerializer(serializers.ModelSerializer):
    """
    Mot-clé du corpus.

    Compétence visée : C5 (épreuve E1)
    """

    class Meta:
        model = MotCle
        fields = ["code_mot_cle", "categorie"]


class SourceSerializer(serializers.ModelSerializer):
    """
    Une des cinq sources, avec ses contraintes d'accès et sa conservation.

    Compétence visée : C1 (épreuve E1) — contraintes de source documentées
    Compétence visée : C4 (épreuve E1) — durée de conservation

    `contraintes_acces` est renvoyée intégralement : quota d'API, respect du
    robots.txt, refus de lire certains fichiers du dump. Un consommateur du jeu
    de données hérite de ces contraintes, il doit les connaître.
    """

    type_source = TypeSourceSerializer(read_only=True)
    nb_documents = serializers.IntegerField(read_only=True)

    class Meta:
        model = Source
        fields = [
            "code_source", "nom", "type_source", "url_racine",
            "contraintes_acces", "duree_conservation_jours", "nb_documents",
        ]


class DocumentListeSerializer(serializers.ModelSerializer):
    """
    Document du corpus, vue de liste.

    Compétence visée : C5 (épreuve E1)
    """

    source = serializers.CharField(source="source_id", read_only=True)
    source_nom = serializers.CharField(source="source.nom", read_only=True)
    licence = serializers.CharField(source="licence_id", read_only=True)
    mots_cles = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="code_mot_cle",
    )
    extrait = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id_document", "source", "source_nom", "code_type_source",
            "identifiant_source", "titre", "extrait", "url_source",
            "langue", "licence", "mots_cles", "extrait_le",
        ]

    def get_extrait(self, document: Document) -> str:
        """
        Renvoie le début du contenu, coupé sur un mot entier.

        Compétence visée : C5 (épreuve E1)

        Choix : couper sur une espace plutôt qu'au caractère près. Motivation :
        un extrait qui se termine au milieu d'un mot se lit mal, et coûte
        exactement la même chose à produire.
        """
        contenu = document.contenu or ""
        if len(contenu) <= LONGUEUR_EXTRAIT:
            return contenu
        coupe = contenu[:LONGUEUR_EXTRAIT]
        derniere_espace = coupe.rfind(" ")
        if derniere_espace > LONGUEUR_EXTRAIT // 2:
            coupe = coupe[:derniere_espace]
        return coupe + " […]"


class DocumentDetailSerializer(serializers.ModelSerializer):
    """
    Document du corpus, vue de détail avec les attributs de sa spécialisation.

    Compétence visée : C5 (épreuve E1)

    Choix : les attributs propres au type de source sont regroupés dans un
    objet `detail`, dont les clés varient selon le type. Motivation : le modèle
    est une spécialisation totale — un document d'API porte un score et un
    nombre de vues, un document de fichier un chemin et un module pédagogique,
    et ces champs n'ont pas d'équivalent l'un chez l'autre. Les aplatir dans
    l'objet document produirait une majorité de valeurs nulles dont le sens
    serait « sans objet », que rien ne distinguerait d'un « non renseigné ».
    """

    source = SourceSerializer(read_only=True)
    licence = LicenceSerializer(read_only=True)
    mots_cles = MotCleSerializer(many=True, read_only=True)
    detail = serializers.SerializerMethodField()
    dernier_vu_le = serializers.DateTimeField(
        read_only=True,
        help_text=(
            "Dernier chargement ayant retrouvé ce document dans sa source. "
            "Un document que sa source ne fournit plus est marqué retiré et "
            "cesse d'être servi par l'API."
        ),
    )

    class Meta:
        model = Document
        fields = [
            "id_document", "source", "code_type_source", "identifiant_source",
            "titre", "contenu", "url_source", "langue", "licence",
            "attribution_requise", "mots_cles", "extrait_le", "dernier_vu_le",
            "detail",
        ]

    def get_detail(self, document: Document) -> dict | None:
        """
        Renvoie les attributs de la table fille correspondant au type de source.

        Compétence visée : C5 (épreuve E1)

        Choix : une table de correspondance explicite plutôt qu'une
        introspection des relations. Motivation : la lisibilité prime ici — un
        lecteur du code voit d'un coup d'œil quels attributs porte chaque type,
        ce qui est précisément ce que le référentiel demande de démontrer sur
        les cinq types de sources.
        """
        correspondances = {
            "api_rest": ("detail_api_rest", (
                "score", "nombre_reponses", "nombre_vues", "cree_le",
            )),
            "scraping": ("detail_web", ("page", "ancre_section")),
            "fichier": ("detail_fichier", (
                "chemin_fichier", "format", "module_pedagogique",
                "index_section", "origine_declaree",
            )),
            "big_data": ("detail_big_data", ()),
            "base_donnees": ("detail_base_donnees", ()),
        }

        entree = correspondances.get(document.code_type_source)
        if entree is None:
            return None

        relation, champs = entree
        objet = getattr(document, relation, None)
        if objet is None:
            # Ne devrait pas arriver : un déclencheur vérifie à chaque
            # validation qu'un document a exactement une ligne fille. Le cas est
            # néanmoins traité — une API ne doit pas rendre 500 parce qu'une
            # invariante de base est violée, elle doit dire ce qu'elle voit.
            return None

        return {champ: getattr(objet, champ) for champ in champs}


class ExtractionSerializer(serializers.ModelSerializer):
    """
    Une campagne d'extraction et son bilan.

    Compétence visée : C1 (épreuve E1) — traçabilité de la collecte
    Compétence visée : C20 (épreuve E5) — suivi d'un traitement

    Le statut distingue trois cas et non deux : `succes`, `echec`, et `vide`
    pour une source qui n'avait légitimement rien à ramener. La distinction
    vient d'un incident réel — voir docs/incidents/.
    """

    source = serializers.CharField(source="source_id", read_only=True)
    source_nom = serializers.CharField(source="source.nom", read_only=True)

    class Meta:
        model = Extraction
        fields = [
            "id_extraction", "source", "source_nom", "horodatage_debut",
            "duree_secondes", "statut", "nb_enregistrements", "nb_erreurs",
            "fichier_sortie",
        ]


class StatistiquesSerializer(serializers.Serializer):
    """
    Volumétrie du corpus, par source et par type.

    Compétence visée : C5 (épreuve E1)

    Choix : un sérialiseur explicite plutôt qu'un dictionnaire brut.
    Motivation : sans lui, la documentation OpenAPI décrirait la réponse comme
    un objet quelconque, et un consommateur devrait deviner sa structure en
    l'appelant.

    Les décomptes portent sur les documents exposés, c'est-à-dire ceux dont la
    licence autorise la redistribution. Un total qui compterait les documents
    non diffusables annoncerait un corpus que l'API ne sait pas servir.
    """

    documents_exposes = serializers.IntegerField(
        help_text="Nombre de documents dont la licence autorise la diffusion.",
    )
    par_source = serializers.ListField(
        child=serializers.DictField(),
        help_text="Décompte par source, avec son nom et son type.",
    )
    par_type_source = serializers.ListField(
        child=serializers.DictField(),
        help_text="Décompte par type de source, les cinq du référentiel.",
    )
    par_licence = serializers.ListField(
        child=serializers.DictField(),
        help_text="Décompte par licence.",
    )
    par_langue = serializers.ListField(
        child=serializers.DictField(),
        help_text="Décompte par langue du document.",
    )
    mots_cles_distincts = serializers.IntegerField(
        help_text="Nombre de mots-clés rattachés à au moins un document exposé.",
    )
    derniere_extraction = serializers.DateTimeField(
        allow_null=True,
        help_text="Horodatage de la campagne d'extraction la plus récente.",
    )
