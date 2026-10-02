---
name: aws-cost-calculator
description: Use when building a cost estimate for an AWS architecture — a proposed design, a Terraform module, or an existing deployment — and the output needs to be a real, shareable AWS Pricing Calculator (calculator.aws) estimate rather than a back-of-envelope number from memory.
license: MIT
compatibility: Requires the sample-aws-pricing-calculator-mcp MCP server (aws-pricing-calculator-mcp-server) and Node.js. Strongly recommended - AWS Knowledge MCP server (used for the documentation fact checks). Works with any agent runtime that supports Agent Skills and MCP.
metadata:
  author: Håkon Eriksen Drange
  version: "0.1.0"
---

# AWS Cost Calculator

## Overview

Builds a real, shareable `calculator.aws` estimate via the [aws-pricing-calculator-mcp](https://github.com/aws-samples/sample-aws-pricing-calculator-mcp) MCP server (no AWS credentials required). Not a memorized rate, not a number scraped off a client-rendered AWS pricing page — both produce numbers that look authoritative but aren't actually current.

The MCP server is an AWS sample project that calls undocumented calculator APIs, which may change without notice. The resulting estimate is a planning figure, not an AWS quote.

## Prerequisite: the MCP server is a hard dependency

This skill cannot work without the `aws-pricing-calculator-mcp-server` MCP server (npm package `sample-aws-pricing-calculator-mcp`, requires Node.js). The skill only supplies the workflow; every estimate is built by that server's tools. Installation instructions are in the README.

## Before starting

Confirm the server's tools are actually available in the current session, for example by checking for `get_server_info`. Tool names are exposed differently per runtime (Claude Code: `mcp__<server-name>__get_server_info`, discoverable with `ToolSearch("select:...")`; other runtimes use their own prefix), and `<server-name>` is whatever name the server was registered under — this repository's plugin and Power register it as `pricing-calculator` (and the documentation server as `aws-knowledge`); the upstream README uses `aws-pricing-calculator-mcp-server`. Tools below are referred to by their bare names. Not available means the server is not installed, or is configured but this session hasn't picked it up yet — MCP servers don't hot-reload mid-session. Point the user to the README's install steps or tell them to restart/reload rather than falling back to `aws pricing get-products` (usually blocked by IAM on a read-only profile), fetching AWS's own pricing pages (they render client-side; a static fetch returns empty placeholder tables), or reciting a training-data rate.

## The workflow loop

1. **Inventory services** — from Infrastructure-as-Code files, a Terraform plan/state (`terraform show -json`, resource types and counts), a design doc, or the user's own list. For usage volumes (request rate, data volume, retention, run-hours) that weren't given: ask the user for anticipated load first — a real question, not a skip. Only if they don't have a figure either, fill the gap with a stated best-effort estimate (reasoned from the workload's own shape — e.g. a typical small internal service vs. a public API — not a round number pulled from nowhere) and mark it as such in the assumptions table (below). Never leave a required numeric field blank to avoid the question, and never present a best-effort number as if it were given.
2. **Per service (read-only, no gate needed):** `search_services` to find the calculator's service key, then `get_service_fields` for real field IDs/options. For curated services (`status: "verified"`/`"partial"` in the response), start from the returned `catalog.minimalConfig` and check `catalog.traps[]` before writing your own config — only a small subset of the catalog is curated (the upstream README listed 18 of ~436 services when this skill was written; `get_server_info` reports the current state), so an uncurated service needs its plain field list read carefully instead. These two tools only read the calculator's catalog — nothing is created externally yet, so no confirmation is needed to run them.
3. **Sanity-check the reasoning with the `aws-knowledge` MCP server before presenting the plan.** The pricing calculator's field list only tells you what's *configurable* — not whether the billing model is complete or the design choice makes sense. For any non-trivial architectural choice (a managed-service billing model, a commitment strategy, a storage-class lifecycle, a service combination), use `aws___search_documentation`/`aws___read_documentation` against AWS's own current docs rather than relying on training data or the calculator catalog alone. Concretely check for:
   - **Cost components the calculator's service list doesn't model at all.** Confirmed example: EKS Auto Mode charges a per-instance-type management fee on top of standard EC2 pricing, independent of the EC2 purchase option — Savings Plans don't reduce it (verified on AWS's own EKS pricing page when this skill was written; re-check against current docs). The calculator's `awsEks` service has no field for this, and `search_services("EKS Auto Mode")` returns zero results — model the compute as plain EC2 and the estimate silently omits this fee. When a tool gap like this is found, name it explicitly in the assumptions table rather than let the estimate understate the total.
   - **Commitment-vs-workload-shape mismatches.** A Savings Plan or Reserved Instance committed against a bursty/triggered workload pays its steady commitment fee whether or not the capacity is actually used — check whether the requested pricing strategy fits the described usage pattern and say so in the assumptions table if it doesn't.
   - **Storage-class minimums and constraints.** Example: S3 Glacier Flexible Retrieval carries a 90-day minimum storage duration charge — if the design's lifecycle deletes or re-processes objects sooner, an early-deletion fee applies on top of the modeled storage cost. Check this whenever an infrequent-access/archival tier is involved.
   - **Whether the service combination is a genuine, currently-supported pattern** — not just individually-priceable services bolted together.
   Note what you checked and what you found, even "checked X, no issue" — this is due diligence, not just a rescue for services with known gaps.
