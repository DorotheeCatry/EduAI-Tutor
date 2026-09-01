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
    var JEUX = {};

    JEUX.grosPlan = {
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
            clin: false,
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

    /* La planche en pied : le salut et la réjouissance. Les états portent
     * d'autres noms que ceux du gros plan, pour qu'un `Koda.etat('parle')`
     * adressé à tout le monde laisse simplement ce Koda-ci tranquille. */
    JEUX.corps = {
        salue: {
            unique: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
                     12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
            cadence: 40, puis: "debout"
        },
        rejouit: {
            unique: [24, 25, 26, 27, 28, 29, 30, 31,
                     32, 33, 34, 35, 36, 37, 38, 39],
            cadence: 40, puis: "debout"
        },
        debout: { boucle: [40, 41, 42, 43, 44, 45, 46, 47], cadence: 120 }
    };

    /* Un état par défaut, affiché quand toute animation est refusée. */
    var IMAGE_FIXE = 0;

    /* Un clignement sur cinq devient un clin d'œil : c'est peu de chose, et
     * c'est ce qui sépare un personnage d'une image qui bat des paupières. */
    var CHANCE_DE_CLIN = 0.2;

    /* Les états depuis lesquels Koda peut s'assoupir. Il ne s'endort pas au
     * milieu d'une phrase. */
    var ETATS_EVEILLES = ["repos", "ecoute"];

    function animer(element) {
        var ETATS = JEUX[element.dataset.jeu || "grosPlan"] || JEUX.grosPlan;
        var colonnes = parseInt(element.dataset.colonnes, 10);
        var largeur = parseInt(element.dataset.largeur, 10);
        var hauteur = parseInt(element.dataset.hauteur, 10);
        var etatCourant = null;
        var minuteur = null;
        var assoupissement = null;
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
            if (assoupissement) { clearTimeout(assoupissement); assoupissement = null; }
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
                if (def.clin !== false && ETATS.clin
                        && Math.random() < CHANCE_DE_CLIN) {
                    jouerSuite(ETATS.clin.unique, ETATS.clin.cadence, tourner);
                    return;
                }
                jouerSuite(def.clignement, def.cadence, tourner);
            }, attente);
        }

        function basculer(nom) {
            if (!ETATS[nom] || nom === etatCourant) { return; }
            etatCourant = nom;
            rang = 0;
            element.setAttribute("data-etat", nom);
            clearTimeout(assoupissement);
            var delai = parseInt(element.dataset.assoupissement, 10);
            if (delai > 0 && ETATS_EVEILLES.indexOf(nom) !== -1) {
                assoupissement = setTimeout(function () {
                    basculer("somnole");
                }, delai);
            }
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
        JEUX: JEUX,
        instances: [],
        /* Il y a DEUX Koda à l'écran : celui de la poignée, visible quand le
         * chat est fermé, et celui du panneau. Un seul est visible à la fois,
         * et l'animateur ne fait rien tant qu'un élément n'est pas affiché —
         * les deux peuvent donc suivre le même état sans rien coûter. */
        brancher: function (selecteur) {
            var elements = document.querySelectorAll(selecteur || "[data-koda]");
            window.Koda.instances = Array.prototype.map.call(elements, animer);
            window.Koda.instance = window.Koda.instances[0] || null;
            return window.Koda.instances;
        },
        /* Raccourci : `Koda.etat('parle')` depuis n'importe quel script. */
        etat: function (nom) {
            window.Koda.instances.forEach(function (i) { i.basculer(nom); });
        },
        /* Réveille les Koda visibles — appelé à l'ouverture du panneau. */
        reveiller: function () {
            window.Koda.instances.forEach(function (i) {
                if (i.etat() === "dort" || i.etat() === "somnole") {
                    i.basculer("reveil");
                }
            });
        }
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { window.Koda.brancher(); });
    } else {
        window.Koda.brancher();
    }
})();
