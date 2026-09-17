# Registering an entrant

No OAuth, no account database, no typed-in username, and no bot with write access
to anything. A participant generates an Ed25519 key pair locally with
`ssh-keygen` and only ever publishes the public half --
see [generating-a-key.md](generating-a-key.md).

1. Fill in the details and the public key, then click **Submit registration via
   GitHub**. The page opens a prefilled `entrants/<id>.json`.
2. GitHub walks you through forking if you do not have one. Save on a new branch
   and open a pull request against **`main`** of
   `assassin808/social-sim-arena-e2e-test`.
3. The file arrives with `"github": ""`. Validation fails on purpose until the
   identity is bound. A `pull_request_target` workflow reads the pull request
   author from GitHub's own metadata and posts an inline suggestion filling that
   line in.
4. Check the account and the public key shown, then click **Commit suggestion**.
   That records the binding in Git history, by your own hand. No username is ever
   typed. A pull request opened from the wrong account should be closed and
   resubmitted from the right one.
5. The existing ownership and schema checks then pass, and a maintainer reviews
   and merges.

## Why the base branch is `main`

It was `qa-signed-intake-registry` for a while, and that was a mistake: **a fork
starts with the default branch only**, so a non-default base forced every
registrant to create that branch in their own fork by hand before they could open
the pull request. That is our plumbing leaking into someone else's first five
minutes.

Isolation is what the whole fork is for. An internal QA branch adds nothing to it
and is not something a registrant should have to know about. `qa-signed-intake-
registry` still exists, but only as the home of the signed-lifecycle rehearsal
report that `site/signed-lifecycle.html` reads.

## Where the safety actually comes from

`tools/validate_submission.py` refuses a new registration whose `github` field is
not the pull request's author, and refuses a change to an existing file by anyone
but its recorded owner. **That check is the security boundary, not the workflow.**

The binding workflow only removes the typing step and turns a confusing
validation failure into one click. If it never runs, nothing unsafe happens: the
`github` field stays empty, validation stays red, and the pull request cannot
merge.

That is why it can safely use `pull_request_target`. It never checks out
contributor code, never runs a contributor script, and never touches repository
contents. Its only write permission is `pull-requests: write`, which is to say
comments. It must live on the default branch to be discoverable.

Existing entrants are never rebound automatically.

## What was removed

The website OAuth endpoints and session handling are gone (`ssa/registration_login.py`,
`api/registration.py` and their tests). The OAuth app and its grants can be revoked
in GitHub settings, and the Vercel project created for that experiment
(`assassin808-ssa-registration`) should be deleted -- it is still serving.

The separate GitHub App used to persist signed answers is a different thing and is
kept. Signature verification and answer encryption are unchanged.

## Hosted verification, 2026-09-17

Test pull request:
<https://github.com/assassin808/social-sim-arena-e2e-test/pull/3>. The bot derived
`assassin808` from the pull request metadata and posted the inline suggestion;
Apply suggestion followed by Commit changes recorded that account in the file. The
pull request was left open, not merged. The initial validation failure on the
empty `github` field is intentional. After the suggestion was applied all three
checks passed: ownership and schema, the binding workflow, and hygiene.

Vercel preview protection is still on. Finishing manual acceptance as a true
first-time external contributor needs a second real GitHub account.
