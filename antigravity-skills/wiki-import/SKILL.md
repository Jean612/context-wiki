---
name: wiki-import
description: Extrae y procesa conversaciones históricas de sesiones previas (Antigravity y Claude Code) en notas atómicas inmutables para la wiki.
---

# Wiki Import — Minería de Sesiones Históricas

Mina las conversaciones pasadas de desarrollo para convertirlas en notas atómicas y actualizar la base de conocimiento.

## Pasos

1. **Extraer conversaciones a raw/:**
   Ejecuta:
   ```bash
   bash -c 'source ~/.config/context-wiki/config 2>/dev/null || source ~/.config/llm-wiki/config; "${PYTHON:-python3}" "$TOOL_DIR/cli.py" extract-sessions <repo|all>'
   ```
   Esto buscará sesiones en Claude Code y Google Antigravity y generará los resúmenes en `$DATA_DIR/raw/sessions_<repo>_<fecha>.md`.

2. **Procesar cada archivo raw/ generado:**
   - Lee el archivo `raw/sessions_*` generado.
   - Identifica decisiones técnicas, features implementadas, endpoints de API creados/modificados y bugs resueltos.
   - Crea notas atómicas inmutables en `$DATA_DIR/atomic/` con `cli.py new-id <slug>` y frontmatter YAML (`id`, `created`, `type`, `tags`, `scope`).
   - Valida tags contra `$DATA_DIR/topics.json`.
   - Conecta las notas con las notas existentes previas (`cli.py titles 6000`).

3. **Actualizar síntesis e índice:**
   - Actualiza `$DATA_DIR/synthesis/` e `$DATA_DIR/index.md`.

4. **Sincronizar:**
   - Ejecuta:
   ```bash
   bash -c 'source ~/.config/context-wiki/config 2>/dev/null || source ~/.config/llm-wiki/config; "${PYTHON:-python3}" "$TOOL_DIR/cli.py" sync push -m "import: sesiones históricas de <repo>"'
   ```
