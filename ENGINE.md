# Kairos engine runbook

You are the nightly run of the Kairos engine for the Etsy shop KairosDesignStudioCo (digital products only).
Darren reviews what you make each morning on the Review Queue page. Your job tonight: research, design,
build, check and queue products, and act on his feedback from the last review. Work through the stages in order.
Every stage writes files; nothing important lives only in your head.

Paths below are relative to the repo root (where this file is). Run `./setup.sh` first.

## Hard rules
- Digital products only. Never physical or handmade.
- Never paste or ask for API keys, the Etsy keystring or shared secret. Etsy API calls run on Darren's laptop.
- Never fetch etsy.com pages (Etsy API terms). Research goes through EverBee only.
- Never copy a competitor's art, wording, titles or layouts. Ideas and features are fair game.
- Only OFL fonts from config/engine.json `fonts_allowed`. No Canva Pro or Envato elements inside products.
- No em dashes in anything a buyer reads.
- Nothing reaches the queue without passing Check.
- Keep the main context small: EverBee calls and review coding go to subagents (briefs in prompts/).

## Stage 0. Plan tonight
1. `python3 run.py plan` writes runs/<id>/plan.json: which product types get teardowns, how many new products,
   which fixes from Darren's reviews (max from config `nightly`).
2. Read the plan. If a fix or a reject reason teaches something general ("text too small"), it is already in
   data/learn/style-rules.json via the Feedback stage; briefs read it.

## Stage 1. Teardown (per product type, refreshed every 30 days)
1. `python3 stages/teardown.py plan-a <type>` -> calls-a.json.
2. Subagent(s) with prompts/everbee-caller.md make those calls (split into slices of about 15).
3. `python3 stages/teardown.py collect-a <type>`. If `missing`, have a subagent make just those calls, collect again.
4. Read teardown/relevance.json. Fix any wrong relevant/not-relevant marks (set `"by": "session"`).
5. `plan-b`, subagents make calls-b.json calls, `collect-b`. Shop teardowns (analyze_shop) are optional; they rate-limit.
6. Result: data/types/<type>/evidence.json and a laptop job for competitor photos and descriptions.

## Stage 2. Insights
1. `python3 stages/insights.py prepare <type>` -> coding batches.
2. One subagent per batch with prompts/review-coder.md (they run in parallel).
3. `python3 stages/insights.py reconcile <type>`, read new-themes.json, write insights/aliases.json for duplicates.
4. `python3 stages/insights.py build <type>` -> insights.json.

## Stage 3. Brief (per new product)
1. `python3 stages/brief.py prepare <type>` -> brief-in.json.
2. A fresh subagent with prompts/brief-writer.md writes data/products/<pid>/brief.json and loops on
   `python3 stages/brief.py check <brief>` until it passes. Product ids: p-<type short>-<3 digits>, next free number.

## Stage 4. Build
1. `python3 stages/build.py run <pid>`.
2. If blocked with `needs_module`: implement each module in lines/<line>/gen.py (register with @module, params,
   description), add it to tests/test_planner_gen.py, run `python3 tests/test_planner_gen.py`, then build again.
3. Over the size budget even in lean mode: reduce what the brief asked for (fewer extra page types), note it in
   the brief's waived list, re-check, rebuild.

## Stage 5. Listing and photos
1. Subagent with prompts/listing-writer.md writes data/products/<pid>/listing.json.
2. `python3 stages/photos.py run <pid>`. Look at every photo yourself before moving on.

## Stage 6. Check
1. `python3 stages/check.py tech <pid>` and `python3 stages/check.py clone <pid>`.
2. `python3 stages/check.py coverage-prep <pid>`, then a fresh subagent with prompts/coverage-checker.md
   (it must not be the agent that wrote the brief or built the product).
3. `python3 stages/check.py finish <pid>`. Fails go back to the stage that caused them, up to
   config `check.max_build_retries` times. Still failing: queue it marked "needs help" with the reasons.

## Stage 7. Queue
`python3 stages/queue.py <pid>` prepares the review payload; publish it to the Review Queue artifact
(images as files, product and evidence rows in its database).

## Stage 8. Feedback, laptop results, stats (start of each night, before Stage 1)
1. Review Queue rows to files: ArtifactData `list` collection `reviews` and `products` with
   `out_dir` data/feedback/raw. Then `python3 stages/feedback.py process`.
   Approve (owner) -> laptop publish job. Fix -> fix queue for tonight. Reject -> lessons.
   Read data/learn/reason-tally.json and lessons.jsonl; when a reason repeats, write a plain rule into
   data/learn/style-rules.json (for example "day pages: minimum 13px body text").
2. Laptop results: device_stage_files the laptop's Kairos\jobs\results\*.json (and new competitor photos under
   Kairos\data\types\<type>\photos\). Then `python3 stages/ingest.py results`.
3. New competitor photos: `python3 stages/ingest.py photo-tasks <type>`, one subagent per task with
   prompts/photo-reader.md, then `photo-merge <type>` and rebuild insights. Briefs written after this see real features.
4. Jobs for the laptop (data/jobs/outbox/*.json) go to Kairos\jobs\outbox\ with device_commit_files, and finished
   product files (PDF, photos) go to Kairos\data\products\<pid>\ so the laptop can publish them.

## Stage 9. Morning report
`python3 run.py report` -> what was made, what failed and why, what is waiting for Darren. Send it with
SendUserMessage and put it on the Review Queue page.
