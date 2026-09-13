# Studio API + MCP: agency integration specification

Status: **proposed**. Planning only. No implementation or Live promote from this
note. Date: 2026-09-13.

Codex wrote this against checkout `codex/varyforge-live-redesign`, not Lab
`tier1`. Reconcile names before any build, do not invent a second admin list:

- Lab code today: `VARIANT_AUTH_ADMIN_EMAIL` (single email). `studio-ia.md`
  still says `SITE_ADMIN_EMAILS` — that is a docs drift, not a second env var.
- `scripts/promote-to-live.sh` exists on Lab. Copy files to `varimo-live`;
  never `git merge`.

## Jeff notes (not signed)

1. **Workspace-wide keys — yes for v1.** A key with gallery/job-read sees
   every pack in that workspace; export can use every configured destination.
   Hard client split = separate workspaces. Per-folder ACLs are not a launch
   requirement.
2. **Pilot spend — entitlements + admission limits.** No per-key daily pack
   cap at launch. Add a volume cap only if a real agency burns through it.

Approval: ____________________  Date: ____________________

---

## A. Thesis — five lines

1. The agency owner issues a workspace key to the agency's own AI or automation.
2. That integration makes Fast packs from approved Drive clips, reads results, and exports selected copies to a configured Drive folder.
3. Studio retains Gallery review, existing Drive connections, Workflows, and the existing generation engine.
4. The agency connects its export folder to Repurpose.io or Buffer and operates its own scheduler account.
5. We do not post, connect Instagram, operate scheduler seats, grant admin access, or promise platform acceptance.

## Evidence and planning boundary

Inspected Lab `variant_maker/server/app.py` and Drive/job/export routes.
Existing Drive creation validates file IDs against videos inside a configured
destination folder, downloads them, and creates a path job. Existing exports
run asynchronously. Existing response models expose internal quality fields, so
they cannot simply become the customer contract unchanged.

## B. Workspace key model

**Ownership.** A key belongs to one immutable workspace and records its issuing owner. Only a logged-in owner in their own workspace may create, list, or revoke keys. A key cannot manage keys. An admin viewing another workspace cannot do so either. Existing cookies continue serving human UI requests.

**Token.** Proposed format: `vf_<random-key-id>_<secret>`, with a cryptographically random 256-bit secret. Store a digest of the full high-entropy token and compare in constant time after key-ID lookup. This is credential hashing, unrelated to media processing. Persist no plaintext. Show the full token once in the successful create response; send `Cache-Control: no-store`. A lost create response requires revoking that entry and creating another key, never retrieving its secret.

**Record.** Key ID, workspace ID, issuer user ID/email, label, display prefix containing no secret bytes, digest, granted scopes, created timestamp, last successful authentication timestamp, revoked timestamp, and optional expiry. Keys are independent per agent/VA integration; default expiry is 90 days, with an owner-selectable shorter lifetime. Rotation means create replacement, update the agency client, revoke old key. Scopes are immutable; replace a key to change its grants.

**Storage.** Local durable credential storage alongside tenant metadata, outside served media paths, protected by filesystem permissions. SQLite transactions are the proposed small local store for credentials, request limits, and idempotency records; no external database service or queue. Check revocation and expiry on every authenticated request without a positive-auth cache. Failure to read the store fails closed. Never fall back to the default workspace when key authentication fails. Disable key issuance and bearer integration access when tenancy/auth is disabled.

| Scope | Permission |
| --- | --- |
| `jobs:create` | Create one Fast pack from one Drive clip |
| `jobs:read` | Read pack status and ready-copy metadata in this workspace |
| `gallery:read` | Read this workspace's gallery metadata |
| `drive:export` | Export selected ready copies to an existing workspace destination and read export status |

The complete loop needs all four; the screen also offers a read-only preset. No wildcard scope. No key access to billing, admin, Diagnostics, raw events, Drive OAuth, connection changes, destination mutations, or member management. Generation still follows existing workspace billing/entitlement rules; lack of billing-management scope does not make generation free.

**Proposed launch limits.** Per key: 60 reads/minute, 6 pack submissions/minute, 6 export submissions/minute. Aggregate per workspace: 180 reads/minute, 12 pack submissions/minute, 12 exports/minute; maximum two active API-created packs and two active API-created exports. Count pending admissions as active so concurrent requests cannot bypass limits. Existing Studio capacity/entitlement limits also apply. Return `429` with `Retry-After`; no automatic spillover to another worker. Limits are server configuration, not key-editable. Invalid credential attempts also receive a bounded source-IP limit using only trusted proxy forwarding headers. These numbers are proposed pilot defaults, not performance claims.

## C. Public HTTP contract and existing-route mapping

