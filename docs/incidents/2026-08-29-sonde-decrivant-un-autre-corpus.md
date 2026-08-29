# Incident 006 — La sonde de santé décrivait un corpus que le service n'interrogeait pas

**Date :** 29 août 2026
**Composant :** `service_ia/main.py`, point de terminaison `/ai/sante`
**Gravité :** mineure en effet, majeure en signification — aucune indisponibilité, un diagnostic faux
**Statut :** résolu et vérifié
**Compétence visée :** C21 (épreuve E5) — résolution d'incident
**Compétences concernées :** C9 (E2), C10 (E3), C20 (E5)

---

## 1. Déclenchement

Trouvé en préparant le déploiement, non par une panne : `/ai/sante` annonçait le
corpus servi par le service IA sous cette forme :

```python
corpus = {
    "present": chemin_corpus.is_dir(),
    "chemin": str(chemin_corpus),
    "collection": "eduai_knowledge_base",   # ← écrit en dur
}
```

Le nom était un littéral, sans lien avec la collection réellement ouverte par
`rechercher()`. Tant que les deux coïncidaient, l'écart ne se voyait pas.

## 2. Ce que la sonde affirmait, et ce qui était vrai

La recherche documentaire a été rebranchée le même jour sur
`eduai_corpus_documentaire` — 21 189 fragments issus du pipeline — parce que
`eduai_knowledge_base`, qui en compte 387, n'était pas le corpus que ce point
de terminaison a vocation à servir (décision 022).

À partir de ce moment, **la sonde décrivait une collection que le service
n'ouvrait plus**. Un exploitant qui aurait diagnostiqué une recherche
défaillante en s'appuyant sur `/ai/sante` aurait vérifié le mauvais corpus,
constaté qu'il est présent, et conclu que le problème était ailleurs.

Le défaut ne rend rien indisponible. Il rend le diagnostic faux, ce qui est une
autre catégorie de dommage : une panne se voit, un diagnostic faux oriente.

## 3. Résolution

Le nom de la collection devient une constante partagée, `COLLECTION_DOCUMENTAIRE`
dans `apps/rag/utils.py`, importée par la recherche **et** par la sonde. Les
deux ne peuvent plus diverger : il n'y a plus deux valeurs à tenir en accord,
il n'y en a qu'une.

## 4. Le motif, pour la sixième fois

C'est la sixième fois que ce projet documente le même écart : **une action et
son compte rendu ne coïncident pas, et c'est le compte rendu qu'on croit.**

| Date | Ce qui affirmait | Ce qui était vrai |
|---|---|---|
| 26/08 | Un extracteur : « succès » | Zéro enregistrement collecté |
| 27/08 | Un chargeur : 6 836 documents | Une base restée vide |
| 27/08 | L'API `/sources/` : un décompte | Supérieur au corpus réel |
| 28/08 | La sonde de monitorage : « branchée » | Aucune trace produite pendant 22 h |
| 29/08 | Un montage `:ro` : une protection | Une fonction rendue impossible |
| **29/08** | **`/ai/sante` : un nom de corpus** | **Une collection que la recherche n'ouvre pas** |

Les cinq premiers ont été trouvés parce qu'on mesurait, ou parce qu'une
fonction échouait. Celui-ci n'aurait échoué nulle part : la sonde répondait 200,
le champ `present` était exact, et seul le nom était faux.

**La leçon, dans le prolongement de l'incident 003 :** un instrument doit non
seulement fonctionner là où il sert, il doit aussi décrire *ce qu'il observe* et
non ce qu'on croit qu'il observe. Un nom écrit en dur dans une sonde est une
affirmation que rien ne vérifie — et une affirmation invérifiable finit par
devenir fausse sans que personne ne s'en aperçoive.

**Contre-mesure appliquée :** une seule source pour le nom de la collection.
La règle générale se formule ainsi — *ce qu'une sonde annonce doit être lu au
même endroit que ce que le service utilise*, jamais recopié à côté.
