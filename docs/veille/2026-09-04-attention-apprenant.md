# Veille pédagogique — l'attention de l'apprenant face à un tuteur IA

**Date de la session :** 04/09/2026
**Thématique :** ce qu'un assistant IA fait à l'attention et à l'apprentissage, et ce qu'un tuteur doit refuser de faire.
**Décision liée :** le panneau du tuteur (E3, C10), le refus de donner la solution (décision 012), le quota par apprenant.

---

## 1. Pourquoi cette thématique

Un tuteur qui répond à tout, tout de suite, est le produit le plus facile à construire et le plus dangereux à mettre devant un apprenant. Le projet a fait trois choix dès le départ — le tuteur ne donne pas la solution, il reçoit le contexte de la page au lieu de forcer l'apprenant à le quitter, chaque apprenant a un quota — et il les a faits sur une intuition pédagogique. Cette session vérifie si la littérature de 2025-2026 confirme, nuance ou infirme ces choix. Le débat public est vif, souvent résumé en « l'IA nous rend bêtes ». La question posée ici est plus étroite : **quelle forme d'aide préserve l'apprentissage, et laquelle le remplace ?**

---

## 2. Qualification des sources

| Source | Nature | Date | Auteur identifié | Confirmable ailleurs | Fiabilité |
|---|---|---|---|---|---|
| Bastani, Bastani, Sungu, Ge, Kabakcı, Mariman — *Generative AI without guardrails can harm learning: evidence from high school mathematics*, PNAS vol. 122 n° 26 | Article évalué par les pairs, essai randomisé en conditions réelles, données et code publiés | 07/2025 | Oui | Données sur GitHub, reprises par de nombreuses synthèses | **Haute** |
| Kosmyna et al. — *Your Brain on ChatGPT*, arXiv 2506.08872 (MIT Media Lab) | Prépublication, EEG, 54 participants, 18 en quatrième session | 06/2025, v2 12/2025 | Oui | Très reprise, non évaluée par les pairs | **Moyenne** — signal, pas preuve |
| Stanković, Hirche, Kollatzsch, Doetsch — *Comment on: Your Brain on ChatGPT*, arXiv 2601.00856 | Commentaire méthodologique | 01/2026 | Oui | Porte sur l'échantillon, l'analyse EEG, la reproductibilité | Haute pour ce qu'il dit : lire Kosmyna avec prudence |
| Working paper chinois sur une « pénalité d'apprentissage » liée à l'IA générative, lycées | Document de travail, connu par des synthèses secondaires | 08/2026 | À vérifier | Non recoupé à la source primaire | **Secondaire — piste, pas preuve** |
| Mark, Gonzalez, Harris — *The cost of interrupted work*, CHI 2008 | Article évalué par les pairs, observation de travailleurs de bureau | 2008 | Oui | Fondateur, très cité | Haute, mais hors contexte d'apprentissage |

Le critère qui a le plus servi : **la date du protocole plutôt que celle du titre**. Bastani a été déposé en juillet 2024 et publié en juillet 2025 ; Kosmyna a été déposé sans relecture et corrigé six mois plus tard. Le second est le plus cité et le moins solide.

---

## 3. Ce que dit l'état de l'art

**L'aide sans garde-fou améliore la performance immédiate et dégrade l'apprentissage.** Bastani et al. ont suivi près d'un millier de lycéens en mathématiques. Pendant les séances d'entraînement, les élèves équipés d'une interface GPT standard font mieux que les autres. À l'examen, sans l'outil, ils font moins bien que ceux qui n'ont jamais eu d'IA — de l'ordre de 17 %. Ils ne s'en rendent pas compte : leur perception de ce qu'ils ont appris ne suit pas leur résultat.

**Le même modèle, contraint, ne produit pas cet effet.** Le second bras de l'étude utilisait un « GPT Tutor » configuré pour donner des indices et non des réponses, avec des consignes écrites par les enseignants. Ce groupe fait mieux pendant l'entraînement, et ne présente aucune pénalité à l'examen. Ce n'est donc pas l'IA qui coûte : c'est **la réponse donnée à la place du raisonnement**.