Use a small **NEW `/api/v1` boundary** rather than making a bearer token a session-equivalent credential across `/api/*`. Thin adapters call the same workspace services/helpers as the UI. No loopback HTTP calls, copied runners, or second job engine. Cookie UI routes retain their current contracts; the new boundary validates a deliberately smaller input and returns a safe output projection. Publish a dedicated OpenAPI contract containing only this public surface.

### Four core operations

| Public endpoint (all NEW adapters) | Existing operation reused | Scope and contract |
| --- | --- | --- |
| `POST /api/v1/packs` | `POST /api/jobs/from-drive` | `jobs:create`; JSON `input_destination_id`, `drive_file_id`, `count`; required `Idempotency-Key`. Maps to `destination_id`, one-element `file_ids`, existing Fast defaults. Returns `201` with `pack_id` (existing job ID) and status URL. |
| `GET /api/v1/packs/{pack_id}` | `GET /api/jobs/{job_id}` | `jobs:read`; state, requested/ready counts, shortfall, source IDs, ready-copy references, safe error, Gallery review URL. |
| `GET /api/v1/gallery?pack_id=…&limit=…&cursor=…` | `GET /api/gallery` | `gallery:read`; safe source/copy projection. Filtering and cursor pagination are NEW; default 25, maximum 100, stable ordering by creation time plus IDs. |
| `POST /api/v1/drive/exports` | `POST /api/drive/exports` | `drive:export`; `destination_id`, explicit `variants: [{source_id,index,caption?}]`; required `Idempotency-Key`. Returns `201`, `export_id`, state, status URL, destination folder URL. |

**Necessary supporting read:** `GET /api/v1/drive/exports/{export_id}` → existing `GET /api/drive/exports/{export_id}`, under `drive:export`. This is a fifth route, not a fifth product operation: export acceptance is not export completion. Refusing this read to preserve an exact four-route count would leave the loop unverifiable. Returns `pending/running/succeeded/partial/failed` as applicable, completed/failed file counts, safe per-file outcomes, and the folder URL. Normalize the existing initial export state to `pending` if necessary.

**NEW human-only management routes:** `GET/POST /api/workspace/api-keys` and `DELETE /api/workspace/api-keys/{key_id}`. Require cookie session, CSRF protection for mutations, strict home-workspace ownership, and no bearer authentication. List returns metadata only. Repeated revoke of an owned revoked key succeeds without revealing the secret.

### Input and output decisions

- **Drive file IDs first.** This is real today. The owner connects Drive and configures source/output destinations in Studio. Copyable destination IDs appear on the key screen; the agency supplies a file ID from its own Drive workflow. Input must be a video directly in the configured source folder, matching existing validation. No arbitrary URL fetcher, recursive folder semantics, or upload-URL promise. Existing chunk uploads are not public v1: their metadata is currently process-global and needs a separate tenancy review before exposure.
- **One source per pack.** `count` follows existing supported Fast pack sizes; the inspected billed path permits 8 or 20 and clips up to 60 seconds. Use those limits for this public v1 even if an unbilled Lab instance permits more. Preserve current validation, reservation, accounting, and worker behavior. The API accepts no quality-mode or creative-engine controls; it selects current Fast behavior. HQ remains optional in the product and outside this contract.
- **Ready is explicit.** Preserve the existing job states (`running`, `done`, `cancelled`) and report safe error/shortfall fields separately: `done` does not imply every requested file exists. Only existing accepted outputs with files present become exportable references. A partial pack requires the agency to select its available copies explicitly; never silently describe it as complete or recreate it.
- **Review stays in Gallery.** Return an ordinary authenticated Studio review link, not a bearer token embedded in a URL or an unauthenticated media link. Gallery metadata is not visual review. No raw media-download endpoint in v1; an operator reviews in Studio and the agency decides when its AI may export. No new approval-state system is implied.
- **Export retains existing names and caption handling.** Optional explicit captions use the existing export naming behavior. Public v1 forces `consume_bank=false` and rejects caption-bank mutation parameters. No split export in v1. The scheduler consumes the configured folder under the agency's existing setup; Studio does not contact it.
- **Safe projections.** Expose IDs, filenames, timestamps, copy readiness, counts, workflow-neutral state, and safe errors only. Omit quality dictionaries, internal processing metrics, presets, raw events, local paths, upstream stack traces, and credential-bearing URLs. Reject unknown input fields rather than silently accepting undocumented controls.

### Retry and completion semantics — NEW boundary behavior

Require a caller-generated idempotency key for both mutations. Bind it to workspace + operation + canonical request, including source/destination/count or selected copies/captions. Repeating the same request returns its recorded resource; a different body with the same key returns `409`. Keep records for at least 30 days and document that window. Checking the key occurs before Drive downloads or generation/export side effects; retries that resolve an existing request do not consume a new-work slot.

