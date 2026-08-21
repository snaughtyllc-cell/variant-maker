# Operator onboarding — VaryForge Studio

First paid day for a **new-workspace owner**: Connect Drive, invite a VA on **Team**, Generate **Fast 20**, **Send to Drive**. You do not need a call for that.

Studio URL: https://varyforge-studio-production.up.railway.app

Forward this page. Invite-only; there is no public signup.

## Invite-only

- **New workspace** comes from the **site admin**. That is your empty studio (your gallery, your Drive).
- **Team** (this studio) is how **you** add VAs. That invite is **join this studio** — they share your gallery, captions, and Drive.
- VAs do **not** get a new empty studio. Do not ask them to “sign up.”

You cannot mint another empty workspace from Team. Ask the site admin.

## Sign in

Open the Studio URL. Use the invited email.

- **Email + password** — first visit **sets** that password (8+ characters). Later visits use the same one.
- Or **Continue with Google** with that same invited email.

Uninvited emails get “ask the operator to add you.”

Drive Connect is **not** Studio login. If you use Google for both, connect both: sign-in, then Drive → Connect Google.

## Drive

Settings → **Drive** → **Connect Google**. Then **add a destination**: paste a Drive folder link.

Workflows and **Send to Drive** use those saved folders. No folder saved → nothing to export to.

Drive Connect is per studio. The owner connects once. VAs in this studio share it.

## Team

**Team** → invite VA (email). They sign in at this Studio URL with that email plus a password they choose, or with Google. First password sign-in sets it.

That is a **join** invite — they land in your studio, not a new one.

## Uniqueness % vs yellow shortfall

Uniqueness on Fast is looking good. Leave the gate where it is.

- The uniqueness **gate stays 24/24** (24 bits vs the source, 24 vs peers) — about a **~38% badge floor**.
- **Medium talking-head often scores higher** than that floor. That is expected.
- Read uniqueness on the **small % badge** on each **Gallery** tile (higher = more different from the original). Open a tile for the uniqueness meter.
- Yellow **“N variants fell short after auto-retry”** is a **quality/VMAF** fail after auto-retry (`best_effort`). It is **not** the uniqueness number. Do not treat that banner as a uniqueness miss.
- **`esc`** on a tile is one stronger uniqueness pass, not a fail.

Regenerating fills a quality shortfall. It does not mean the uniqueness badge failed.

## Fast vs HQ

Uniqueness on Fast is looking good, so **daily packs stay Fast**. HQ is optional hero takes, not the daily 20.

On Studio **Generate** (Advanced → Quality). Leave uniqueness and quality checks on.

| | **Fast** (daily) | **HQ** (optional) |
|---|---|---|
| Use for | Daily packs (usual **20**) | Hero takes (1–3) |
| How | CPU | Reconstructive GPU (Real-ESRGAN), one-at-a-time |
| Feel | Minutes for a 20, not seconds | Slower; do **not** run a 20 |

Stay on **Fast** unless you specifically want HQ.

## Workflow vs Generate

- **Waiting** = Studio **Generate** (1–2 clips or a Fast 20). Stay until tiles show; Gallery stays empty until a variant finishes.
- **Workflows** (Drive inbox → output folder) can sit in the background.
- Do not expect Telegram-bot seconds.

## Gallery labels

VaryForge is **not** a detector. The real platform is the oracle.

- Unlabeled clips count as **pass**. You do not have to click Passed on every file.
- Mark **Duplicate rejected** only when the real platform said duplicate.
- **Flagged** comes later — same rule: only when the real platform said so.

## First-day checklist (owner)

1. Sign in at the Studio URL (invited email + password or Google).
2. Drive → Connect Google → add a destination folder.
3. **Team** → invite VA (join this studio).
4. Studio → Generate **Fast 20**. Stay on the page until tiles show.
5. Gallery → read uniqueness **%** on the small tile badges. Ignore yellow shortfall when reading that %.
6. Gallery → **Send to Drive**.

## Cheat sheet (forward to a VA)

1. Open the Studio URL. Sign in with the **invited email** plus a password you choose (first visit **sets** it) or **Continue with Google** with that same email.
2. Drop a clip → **Generate Fast**. Fast CPU is the daily pack (usual **20**). Skip HQ unless asked.
3. **Uniqueness %** is the small Gallery tile badge. Floor ~38% (gate 24/24). Medium talking-head often scores higher.
4. Yellow **“N variants fell short after auto-retry”** is VMAF `best_effort`, not uniqueness.
5. Gallery → **Send to Drive** (owner must have connected Drive and saved a folder).
