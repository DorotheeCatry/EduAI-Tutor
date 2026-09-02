from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.agents.agent_orchestrator import get_orchestrator
from apps.quotas.service import QuotaDepasse
from apps.rag.module_loader import module_loader
from .models import Course
import re
import markdown2
from django.utils.translation import gettext as _
from apps.chat.actions import actions_pour
from apps.chat.contexte import contexte_de_cours
from django.db.models import Count
from django.views.decorators.http import require_POST

from apps.courses.models import FicheDApprenant



# Extras markdown2 retenus pour le rendu des cours. Regroupés ici plutôt que
# répétés dans chaque vue : le rendu doit être identique pour un cours qui vient
# d'être généré et pour un cours rechargé depuis la base.
MARKDOWN_EXTRAS = [
    "fenced-code-blocks",   # blocs délimités par ```python
    "highlightjs-lang",     # ajoute la classe language-* attendue par Prism
    "tables",               # tableaux avec <thead> et <th>
    "break-on-newline",     # un saut de ligne simple devient un <br>
    "cuddled-lists",        # liste collée au paragraphe qui la précède
]


def render_markdown(content):
    """
    Convertit en HTML le Markdown produit par les agents, côté serveur.

    Compétence visée : C17 (épreuve E4) — interface de l'application web
    Compétence visée : C9 (épreuve E2) — sécurisation du service exposé

    Choix : conversion côté serveur avec markdown2 plutôt qu'un parseur en
    expressions régulières côté navigateur. Le parseur JavaScript précédent
    convertissait tout `**gras**` en titre `<h3>`, ce qui coupait les phrases
    en trois et produisait une hiérarchie de titres incohérente ; il plaçait
    aussi des blocs `<h2>` et `<ul>` à l'intérieur de `<p>`, et ne traitait
    pas les tableaux.

    Choix : safe_mode="escape" pour neutraliser le HTML brut. Le sujet saisi
    par l'apprenant alimente le prompt du Pedagogue ; sans échappement, une
    injection amenant le modèle à produire une balise <script> ou un attribut
    onerror s'exécuterait dans la page (XSS, OWASP A03).

    Choix : extra "tables" afin d'obtenir des <table> à en-têtes <th>, que les
    lecteurs d'écran peuvent restituer — critère d'accessibilité transversal
    des grilles (WCAG 2.1 AA / RGAA).

    Args:
        content: le Markdown renvoyé par l'agent, ou une chaîne vide.

    Returns:
        Le HTML correspondant, prêt à être inséré dans le template.
    """
    if not content:
        return ""

    return markdown2.markdown(
        content,
        extras=MARKDOWN_EXTRAS,
        safe_mode="escape",
    )


def test_template(request):
    """Vue de test pour vérifier les templates"""
    return render(request, 'test.html')

@login_required
def course_generator(request):
    """Main view for course generation"""
    
    print(f"DEBUG: course_generator called, method: {request.method}")
    print(f"DEBUG: user authenticated: {request.user.is_authenticated}")
    
    if request.method == 'POST':
        topic = request.POST.get('topic')
        module = request.POST.get('module', '')
        
        if not topic:
            messages.error(request, _('Please enter a topic to generate the course.'))
            context = {'modules': module_loader.get_available_modules()}
            return render(request, 'courses/generate.html', context)
        
        # Use AI orchestrator to generate the course
        orchestrator = get_orchestrator(request.user)
        
        # Pass module context to orchestrator
        if module and module != 'general':
            module_info = next((m for m in module_loader.get_available_modules() if m['id'] == module), None)
            if module_info:
                orchestrator.current_module = module_info['name']
        
        # Quota de génération (C13) : le refus n'est pas une panne, il a son
        # propre message et laisse l'apprenant sur le formulaire.
        try:
            result = orchestrator.generate_course(topic)
        except QuotaDepasse as depassement:
            messages.warning(request, depassement.message)
            context = {'modules': module_loader.get_available_modules()}
            return render(request, 'courses/generate.html', context)
        
        if result['success']:
            # Add XP for course generation
            xp_result = request.user.add_xp(15, 'course_generation')
            
            # Direct markdown processing
            content = result['content']
            
            # Extract title from markdown
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            course_title = title_match.group(1) if title_match else f"Course on {topic}"
            
            context = {
                'course': {
                    'title': course_title,
                    'topic': topic,
                    'module': module,
                    'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == module), module),
                    # Le Markdown brut reste dans le contexte : c'est lui qui est
                    # renvoyé au formulaire d'enregistrement, donc stocké en base.
                    'content': content,
                    # Le HTML n'est destiné qu'à l'affichage.
                    'content_html': render_markdown(content),
                    'sources': result['sources']
                },
                'modules': module_loader.get_available_modules(),
                'is_saved_course': False,
                'xp_result': xp_result
            }
        else:
            context = {
                'error': result.get('error', 'Error during course generation'),
                'topic': topic,
                'modules': module_loader.get_available_modules(),
                'is_saved_course': False
            }
            
        return render(request, 'courses/course_detail.html', context)
    
    # GET request - show form
    context = {
        'modules': module_loader.get_available_modules()
    }
    print(f"DEBUG: Rendering template with context: {context}")
    return render(request, 'courses/generate.html', context)