4. **Write the estimate basis, then plan-and-confirm gate — before any tool that writes to calculator.aws.** First write the basis to a local file (see **Estimate basis artifact** below) so the inputs behind the estimate exist on disk, reviewable and diffable, before anything is built. Then render the planned line items as a markdown table (**Service | Sizing/config | Key assumption**), including anything flagged in step 3, and ask the user to validate it. Revisions the user asks for go into the same file, so the file always matches the plan being confirmed. Wait for an explicit go-ahead ("go", "yes", "looks right", "proceed") before calling `create_estimate`, `add_service`, `build_estimate`, or `export_estimate` — all four create or mutate a real draft estimate on AWS's own service, and revising a wrong assumption after export means the external estimate has already been written, possibly more than once. This is why the workflow is a loop: expect the user's answer to the plan table to send you back to step 1 (a number changes) before you ever touch the external service.
   - **Skip the gate only on an explicit override** — the user says something like "just build it," "skip the review," or "force create" up front. Treat that as a standing instruction for the rest of the current request, not a one-time nod; still show the plan table in your response for the record, just don't wait on it.
5. `create_estimate` once, `add_service` per line item (or `build_estimate` for a one-shot create+add+validate+save on a small estimate). **Add every service in as few `add_service`/`build_estimate` calls as possible — ideally one.** Reusing the same `group` name across two *separate* `add_service` calls has been observed to silently overwrite that group's prior contents instead of merging into it (lost 3 services this way in live testing) — batching avoids the failure mode entirely rather than requiring you to route around it with per-call unique group names.
6. `validate_estimate` and check the result against **Definition of done** below. Not met → **Recovering from a failed validation**, then repeat step 6. Met → step 7.
7. `export_estimate` — **the shareable link is the deliverable.** An estimate that ends with a total and no link isn't done; the number isn't independently verifiable without it. (`build_estimate` already includes this step — don't call `export_estimate` again afterward.)
8. **Second `aws-knowledge` QA pass on the final, as-built estimate — before finalizing the basis file.** Step 3 sanity-checked the *plan*; this checks the estimate that actually got saved, since numbers can shift between planning and build (a revised sizing, a re-add after a validation failure). Re-verify against AWS's own docs: does the final saved config still match the workload it claims to model (e.g. the instance family/pricing-strategy combination actually reflects the described usage), and does every flag raised in step 3 (missing cost components, commitment mismatches, storage-class constraints) still hold against the numbers that ended up in the export? Fold anything found straight into the write-up in step 9 — don't discover a QA finding and then omit it from the doc it was meant to inform.
9. **Finalize the estimate basis file.** Update the file written in step 4: set its status to built, add the `sharable_url`, the validation result and the step 8 findings, and add a row to its history table. Do not create a second file. Leave committing to the user: tell them where the file is and that committing it (before and after the build) gives a changelog of the estimate. Never run `git commit` or `git push` yourself.

### Estimate basis artifact

The basis is the record of what the estimate was built from. It lives in a plain, diffable markdown file so that a change in the inputs shows up as a change in a git diff.

- **Location:** `cost-estimate/<name>.md` at the project root, or wherever the user directs. It is a deliverable, so do not put it in a gitignored scratch directory, and do not overwrite the project's `README.md` or existing docs.
- **One file per estimate, updated in place.** A re-estimate after a change edits the same file, so `git log` and `git diff` on it are the changelog. Add a row to the history table instead of creating `-v2` files.
- **Contents, in this order:**
  1. **Status** — `draft` (written at step 4), `confirmed` (user approved the plan), or `built` (step 9).
  2. **Sources** — the artifacts the inventory came from (Terraform paths, plan or state file, design documents), with a commit hash or file date where known.
  3. **Plan table** — Service | Sizing/config | Key assumption, as confirmed by the user.
  4. **Assumptions table** — Input | Value used | Source (confirmed / best-effort estimate — asked, not available / best-effort estimate — not asked), per **Assumption tracking** below.
  5. **Documentation checks** — what was checked against `aws-knowledge`, including "checked X, no issue", and any cost components the calculator does not model.
  6. **Result** — `sharable_url`, validation verdict and the step 8 findings; empty until status is `built`.
  7. **History** — Date | Status | `sharable_url` | What changed, newest first.

### Definition of done

All of the following, not just the first that passes:

- [ ] The reasoning was sanity-checked against `aws-knowledge` for missing cost components, commitment/workload mismatches, and storage-class constraints, both before the plan was presented (step 3) and again against the final as-built estimate before the basis file is finalized (step 8) — findings noted, not silently absorbed
- [ ] The plan table was shown and confirmed before any write call — unless the user explicitly gave a force-create override
- [ ] Every requested service is present — count matches the step-1 inventory
- [ ] `validate_estimate`'s `lint_verdict` is `"editable"`, with an empty `failures` array on every entry in `lint_services`
- [ ] No `missing_required_fields` left over from any `add_service` response
- [ ] No duplicate rows — each service appears once, unless the design genuinely calls for two separate instances of it (say so in the description field if so)
- [ ] `export_estimate` actually ran and returned a real `sharable_url`
- [ ] Every unconfirmed input is in the assumptions table (below) — none folded silently into the total
- [ ] Every item in **Commonly missed cost lines** (below) was explicitly checked — included, or excluded with a note, never silently absent
- [ ] The estimate basis file was written before the first call that writes to calculator.aws (step 4), and finalized in place with the link and QA findings afterward (step 9) — one file, not a copy
- [ ] The user was told where the basis file is; nothing was committed or pushed on their behalf

### Recovering from a failed validation

The tool's response names the exact problem — read it, don't guess a different config or drop the service:

- **`missing_required_fields: ["fieldName"]`** on an `add_service`/`build_estimate` result → look up `fieldName` in that service's `get_service_fields` response (its `catalog.required[]` entry if curated) and re-add with it included.
- **Duplicate-row warning** on `add_service` ("An entry with service=... already exists... has appended a duplicate row") — confirmed live: re-adding a service that's already in the estimate (even a `partial: true` one missing a required field) does not patch it in place, it appends a second row and inflates the total. Don't try to "fix in place" — call `create_estimate` fresh and re-add every service cleanly.
- **`lint_verdict` not `"editable"`**, or any `lint_services[].failures` non-empty → `validate_estimate`'s `would_be_payload` shows the exact computed config per service; compare it against that service's `catalog.traps[]` for the specific field-shape gotcha (composite fields like RDS's `columnFormIPM` matrix are the usual culprit — the dotted-path shortcut silently produces a $0 estimate instead of an error).

## Assumption tracking — non-negotiable

Every number that wasn't explicitly given (run-hours/month, request volume, storage growth, "24/7" vs. a real usage pattern) goes in a visible table: **Input | Value used | Source**, where Source is one of **confirmed** (the user gave it), **best-effort estimate — asked, not available** (the user was asked and couldn't say, so a reasoned figure was used), or **best-effort estimate — not asked** (only for a genuinely minor line where asking would be noise; use sparingly and say why). Never fold an estimated number into the total silently — an estimate with hidden guesses is a liability in front of a customer or sponsor, not a deliverable.

## Commonly missed cost lines

Check each explicitly before calling an estimate complete: root EBS volume (EC2), data transfer/egress, backup storage, Multi-AZ/HA multiplier, support plan tier, taxes, **EKS Auto Mode's per-instance-type management fee** (confirmed real, not modeled by the calculator's `awsEks` service — see step 3), **S3 Glacier/archival-tier minimum storage duration** (early-deletion fee if the lifecycle removes data sooner).

