# Knowledge proposals - case1

## Sorted TStringList order depends on the locale collation (rule.md §6)

**Behavior:** a `TStringList` with `Sorted := True` and `CaseSensitive = False` (FPC default) orders by
`AnsiCompareText`, which under `cwstring` upper-cases and calls glibc `strcoll` in the process locale. In
en_US.UTF-8 punctuation is ignored at the first level, so `(UNKNOWN)` sorts after `TAIPEI`, not first.

**Evidence:** legacy uCitySum.pas:44-45,52,56,69; case C01, T_CITY_SUM.csv rows: HSINCHU, KAOHSIUNG, TAICHUNG,
TAINAN, TAIPEI, (UNKNOWN), ZüRICH, 台南. A `TreeMap` with `String.CASE_INSENSITIVE_ORDER` or `java.text.Collator`
(US) puts `(UNKNOWN)` first and differs.

**Sentence to add (rule.md §6, row `TStringList` with `Sorted := True`):** "The order is `AnsiCompareText`: the
legacy run's locale collation of the upper-cased text (glibc en_US.UTF-8 on the testbed, punctuation ignored at the
first level); reproduce it with `DelphiRtl.ansiCompareText`, not with `CASE_INSENSITIVE_ORDER`."
