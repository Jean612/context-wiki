# Instalación

## Cómo queda organizado

La herramienta y tus datos viven en carpetas separadas:

```
~/code/context-wiki/          ← la herramienta (este repo): cli.py, comandos, docs
~/context-wiki-data/          ← tus datos: atomic/ synthesis/ raw/ index.md topics.json
~/.config/context-wiki/config ← apunta a ambas, a tu carpeta de repos y al Python a usar
```

Puedes actualizar la herramienta sin tocar tus notas, y tus notas nunca viajan dentro del repo de la herramienta.

## Requisitos

| Qué | ¿Hace falta? | Para qué | Cómo verificarlo |
|---|---|---|---|
| **git** | Sí | Clonar la herramienta, el aviso de actualizaciones, sacar el nombre de cada repo de su remote | `git --version` |
| **Python 3.8 o más nuevo** | Sí | El CLI (`cli.py`). Usa sólo la librería estándar: no hay `pip install` | `python3 --version` (en Windows, `python --version`) |
| **bash** | Sí | El instalador. Alcanza el bash 3.2 que trae macOS | `bash --version` |
| **Claude Code o Google Antigravity** | Al menos uno | Los comandos `/wiki-*`. Sin ninguno, el CLI se puede usar igual a mano | — |
| **Clave SSH cargada en GitHub** | Sólo para clonar con `git@github.com:` | Alternativa: clonar con la URL `https://` | `ssh -T git@github.com` |
| **Un repo vacío y privado** | Sólo si publicas tu wiki | Respaldarla y usarla desde varias máquinas | — |
| **Obsidian** | No | Ver el grafo de notas. Las notas son markdown plano y se leen con cualquier editor | — |

