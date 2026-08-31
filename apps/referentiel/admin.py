"""
Administration du référentiel — le seul chemin de lecture avant la page d'accueil.

Compétence visée : C17 (épreuve E4) — application web

Pourquoi cette inscription compte : entre l'import et la page d'accueil, rien
n'affiche le référentiel. L'administration lui donne un consommateur réel,
atteignable par une personne, dès maintenant — sans quoi ces modèles seraient
du code écrit, joignable et jamais appelé, soit la troisième famille
d'incidents de ce projet (`docs/motifs_incidents.md`).

Choix : lecture seule sur les compétences importées. Motivation : le
référentiel est un fichier, et l'éditer par l'administration ferait diverger la
base de sa source sans que le prochain import le signale — il écraserait la
retouche sans rien dire.
"""

from django.contrib import admin

from .models import Competence, Module, Referentiel


class CompetenceEnLigne(admin.TabularInline):
    model = Competence
    extra = 0
    can_delete = False
    fields = ("ordre", "code", "intitule", "description")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class ModuleEnLigne(admin.TabularInline):
    model = Module
    extra = 0
    can_delete = False
    fields = ("ordre", "code", "intitule")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Referentiel)
class ReferentielAdmin(admin.ModelAdmin):
    list_display = ("intitule", "code", "version", "est_actif", "nombre_de_competences",
                    "importe_le")
    list_filter = ("est_actif",)
    search_fields = ("code", "intitule", "source")
    inlines = [ModuleEnLigne]
    readonly_fields = ("importe_le",)

    @admin.display(description="Compétences")
    def nombre_de_competences(self, objet):
        return Competence.objects.filter(module__referentiel=objet).count()


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("intitule", "code", "referentiel", "ordre", "nombre_de_competences")
    list_filter = ("referentiel",)
    search_fields = ("code", "intitule")
    inlines = [CompetenceEnLigne]

    @admin.display(description="Compétences")
    def nombre_de_competences(self, objet):
        return objet.competences.count()


@admin.register(Competence)
class CompetenceAdmin(admin.ModelAdmin):
    list_display = ("intitule", "code", "module", "ordre")
    list_filter = ("module__referentiel", "module")
    search_fields = ("code", "intitule", "description")