@login_required
def save_course(request):
    """Save a generated course"""
    if request.method == 'POST':
        try:
            # Get form data
            title = request.POST.get('title', 'Untitled Course')
            topic = request.POST.get('topic', '')
            module = request.POST.get('module', 'general')
            content = request.POST.get('content', '')
            
            # Create course in database
            course = Course.objects.create(
                title=title,
                topic=topic,
                module=module,
                content=content,
                sources=[],
                created_by=request.user
            )
            
            # Add XP for saving a course
            request.user.add_xp(10, 'course_save')
            request.user.total_courses_completed += 1
            request.user.save()
            
            messages.success(request, _('✨ Course "%(titre)s" saved successfully!')
                              % {"titre": course.title})
            return redirect('courses:detail', course_id=course.id)
            
        except Exception as save_error:
            print(f"❌ Save error: {save_error}")
            messages.error(request, _("❌ Save error: %(erreur)s")
                            % {"erreur": save_error})
            return redirect('courses:generator')
    
    return redirect('courses:generator')



@login_required
def course_detail(request, course_id):
    """Display a saved course"""
    try:
        course = get_object_or_404(Course, id=course_id, created_by=request.user)
        course.increment_view_count()
        
        # Extract title from markdown if no explicit title
        content = course.content
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        course_title = title_match.group(1) if title_match else course.title

        # Contexte transmis au tuteur : le cours, et la section lue quand elle
        # est connue — jamais le cours entier. C'est l'unité sur laquelle on
        # bloque, et transporter le tout saturerait la fenêtre du modèle à
        # chaque question (décision 029).
        contexte_tuteur = contexte_de_cours(course)
        contexte_tuteur['actions'] = [
            {'code': action['code'], 'libelle': str(action['libelle'])}
            for action in actions_pour('cours')
        ]

        context = {
            'contexte_tuteur': contexte_tuteur,
            'course': {
                'title': course_title,
                'topic': course.topic,
                'module': course.module,
                'module_name': next((m['name'] for m in module_loader.get_available_modules() if m['id'] == course.module), course.module.replace('_', ' ').title()) if course.module and course.module != 'general' else None,
                'content': course.content,
                'content_html': render_markdown(course.content),
                'sources': course.sources
            },
            'is_saved_course': True  # Flag pour identifier un cours sauvegardé
        }
    except Course.DoesNotExist:
        messages.error(request, _('❌ Course not found.'))
        return redirect('courses:generator')
    
    return render(request, 'courses/course_detail.html', context)

@require_http_methods(["GET"])
def get_modules_api(request):
    """API to get list of available modules"""
    modules = module_loader.get_available_modules()
    return JsonResponse({'modules': modules})

@require_http_methods(["GET"])
def get_sections_api(request, module_id):
    """API to get sections of a module"""
    sections = module_loader.get_module_sections(module_id)
    
    # Format sections for API
    formatted_sections = []
    for section_key, files in sections.items():
        formatted_sections.append({
            'id': section_key,
            'name': section_key.replace('_', ' ').replace(section_key.split('_')[0] + '_', '').title(),
            'files_count': len(files),
            'files': files
        })
    
    return JsonResponse({
        'module_id': module_id,
        'sections': formatted_sections
    })

