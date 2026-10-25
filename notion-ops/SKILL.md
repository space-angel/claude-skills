---
name: "notion-ops"
description: "Decides between the ntn Notion CLI and the Notion MCP connector for any Notion task, and supplies the exact command. Use for requests like \"add this to Notion\", \"create/upload a Notion page\", \"move this doc to Notion\", \"update that Notion page\", \"find it in Notion\", \"query my Notion database\". The CLI is the default for anything whose location is already known; switch to MCP only for workspace-wide semantic search or for connected external sources like Slack and Drive. Measured 2026-08-04: the CLI costs consistently fewer tokens across page create/read/update (~1.9-2x, and the ratio does not narrow as document count grows), and MCP's search advantage holds only when AI search is enabled on the workspace plan."
---

# Notion operations — CLI by default, MCP only for search and external sources

## Conclusions (measured 2026-08-04)

- **Anything whose location you already know (create, read, update) → the `ntn` CLI.** It costs fewer tokens than MCP every time. One document (15,085 chars) came out ~1.87x cheaper; thirteen documents (126,856 bytes) came out ~1.97x cheaper. The ratio does not narrow with volume, so never switch to MCP because "there are a lot of files."
- **Consider MCP `notion-search` only when you have to find a document somewhere in the workspace.** This advantage exists only if the workspace plan has AI (semantic) search enabled. Without it, MCP does the same lexical matching as `ntn api v1/search` and buys you nothing — run the check below first.
- **Use MCP when the search must reach Slack, Google Drive, or another connected source.** `ntn` wraps only the public Notion API, so this is structurally impossible for the CLI. True regardless of plan.

The ratio comes from **how content reaches the API**. With the CLI, bash reads the file from disk and streams it to the API, so not one character of content passes through the model's output tokens. With MCP, the model types the content into the `content` parameter itself. The bigger the file and the more files there are, the more that difference compounds.

### How this was measured

Two runs on the same workspace, same source documents, same tokenizer (`claude-opus-5`), counting the full turn cost of create-then-read-back:

| Workload | CLI | MCP |
|---|---|---|
| 1 document, 15,085 chars | 16,341 tokens | 30,606 tokens (~1.87x) |
| 13 documents, 126,856 bytes | 61,809 tokens | 121,668 tokens (~1.97x) |

Every command in this skill was executed against a live workspace on `ntn 0.16.0`.

## Before starting

```bash
ntn --version || curl -fsSL https://ntn.dev | bash
ntn whoami      # auth + which workspace, in one line
```

If `whoami` fails, run `ntn login`. If the cause is unclear, run `ntn doctor`. For headless/CI use `NOTION_API_TOKEN`; if the OS keychain is unavailable set `NOTION_KEYRING=0`; with multiple workspaces set `NOTION_WORKSPACE_ID`.

## Step 1 — identify the target

`ntn` **takes IDs only.** Never pass a name or a URL straight through.

| What the user gave you | What to do |
|---|---|
| A Notion URL | The trailing 32 hex chars are the ID. `…/Title-3b188265638078…?v=…` → strip dashes and query, keep 32 chars |
| A page name only | `ntn api v1/search query="name" page_size:=5 \| jq -r '.results[] \| "\(.id)\t\(.properties.title.title[0].plain_text // .title[0].plain_text // "")"'` |
| A database ID | Resolve it first: `ntn datasources resolve <database-id>` |
| Nothing | Go to the search row in the decision table below |

If several candidates match, do not pick one yourself. Show the list and let the user choose.

## Step 2 — decision table

| Request | Tool | Command |
|---|---|---|
| Publish a local doc to a known page/DB | CLI | `ntn pages create --parent page:<id> < file.md` |
| Read a page you have the ID for | CLI | `ntn pages get <page-id>` |
| Replace a page's body | CLI | `ntn pages update <page-id> < updated.md` |
| Inspect DB schema (properties) | CLI | `ntn api v1/data_sources/<ds-id> \| jq '.properties \| map_values(.type)'` |
| Query/filter DB rows | CLI | `ntn datasources query <ds-id> --limit 25 -s "Created desc"` |
| Edit page properties only | CLI | `ntn api v1/pages/<page-id> -X PATCH -d '{"properties":{…}}'` |
| Read/write comments | CLI | `ntn api v1/comments block_id==<page-id>` (reads use `==`) |
| Upload a file | CLI | `ntn api v1/file_uploads mode=single_part` → `…/send --file <path>` |
| Workspace search — AI search enabled | MCP | `notion-search` |
| Workspace search — AI search off/unknown | CLI (equal or cheaper) | `ntn api v1/search query="…"` + `jq` |
| Search reaching Slack/Drive/etc. | MCP | `notion-search` (only meaningful if a source is actually connected) |
| Anything not in this table | CLI | Find the endpoint with `ntn api ls`, check its shape with `--spec` |

### Checking for AI search (once per session)

Before reaching for MCP search, do not guess whether this workspace supports semantic search — test it. Fire one `notion-search` with a query that shares no words with the target's title or body but is semantically related. If it misses and the response carries a lexical-matching signal such as `"type":"workspace_search"`, treat the CLI as sufficient for search for the rest of the session and stop re-checking.

## Step 3 — command reference (verified on `ntn 0.16.0`)

### pages

```bash
ntn pages create --parent page:<id> < file.md      # stdin is the default path; --content only for short strings
ntn pages create --parent data-source:<ds-id> < row.md
ntn pages get <page-id>                            # markdown; add --json only when you need block structure
ntn pages update <page-id> < updated.md            # full body replace. The subcommand is `update`, not `edit`
ntn pages trash <page-id>                          # add --yes only when the user asked for it
```

