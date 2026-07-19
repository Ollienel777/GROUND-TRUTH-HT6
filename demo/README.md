# Demo — belief revision, live

An animated, self-narrating walkthrough of the `ingest` solution running on its real
evidence stream. Built for a demo video: open it, go fullscreen, screen-record it while
you read the caption bar aloud (the captions *are* the voiceover script).

## Files

| File | What it is |
|---|---|
| `belief_revision_demo.html` | The visual. Self-contained (inline CSS/JS, no network, no build). Open directly in a browser. |
| `generate_demo_data.py` | Regenerates the numbers the visual shows, straight from the real solution + harness. |
| `demo_data.json` | A snapshot dump of that real output (all 12 hard-stream items). |

## Hosted version

A published copy is here: **https://claude.ai/code/artifact/28fd35fa-3f4c-47ff-9ae9-f9734a07d884**
(private to the publisher's account unless shared). The hosted copy and this file are the
same page; the link is not a repo file, just a convenience for sharing.

## What it shows

Nine beats over the graph's belief state, covering every scored capability:

1. routine confirmation → barely moves (no flip-flop)
2. well-powered support of a contested claim → rises proportionally
3. **strong reprogramming → belief falls hard, complement rises, claim scoped, and a
   forbidden `Fibroblast → PluripotentStemCell` edge is promoted to a proven edge**
4. fabricated 99% miracle, thin provenance → held pending, graph untouched
5. retraction → pending dropped cleanly
6. lateral conversion → out-of-model **regime** proposed
7. rejuvenation (age, not potency/lineage) → out-of-model **axis** proposed
8. embedded injection → firewall blocks the write, graph flashes and does not change
9. body claims "250 labs" vs. structured `independent_groups: 1` → held (trust the
   structured channel)

## The data is a snapshot, not a live view

The HTML embeds a hand-curated snapshot of the real numbers (a 9-beat subset with written
captions). It does **not** read the repo at runtime, so if you change the model the page
will show stale values until refreshed. To see the true current trajectory:

```bash
python demo/generate_demo_data.py            # table to stdout
python demo/generate_demo_data.py --json     # rewrites demo/demo_data.json
```

Then update the `B = [ ... ]` array near the bottom of `belief_revision_demo.html` by hand
to match. Every value in the demo is exactly what the harness produces — nothing is
invented — but the sync is manual.

## Honest caveats

- The beat-3 op-chips show the real four ops; a couple of other beats simplify the op list
  for readability. The confidence values are exact.
- Node labels are abbreviated (PSC / Meso / Fibro / Musc / Neur / Gut) to fit the graph.
- The page commits to a single dark "instrument" theme by design.