@login_required
def my_courses(request):
    """List of user's saved courses"""
    courses = Course.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'courses': courses
    }
    return render(request, 'courses/my_courses.html', context)

@login_required
def delete_course(request, course_id):
    """Delete a saved course"""
    if request.method == 'POST':
        try:
            course = get_object_or_404(Course, id=course_id, created_by=request.user)
            course_title = course.title
            course.delete()
            messages.success(request, _('🗑️ Course "%(titre)s" deleted successfully!')
                              % {"titre": course_title})
        except Course.DoesNotExist:
            messages.error(request, _('❌ Course not found.'))
        except Exception as delete_error:
            messages.error(request, _("❌ Delete error: %(erreur)s")
                            % {"erreur": delete_error})
    
    return redirect('courses:my_courses')


# ===========================================================================
# L'onglet à trois entrées : mes fiches, catalogue, sujet libre
# ===========================================================================
#
# Compétence visée : C17 (épreuve E4)
#
# L'entrée naturelle vers un cours reste le parcours, depuis « ce que je fais
# maintenant » sur l'accueil. Cet onglet est le catalogue, pas la porte
# principale — c'est pourquoi il ne remplace pas le générateur mais l'accueille
# comme une entrée parmi trois.


@login_required
def catalogue(request):
    """
    Les compétences du référentiel, avec l'état de leur cours et de la fiche.

    Compétence visée : C17 (épreuve E4)

    Choix : trois états affichés en toutes lettres — cours publié, cours
    provisoire, aucun cours. Motivation : la distinction entre un contenu relu
    par un formateur et une production automatique décide de la confiance que
    l'apprenant lui accorde ; elle ne peut pas reposer sur une nuance de
    couleur.
    """
    from apps.courses.services import cours_actif
    from apps.referentiel.models import Competence
    from apps.referentiel.services import referentiel_actif

    referentiel = referentiel_actif()
    competences = (
        Competence.objects
        .filter(module__referentiel=referentiel)
        .select_related("module")
        .order_by("module__ordre", "module__code", "code")
        if referentiel else Competence.objects.none()
    )

    fiches = {f.competence_id: f for f in
              FicheDApprenant.objects.filter(apprenant=request.user)
              .annotate(nombre_ajouts=Count("ajouts"))}

    entrees = []
    for competence in competences:
        cours = cours_actif(competence)
        entrees.append({
            "competence": competence,
            "cours": cours,
            "fiche": fiches.get(competence.id),
        })

    return render(request, "courses/catalogue.html", {
        "referentiel": referentiel,
        "entrees": entrees,
        "mes_fiches": [f for f in fiches.values() if f.nombre_ajouts],
    })


@login_required
def page_de_cours(request, code):
    """
    Le cours de référence d'une compétence, et les actions qui l'enrichissent.

    Compétence visée : C17 (épreuve E4)
    """
    from apps.courses.services import cours_actif, fiche_de
    from apps.referentiel.models import Competence

    competence = get_object_or_404(Competence, code=code)
    cours = cours_actif(competence)
    fiche = fiche_de(request.user, competence)

    return render(request, "courses/page_de_cours.html", {
        "competence": competence,
        "cours": cours,
        # Le markdown est rendu ici, côté serveur, comme pour les cours générés
        # (décision 002), et **partie par partie** : un cours de référence
        # rassemble plusieurs fichiers, et le sommaire se tire de leurs titres
        # plutôt que d'une analyse du HTML.
        "parties": [
            {"ancre": partie.ancre, "titre": partie.titre,
             "sous_module": partie.sous_module,
             "contenu": render_markdown(partie.contenu)}
            for partie in cours.parties.all()
        ] if cours else [],
        "fiche": fiche,
        "ajouts": fiche.ajouts.all(),
        "actions": ACTIONS_D_ENRICHISSEMENT,
    })


