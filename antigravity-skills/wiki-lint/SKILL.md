---
name: wiki-lint
description: Audita y verifica la salud e integridad de la wiki (notas huérfanas, links rotos, síntesis desactualizada y coherencia de vocabulario topics.json).
---

# Wiki Lint — Auditoría de Salud de la Wiki

Verifica la integridad de las notas, sus hipervínculos y su vocabulario.

## Pasos

1. **Ejecutar auditoría base:**
   Ejecuta:
   ```bash
   bash -c 'source ~/.config/context-wiki/config 2>/dev/null || source ~/.config/llm-wiki/config; "${PYTHON:-python3}" "$TOOL_DIR/cli.py" lint'
   ```

2. **Accionar sobre hallazgos:**
   - **Notas huérfanas:** Revisa si deberían enlazarse desde los archivos en `synthesis/` o desde `index.md`. Nunca edites las notas atómicas viejas; los enlaces correctivos van en `synthesis/`.
   - **Links rotos:** Identifica a qué nota correspondía el enlace e introdúcelo en `synthesis/` o `index.md`.
   - **Tags fuera del vocabulario:** Decide si el tag debe incluirse como alias en un topic existente en `topics.json` o si es un topic nuevo.
   - **Síntesis desactualizada:** Compara notas atómicas recientes con el estado de las síntesis para reflejar cambios no compilados.
