# API contract, questions and scoring

Audit 2026-09-15, then the fixes it produced. Read-only against the test site
plus local production rules: no keys were read, no forecast was submitted, no
model was called, nothing was deployed.

## What the audit found

Three defects, each with a regression test.

**1. `answer_schema` could not be used on its own.** `_schema_branches` in
`ssa/questionnaire_api.py` returned a branch and dropped the root `definitions`,
so validating a legal `{round_id, target_type, response: {value: 0}}` against the
returned schema raised `PointerToNowhere: /definitions/round_id`. A client
generating a form or an automated entrant could not consume it.
Regression: `test_human_manifest_schema_is_standalone`.

**2. A bundle accepted answers before publication.** Calling `bundle.normalise`
one second before `published_at=2027-12-29T14:00:00Z` returned `accepted=3` and
wrote three records. The receiving path checked the deadline but not the opening
time, which contradicts the manifest rule that an unpublished question is
invisible. Verified locally against the real function; this does **not** show
that anything was filed early in production.
Regression: `test_bundle_rejects_before_publication`.

**3. All 17 live questions had `resolution_source_url: null`.** `GET
/api/v1/questionnaire` returned 200 with `generated_at=2026-09-15T23:20:30Z` and
no machine-readable source URL anywhere. The prose `resolution_rule` was still
readable, so this is "no machine-readable source", not "no source information".
Regression: `test_manifest_supplies_machine_readable_resolution_sources`.

## What was fixed

- Every human and agent branch of `answer_schema` now carries the root
  `definitions` and a dialect declaration, so local `$ref`s resolve standalone.
- `resolution_source_url` resolves in order: the question's explicit URL, then a
  mapping from published `data.tasks` by series / series_prefix / target_type,
  then archived provenance via `series_provenance -> sources.url`. An unknown
  source stays `null`; no link is invented. All 17 open questions in the
  2026-09-15 snapshot now carry one.
  A source link is a publisher entry point. It is not a download link for the
  specific snapshot a question resolves against, and it says nothing about that
  day's availability.
- A bundle now checks `batches.published_at` per question against `lock_at`
  (existing rule: one week before the deadline). The opening instant is
  inclusive, the deadline is exclusive, and an early answer returns
  `not_published` without writing a record. A batch's earliest opening time no
  longer lets a later question in it be answered early.
- Three former `expectedFailure` markers became ordinary regressions, so a fixed
  defect cannot keep reporting as "expected to fail".

## Friday and source failure: the behaviour that already exists

From `ssa/batches.py`, `ssa/series.py`, `ssa/adapters/civiqs.py`, `ssa/resolve.py`
and `docs/sources/civiqs.md`:

1. The deadline is strictly the question's own `lock_at`. Friday is Civiqs'
   target observation day, not one lock time shared by every question.
2. The registered Civiqs series declares `weekday=4`, archives daily and reads
   the displayed dashboard value. The underlying model's Thursday date is not
   rewritten into a Friday raw survey result.
3. A gap-fill looks for the earliest snapshot on or after the target day and
   reads that snapshot's value. That can differ from "what the dashboard showed
   on Friday", and it is not an immutable first print at a fixed Friday hour.
4. When upstream fails, existing archives are served and the run is marked. With
   no readable archive the run refuses to emit an empty series. The resolver
   refuses to resolve before the release time, without history, or without a new
   observation, and never overwrites a completed resolution. "An old archive is
   available" is not "the target day has really resolved".

## Open, and deliberately not decided by QA

- Which timezone and which hour does "Friday" mean, and when a day is fetched or
  revised more than once, is it the first or the last reading?
- How long may a failed target-day fetch be retried, and can a later snapshot
  stand in for the original target day?
- After the grace period: postpone or cancel, and how does a cancelled question
  leave the leaderboard denominator?
- When a source issues a correction after resolution: keep the first result, or
  publish a versioned recomputation?

These change published answers and scores, so they are not for a test engineer to
apply retroactively. Once decided, release them versioned on isolated future QA
questions first, then test source loss, late arrival, same-day revision and
cancellation.

## Question wording and resolvability

- The current Civiqs "angry" question names its population and its percentage
  metric and locks at `2026-09-16T14:00:00Z`. Its resolution text is still
  "dashboard Friday value, from the daily archive", with no timezone and no rule
  for which snapshot wins when a day is revised. The 16-cell profile depends on
  the same Friday archive. This is a dispute-handling gap, not evidence that the
  result cannot be fetched.
- `wiki-top10-2026-09-27` already states "seven daily top-1000 lists summed" and
  the namespace exclusions, and its `resolution_rule` states that a missing day
  contributes zero and that ties break by title ascending. The earlier report's
  complaint that the truncation was under-specified should be dropped. It is a
  weekly aggregate over truncated lists and should not be read as a ranking by
  full pageviews.

## Reproduce

```sh
.local/venv/bin/python -m unittest tests.test_qa_contract_fixes tests.test_qa_api_scoring tests.test_bundle_api -q
.local/venv/bin/python -m tests.test_bundle
.local/venv/bin/python -m tests.test_profile_scoring
.local/venv/bin/python -m tests.test_scoring
```

71 existing assertions pass (bundle API 25, bundle 28, profile scoring 14,
scoring 4) plus 34 from the contract-fix suites and 28 bundle regressions.
Coverage includes: one second before publication, exactly at publication, one
second before the deadline, exactly at the deadline; unknown and duplicate
rounds; wrong answer shape; missing profile cells; out-of-basket rankings; zero
variance; identity and revocation; late answers not overwriting; cache-style
repeat uploads; storage unavailable; profile energy determinism.

Not covered here: real submission storage (isolated temp dirs and mocks),
concurrency and load, future cron runs, every upstream source, browser
interaction, and paid or free model behaviour -- those belong to the other
reports.

Read-only online check: fetch the [public questionnaire
API](https://social-sim-arena-e2e-test.vercel.app/api/v1/questionnaire) and
inspect `questions` length, `resolution_source_url` and `answer_schema`. The
count moves with real time; 17 was the snapshot at the moment above.