`--parent` accepts `page:<id>`, `database:<id>`, and `data-source:<id>`. `page:` and `data-source:` are the two confirmed by execution.

> Some published docs still show `ntn pages edit`. There is no `edit` subcommand in 0.16.0 — it is `update`.

### datasources

```bash
ntn datasources resolve <database-id>              # database ID → data source ID
ntn datasources query <ds-id> --limit 25
ntn datasources query <ds-id> -s "Status asc" -s "Decided desc"   # repeatable; order is precedence
ntn datasources query <ds-id> --filter '{"property":"Status","select":{"equals":"Accepted"}}'
ntn datasources query <ds-id> --filter-file - < filter.json
```

Default output is **one tab-separated line per row**, already compact. Adding `--json` inflates it, so use that only when you need block structure. When results are truncated, the last line prints the `--start-cursor` value to continue with. If the filter JSON shape is unclear, run `ntn api v1/data_sources/<id>/query --docs`.

### api (everything not in the table)

**Get the inline-input syntax right first. This is the most common mistake.**

| Syntax | Meaning | Example |
|---|---|---|
| `name=value` | **Body** field (string) | `query=roadmap` |
| `name:=json` | **Body** field (JSON literal) | `page_size:=10`, `archived:=true` |
| `name==value` | **Query parameter** | `block_id==<page-id>` |
| `-d '<json>'` | Whole body at once | |

Use exactly one body source: stdin, `-d`, or inline body fields. **Any body field at all forces the method to POST** — using `=` on a GET endpoint returns 400. Reads take `==`.

```bash
ntn api ls                                         # every supported endpoint
ntn api v1/pages/<id> --spec                       # reduced OpenAPI; --docs prints the full (long) docs
ntn api v1/comments block_id==<page-id>            # read = query parameter
ntn api v1/comments -d '{"parent":{"page_id":"<id>"},"rich_text":[{"text":{"content":"Looks good"}}]}'
ntn api v1/pages/<id> -X PATCH -d '{"properties":{…}}'
```

### files — `ntn files create` fails on free-plan workspaces

`ntn files create` uploads via multipart, and free-plan workspaces reject multipart (`400 … does not support multipart uploads`). Use the two-step path instead. It works on any plan, so prefer it unless you know multipart is available.

```bash
ntn api v1/file_uploads mode=single_part filename="x.md" content_type="text/markdown"   # → id
ntn api v1/file_uploads/<id>/send --file ./x.md                                          # → status: uploaded
ntn files list        # listing and retrieval work normally (TSV)
```

`--file` reads a file into the multipart `file` form field. Single-part uploads cap at 5 MB.

Note that the public API has no delete for file uploads. An upload left unattached simply expires.

### Output formats

`--json` (machine parsing) and `--plain` (tab-separated, no headers) are mutually exclusive. `pages get` returns markdown and `datasources query` / `files list` return TSV by default, so **for anything a human will read, passing neither is the shortest.**

## Execution rules that protect the token win

Choosing the CLI does not make a task cheap on its own. Dumping raw output into context gives the advantage straight back.

- **Always narrow `ntn api` JSON with `jq`.** Three raw search results run to thousands of tokens, most of it `annotations`, `created_by`, and other fields you never read. Leave `pages get`, `datasources query`, and `files list` alone — they already return markdown or TSV.
- **Stream content through stdin.** `--content "$(cat file.md)"` routes the file back through model output and costs the same as MCP. Use `< file.md`.
- **Bulk publishing is a bash `for` loop.** Do not make one tool call per file.
- **`pages get` defaults to markdown.** Skip `--json` unless you actually need block IDs.
- **Verify with diff, not by reading.** `diff <(ntn pages get <id>) file.md`.

## Traps

- **`ntn pages get` happily returns pages that are in the trash.** Getting content back does not mean the page is live. Check existence with `ntn api v1/pages/<id> | jq .in_trash`. Pass a trashed page as `--parent` and the failure only surfaces later, as `Can't edit block that is archived`.
- **Always set `--parent`.** A workspace-root page created without one cannot be trashed through the API — the user has to delete it by hand in the Notion app. Pages that have a parent trash normally.
- **Obsidian callouts (`> [!note]`) survive neither CLI nor MCP.** The brackets come through as escaped literal text. Warn the user before moving a document that uses them.
- **Toggles, columns, and synced blocks work with plain standard tags.** `<details><summary>`, `<columns><column>`, `<synced_block>`, and GFM pipe tables all become real blocks under both CLI and MCP without reading any spec first.
- **Never make `--allow-deleting-content` a default on `pages update`.** Being blocked when overwriting a page that has child pages or nested databases is correct behavior. Passing the flag casually deletes all of that child content.
- **Never hardcode `--yes` on `pages trash`.**
- **When MCP is genuinely required**: `notion-create-pages` instructs you to read `enhanced-markdown-spec` first, but tables, toggles, columns, and synced blocks parse correctly without it. Read the spec only for constructs you have not verified, such as mentions or inline databases.

## Do not

- Switch from CLI to MCP because there are many documents — the ratio held at ~1.9x for both a 1-file and a 13-file run
- Assert that "MCP is better at search" without checking whether AI search is enabled
- Bulk-create pages from a script without `--parent` (you will not be able to clean them up through the API)
- Retype large content into the MCP `content` parameter and trust it without diffing against the source — a single-character corruption has actually occurred this way. The CLI reads the file directly and does not carry this risk
- Read `ntn api` output without `jq`
- Pick arbitrarily among multiple search candidates before editing or deleting