Existing generation deduplication applies only when billing is enabled and compares count/source count; it is insufficient as the public guarantee. The boundary needs durable request admission and correlation to existing job/export IDs, reusing the existing billing reservation key. Concurrent submissions serialize at admission. After a crash in an uncertain submission window, reconcile by the durable resource correlation; if uncertain, return a recoverable conflict for operator resolution rather than blindly starting another job or export. This is request bookkeeping around existing services, not a queue rewrite. Do not promise exactly-once delivery to Drive.

Poll at five-second intervals, back off to 30 seconds, honor `Retry-After`. Retry transient read errors. Retry mutations only with the same idempotency key and body. A timeout may occur during the existing synchronous Drive download before pack creation returns; repeat the same request to recover its result. Partial/failed export is surfaced for Studio recovery, not automatically resubmitted as a fresh export.

Use stable errors `{error:{code,message,request_id}}`: `401` invalid/revoked/expired key; `403` missing scope or unavailable entitlement; `404` missing or other-workspace resource; `409` conflicting/in-progress/uncertain request; `422` invalid source/count/destination input; `429` throttled; `503` temporary Studio/Drive unavailability. Preserve a safe distinct insufficient-funds outcome (`402`) from existing billing behavior. No promise that Studio stays reachable while its host is asleep/offline.

## D. MCP package and example agency loop

Ship a small versioned Python stdio package with a proposed `varimo-mcp` executable. It reads `VARIMO_BASE_URL` and `VARIMO_API_KEY` from its environment, calls only the public HTTP contract, and holds no Drive/Instagram credentials. The client launches the subprocess; stdout is reserved for MCP protocol messages and redacted diagnostics go to stderr, following the official MCP stdio transport contract.

| Tool | Inputs | Behavior |
| --- | --- | --- |
| `create_pack` | input destination ID, Drive file ID, count, caller request ID | POST pack; return pack ID/status, without waiting through generation |
| `get_pack` | pack ID | GET status, ready references, shortfall, review link |
| `list_gallery` | optional pack ID, limit, cursor | GET safe gallery page |
| `send_to_drive` | destination ID, selected copy references, caller request ID; **or** export ID for status | Submit via POST, or read via supporting GET; return current export state and folder URL |

`send_to_drive` has two explicit mutually exclusive schemas: submit inputs or status inputs. This preserves four job-oriented tools without pretending a long export always finishes inside a tool timeout. Reads do not mutate. Mutation annotations identify side effects; authorization remains server-enforced. Stable caller request IDs become HTTP idempotency keys, including across MCP restarts. No tool accepts a replacement base URL, token, arbitrary HTTP path, or workspace selector.

Example: the agency's AI already knows an approved Drive clip ID and source/output destination IDs. It calls `create_pack` for eight copies, polls `get_pack`, and uses `list_gallery` to inspect metadata. The operator follows the review link when review is required by the agency. After the agency's export authorization, the AI calls `send_to_drive` with selected ready references, then checks that export ID until it succeeds or reports partial/failure. It returns the folder link to the agency. Repurpose.io/Buffer is already attached to that folder by the agency; no posting tool runs.

The owner supplies secrets through the MCP client's local secret/environment configuration, never through the chat prompt. Configure a fixed HTTPS Studio base URL; localhost HTTP is permitted for Lab only. Do not forward Authorization across redirects or to another origin. Desktop clients that support local stdio can use this package. A cloud-only AI platform that cannot run stdio uses HTTP directly where supported; hosted remote MCP is a separate future transport decision, not a universal-compatibility promise.

## E. Studio UI and operator documentation

Choose **Settings → Integrations**, one screen. Keys authorize packs and Gallery as well as Drive; placing them inside Drive would imply they are Drive credentials. This is one small owner surface, not a settings redesign.

Screen content: workspace identity; Create key (label, scope preset/checklist, expiry); one-time reveal with Copy; key table (label, prefix, scopes, created, expiry, last used, revoked status); Revoke action; configured Drive destination names and copyable IDs; operator guide link. Creation states that a key can generate billable work and access the granted workspace data. Missing Drive configuration links to the existing Drive screen. VA/member sessions and admins viewing another workspace cannot reveal or manage keys. Existing review/export UI remains usable.

One operator page, expanded when MCP ships, covers:

1. Connect Drive and choose existing input/output folders; create an owner-issued key.
2. Supply the base URL and key locally, then make one pack with curl, poll it, read its Gallery entry, export selected copies, and verify export completion.
3. Configure the installed stdio executable with the same base URL/key in the agency's client; show the equivalent tool loop.
4. Attach the export folder to the agency's own Repurpose.io/Buffer setup; the agency holds the subscription and controls posting.

The published guide must not include fingerprint or encoding internals, internal thresholds, required HQ steps, detector language, or platform acceptance predictions. How-to and this page teach the same human/machine loop and may progress independently.

## F. Security and authorization boundaries

