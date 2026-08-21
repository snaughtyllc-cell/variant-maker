# VaryForge Studio — VA sheet

Studio: https://varyforge-studio-production.up.railway.app

Forward this. Invite-only; there is no public signup.

## Cheat sheet

1. Open the Studio URL. Sign in with the **invited email** plus a password you choose (first visit **sets** it, 8+ characters) or **Continue with Google** with that same email.
2. **Drive** → **Connect Google**, then **add a destination** (paste a Drive folder link). **Send to Drive** needs a saved folder.
3. Studio → drop a clip → **Generate Fast**. Fast CPU is the daily pack (usual **20**). Stay on the page until tiles show.
4. **Uniqueness %** is the small badge on each **Gallery** tile (higher = more different from the original). Look-first uniqueness is live on Fast. Talking-head medium typically **55–65%** with high VMAF; motion often **~80%**. The pass gate is still **24 bits (37.5%)**.
5. Yellow **“N variants fell short after auto-retry”** is a quality/VMAF fail (`best_effort`), not the uniqueness number. A 55–65% tile is a normal Fast pack. Do not treat that banner as a uniqueness miss.
6. **`esc`** on a tile is one stronger uniqueness pass, not a fail.
7. Skip **HQ** unless asked. HQ is Real-ESRGAN on the 4090, one-at-a-time, optional/slow.
8. Unlabeled Gallery clips count as **pass**. Mark **Duplicate rejected** only when the real platform said duplicate.

## Login

Use the invited email. Uninvited emails get “ask the operator to add you.” You cannot sign up.

Drive Connect is **not** Studio login. If you use Google for both, connect both: sign-in, then Drive → Connect Google.

## Drive

Settings → **Drive** → **Connect Google** → add a destination folder. Workflows and Send to Drive use those saved folders. No folder → nothing to export to.

Drive is per studio. VAs on a **join** invite share the operator’s gallery, captions, and Drive.

## Fast vs HQ

On Studio **Generate** (Advanced → Quality). Leave uniqueness and quality checks on.

| | **Fast** (what VAs use) | **HQ** (optional) |
|---|---|---|
| Use for | Daily packs (usual **20**) | Hero takes (1–3) |
| How | CPU | Real-ESRGAN on the 4090, one-at-a-time |
| Feel | Minutes for a 20, not seconds | Slow; do not run a 20 |

Stay on **Fast**.

## Uniqueness % vs shortfall

- Read uniqueness on the **small % badge** on each Gallery tile. Open a tile for the uniqueness meter (typical medium ~55–65%; pass line ~38%).
- The yellow Gallery banner **“N variants fell short after auto-retry”** is a **quality/VMAF** fail after auto-retry (`best_effort`). It is **not** the uniqueness score. Ignore it when you are checking uniqueness %.
- Regenerating fills a quality shortfall. It does not mean the uniqueness badge failed.

## Team (operators inviting VAs)

- **Team** invite = **join this studio** (same as Admin **Join my workspace**). They land in your gallery on purpose.
- **New workspace** is site Admin only — an empty studio + their own Drive Connect. VAs do **not** get this. Do not ask them to “sign up.”

## Workflow vs Generate

- **Waiting** = Studio **Generate** (1–2 clips or a Fast 20). Stay until tiles show; Gallery stays empty until a variant finishes.
- **Workflows** (Drive inbox → output folder) can sit in the background.

## First day

Operators: **Team** → invite VA (join this studio). Then the VA:

1. Signs in (invited email + password or Google).
2. Drive → Connect Google → add a destination.
3. Generate **Fast 20**.
4. Reads uniqueness % on Gallery tiles. Ignores yellow shortfall when reading that %.
5. Sends to Drive.
