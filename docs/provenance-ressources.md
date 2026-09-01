# Provenance des ressources graphiques

**Compétence visée :** C19 (épreuve E5) — traçabilité
**Compétences concernées :** C1 (E1) — conditions d'usage des sources ; C17 (E4)

Ce document recense l'origine et les conditions d'usage de chaque ressource
graphique de l'application. Le projet documente déjà la licence de chacune de
ses cinq sources de données ; les illustrations relèvent de la même exigence,
et le fait que les droits soient clairs ne dispense pas de les écrire.

---

## Koda — personnage et animations

| | |
|---|---|
| **Auteure** | Camille Catry |
| **Nature** | Illustrations originales, animées image par image |
| **Cession** | Cédées à l'autrice du projet pour usage dans EduAI Tutor |
| **Date d'entrée au dépôt** | 1er septembre 2026 |

### Ce qui a été livré

Cinq séquences animées, chacune fournie sous deux formes — un GIF monté et la
suite de frames PNG qui le compose :

| Séquence | Frames | Cadrage |
|---|---|---|
| `NEUTRAL_TALKING` | 43 | gros plan, bras levé |
| `SLEEPING_TALKING` | 100 | gros plan, sans bras |
| `ANGRY_TALKING` | 48 | buste, poings serrés |
| `SALUTE` | 24 | corps entier |
| `JUMPING` | 48 | corps entier |

Soit 263 frames en 1920×1080 RGBA, 44 Mio, et 3,4 Mio de GIF.

### Ce qui est versionné, et ce qui ne l'est pas

**Versionné :** les cinq GIF d'origine et les planches de sprites assemblées.

**Non versionné :** les 263 frames PNG. Quarante-quatre mégaoctets de sources
en pleine définition dans un dépôt de vingt mégaoctets seraient
disproportionnés, et les GIF conservent la même suite d'images. Les frames
restent chez l'autrice ; leur absence est déclarée ici plutôt que subie.

### Transformations appliquées

Les planches servies par l'application ne sont pas les frames telles quelles :
elles sont recadrées sur le personnage, réduites à la taille d'affichage et
ramenées à une palette de 64 couleurs. **Certaines images n'existent dans
aucune séquence livrée** : elles sont composées en greffant la zone des yeux
d'une frame sur le corps d'une autre — un clignement paupières closes et bouche
fermée, un clin d'œil. Ces compositions restent l'œuvre de l'illustratrice ;
seul l'assemblage est du fait du projet, et il est décrit dans la décision 035.

---

## Autres ressources

| Ressource | Origine | Conditions |
|---|---|---|
| Avatars `static/koda/` | Illustrations du même jeu graphique | Même cession |
| Icônes Lucide | Projet Lucide, licence ISC | Chargées depuis un CDN |
| Police système | Pile de polices du système d'exploitation | Aucune police embarquée |