## Quick reference — the 9 MCP tools

| Tool | Purpose |
|---|---|
| `search_services` | Find AWS services by name/key |
| `get_service_fields` | Field IDs, types, options, catalog gotchas |
| `create_estimate` | Initialize a new estimate |
| `add_service` | Add one service, with validation |
| `validate_estimate` | Dry-run preflight check |
| `build_estimate` | One-shot create + add + validate + save |
| `export_estimate` | Save and return the shareable `calculator.aws` URL |
| `import_estimate` | Load an existing estimate by URL/ID |
| `get_server_info` | Version/capability check |

## Cross-check (optional, higher confidence)

Two independent MCP servers can validate this skill's output beyond the pricing calculator itself — check which tools are available in the session rather than assuming either is connected:

- **`aws-knowledge`** (`aws___search_documentation`/`aws___read_documentation`) — step 3's sanity-check server. Usually available; if it isn't, state plainly that the architectural reasoning wasn't independently checked rather than skipping the step silently.
- **`awslabs.aws-pricing-mcp-server`**, if connected — spot-check any unit rate that looks surprising, or that step 3 flagged as a modeling gap (e.g. confirming the actual EKS Auto Mode management-fee rate for a specific instance type). It queries the live AWS Price List API directly, independent of the Calculator's own catalog.

