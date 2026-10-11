# Verification: case1

Written by `scripts/proof_pack.py` on 2026-10-11 11:49 UTC. Each module's verdict is computed from the evidence files by the fixed rules at the end of this page. No model's opinion is part of it.

**Overall: PROVEN** (1 proven)


You asked about `java`. Every built module is judged from its current evidence files on every run, so no verdict here depends on an earlier run.

Legacy source: `legacy/case1` (a link to `/tmp/claude-1000/-mnt-a0df7f69-337a-4cb4-a10a-f48243e3ddfc-Code-CodeMigration2/ef7f9c1b-0600-4386-8caa-a102b43a32a7/scratchpad/case1-cm/_given/src`). Could it run here: yes. The source was checked by modification time, and no version-control tool was run.

| Module | Track | Verdict | Tests executed | Failed | P0 rules tested | Same behavior | Fresh inputs |
|---|---|---|---|---|---|---|---|
| java | rewrite | **PROVEN** | 27 | 0 | 4 of 4 | pass | pass |

## java: PROVEN

Track: rewrite. Folder: `modernized/case1/java`. Checked 2026-10-11 11:49 UTC.

**What passed**

- Tests ran: 27 test(s) executed, 0 failed, 0 skipped.
- Rules traced: All 4 P0 rule(s) this module answers for are backed by a test that ran and passed.
- Same behavior: 3 of 3 development case(s) executed: 3 same, 0 differ, 0 missing; comparator self-check passed.
- Fresh inputs: 13 new input(s), 39 comparison(s), ran on the legacy and the new code with no difference.
- Canary: 1 canary run(s) shown by a result file or log; the first (DelphiRtl.round(BigDecimal) RoundingMode.HALF_EVEN -> HALF_UP (DelphiRtl.java:32), scratch copy outside modernized/; ran OrdersTest, DelphiRtlTest, CitySumTest) made 1 more test(s) fail than the clean run (analysis/case1/equivalence/canary/java).
- Source untouched: legacy/case1 is untouched: no file changed after the analysis started (5 files compared). Checked by modification time, and no version-control tool was run.

| Check | Result | Detail |
|---|---|---|
| Tests ran | pass | 27 test(s) executed, 0 failed, 0 skipped. |
| Rules traced | pass | All 4 P0 rule(s) this module answers for are backed by a test that ran and passed. |
| Same behavior | pass | 3 of 3 development case(s) executed: 3 same, 0 differ, 0 missing; comparator self-check passed. |
| Fresh inputs | pass | 13 new input(s), 39 comparison(s), ran on the legacy and the new code with no difference. |
| Canary | pass | 1 canary run(s) shown by a result file or log; the first (DelphiRtl.round(BigDecimal) RoundingMode.HALF_EVEN -> HALF_UP (DelphiRtl.java:32), scratch copy outside modernized/; ran OrdersTest, DelphiRtlTest, CitySumTest) made 1 more test(s) fail than the clean run (analysis/case1/equivalence/canary/java). |
| Source untouched | pass | legacy/case1 is untouched: no file changed after the analysis started (5 files compared). Checked by modification time, and no version-control tool was run. |

tests executed: 27, failed 0, skipped 0

- unit tests: `mvn -q -o -f modernized/case1/java/pom.xml clean test -Dmaven.test.failure.ignore=true (JAVA_HOME=/home/linuxbrew/.linuxbrew/opt/openjdk@8, target/ deleted first)` (from result files): 27 executed, 0 failed, 0 skipped, 6 result files written 2026-10-11 11:46 UTC

### P0 business rules

| Rule | Name | Confidence | Result | Tests | Code | A test that names it |
|---|---|---|---|---|---|---|
| RULE-001 | Notes attached to customers from the Big5 file | High | tested | 5 | 0 | `modernized/case1/java/src/test/java/etl/units/CustomerTest.java:58` |
| RULE-002 | Zero-quantity orders are voided | High | tested | 2 | 0 | `modernized/case1/java/src/test/java/etl/units/OrdersTest.java:42` |
| RULE-003 | Payable order amount | High | tested | 1 | 0 | `modernized/case1/java/src/test/java/etl/units/OrdersTest.java:59` |
| RULE-007 | Order count and total per city | High | tested | 1 | 0 | `modernized/case1/java/src/test/java/etl/units/CitySumTest.java:42` |

