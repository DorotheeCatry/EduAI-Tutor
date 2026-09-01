/*
 * Construction de la feuille de style, en Tailwind 3.4.17.
 *
 * Compétence visée : C17 (épreuve E4) — application web
 * Choix : la version reprend exactement celle que servait le CDN, pour que le
 * passage d'une feuille générée dans le navigateur à une feuille compilée ne
 * change rien à l'apparence. Le nécessaire `django-tailwind` déjà présent est
 * en version 4 : il produirait un rendu différent, et sa construction échoue
 * de toute façon sur le Node 12 installé (décision 034).
 *
 * Les chemins ci-dessous doivent couvrir TOUT gabarit contenant des classes.
 * Un gabarit oublié perd ses styles sans que rien ne le signale — c'est le
 * risque propre à cette approche, et la raison du test de non-régression.
 */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './theme/templates/**/*.html',
    // Les gabarits ne sont pas les seuls porteurs de classes : les widgets de
    // formulaire les déclarent en Python (`apps/users/forms.py`). Un chemin
    // oublié ici donne une page sans styles, sans que rien ne le signale.
    './apps/**/*.py',
  ],
  theme: {
    extend: {
      colors: {
        'primary-rose': '#C586C0',
        'primary-blue': '#007ACC',
        'primary-green': '#4CAF50',
        'primary-gray': '#D4D4D4',
      },
    },
  },
}
