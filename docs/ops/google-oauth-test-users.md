# Google Drive for outside operators (Jeff ops)

Operators never open Google Cloud. Connect Google in Studio uses **this**
OAuth client on Railway.

## What operators do

Settings → Drive → **Connect Google** as the Google account that owns the
folders → paste a folder link. They do **not** share a folder with Jeff’s
Gmail. Per-workspace token.

## What blocks them

The OAuth app is likely **unverified**. Drive (`.../auth/drive`) is a
restricted scope. Until Google verification, only **test users** can finish
Connect Google. Everyone else sees “Google hasn’t verified this app.”

When you send a **New workspace** invite, add that operator’s Google email
as a test user on the same GCP OAuth client (APIs & Services → OAuth consent
screen → Test users). Do that the same day as the invite.

Do not ask them to create a GCP project or enable APIs.

## Tools-email fallback (only if they refuse OAuth)

A branded address (`drive@varyforge.app`), share one folder as Editor. Show
that human address in Studio, never `*.iam.gserviceaccount.com`. Still
third-party share — worse than Connect Google as *their* account.

## Verification (later)

Publishing the app / CASA for full Drive is a Jeff/legal track, not an
operator tutorial. Probe `drive.file` + folder picker before paying for
restricted-scope verification.

See `docs/superpowers/specs/2026-08-20-operator-friction.md`.
