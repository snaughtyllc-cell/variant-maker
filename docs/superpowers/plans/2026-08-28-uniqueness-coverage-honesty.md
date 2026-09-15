# Uniqueness coverage honesty — implementation plan

> **For agentic workers:** TDD. Failing test → implement → green → stop. Spec:
> `docs/superpowers/specs/2026-08-28-uniqueness-coverage-honesty.md`. Studio UI
> only. Do not merge copyid engine PR #55.

**Goal:** Studio says what Originality measures (3-frame pixel SSIM vs the
original) and what it does not (platform pass, visual copy-id, audio).

**Constraints**

- Keep the customer label **Originality**.
- `quality.heads` is additive and optional. Today’s payloads omit it.
- Pixel chip reads top-level `uniqueness`, not `heads.ssim`.
- Visual / audio chips score only when `available === true`.
- No Python. No Fast pin. Gate stays 24/24.

```
cd web && npm test
```

---

## Task 1: Copy helpers + types

**Files:** `web/lib/types.ts`, `web/lib/prepareCopy.ts`, `web/lib/format.ts`,
`web/lib/__tests__/prepareCopy.test.ts`, `web/lib/__tests__/format.test.ts`

- [ ] `QualityHead` + `Quality.heads?` match the copyid spec shape.
- [ ] `uniquenessCoverageChips(uniqueness, heads)` returns Pixel / Visual
      copy-id / Audio with `scored` | `not_scored`.
- [ ] Subcopy and gallery badge title name pixel SSIM and deny a platform
      check.
- [ ] `ESCALATED_TITLE` drops “visual score”, keeps 55–65 / 38 / 30 / not a
      fail, adds not a platform check.

## Task 2: Sheet + gallery

**Files:** `web/components/variant/QualityPanel.tsx`,
`web/components/variant/VariantSheet.tsx`,
`web/components/gallery/VariantCard.tsx`,
`web/components/gallery/SourceGroup.tsx`,
`web/components/studio/AdvancedPanel.tsx`, matching tests.

- [ ] QualityPanel always renders three chips + subcopy.
- [ ] Heads with `visual.available` / `audio.available` light those chips.
- [ ] Gallery % badge `title` is the pixel-SSIM line.
- [ ] Source-group Originality summary has the same subcopy as `title`.
- [ ] Advanced escalate copy says pixel SSIM and not a platform check.