### Development cases, judged again

3 of 3 executed: 3 same, 0 differ, 0 missing.

Inputs left out of the fresh check: No fresh input was refused by the legacy; all 13 (F01-F13) ran on both sides.; F04: all outputs are header-only (empty tables), so it does not count toward the 10 distinct non-empty inputs.; Outside the input domain (DECISIONS D-004), not tried: TDateTime outside 0..2958465, amounts where Qty*Price*100 overflows Currency, DISCOUNT_PCT outside 0..100, prices with more than 4 decimals, not…

### Fresh inputs

13 new input(s) counted from 39 comparison(s) executed: 39 same, 0 differ, 0 missing.

### Waiting for a person

Claude never ticks these. A person decides them.

- No MODERNIZATION_BRIEF.md was found, so no criterion could be listed.

### What this does not prove

- It does not prove behavior on inputs nobody tried: the equivalence cases and the fresh inputs are samples, not the whole input space.
- It does not cover speed, capacity, security, concurrency, or anything the tests and cases do not exercise.
- It traces only the rules that were extracted: behavior nobody wrote down as a rule has no rule to trace.
- A test that names a rule shows the rule is mentioned, not that the test is a good one. The canary shows only that some test can fail.
- It does not replace the review and sign-off of the people who own the system.

## Sign-off

A person fills this in. Claude leaves it blank.

| | |
|---|---|
| Name | ________________ |
| Role | ________________ |
| Date | __________ |
| Decision | accept / accept with conditions / reject |

## How each verdict is computed

PROVEN needs every check to pass: the six below, and for an uplift three more (7 to 9). NOT PROVEN when any check fails. PARTLY PROVEN when nothing failed but a check could not pass.

1. Tests ran: at least one test executed in a fresh run, none failed, none was skipped without a reason, and every result file is newer than the code. The counts must be read by this script from result files or a saved raw runner log; counts only typed in cannot reach PROVEN.
2. Rules traced (rewrite and reimagine): every P0 rule the module answers for is backed by a test that ran and passed: its id is in the test or class name of a result this script parsed, or a test file names it on a line not marked skipped or pending and that file's class ran and passed. A rule named only by skipped, pending or failing tests is named, not run; one only the notes name is claimed. Neither is tested.
3. Same behavior: the development cases, judged again by compare.py, executed at least one case and none differs or is missing (a difference a person approved is allowed and listed); for an uplift, no regression, no new failure, no missing test and no drop in executed tests against BASELINE.md.
4. Fresh inputs: at least 10 new inputs, none with the same output as a development case, ran on the legacy and the new code with no difference. Needed whenever the legacy could run here; when it could not, the proof is trace-based and the best verdict is PARTLY PROVEN.
5. Canary: a deliberate one-line break whose own result file or saved runner log shows failing tests. A line in the notes is a claim.
6. Source untouched: no file under legacy/<system> is newer than the analysis (PREFLIGHT.md), by a plain file walk; no version-control tool is run.
7. Baseline measured (uplift): the old version's numbers in BASELINE.md come from per-test result files, a per-test results file or a raw runner log that this script parsed (in analysis/<system>/baseline/, or on a Recorded: or Machine-readable: line of BASELINE.md), and the typed table agrees with them. A table typed by hand, or sources that disagree, cannot reach PROVEN.
8. Tests kept (uplift): no test file of the untouched legacy tree is missing from the working copy, no more than 25% of them changed, and the legacy tree has test files to compare against (walked by file, no process is run). The list is for a person to review; weakened assertions cannot be detected, only that files changed.
9. Deltas covered (uplift): every Behavioral-silent delta in DELTA_CATALOG.md has its site's file named, as a whole word, by some test file of the working copy. A name is not proof that the test exercises the change.
Open questions, unticked criteria and the sign-off are for a person. They never change the verdict.
A folder that holds only test code and the files that build it is test tooling: it is listed, not judged, and not counted.