- **Tenant selection precedes resource lookup.** Authenticate the bearer key and bind the workspace for every service access, including export runners and request bookkeeping. All pack, source, variant, destination, and export references are looked up within that bundle. Foreign IDs return the same `404` as nonexistent IDs. No workspace ID from body, header, query, or admin view cookie overrides the key.
- **Bearer is not a human identity.** Introduce a scoped integration principal, not a synthetic owner user. A request with Authorization uses bearer handling or fails; it never falls back to a valid cookie after a bad key. Bearer credentials on non-allowlisted routes are rejected even if a session cookie accompanies them. Human UI requests without Authorization keep existing session behavior.
- **Owner versus VA.** Only the owner issues keys. A VA may operate a dedicated owner-issued key and receives exactly its scopes. Keys are workspace-wide within those scopes, not per-client asset ACLs; different client names/folders do not create isolation inside a workspace. Separate workspaces are required for hard separation in v1. Removing a VA's human login does not revoke an agency key shared with that VA: offboarding must revoke that dedicated key. Deleted/demoted issuers invalidate their issued keys; ownership transfer requires replacement issuance.
- **Viewing-other admin.** Do not reuse `_require_workspace_owner` unmodified: it currently grants an admin exception. Key management requires `role == owner` and home workspace equals viewed workspace, regardless of site-admin configuration. Neither admin status nor a view cookie broadens a key.
- **Leaked keys.** The owner revokes the exposed key, checks key-ID audit records for pack/export activity, and issues a replacement if needed. Revocation is effective for requests admitted after the revoke transaction commits. It does not undo an already-authorized export or cancel an existing pack; operators can use existing Studio recovery/cancel controls. Avoid claiming that files already delivered to Drive can be recalled.
- **Secret hygiene.** Redact Authorization and token patterns in application, proxy, exception, telemetry, and MCP logs. Disable request/response body capture on key issuance. Audit key ID, workspace, operation, resource ID, time, and result; never credentials or raw media. Scrub downstream Drive errors. No keys in analytics, browser persistence, URLs, examples, screenshots, prompts, or worker images. Store the owner's one-time token only as transient reveal state; clear it on dismissal/navigation.
- **Admission and recovery.** Enforce expiry, revocation, scopes, limits, and idempotency before expensive work. A key may spend only under current workspace entitlements. Existing worker scheduling remains authoritative. Auth-store failure denies new bearer work rather than silently granting access.

## G. Phases, sign-off criteria, and cuts

**Phase 1 — keys + four core HTTP operations, plus export status.** Lab first. Sign-off requires a real Drive clip → existing Fast job → Gallery review → configured Drive export loop, recovery from a timed-out submission without duplicate work, honest partial/missing-copy outcomes, instant revocation on the next request, and unchanged human cookie behavior. Cross-workspace IDs, admin-view cookies, VA key management, scope bypass, concurrent retries, and credential capture must be demonstrated safe before promotion. This validates integration/auth behavior, not a new rendering algorithm.

**Phase 2 — MCP.** The stdio package wraps the phase-1 API and uses the same scopes, retries, safe outputs, and errors. Sign-off requires the loop from an actual supported client, including process restart and export status recovery. HTTP keys rank first: MCP-only still needs workspace authorization and the same four business operations, while excluding software that calls HTTP directly. Wrapping cookie sessions would be a brittle shortcut.

**Phase 3 — trigger an existing workflow.** Add explicit `workflows:read` and `workflows:run` grants to newly issued keys; never expand existing keys silently. Map public list/run/status adapters to existing `GET /api/workflows` and `POST /api/workflows/{id}/run`, with existing workflow summaries/ledger behavior. A run triggers the existing inbox sweep, not necessarily one clip or immediate completion. Only existing Fast workflows qualify. Workflow creation/editing, Drive connection changes, and scheduler management stay human-only. Caption-bank read is optional later with a separate read scope; no implied cursor mutation permission.

**Not in v1:** workflow triggers; caption-bank read/consume; HQ generation; upload URLs/chunk uploads; arbitrary remote URL ingestion; raw media download; public events/Diagnostics; split export/retry endpoints; webhooks; remote hosted MCP/OAuth; per-client ACLs inside a workspace; Instagram connect/sync/posting; scheduler seat operation; new queues, Redis, cloud-worker migration; G-Lark; face swaps; upscaling.

**Invariant and release boundary.** Do not change Fast, look/color behavior, uniqueness, or the existing generation path. The internal uniqueness gate remains 24; this is never customer API documentation. No tone-curve or reconstruct-first requirement is added. No Lab → Live Git merge. After separate acceptance, promote reviewed files from `snaughtyllc-cell/variant-maker` to `snaughtyllc-cell/varimo-live` using `scripts/promote-to-live.sh`. Never patch Live Fast or push `variant-fast:latest` from Lab. No promotion is part of this planning task.
