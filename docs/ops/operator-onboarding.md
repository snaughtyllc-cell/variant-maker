# Operator onboarding — VaryForge Studio

First paid day: Connect Drive, invite a VA on **Team**, Generate **Fast 20**, **Send to Drive**. You do not need a call for that.

Studio URL: https://varyforge-studio-production.up.railway.app

## Invite-only

VaryForge is invite-only. There is no public signup.

- **New workspace** comes from the **site admin**. That is your empty studio (your gallery, your Drive).
- **Team** (this studio) is how **you** add VAs. That invite is **join this studio** — they share your gallery, captions, and Drive.
- VAs do **not** get a new empty studio. Do not ask them to “sign up.”

You cannot mint another empty workspace from Team. Ask the site admin.

## Sign in

Open the Studio URL. Use the invited email.

- **Email + password** — first visit **sets** that password (8+ characters). Later visits use the same one.
- Or **Continue with Google** with that same invited email.

Uninvited emails get “ask the operator to add you.”

## Drive

Settings → **Drive** → **Connect Google**. That consent is **Drive**, not Studio login — connect both if you use Google for sign-in.

Then **add a destination**: paste a Drive folder link. Workflows and **Send to Drive** use those saved folders. No folder saved → nothing to export to.

Drive Connect is per studio. Your VAs in this studio share it.

## Fast vs HQ

On Studio **Generate** (Advanced → Quality):

| | **Fast** | **HQ** |
|---|---|---|
| Use for | Daily packs (usual **20**) | Optional hero takes (1–3) |
| How | CPU, libx264 | GPU, 1080 reconstructive upscale |
| Feel | Minutes for a 20, not seconds | Slower; one variant at a time |

Stay on **Fast** unless you specifically want HQ. Quality checks (VMAF) and uniqueness stay on for both — leave them.

## Workflow vs one-off Generate

- **Workflows** (Drive inbox → output folder) can sit in the background. That path is allowed to be slow.
- **Waiting** is the interactive 1–2 clips (or a Fast 20) on Studio **Generate**. Stay on that page until tiles show; Gallery stays empty until a variant finishes.
- Do not expect Telegram-bot seconds.

## Gallery labels

VaryForge is **not** a detector. The real platform is the oracle.

- Unlabeled clips count as **pass**. You do not have to click Passed on every file.
- Mark **Duplicate rejected** only when the real platform said duplicate.
- **Flagged** comes later — same rule: only when the real platform said so.

## First-day checklist

1. Sign in at the Studio URL (invited email + password or Google).
2. Drive → Connect Google → add a destination folder.
3. **Team** → invite VA (join this studio).
4. Studio → Generate **Fast 20**.
5. Gallery → **Send to Drive**.
