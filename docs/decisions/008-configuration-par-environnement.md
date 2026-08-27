# 008 — Configuration par l'environnement et réglages de sécurité conditionnels

**Date :** 27/08/2026
**Statut :** adoptée
**Compétences concernées :** C13 (E3), C17 (E4)

## Contexte

La bascule vers `eduai_app` obligeait à écrire des paramètres de connexion dans
`settings.py`. Le fichier est versionné, et il contenait déjà trois valeurs qui
n'auraient pas dû s'y trouver : `DEBUG = True` en dur, le domaine
`.ngrok-free.app` en dur, et — jusqu'au commit `30d4e94` — la clé secrète.

## Options

1. **Tout dans `settings.py`**, y compris le mot de passe de la base. Écarté :
   un mot de passe versionné est un mot de passe public.
2. **Variables d'environnement avec valeurs de repli dans le code.** Le
   démarrage ne casse jamais, mais un `.env` oublié fait tourner l'application
   avec les valeurs de repli sans que rien ne l'annonce.
3. **Variables d'environnement, sans repli sur les valeurs sensibles.**

## Décision

Option 3, avec une règle de défaut asymétrique. Les secrets — clé Django, mot
de passe PostgreSQL — n'ont aucune valeur de repli : leur absence interrompt le
démarrage. Les réglages de confort ont un défaut, choisi du côté sûr :
`DJANGO_DEBUG` vaut `False` faute de variable, `DJANGO_ALLOWED_HOSTS` se limite
à la boucle locale.

Les réglages de transport — redirection HTTPS, HSTS, cookies `Secure` — sont
conditionnés à `DEBUG = False`. Ils exigent HTTPS, que le serveur de
développement ne fournit pas.

## Conséquences

- Une variable oubliée dégrade le confort de développement, jamais la sécurité
  de l'exposition. C'est le sens du défaut à `False`.
- Le conditionnement par `DEBUG` évite le contournement le plus courant :
  un réglage qui gêne en local finit désactivé globalement, pas
  conditionnellement.
- `SECURE_PROXY_SSL_HEADER` n'est posé que sur déclaration explicite
  (`DJANGO_DERRIERE_PROXY`). Faire confiance à cet en-tête sans proxy devant
  permettrait à n'importe quel client de l'émettre lui-même et de contourner la
  redirection HTTPS.
- Le domaine d'exposition par tunnel se retire en modifiant `.env`, sans
  commit. Un domaine public inscrit dans le dépôt survit à la démonstration qui
  l'a justifié.
- Preuve vérifiable : `DJANGO_DEBUG=False uv run python manage.py check
  --deploy` ne signale aucun avertissement.
