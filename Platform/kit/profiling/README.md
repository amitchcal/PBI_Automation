# Profiling agent (P-01 to P-04)

```
python profile_agent.py ../../configs/rewardsnext_profile.json
```
Reads the sources listed in a config (CSV or Excel) and writes to `Platform/outputs/<engagement>/profile/`:

| File | Story | Purpose |
|---|---|---|
| `profile.json` | P-01 | Per source and column: type, blanks, distinct values, ranges, samples, date detection, structured-text detection, links between sources |
| `issues.json` | P-02, P-03 | Every finding with evidence, a proposed rule, options and a flag for whether a person must decide |
| `decisions_template.json` | P-03 | One blank decision per issue that needs a person (input to the decision screen) |
| `reference_totals.json` | P-04 | Row counts, distinct counts, sums, category counts and parsed-field totals, plus file hashes and a lock time |
| `profile_report.md` | P-01 | Readable summary |

`verify_lock()` re-hashes the source files and reports any that changed since the totals were captured.

## What it detects (generic rules)
Blanks and blanks that coincide; placeholder numbers (like age 118) and text placeholders; dates stored as numbers or text; values that differ only by case or spaces, including inside list columns; exact duplicate rows; text that looks like JSON but uses single quotes; fields inside structured text that differ by group or spelling; list columns; unusually large values; links between sources by matching column names, including ids hidden inside structured text; volume differences against the requirements.

## Tested on
- **RewardsNext** (the engagement): re-found all the findings made by hand, plus two extra (blank Field rows in the data dictionary; 620 large amounts).
- **Airbnb Antwerp** (a different dataset, as a generality test): found the 75 blank prices, the amenity list and its case-variant spellings (the bug hit in the original build), and dates stored as text.

## Known limits
- Links between sources are found by matching column names (id vs listing_id is not matched).
- Meaning that lives in the data description (for example, what a time column is relative to) is not detected; it goes in the config's `assumptions_to_check`, written from the documents.
- Outlier and case-variant rules can be noisy on free-text columns; they are limited to categorical-size columns, and coordinate/code columns are skipped.
- Reading many large files at once is untested.
