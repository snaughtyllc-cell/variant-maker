# Google Drive for outside operators (Jeff ops)

Operators never open Google Cloud. Connect Google in Studio uses **this**
OAuth client on Railway.

## What operators do

Settings → Drive → copy the VaryForge share email (`drive@varyforge.app`) →
share that address as **Editor** on the Google Drive folder → paste the
folder link. They do **not** share a folder with Jeff’s Gmail.

Connect Google is Jeff-once: sign Studio in as `drive@varyforge.app` so
those shared folders actually open. Per-operator “use my Google account”
is later.

## What blocks them

The OAuth app is likely **unverified**. Drive (`.../auth/drive`) is a
restricted scope. Until Google verification, only **test users** can finish
Connect Google. Everyone else sees “Google hasn’t verified this app.”

When you send a **New workspace** invite, add that operator’s Google email
as a test user on the same GCP OAuth client (APIs & Services → OAuth consent
screen → Test users). Do that the same day as the invite.

Do not ask them to create a GCP project or enable APIs.

## Tools-email (current operator path)

Operators share a branded address (`drive@varyforge.app`) as Editor, then
paste the folder link. Show that human address in Studio with a copy
button — never Jeff’s Gmail, never `*.iam.gserviceaccount.com`.

Jeff-once: create the mailbox, Connect Google as that account on Studio,
set `VARIANT_DRIVE_SHARE_EMAIL` if it is not the default.

Connect-your-own-Google stays the later path (unverified OAuth app). Do
not ask operators to share with a personal inbox in the meantime.

## Verification (later)

Publishing the app / CASA for full Drive is a Jeff/legal track, not an
operator tutorial. Probe `drive.file` + folder picker before paying for
restricted-scope verification.

See `docs/superpowers/specs/2026-08-20-operator-friction.md`.
