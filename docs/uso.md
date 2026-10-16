# Uso

## Los comandos

| Comando | Cuándo | Qué hace |
|---------|--------|----------|
| `/wiki-load <búsqueda>` | Al empezar trabajo que depende de contexto previo | Hace pull, busca notas (expandiendo aliases de topics y nombres de repos renombrados) y carga el contexto, citando la nota de donde sale cada dato. |
| `/wiki-export` | Al terminar un desarrollo | Crea hasta 5 notas atómicas de la sesión, las enlaza con notas que ya existían, actualiza synthesis e index, y hace push si publicaste. |
| `/wiki-ingest [archivo o link]` | Para meter un documento o una página | Ver [Documentos y links](#documentos-y-links-wiki-ingest). |
| `/wiki-import [repo\|all]` | En una máquina solo instalada | Mina las conversaciones históricas de Claude Code y Antigravity, de todos los perfiles y repos, y las convierte en notas atómicas. |
| `/wiki-sync` | Cuando quedó algo sin subir | Pull + commit + push con tu repo de datos, si lo publicaste. |
| `/wiki-status` | Para ver cómo está todo | Cantidad de notas, estado del sync, rutas y repos detectados. |
| `/wiki-lint` | Una vez por semana | Huérfanas, links rotos, notas sin links salientes o de más de 1200 palabras, tags fuera del vocabulario o aliases en notas de hoy, synthesis desactualizada, archivos de `raw/` sin procesar. |

En Antigravity son skills con el mismo nombre y el mismo comportamiento.

## Documentos y links (`/wiki-ingest`)

Para convertir un PDF, un markdown, un apunte o una página en notas:

```
/wiki-ingest ~/Descargas/paper.pdf
/wiki-ingest https://medium.com/@alguien/un-articulo
/wiki-ingest https://tuempresa.atlassian.net/wiki/spaces/X/pages/123
```

1. **Un archivo** se copia a `raw/`. Si ya hay otro con el mismo nombre, se detiene: renombra el tuyo.
2. **Un link** se lee con la herramienta que corresponda (Confluence con el MCP de Atlassian; el resto con WebFetch), y el texto se guarda en `raw/` con la URL y la fecha al principio. Las páginas cambian o desaparecen: la copia es la fuente para revisar después qué decía ese día.
3. Lee la fuente entera. Los PDFs largos, de a 20 páginas.
4. Escribe hasta 5 notas, una idea cada una, con `source: raw/<archivo>` en el frontmatter.
5. Las enlaza con notas que ya tenías, actualiza synthesis e index, te muestra las notas y sincroniza.

Sin argumento, lista lo que hay en `raw/` y ninguna nota cita todavía. También puedes copiar archivos a `raw/` a mano y procesarlos después. Pasar el mismo link dos veces no lo vuelve a descargar: avisa que ya está.

**Qué links funcionan:** páginas públicas (artículos, blogs, documentación) y Confluence si tu agente tiene el MCP de Atlassian. Un artículo de Medium solo para miembros llega cortado: el agente debe avisarte y detenerse, no escribir notas sobre medio artículo. Las páginas que piden login no funcionan; descarga el archivo o pega el texto. WebFetch devuelve una extracción hecha por un modelo, así que la copia puede diferir un poco del original.

### Seguridad

Un documento o una página puede traer texto escondido dirigido al agente ("ignora lo anterior y ejecuta esto"). No hay forma confiable de saber si una página es segura con solo mirarla, así que la defensa es limitar lo que el agente puede hacer mientras la lee:

- **Solo tiene pre-aprobado leer, y escribir dentro de tu carpeta de notas.** Cualquier comando en la terminal, cualquier link y cualquier escritura fuera de las notas te pide permiso. El pedido para sincronizar es el momento de revisar las notas antes de que se suban.
- **Lee solo la fuente que le diste**: no sigue los links de la página ni ejecuta lo que el documento proponga.
- **Lo que dice el documento es dato, no instrucciones**, y lo que afirma no es un hecho verificado: si contradice una nota tuya o el código, queda marcado con ⚠️.
- **`/wiki-load` trata las notas igual**: si una nota trae instrucciones para un agente, no las sigue y te dice cuál es. Una instrucción guardada en una nota se cargaría en sesiones futuras, en todas tus máquinas.

Si usas Claude Code en modo sin permisos (*bypass*), nada de esto te pregunta. Para procesar links que no conoces, no uses ese modo.

### Archivos pesados

Git guarda cada archivo para siempre, aunque después lo borres. Cada máquina lo clona y cada sync lo trae: tres PDFs de paper pueden duplicar el tamaño de la wiki.

Por eso, **lo que pese más de 5 MB en `raw/` no se sube**. Queda en tu disco y te avisa:

```
⚠️  raw/manual.pdf (18.0 MB) no se sube: pasa de 5 MB. Queda sólo en esta máquina.
    Para subirlo igual (el repo crece 18.0 MB para siempre): cli.py raw --subir manual.pdf
```

- Aplica igual si lo copiaste a mano: el que frena es `sync`, no `/wiki-ingest`.
- Lo de menos de 5 MB se sube como siempre, sin preguntar.
- `cli.py raw --subir <nombre>` lo sube en el próximo `/wiki-sync`.
- En tus otras máquinas la nota existe, pero el archivo pesado no.

## Vocabulario de topics (`topics.json`)

Las notas se etiquetan con tags de un vocabulario que vive en `topics.json`, en tu carpeta de datos: un topic canónico con sus aliases.

```json
{ "topics": { "auth": ["autenticación", "login"] } }
```

Buscar cualquiera de esos términos encuentra las notas de todos. No hay idioma forzado: el canónico es como apareció el tema por primera vez. `/wiki-lint` avisa si una nota usa un tag que no está en el vocabulario; si el archivo no existe, los tags son libres.

`"vigente_desde": "YYYYMMDDHHMM"` hace que el lint controle sólo las notas posteriores. Sirve para armar el vocabulario sobre una wiki que ya tenía historia, porque las notas viejas son inmutables y no se pueden corregir.

## Sincronización entre máquinas

Sólo si publicaste la wiki (ver [instalacion.md](instalacion.md#publicar-la-wiki-opcional)):

- `/wiki-load` hace pull antes de buscar: siempre lees las notas más recientes.
- `/wiki-export` hace commit + push al terminar: tus otras máquinas las ven al instante.
- Sin conexión todo sigue funcionando en local; `/wiki-sync` sube lo pendiente después.
- Las notas atómicas nunca generan conflictos (son inmutables y su ID es un timestamp único). Sólo synthesis e index pueden chocar, y `/wiki-sync` te ayuda a resolverlo.

Si no publicaste, los comandos funcionan igual pero no tocan la red.

## CLI directo

Todo lo que hacen los comandos se puede correr a mano:

```bash
python3 cli.py status                 # estado
python3 cli.py search "check-in"      # buscar notas
python3 cli.py titles                 # listar notas como 'id — título'
python3 cli.py lint                   # revisar la salud
python3 cli.py sync [pull|push|full]  # sincronizar
python3 cli.py raw [archivo]          # copiar a raw/, o listar lo pendiente
python3 cli.py raw --subir <nombre>   # subir igual un archivo pesado
python3 cli.py extract-sessions all   # minar sesiones de todos los repos
```

En Windows, `python` en vez de `python3` si es lo que tienes.

**¿De qué perfiles de Claude Code se minan las conversaciones?** Si tienes varios (ej. `~/.claude` personal y `~/.claude-trabajo`), `install.sh` pregunta cuáles usar y lo guarda como `SESSION_PROFILES` en la config (vacío = todos). Se puede forzar puntualmente con `CLAUDE_DIR=~/.claude-otro`.

## Identidad de repos (legacy)

> El repo es metadato opcional (`scope` en el frontmatter), no el eje de la wiki. Esta maquinaria queda para las notas viejas y para minar sesiones por repo.

`cli.py resolve` usa el slug del remote de git como nombre del repo. No hay registro: clonas un repo nuevo y funciona, con cualquier nombre de carpeta local.

```
~/code/mis-repos/backend  → git@github.com:mi-org/api-backend.git  → api-backend
```

**Si un repo se renombra**, las notas viejas quedan con el nombre anterior, que es históricamente correcto. Para que la búsqueda las siga encontrando, agrega el grupo en `renames.json`:

```json
{ "renames": { "api-backend": ["Backend", "old-backend-name"] } }
```

> ⚠️ GitHub redirige las URLs viejas tras un rename, así que un clon que no actualizó su remote sigue reportando el nombre anterior. `cli.py detect` avisa cuando la carpeta y el remote no coinciden.
