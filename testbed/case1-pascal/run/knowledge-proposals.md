# Knowledge proposals (case 1)

Proposed additions for `delphi-to-java-etl` (`rule.md` / `SKILL.md`). Nothing
here has been merged. Only items proven by comparison are listed.

## Proposed for rule.md

| Proposed rule | Evidence |
|---|---|
| `UpperCase` converts ASCII letters only; `zürich` → `ZüRICH`. Java `toUpperCase()` is wrong here. | ETL-001/OP-04; naive variant produced diff on CUST_ID 103 (mutation test), correct variant: run-001, 0 diffs |
| `Trim` removes leading and trailing characters <= #32; CHAR(n) padding is not the only whitespace (leading spaces exist). Right-trim alone is wrong. | ETL-001/OP-03; naive variant produced diff on CUST_ID 102 (mutation test), run-001, 0 diffs |
| `Round(Amt * 100)` on a Currency amount is half-to-even; `HALF_UP` differs on exact half-cent amounts (e.g. 0.125 × qty). | ETL-002/OP-04; naive variant produced 18 diffs (mutation test), run-002, 0 diffs |
| Double → Currency conversion: scale by 10000 and round half to even (`Math.rint(d * 10000)`), then compute in fixed point. | ETL-002/OP-03; run-002, 0 diffs on 433 rows |
| Big5 fixed-width notes: decode bytes with `MS950`, right-trim chars <= #32. | ETL-001/OP-01; run-001, 0 diffs (includes Chinese notes) |

## Proposed for SKILL.md (feature → handling table)

| You see | Do | Evidence |
|---|---|---|
| Global flag assigned in a form event (`GSkipVoid` in `FormCreate`) | Implement as a named constant in the job with a comment citing the legacy location | ETL-002/OP-02, run-002 |

## Not proposed (unverified)

- `TStringList.Sorted` treating keys case-insensitively: the Java uses a
  case-insensitive map and matches, but no data row exercises two keys that
  differ only in case, so the comparison cannot confirm it.

## Open items for the user (assumed decisions)

| Decision | Assumed | Affects |
|---|---|---|
| How a job receives the notes file path | job constructor; `EtlRunner` reads `notes.file` from `etl.properties` | ETL-001/OP-01 |
