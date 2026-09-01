/*
 * Koda — le tuteur incarné.
 *
 * Compétence visée : C17 (épreuve E4) — application web
 * Compétences concernées : C13 (E3) — accessibilité et poids des ressources
 *
 * Une planche de sprites unique, déplacée par `background-position`. Deux
 * options ont été écartées :
 *
 *  - `steps()` en CSS seul : impose une cadence constante par état, alors que
 *    le repos demande un clignement à intervalle IRRÉGULIER — un clignement
 *    métronomique donne un automate, pas un personnage.
 *  - `<canvas>` : même nombre de requêtes, mais retire l'image du flux du
 *    document, donc de la portée d'un lecteur d'écran, pour aucun gain ici.
 *
 * L'ÉTAT DE KODA NE PORTE JAMAIS SEUL UNE INFORMATION. Il accompagne un texte
 * qui reste lisible sans lui.
 */
(function () {
    "use strict";

    /* Les durées sont ici, en un seul endroit, et se règlent sans toucher au
     * reste du code — comme le demande le cahier du chantier. */
    var ETATS = {
        repos: {
            base: 0,
            clignement: [1, 2, 3, 2, 1],
            cadence: 60,
            reposMin: 4000, reposMax: 7000
        },
        ecoute: {
            base: 4,
            clignement: [1, 2, 3, 2, 1],
            cadence: 60,
            reposMin: 8000, reposMax: 12000
        },
        reflechit: {
            base: 1,
            clignement: [2, 3, 2],
            cadence: 90,
            reposMin: 2500, reposMax: 4000
        },
        parle: {
            boucle: [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
            cadence: 70
        },
        clin: { unique: [1, 23, 23, 23, 1, 0], cadence: 80, puis: "repos" },
        somnole: { unique: [24, 25, 26, 27, 28], cadence: 120, puis: "dort" },
        dort: { boucle: [29, 30, 31, 32], cadence: 250 },
        reveil: { unique: [36, 35, 34, 33], cadence: 80, puis: "repos" }
    };

    /* Un état par défaut, affiché quand toute animation est refusée. */
    var IMAGE_FIXE = 0;

    function animer(element) {
        var colonnes = parseInt(element.dataset.colonnes, 10);
        var largeur = parseInt(element.dataset.largeur, 10);
        var hauteur = parseInt(element.dataset.hauteur, 10);
        var etatCourant = null;
        var minuteur = null;
        var rang = 0;

        function poser(indice) {
            element.style.backgroundPosition =
                (-(indice % colonnes) * largeur) + "px " +
                (-Math.floor(indice / colonnes) * hauteur) + "px";
        }

        function mouvementRefuse() {
            /* Deux refus indépendants : le réglage du système, et celui que
             * l'apprenant a posé dans son profil. L'un ou l'autre suffit. */
            if (element.dataset.animation === "desactivee") { return true; }
            return window.matchMedia
                && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        }

        function invisible() {
            /* Une boucle qui tourne dans un onglet en arrière-plan ou derrière
             * un panneau replié consomme de la batterie pour rien. */
            return document.hidden || element.offsetParent === null;
        }

        function arreter() {
            if (minuteur) { clearTimeout(minuteur); minuteur = null; }
        }

        function jouerSuite(images, cadence, apres) {
            var i = 0;
            (function suivante() {
                if (i >= images.length) { apres(); return; }
                poser(images[i]);
                i += 1;
                minuteur = setTimeout(suivante, cadence);
            })();
        }

        function tourner() {
            arreter();
            var def = ETATS[etatCourant];
            if (!def) { return; }

            if (mouvementRefuse()) {
                poser(def.base !== undefined ? def.base : IMAGE_FIXE);
                return;
            }
            if (invisible()) { return; }

            if (def.boucle) {
                rang = (rang + 1) % def.boucle.length;
                poser(def.boucle[rang]);
                minuteur = setTimeout(tourner, def.cadence);
                return;
            }
            if (def.unique) {
                jouerSuite(def.unique, def.cadence, function () {
                    if (def.puis) { basculer(def.puis); }
                });
                return;
            }
            /* État au repos : une image fixe, et un clignement de loin en
             * loin, à intervalle tiré au hasard dans une fourchette. */
            poser(def.base);
            var attente = def.reposMin
                + Math.random() * (def.reposMax - def.reposMin);
            minuteur = setTimeout(function () {
                if (invisible()) { tourner(); return; }
                jouerSuite(def.clignement, def.cadence, tourner);
            }, attente);
        }

        function basculer(nom) {
            if (!ETATS[nom] || nom === etatCourant) { return; }
            etatCourant = nom;
            rang = 0;
            element.setAttribute("data-etat", nom);
            /* L'alternative textuelle ne décrit que les états qui SIGNIFIENT
             * quelque chose. La boucle de repos est décorative : un lecteur
             * d'écran ne doit pas annoncer « Koda respire » toutes les deux
             * secondes. */
            var parlant = element.dataset["alt" + nom.charAt(0).toUpperCase() + nom.slice(1)];
            if (parlant) {
                element.setAttribute("role", "img");
                element.setAttribute("aria-label", parlant);
                element.removeAttribute("aria-hidden");
            } else {
                element.removeAttribute("role");
                element.removeAttribute("aria-label");
                element.setAttribute("aria-hidden", "true");
            }
            tourner();
        }

        document.addEventListener("visibilitychange", tourner);
        if (window.matchMedia) {
            var requete = window.matchMedia("(prefers-reduced-motion: reduce)");
            if (requete.addEventListener) { requete.addEventListener("change", tourner); }
        }

        basculer(element.dataset.etatInitial || "repos");
        return { basculer: basculer, arreter: arreter, etat: function () { return etatCourant; } };
    }

    window.Koda = {
        ETATS: ETATS,
        brancher: function (selecteur) {
            var element = document.querySelector(selecteur || "[data-koda]");
            if (!element) { return null; }
            window.Koda.instance = animer(element);
            return window.Koda.instance;
        },
        /* Raccourci : `Koda.etat('parle')` depuis n'importe quel script. */
        etat: function (nom) {
            if (window.Koda.instance) { window.Koda.instance.basculer(nom); }
        }
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { window.Koda.brancher(); });
    } else {
        window.Koda.brancher();
    }
})();
