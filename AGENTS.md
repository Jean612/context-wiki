# AGENTS.md — Herramienta de wiki de contexto

> Este archivo aplica cuando Antigravity, Gemini, Claude Code u otros agentes trabajan en la wiki (esta herramienta o los datos).
> No afecta los AGENTS.md / GEMINI.md / CLAUDE.md de los repos de código — esos son autoridad para convenciones de código de cada proyecto.
> No hay rutas que configurar a mano: `install.sh` escribe `~/.config/context-wiki/config`.

## Tu rol

Eres el mantenedor disciplinado de la wiki de conocimiento: compilas lo aprendido en cada sesión de desarrollo, mantienes el contexto cruzado entre repos y preservas las decisiones técnicas.

## Organización por topics

El eje de la wiki es el **tema**, no el repo. Cada nota lleva `tags` de un vocabulario controlado que vive en `topics.json` (DATA_DIR):

```json
{ "topics": { "auth": ["autenticación", "login"],
              "deploy": ["deployment", "despliegue"] } }
```

- Antes de poner un tag, **revisa `topics.json`**: si el tema ya existe (como canónico o alias), usa el canónico. Topic nuevo sólo si es genuinamente nuevo — agrégalo al archivo con sus aliases.
- Sin idioma forzado: el canónico es como el tema apareció primero; los aliases cubren el otro idioma. `search` expande aliases, así que buscar cualquiera encuentra todos.
- La relación entre notas es por tema y por wikilinks, no por repo de origen.

## Identidad de repos (legacy)

Las notas viejas llevaban el nombre del repo en el archivo y el `scope` como eje. Ese modelo cambió: el usuario nunca consultaba por repo, siempre por palabra clave. Lo que queda:

- `python3 cli.py resolve <path>` sigue derivando el nombre de un repo de su git remote — útil como **metadato opcional** (`scope` en el frontmatter cuando la nota es claramente de un repo).
- Notas viejas con nombres antiguos (`web-app`, `api-legacy`) siguen válidas: registran cómo se llamaba el repo ese día. No las edites.
- `renames.json` (opcional) agrupa nombres históricos de repos renombrados para que la búsqueda encuentre también las notas viejas. Sólo se toca si un repo viejo se renombra.

## Estructura

La herramienta y los datos viven separados. `~/.config/context-wiki/config` apunta a ambos (`TOOL_DIR`, `DATA_DIR`).

```
TOOL_DIR/                ← la herramienta (repo propio, se actualiza con git pull)
├── cli.py               ← CLI (resolve, search, titles, sync, publish, lint, extract-sessions)
├── install.sh           ← instalador idempotente multi-agente
├── claude-commands/     ← slash commands para Claude Code
└── antigravity-skills/  ← skills para Google Antigravity (~/.gemini/config/skills/)

DATA_DIR/                ← tus notas (local por default; publicar es opcional)
├── topics.json          ← vocabulario controlado de tags (canónicos + aliases)
├── renames.json         ← legacy: nombres históricos de repos renombrados
├── index.md             ← tabla de contenidos (MUTABLE)
├── raw/                 ← fuentes inmutables (Technical Discoveries)
├── atomic/              ← notas por desarrollo (INMUTABLES una vez creadas)
└── synthesis/           ← síntesis compiladas (MUTABLES, siempre actualizar)
```

**La wiki es local por default.** `cli.py sync` no hace nada si `DATA_DIR` no tiene remote — publicarla es una decisión explícita del usuario (`cli.py publish <url>`). Nunca publiques la wiki por tu cuenta.

## Formato de nota atómica

Nombre de archivo: `YYYYMMDDHHMM_<descripción_del_tema>.md` (sin repo — el eje es el tema; notas viejas llevan el repo en el nombre y son válidas igual).

```yaml
---
id: YYYYMMDDHHMM
created: YYYY-MM-DD HH:MM
type: endpoint | feature | discovery | bug_fix
status: stable | draft
tags: [auth, deploy]                  # SIEMPRE del vocabulario de topics.json
scope: [api-backend]                  # OPCIONAL: repo(s) involucrados, si aplica
ticket: PROJ-123                      # si aplica
---

# Título claro del desarrollo

## Qué cambió
## API/Endpoints (si aplica)
## Database changes (si aplica)
## Decisiones técnicas / Conflictos (⚠️)
## Links
- Links to: [[YYYYMMDDHHMM_nombre]]
```

### Tipos de nota

| Tipo | Cuándo |
|------|--------|
| `endpoint` | API nueva o modificada — incluir URL, inputs, outputs, auth |
| `feature` | Cambio de lógica de negocio que toca múltiples repos |
| `bug_fix` | Bug complejo con síntoma, root cause y solución |
| `discovery` | Investigación técnica — problema, alternativas, decisión final |

### Tamaño y enlaces

- **400-1200 palabras por nota.** Si supera 1200, dividila en notas enlazadas (la nueva referencia a la vieja, que nunca se edita). Las notas largas cuestan tokens en cada carga de contexto.
- **Toda nota enlaza al menos 1 relacionada** (paso 2.5 de exportación). Es más barato prevenir huérfanas al escribir que detectarlas después con lint.

## Reglas de oro (NUNCA VIOLAR)

1. **Atomic notes = INMUTABLES** — si algo cambió, crea nota nueva que linkee a la vieja.
2. **Synthesis = SIEMPRE ACTUALIZAR** — cada export actualiza synthesis/ e index.md.
3. **raw/ = SOLO LECTURA** — fuente de verdad.
4. **Conflictos = MARCAR (⚠️), no resolver** — el humano decide.
5. **Tags = VOCABULARIO CONTROLADO** — antes de etiquetar, revisa `topics.json` y usa el canónico; topic nuevo sólo si es genuinamente nuevo (agrégalo con sus aliases).
6. **Sync** — pull antes de leer, commit+push después de escribir (`cli.py sync`). Si la wiki es local, no hace nada: está bien, no es un error.

## CLI de referencia

```bash
python3 cli.py status                    # estado + sync status
python3 cli.py titles                    # lista notas existentes para enlazar hacia atrás
python3 cli.py resolve .                 # ¿qué repo es esta carpeta?
python3 cli.py detect                    # repos git en la carpeta de proyecto
python3 cli.py search "auth"             # búsqueda con expansión de topics y renombres
python3 cli.py sync [pull|push|full]     # sincronizar (si está publicada)
python3 cli.py publish <url>             # publicar la wiki en un repo propio
python3 cli.py lint                      # huérfanas + links rotos + validación de topics
python3 cli.py new-id mi_descripcion     # genera ID/filename para nota nueva
CLAUDE_DIR=~/.claude-work python3 cli.py extract-sessions web  # minar sesiones históricas
```
