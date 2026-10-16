---
name: wiki-status
description: Consulta y reporta el estado actual de la wiki (cantidad de notas, estado de sincronización git y repositorios locales detectados).
---

# Wiki Status — Estado de la Wiki

Consulta métricas de la wiki y los repositorios locales vinculados.

## Pasos

1. **Consultar estado general:**
   Ejecuta:
   ```bash
   bash -c 'source ~/.config/context-wiki/config 2>/dev/null || source ~/.config/llm-wiki/config; "${PYTHON:-python3}" "$TOOL_DIR/cli.py" status'
   ```

2. **Detectar repositorios locales:**
   Ejecuta:
   ```bash
   bash -c 'source ~/.config/context-wiki/config 2>/dev/null || source ~/.config/llm-wiki/config; "${PYTHON:-python3}" "$TOOL_DIR/cli.py" detect'
   ```

3. **Reportar al usuario:**
   Resume el número de notas atómicas, síntesis y fuentes crudas, si la base está al día con el remoto o tiene commits pendientes, y los repositorios del proyecto.