## Common mistakes

- Treating a remembered/trained rate as current — AWS pricing changes; always resolve it through the tool.
- Skipping `export_estimate` and reporting a total with no link.
- Silently assuming usage volumes to make the estimate look complete — flag them instead.
- Falling back to scraping `aws.amazon.com` pricing pages when the MCP tool isn't loaded, instead of telling the user to restart the session.
- Re-adding a service to patch a validation error instead of starting a fresh `create_estimate` — appends a duplicate row and inflates the total (see **Recovering from a failed validation**).
- Calling the estimate done because `add_service`/`build_estimate` returned `"success": true` — a `partial: true` result or an unresolved lint failure still means not done; check against **Definition of done**, not the first success flag.
- Calling `create_estimate`/`add_service`/`build_estimate`/`export_estimate` before the user has confirmed the plan table — each call writes a real draft to AWS's own service; a wrong assumption caught after export means redoing external writes, not just editing a local file.
- Splitting one logical batch of services across multiple `add_service` calls that reuse the same `group` name — confirmed live: the second call silently overwrote the first call's services in that group rather than merging (3 services vanished from the estimate this way). Batch into as few calls as possible instead of routing around it with unique group names per call.
- Writing the basis only after the estimate is built, or only in the chat reply — the inputs must exist as a file before the build so a changed assumption is visible as a diff, not reconstructed afterward.
- Creating a new basis file per revision, or writing it into a project's `README.md` or existing docs — keep one dedicated file per estimate and update it in place.
