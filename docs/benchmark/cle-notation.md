# Clé de la notation en aveugle

**Compétence visée :** C7 (épreuve E2)

À n'ouvrir qu'après avoir renseigné les notes de `notation-aveugle.md`.

| Prompt | A | B | C | D |
|---|---|---|---|---|
| p1 | `openai/gpt-oss-20b` | `qwen/qwen3.6-27b` | `qwen3:4b` | `openai/gpt-oss-120b` |
| p2 | `qwen/qwen3.6-27b` | `qwen3:4b` | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` |
| p3 | `qwen3:4b` | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` | `qwen/qwen3.6-27b` |
| p4 | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` | `qwen/qwen3.6-27b` | `qwen3:4b` |
| p5 | `openai/gpt-oss-20b` | `qwen/qwen3.6-27b` | `qwen3:4b` | `openai/gpt-oss-120b` |
| p6 | `qwen/qwen3.6-27b` | `qwen3:4b` | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` |
| p7 | `qwen3:4b` | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` | `qwen/qwen3.6-27b` |
| p8 | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` | `qwen/qwen3.6-27b` | `qwen3:4b` |
| p9 | `openai/gpt-oss-20b` | `qwen/qwen3.6-27b` | `qwen3:4b` | `openai/gpt-oss-120b` |
| p10 | `openai/gpt-oss-20b` | `qwen/qwen3.6-27b` | `qwen3:4b` | `openai/gpt-oss-120b` |

Le décalage des étiquettes est déterministe, tiré de l'identifiant du prompt : deux exécutions de l'analyse produisent le même document, ce qu'un tirage aléatoire ne permettrait pas.

**Réserve.** La notatrice est aussi l'autrice du code. L'aveugle est ici une discipline de procédure — la clé vit dans un fichier séparé — et non une garantie technique. Le dire vaut mieux que revendiquer une rigueur que le dispositif n'a pas.
