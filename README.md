# context-wiki — Wiki de contexto para LLMs

Base de conocimiento personal que preserva el contexto entre sesiones de Claude Code, Google Antigravity o cualquier otro LLM.

Las notas se organizan por **temas**, no por repo: sirve igual para un repo, para diez, o para notas que no son de código. Son notas atómicas inmutables más síntesis compiladas, en markdown plano, que se manejan con slash commands (Claude Code) o skills (Antigravity).

Este repo es la **herramienta**. Tus notas viven en otra carpeta y nunca se mezclan con él. **Por default todo es local**: publicar la wiki en un repo propio para usarla desde varias máquinas es opcional.

## Instalación

Requisitos: git, Python 3.8+, bash, y Claude Code o Google Antigravity. En Windows, Git for Windows (trae git y bash). Sin librerías extra de Python. Detalle en [docs/instalacion.md#requisitos](docs/instalacion.md#requisitos).

```bash
git clone https://github.com/Jean612/context-wiki.git ~/code/context-wiki
bash ~/code/context-wiki/install.sh
```

Después reinicia Claude Code o Antigravity. El instalador pregunta dónde guardar las notas (una ruta, o la URL de una wiki que ya publicaste) y dónde están tus repos.

Para actualizar, vuelve a ejecutar `install.sh`. Al abrir una sesión, un aviso te dice si hay cambios nuevos; nunca se actualiza solo.

### Instalar con tu agente

Copia esto en Claude Code, Antigravity u otro agente con acceso a una terminal:

```text
Instala la herramienta context-wiki desde https://github.com/Jean612/context-wiki

1. Clónala en ~/code/context-wiki.
2. Lee docs/instalacion.md, sección "Instalación hecha por un agente", y síguela paso a paso.
3. Antes de ejecutar el instalador, hazme las preguntas que pide esa sección y dime qué archivos de mi máquina va a modificar.
4. Al terminar, muéstrame la verificación y explícame en pocas líneas cómo se usa.
```

El agente te va a hacer tres preguntas (dónde guardar tus notas, dónde están tus repos, para qué agente instalar) y te va a pedir permiso antes de ejecutar el instalador. Si eres un agente leyendo esto, sigue [docs/instalacion.md#instalación-hecha-por-un-agente](docs/instalacion.md#instalación-hecha-por-un-agente).

## Comandos

| Comando | Para qué |
|---------|----------|
| `/wiki-load <búsqueda>` | Cargar contexto previo antes de trabajar |
| `/wiki-export` | Guardar lo que se hizo en esta sesión como notas |
| `/wiki-ingest [archivo o link]` | Convertir un documento propio (PDF, markdown) o una página (web, Confluence) en notas |
| `/wiki-import [repo\|all]` | Minar conversaciones viejas, en una máquina recién instalada |
| `/wiki-sync` | Sincronizar con tu repo de datos, si la publicaste |
| `/wiki-status` | Ver el estado: notas, sync, repos detectados |
| `/wiki-lint` | Revisar la salud: huérfanas, links rotos, tags fuera del vocabulario |

## Documentación

- [docs/instalacion.md](docs/instalacion.md): instalación detallada, Windows, actualizaciones, publicar la wiki, instalación por un agente
- [docs/uso.md](docs/uso.md): cada comando en detalle, documentos en `raw/` y su límite de tamaño, vocabulario de topics, sincronización, CLI directo
- [CLAUDE.md](CLAUDE.md), [AGENTS.md](AGENTS.md) y [GEMINI.md](GEMINI.md): reglas del sistema para el agente (inmutabilidad, formato de notas)
