---
name: wiki-sync
description: Sincroniza la base de conocimiento multi-repo (wiki) con GitHub (pull, commit y push).
---

# Wiki Sync — Sincronización con Repositorio Remoto

Sincroniza la base de notas de la wiki con su repositorio Git remoto.

## Pasos

1. **Ejecutar sincronización:**
   Ejecuta:
   ```bash
   bash -c 'source ~/.config/context-wiki/config 2>/dev/null || source ~/.config/llm-wiki/config; "${PYTHON:-python3}" "$TOOL_DIR/cli.py" sync full'
   ```
   *(También admite modos `pull` o `push`).*

2. **Interpretar resultado:**
   - **Wiki local (sin remote):** Si no está publicada, el CLI avisa que es puramente local (lo cual es normal si no se ha publicado con `cli.py publish`).
   - **Pull/Push exitoso:** Informa brevemente el estado al usuario.
   - **Offline:** Los commits quedan guardados en local para sincronizarse después.
   - **Conflictos:** Ocurren únicamente en archivos mutables (`synthesis/` o `index.md`), nunca en `atomic/`. Ayuda al usuario editando los archivos en conflicto y finalizando con `git rebase --continue`.