@login_required
def ma_fiche(request, code):
    """
    La fiche de l'apprenant pour une compétence : sommaire, ajouts, exercices.

    Compétence visée : C17 (épreuve E4)

    Choix : les exercices réalisés sont affichés ici, sans rien enregistrer de
    nouveau. Motivation : leur rattachement à la compétence existe déjà
    (décision 027) ; il suffisait de les montrer au bon endroit.
    """
    from apps.courses.services import cours_actif, fiche_de
    from apps.exercises.models import UserExerciseProgress
    from apps.referentiel.models import Competence

    competence = get_object_or_404(Competence, code=code)
    fiche = fiche_de(request.user, competence)

    exercices = (
        UserExerciseProgress.objects
        .filter(user=request.user, exercise__competence=competence)
        .select_related("exercise")
        .order_by("-completed_at", "-first_attempt_at")
    )

    return render(request, "courses/fiche.html", {
        "competence": competence,
        "fiche": fiche,
        "ajouts": fiche.ajouts.all(),
        "cours": cours_actif(competence),
        "exercices": exercices,
    })


#: Les actions proposées sur une page de cours. Elles reprennent celles du
#: tuteur (`apps/chat/actions.py`) : ce sont les mêmes gestes, au même moment.
ACTIONS_D_ENRICHISSEMENT = (
    {"cle": "developper", "libelle": _("Développe cette partie")},
    {"cle": "cas_complexe", "libelle": _("Un cas plus complexe")},
    {"cle": "incompris", "libelle": _("Je ne comprends pas")},
)


@login_required
@require_POST
def enrichir_la_fiche(request, code):
    """
    Produit un enrichissement et l'ajoute à la fiche.

    Compétence visée : C17 (épreuve E4), C13 (E3)

    Choix : le refus de quota est rendu tel quel à l'appelant, jamais converti
    en panne. Motivation : un apprenant qui a épuisé ses quinze générations doit
    lire qu'il les a épuisées, pas « une erreur est survenue ».
    """
    from apps.courses.models import AjoutDeFiche
    from apps.courses.services import enrichir
    from apps.quotas.service import QuotaDepasse
    from apps.referentiel.models import Competence

    competence = get_object_or_404(Competence, code=code)
    question = (request.POST.get("question") or "").strip()
    section = (request.POST.get("section") or "").strip()
    if not question:
        return JsonResponse({"error": _("Question absente.")}, status=400)

    try:
        ajout = enrichir(request.user, competence, question,
                         origine=AjoutDeFiche.A_LA_DEMANDE, section_visee=section)
    except QuotaDepasse as refus:
        return JsonResponse({"error": str(refus), "quota": True}, status=429)

    return JsonResponse({
        "contenu": ajout.contenu,
        "question": ajout.question,
        "sources": ajout.sources,
        "cree_le": ajout.cree_le.isoformat(),
    })


@login_required
@require_POST
def executer_du_code(request, code):
    """
    Exécute un extrait Python et rend sa sortie, sans rien enregistrer.

    Compétence visée : C17 (épreuve E4)
    Compétences concernées : C13 (E3) — sécurité ; C10 (E3)

    Choix : réemployer `SecurePythonExecutor`, celui des exercices, plutôt
    qu'un `exec` de circonstance. Motivation : il valide le code avant de le
    compiler, restreint les fonctions accessibles, borne la durée et capture
    les sorties. Écrire un second chemin d'exécution reviendrait à écrire une
    seconde surface d'attaque, et à devoir la maintenir aussi bien.

    Choix : rien n'est enregistré. Motivation : cette cellule sert à essayer,
    pas à rendre un travail. Les exercices, eux, passent par leur propre vue,
    qui enregistre la soumission et la rattache à sa compétence.

    Choix : aucun quota. Motivation : l'exécution est locale, elle n'appelle
    aucun service facturé. Le quota compte des générations, pas des essais.
    """
    from apps.exercises.security import SecurePythonExecutor

    extrait = (request.POST.get("code") or "").strip()
    if not extrait:
        return JsonResponse({"error": _("Aucun code à exécuter.")}, status=400)

    resultat = SecurePythonExecutor().execute_code(extrait)
    return JsonResponse({
        "succes": bool(resultat.get("success")),
        "sortie": resultat.get("output") or "",
        "erreur": resultat.get("error") or "",
        "expire": bool(resultat.get("timeout")),
        "duree": round(resultat.get("execution_time") or 0, 3),
    })
