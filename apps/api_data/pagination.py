"""
Pagination de l'API du jeu de données.

Compétence visée : C5 (épreuve E1) — API REST exposant le jeu de données
"""

from rest_framework.pagination import PageNumberPagination


class PaginationJeuDonnees(PageNumberPagination):
    """
    Pagination par numéro de page, avec un plafond.

    Compétence visée : C5 (épreuve E1)
    Compétence visée : C13 (épreuve E3) — disponibilité du service

    Choix : pagination par numéro de page plutôt que par curseur. Motivation :
    le corpus est stable entre deux extractions — les documents n'y sont pas
    insérés en continu. Le décalage de pages que le curseur évite ne se produit
    donc pas en pratique, et le numéro de page reste bien plus simple à
    consommer.

    Choix : une taille de page modifiable par le client, mais plafonnée à 100.
    Motivation : sans plafond, `?taille_page=100000` ramène le corpus entier en
    un appel, contenu compris — plusieurs dizaines de mégaoctets sérialisées en
    mémoire. C'est le déni de service le moins coûteux à monter et le plus
    simple à prévenir. Le plafond répond aussi à la recommandation OWASP API4,
    « Unrestricted Resource Consumption ».
    """

    page_size = 20
    page_size_query_param = "taille_page"
    max_page_size = 100
    page_query_param = "page"