No hace falta el CLI de GitHub (`gh`), ni Node, ni Docker. Funciona en Linux, macOS y Windows (con Git Bash; ver [Windows](#windows)).

En **Windows**, Git for Windows trae git y bash juntos, y Claude Code ya lo pide para funcionar. Python se instala aparte, desde python.org o la Microsoft Store.

El instalador verifica Python y avisa si no encuentra 3.8 o más nuevo.

## En una máquina nueva


```bash
# 1. Clonar la herramienta
git clone https://github.com/Jean612/context-wiki.git ~/code/context-wiki

# 2. Instalar: pregunta dónde guardar las notas, detecta tus repos e instala
#    los comandos en Claude Code y/o las skills en Antigravity
bash ~/code/context-wiki/install.sh

# 3. Reiniciar Claude Code o Antigravity
```

**Si ya tenías una wiki publicada** en otra máquina, pega la URL del repo cuando el instalador pregunte dónde guardar las notas: la clona y la usa. Si pegas una URL, pregunta dónde clonarla (default `~/<nombre-del-repo>`). Si ya la tenías clonada, pasa la ruta y no vuelve a clonar.

### Sin preguntas (variables de entorno)

Cada pregunta del instalador tiene su variable. Si la pasas, no pregunta:

| Variable | Qué responde | Ejemplo |
|---|---|---|
| `WIKI_DATA_DIR` | Dónde guardar las notas: una ruta, o la URL de una wiki publicada | `~/context-wiki-data` |
| `WIKI_CLONE_DIR` | Dónde clonar, si `WIKI_DATA_DIR` es una URL | `~/code/mi-wiki` |
| `WIKI_PROJECT_DIR` | Carpeta que contiene tus repos | `~/code` |
| `WIKI_AGENTS` | Para qué agentes instalar, separados por `:` | `claude:antigravity` |
| `WIKI_CLAUDE_DIRS` | Perfiles de Claude Code, separados por `:` | `~/.claude:~/.claude-trabajo` |

```bash
WIKI_DATA_DIR=git@github.com:tuusuario/mi-wiki.git WIKI_PROJECT_DIR=~/code bash ~/code/context-wiki/install.sh
```

Sin terminal interactiva, cada pregunta sin variable usa su default. La excepción es la carpeta de repos: si el instalador encuentra más de una candidata, no elige por ti y termina con error. Pasa siempre `WIKI_PROJECT_DIR`.

## Actualizaciones

Al abrir una sesión de Claude Code, un hook revisa si hay commits nuevos en la herramienta y, si los hay, te avisa:

```
context-wiki: hay 2 commit(s) nuevos en la herramienta.
  ver qué cambió:  git -C ~/code/context-wiki log --oneline HEAD..@{u}
  actualizar:      bash ~/code/context-wiki/install.sh
```

**Nunca se actualiza solo.** Bajar y ejecutar código en cada sesión convertiría un "sí" al instalar en un permiso permanente para que quien tenga push al repo ejecute código en tu máquina. El aviso baja los cambios (`git fetch`) pero no los ejecuta: eso pasa solo cuando ejecutas `install.sh`.

Antigravity no tiene este aviso: si usas sólo Antigravity, actualiza corriendo `install.sh` de vez en cuando.

## Windows

Funciona desde **Git Bash**, que Claude Code en Windows ya requiere.

- Python de python.org o de la Microsoft Store: el instalador usa el primero que realmente ejecute Python 3 (`python3` o `python`) y lo guarda en la config.
- La config queda con rutas de Git Bash (`/c/Users/...`); el CLI las convierte al leerlas.
- WSL también funciona, pero es una instalación Linux aparte: no ve el Claude Code de Windows.

**Sin verificar en una máquina Windows real:** que Claude Code ejecute el hook de aviso a través de Git Bash, y que no acorte con un hash el nombre de la carpeta de sesiones en rutas muy largas. Si algo de esto falla, abre un issue con la salida.

## Publicar la wiki (opcional)

Por default nada sale de tu disco. Para respaldarla o usarla desde otra máquina, crea un repo **vacío y privado** y publica:

```bash
python3 ~/code/context-wiki/cli.py publish git@github.com:tuusuario/mi-wiki.git
```

A partir de ahí `/wiki-sync`, `/wiki-load` y `/wiki-export` la mantienen al día. Si no publicas nunca, todo sigue funcionando en local.

## Instalación hecha por un agente

Si te pasaron este repo para que lo instales tú (Claude Code, Antigravity u otro agente con acceso a una terminal), sigue estos pasos. El instalador funciona sin terminal interactiva: cada pregunta tiene su variable de entorno.

1. **Pregúntale al usuario**, antes de ejecutar nada (las tres respuestas van como variables: sin la carpeta de repos el instalador puede terminar con error):
   - ¿Dónde guardar las notas? Una carpeta nueva (default `~/context-wiki-data`) o la URL de una wiki que ya tenga publicada.
   - ¿En qué carpeta están sus repos de código?
   - ¿Para qué agentes instalar? Claude Code, Antigravity o ambos.
2. **Clonar la herramienta** en `~/code/context-wiki`, salvo que el usuario prefiera otro lugar. Usa la URL `https://`: no requiere clave SSH. Nunca la clones dentro de la carpeta de notas.
3. **Instalar** con las respuestas como variables. En Windows, desde Git Bash:
   ```bash
   WIKI_DATA_DIR=<ruta-o-url> WIKI_PROJECT_DIR=<carpeta-de-repos> WIKI_AGENTS=<claude|antigravity|claude:antigravity> bash <clon>/install.sh
   ```
   El instalador escribe en `~/.config/context-wiki/`, en `~/.claude*/commands/`, `~/.claude*/agents/` y `~/.claude*/settings.json` (registra un hook que sólo avisa de actualizaciones), y en `~/.gemini/config/skills/` si eligió Antigravity. Díselo al usuario antes de ejecutarlo.
4. **Verificar** con `python3 <clon>/cli.py status` (o `python` en Windows) y mostrarle la salida.
5. **Explicarle cómo se usa:** pídele que reinicie la sesión para que aparezcan los comandos, y resúmele la tabla de comandos del [README](../README.md). Lo que más va a usar: `/wiki-export` al terminar un trabajo y `/wiki-load` al empezar uno.
