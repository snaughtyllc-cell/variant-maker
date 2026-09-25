# Lab PR #91 security review

Reviewed `11b3be9848d251b9dffc4acb2623468dfffb3285` against its stacked base,
`cursor/lab-live-parity-b385` (#90), in `snaughtyllc-cell/variant-maker` only.
Verdict on the submitted head: **fix-then-ship**. All five findings below are
patched in this follow-up. No remaining security blocker was identified in the
reviewed scope. This is not a review of the entire parity port or a Live promotion.

## Findings and fixes

1. **High / P1 — shared-object download IDOR.**
   `variant_maker/server/app.py`, `variant_file`, `look_still`, `source_zip`
   (submitted-head lines 1960–1989 and 2180–2192).
   A signed-in user who knows another workspace's source ID receives a signed
   object URL even though the source is absent from their tenant store. Local-only
   isolation tests miss this fallback. Three regression cases reproduced HTTP 302
   across tenants. Each route now checks tenant source ownership before lookup or
   signing. This inherited path is directly relevant to #91's shared-bucket
   isolation mitigation; the from-object allowlist cannot protect download routes.

2. **High / P1 — chunked PUT buffers unbounded input before its cap.**
   `variant_maker/server/app.py`, `put_upload_chunk` (submitted-head line 1713).
   A signed-in operator can send an arbitrarily large PUT to an owned upload;
   `request.body()` consumes it into RAM before returning 413, risking process OOM
   for all workspaces. The handler now streams, rejects the first overflowing
   chunk, and performs file I/O off the event loop. The declared upload size and
   2 GiB ceiling both apply. The regression uses a reduced cap and verifies that
   the handler stops receiving at overflow rather than draining the request.

3. **Medium / P2 — direct-upload size cap can be bypassed.**
   `variant_maker/server/app.py`, `init_direct_upload` / `_claim_direct_upload_key`
   (submitted-head lines 1694–1696 and 918–925);
   `variant_maker/server/storage.py`, `presign_put`.
   The caller could declare a small size, PUT a larger object with the unconstrained
   URL, then have Studio copy/download/process it without checking actual size.
   URLs now sign Content-Length; finalization checks object size before copying.
   Tests inspect a real botocore signature and reject an oversized object before
   any input copy or job starts. Browser-supplied File/Blob bodies provide their
   own Content-Length; JavaScript need not set a forbidden request header.

4. **Medium / P2 — proxy middleware defeats the TCP-peer throttle key.**
   `variant_maker/server/app.py`, `_login_bucket` (submitted-head lines 1013–1016);
   `variant_maker/server/cli.py`, `main` (lines 90–91).
   The launcher leaves Uvicorn proxy-header processing enabled. A trusted loopback
   proxy can supply XFF that rewrites `request.client`, so reading that attribute
   is not necessarily reading the TCP peer. A test using the launcher's actual
   Uvicorn configuration bypassed eight failures by rotating XFF values.
   The launcher now uses `proxy_headers=False`. Alternate Uvicorn entrypoints must
   also disable proxy-header rewriting. Cookie/redirect code still handles the
   existing forwarded-proto behavior. Shared-proxy per-email lockout remains the
   explicitly accepted limitation; Google login stays outside this throttle.

5. **Medium / P2 — owner-only Instagram metrics leak through other responses.**
   `variant_maker/server/app.py`, `_variant_out`, `_source_out`, `gallery`
   (submitted-head lines 255–257, 361–370, 1926).
   Members denied `/api/instagram/analytics` still receive cached `ig_insights`,
   account identifiers and aggregate metrics in Gallery, job detail/cancel and
   variant mutation responses. Serializers now require an explicit visibility
   decision derived from the signed-in user's owner/admin role on every call.
   Tests verify member redaction while owner data remains intact.

## Validation

- TDD: all eight exploit cases failed before their fixes and passed afterward.
- Eleven new security tests pass, including attribution-spoof rejection, truncated
  signed-cookie rejection, non-admin view-cookie isolation, direct-upload tenant
  ownership, consumed-upload rejection and inputs/outputs allowlist rejection.
- Latest complete server run: **417 passed, 1 failed**. The failure is
  `tests/server/test_jobs.py::test_two_jobs_use_separate_folders_and_cancel_is_per_job`:
  concurrent `_persist` calls race on `job.json.tmp`. It reproduced on the
  unmodified submitted head in an isolated checkout. An earlier full run passed
  all 415 tests present before the final three preservation checks were added.
  The existing persistence race is reported, not changed in this security patch.
- Ruff passes for the new regression file; `git diff --check` passes. Broader lint
  has existing import/broad-exception warnings. No new dependency was added.
- Tests use fake media/object stores and real local botocore signing/Uvicorn
  middleware. No live Railway, R2, Drive, Instagram or caption-provider calls were
  made; provider/browser integration is not claimed as verified.

## Accepted leftovers and data handling

- Shared R2 keys remain unprefixed by workspace. Keep the from-object allowlist;
  tenant checks on the output download fallbacks are also necessary and now added.
- `_UPLOAD_META` remains in memory for one Railway replica.
- HttpOnly, SameSite=lax cookies remain without CSRF tokens; this does not provide
  general same-site-origin CSRF protection.
- Multipart `/api/jobs` still reads media into RAM. That acknowledged path is
  unchanged; the finding above concerns the separately promised chunked cap.
- Operator email in `usage.jsonl` and configured PostHog events is intentional PII.
  Attribution comes from `request.state.user`; Team/Admin reads remain privileged,
  and public job serializers do not expose `customer_email`. No new token or
  caption-provider-key response leak was identified in the reviewed changes.

No Lab/Live merge, file promotion, sampler/filtergraph change or `.vmdata` commit.