**Sur l'attention elle-même, le signal est plus faible que sa réputation.** Kosmyna et al. ont mesuré par EEG une connectivité cérébrale plus faible chez les rédacteurs assistés par un modèle, et une moindre capacité à citer leur propre texte. C'est cohérent avec Bastani, mais Stanković et al. rappellent que 54 participants, 18 en dernière session, une analyse EEG non reproduite et des comparaisons sans intervalle de confiance ne permettent pas de conclure à un effet durable. À lire comme un indice convergent, pas comme une mesure.

**L'interruption a un coût connu, mais mesuré ailleurs.** Mark et al. ont montré qu'après une interruption, un travailleur met de l'ordre de vingt minutes à revenir pleinement à sa tâche, et compense en travaillant plus vite et sous plus de tension. Le résultat porte sur des employés de bureau, pas sur des apprenants ; il dit néanmoins qu'un outil qui oblige à quitter la tâche pour poser une question n'est pas neutre.

---

## 4. Confrontation au projet

| Constat de la littérature | Ce que fait EduAI Tutor | Verdict |
|---|---|---|
| La réponse donnée à la place du raisonnement dégrade l'apprentissage (Bastani) | Le tuteur ne reçoit jamais la bonne réponse d'un quiz ; l'expurgation est côté serveur, gardée par trois tests. Aucune des sept actions préformées ne demande de résoudre à la place | Confirmé — et c'est exactement le « GPT Tutor » du protocole, pas le « GPT Base » |
| Le même outil avec des consignes pédagogiques ne pénalise pas (Bastani) | Quatre agents à rôle borné ; le coach commente une soumission, il ne la réécrit pas | Confirmé |
| Quitter la tâche pour demander de l'aide a un coût (Mark) | Le chat a quitté sa page pour devenir un panneau latéral qui reçoit le contexte : la section en cours, le code saisi, la dernière erreur. L'apprenant ne réexplique rien et ne part nulle part | Confirmé — c'était le motif de la refonte de C10, sans que la source soit citée |
| L'usage réflexe et systématique est le facteur de risque, pas l'usage ponctuel | Quota de quinze appels par jour et par apprenant, décompte visible | Cohérent, mais le seuil n'est pas fondé sur une mesure |
| Les apprenants surestiment ce qu'ils ont appris avec l'IA | Rien dans le projet ne le corrige : aucune mesure de rétention sans le tuteur | **Écart** |

Le point le plus utile de la session : **le projet a construit le bon bras de l'expérience de Bastani sans le savoir**. Ce qui manque n'est pas une fonctionnalité, c'est une mesure.

---

## 5. Impact concret sur le projet

| Constat | Conséquence |
|---|---|
| Les trois choix de conception sont confirmés par un essai randomisé publié | Les citer comme fondement, dans la documentation de C10 et à l'oral, plutôt que comme intuition |
| Le quota de quinze n'est fondé sur aucune mesure | L'écrire dans le registre des réserves : seuil de conception, pas seuil mesuré |
| Aucune mesure de rétention sans le tuteur | Ouvrir une réserve : le protocole de Bastani — s'entraîner avec, être évalué sans — est reproductible avec les quiz existants et le bloc « à revoir ». C'est la même mesure qui manque à la preuve de concept multi-agents : un avant/après sur un critère fixé d'avance |
| Kosmyna est la source la plus citée et la moins solide | Ne pas la mettre en avant. Si elle est évoquée à l'oral, la donner avec sa critique |

---

## 6. À suivre

- La publication évaluée par les pairs de Kosmyna et al., si elle vient, et ce qu'elle retient des critiques de Stanković.
- La source primaire du working paper chinois, pour le sortir du rang de piste.
- Un protocole de mesure de rétention sur le projet : dix apprenants, un module, un quiz final sans tuteur, critère de réussite écrit avant.

---

## 7. Ce que cette session a appris sur la méthode

Une source très reprise n'est pas une source solide : la note la plus partagée de 2025 sur ce sujet est une prépublication à 54 participants, et l'essai randomisé à mille élèves, évalué par les pairs, est cité dix fois moins. Le critère « confirmable ailleurs » ne suffit pas quand tout le monde reprend la même source ; il faut remonter au protocole. Et une conception peut être juste avant d'être fondée — ce qui ne dispense pas d'aller chercher le fondement, parce que c'est lui qui permet de dire ce qui manque encore.
