# Backlog: deferred items to do together

Recorded at the end of Stage 2 so they are not lost while we build Stage 3.

## Stage 2 follow-ups

1. **Evaluation fix (small, do first when we return).** In `engine/evaluation/gold.py`, add a random baseline for "candidate starts within 3 s of the pick" and make it the headline metric. Keep the current coverage recall, labelled as lenient. Reason: on the reference set, coverage recall was 100% for the rules vs 92% for random clips, so it cannot tell them apart; start-within-3 s was 50% vs 32%.
2. **Human review of the reference set.** `gold_promos_art_director_proposed.json` (10 picks) was made by ChatGPT. Review each pick in `data/config/gold_worksheet.md` (keep / adjust / drop, about 10 minutes), then add a sentence to `method` saying it was human-reviewed. Until then, call it an "AI-proposed reference set checked against the screenplay", never a human gold set.
3. **Scripted endings are under-ranked.** Reference picks ending mid-episode ranked about #43 on average; the three ending at an episode's own ending ranked #113, #177 and #214. Check whether the Stage 3 AI judge fixes this before changing any rule weight (10 AI picks are too few to tune on).
4. **Ending cap is redundant at 1.** With 50% max overlap and a 3 s ending zone, two ending clips always overlap at least 85%, so the overlap rule removes the second first. The cap only matters at 0. Decide later: keep as is (document), or change the order of checks.
5. **"Cut before a reply" dominates the cliffhanger score.** 188 of 230 candidates earn it. Revisit with the evaluation fix in place.

## Results to quote in the solution doc

- 16,837 valid windows, 230 candidates, 0 hard-rule failures, byte-identical across runs, about 2 s.
- Reference set (10 AI-proposed picks): all 10 inside the shortlist; 5 of 10 with a candidate starting within 3 s (random: 32%).
