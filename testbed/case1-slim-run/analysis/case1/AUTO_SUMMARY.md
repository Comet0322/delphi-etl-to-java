# Auto summary — case1

This is a **draft**: decisions below were assumed, nothing was approved by a person.

## Result

- Gate OVERALL: **DONE**
- Proof pack verdict: **PROVEN**
  - passed (java): Tests ran: 27 test(s) executed, 0 failed, 0 skipped.
  - passed (java): Rules traced: All 4 P0 rule(s) this module answers for are backed by a test that ran and passed.
  - passed (java): Same behavior: 3 of 3 development case(s) executed: 3 same, 0 differ, 0 missing; comparator self-check passed.
  - passed (java): Fresh inputs: 13 new input(s), 39 comparison(s), ran on the legacy and the new code with no difference.
  - passed (java): Canary: 1 canary run(s) shown by a result file or log; the first (DelphiRtl.round(BigDecimal) RoundingMode.HALF_EVEN -> HALF_UP (DelphiRtl.java:32), scratch copy outside modernized/; ran OrdersTest, DelphiRtlTest, CitySumTest) made 1 more test(s) fail than the clean run (analysis/case1/equivalence/canary/java).
  - passed (java): Source untouched: legacy/case1 is untouched: no file changed after the analysis started (5 files compared). Checked by modification time, and no version-control tool was run.

| ETL | Gate state | Diffs | Fix rounds | Stage |
|---|---|---|---|---|
| ETL-001 | EQUIVALENT | 0 | 0 | built |
| ETL-002 | EQUIVALENT | 0 | 0 | built |
| ETL-003 | EQUIVALENT | 0 | 0 | built |

| Stage | Start | End | Check |
|---|---|---|---|
| analyze | 19:34 | 19:40 | PASS |
| transform | 19:40 | 19:47 | PASS |
| verify | 19:47 | 19:52 | PASS |

## Blocked

None.

## Assumed decisions (4 of 7)

| Id | Stage | Question | Decision | Source | Affects |
|---|---|---|---|---|---|
| D-003 | analyze | TStringList semantics (Values[k] := '' deletes key; sorted list case-insensitive in FPC) | reproduce with TreeMap/LinkedHashMap: empty value removes the key; city bucket comparison case-insensitive as FPC default CaseSensitive=False; verified by dual run | assumed | ETL-001, ETL-003 |
| D-004 | analyze | Input domain line | database text UTF-8, dates TDateTime between 0 and about 2958465, quantities/prices within Integer/Currency ranges, notes file lines in Big5 as the producer writes; absurd magnitudes and invalid encodings not tested | assumed | ETL-001, ETL-002 |
| D-006 | transform | Sorted TStringList (CaseSensitive False) order: FPC AnsiCompareText under cwstring = AnsiUpperCase + glibc strcoll in the run locale (en_US.UTF-8); C01 shows '(UNKNOWN)' between TAIPEI and ZüRICH. JNI/ICU not allowed | DelphiRtl.ansiCompareText emulates it with the JDK: letters/digits only at Collator(US) PRIMARY, then TERTIARY, then code point of the upper-cased text; equal only for equal AnsiUpperCase text. Exact glibc tie-breaks for punctuation-only differences are outside what C01 shows | assumed | ETL-003 |
| D-007 | transform | `Amt - Amt * Disc / 100` with '/' on Currency: FPC may evaluate in extended float | computed exactly in BigDecimal, rounded half-even to scale 4 at the assignment; C01 (433 rows) matches; fresh rounding ties will confirm | assumed | ETL-002 |

## Audit findings (10)

- **high** wrong rule link at uOrders.pas:48-51: OP-03 (Qty*Price minus discount, the central calculation) lists rules [RULE-001], which is the Big5 notes rule of ETL-001. RULE-003 (P0, uOrders.pas:48-55) is linked to no op, so the P0 rule has no operation and tests named after RULE-003 cannot be traced.
- **high** wrong rule link at uOrders.pas:15-26,55: OP-05 (CentsToStr(Round(Amt*100)) text) lists rules [RULE-001] (notes file); it implements the two-decimal text part of RULE-003.
- **high** wrong rule link at uOrders.pas:52: OP-04 (status S/N, discount > 10) lists [RULE-003]; the status rule is RULE-004. RULE-004 is linked to no op.
- **low** missing implicit at uOrders.pas:51: OP-03 implicit says scale 4 HALF_EVEN after every operation but not that Amt*Disc/100 mixes Currency with Integer and the '/' operator: rule.md §4 makes '/' a double division while the legacy statement is assigned to a Currency. Whether FPC divides as Currency (truncating or rounding at 4 decimals) or as float then converts decides the 4th decimal, which Round(Amt*100) can expose on ties.
- **low** missing implicit at uCitySum.pas:44-45,52: OP-02 names case-insensitive comparison but not (a) which spelling is kept as the stored key when two spellings merge (the first one seen, in T_ORDER_AMT order) nor (b) that the sort order is the TStringList compare, not Java natural order. C01 has non-ASCII cities ('ZüRICH', '台南') and UpperCase is ASCII only, so 'zürich'/'ZÜRICH' would merge under AnsiCompareText. OP-04 implicit 'city order of the sorted list' is not actionable.
- **low** missing work at LegacyEtl.pas:24: GSkipVoid := True in FormCreate is in no op and not in MAPPING driver; ETL-002 OP-02 only mentions it in implicit.
- **low** missing work at LegacyEtl.pas:39: DefaultSystemCodePage := CP_UTF8 is in no op and no mapping; it decides that SetCodePage(Note, CP_UTF8, True) in uCustomer.pas:34 gives UTF-8 and that string field values are UTF-8.
- **low** wrong classification at uCommon.pas:11: GTrans (a transaction holder) is mapped to capability db.transaction (action keep, Db.current().inTransaction); rule.md §2 says a global that only holds a connection or transaction disappears.
- **low** imprecise source_loc at uCustomer.pas:55-62: OP-07 and OP-09 both list writes T_CUST_CLEAN.CUST_ID/NAME/CITY, so trace_diff cannot tell the computing op (OP-07) from the writing op (OP-09); OP-09 reads [] although it reads the notes map. Also the notes-map call at uCustomer.pas:52 and RunCitySum/RunOrderAmount call order are in no op.
- **low** imprecise source_loc at uOrders.pas:15-26: RULE-003 (P0) Source uOrders.pas:48-55 does not include CentsToStr (uOrders.pas:15-26), which implements the 'two decimals text, negative sign' part of the rule.

## For a person to do

1. Review the assumed decisions below, above all the input domain; change INTENT.md or the domain knowledge where one is wrong and run modernize-auto again.
2. Review the P0 rules in BUSINESS_RULES.md.
3. Accept or reject each remaining difference (`approvedDifference` in the cases files). This run never does.
4. Sign VERIFICATION.md.
5. Merge knowledge-proposals.md into the domain knowledge (rule.md).

## What this does not prove

- It does not prove behavior on inputs nobody tried: the equivalence cases and the fresh inputs are samples, not the whole input space.
- It does not cover speed, capacity, security, concurrency, or anything the tests and cases do not exercise.
- It traces only the rules that were extracted: behavior nobody wrote down as a rule has no rule to trace.
- A test that names a rule shows the rule is mentioned, not that the test is a good one. The canary shows only that some test can fail.
- It does not replace the review and sign-off of the people who own the system.

## Knowledge proposals

1 proposal(s) in `knowledge-proposals.md`.

Report: `REPORT.html`. Proof: `VERIFICATION.md`. Traces of differences: `equivalence/TRACE.md`.
