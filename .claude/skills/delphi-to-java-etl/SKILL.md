---
name: delphi-to-java-etl
description: Domain knowledge for migrating small Delphi ETL programs to Java 8. SKILL.md describes the template project (Db connection holder, DataAccess wrapper, BatchRun entry point, old/new table suffix) and how to use it; rule.md holds the mapping rules (structure one to one, infrastructure capabilities and their designated Java targets, types, RTL routines, field access, charset). Use when analyzing, clarifying or converting a Delphi ETL migration.
---

# Delphi → Java ETL

Two things come with this skill:

- `template-project/`: the Java project every migration starts from.
- `rule.md`: the mapping rules, what each Delphi construct becomes in Java (structure, capabilities, tables,
  types, RTL routines, field access and charset). Apply them exactly.

## Template design

Maven, Java 8, JUnit 4.

- `etl.core`, infrastructure, never edited:
  - `Db`: the designated connection: `Db.open(props)`, `Db.current()`, `Db.commit()`, `Db.rollback()`,
    `Db.close()`. It opens one transaction. In the company it wraps the internal Oracle library; here it uses
    JDBC. Only `Db.open` changes between environments.
  - `DataAccess` (query, queryScalar, execute, insertBatch, inTransaction) and its JDBC implementation.
  - `Tables.out(name)`: the single place the old/new suffix (`_NEW`) is applied. Migrated output goes to
    `<TABLE>_NEW`; plain `<TABLE>` is the legacy baseline and is read-only.
  - `Row`, `EtlException`.
- `etl.BatchRun`: the entry point and the only place that opens, commits and closes the database. Its `run`
  method mirrors the legacy driver line by line; a person debugs a batch by setting a breakpoint there.
- `etl.units`: one class per legacy unit, plus `DelphiRtl` for RTL routines (rule.md §1, §5).

## How to use

1. Copy `template-project/` to the target dir; change `groupId`/`artifactId`.
2. Do not edit `etl.core`.
3. Write the unit classes, `DelphiRtl` and `BatchRun.run` by rule.md.
4. Run: `mvn -q package`, then `java -cp target/classes:target/lib/* etl.BatchRun etl.properties`.
5. Tests: open a temporary SQLite database, `Db.setCurrent(new JdbcDataAccess(conn))`, call the unit's method,
   assert on the tables (`DbTest` and `JdbcDataAccessTest` show the pattern).

## Running both programs and capturing their output

The migration tool compares the two programs' output as one CSV per output table (header row, NULL as `\N`
unless stated). How each side is built, run and made to produce those files is decided here.

**Input case.** A folder holding the input database file and every input file the program reads (for the
testbed: `legacy.db` with the input tables, and the Big5 notes file).

**Legacy (testbed).** The Delphi source builds on Linux with Free Pascal: `fpc -Mdelphi -FU<build dir> -FE<build
dir> <program file>` with the build folder under `{tmp}`, never inside the source. The program's usage line (top of
the program file) gives its arguments, typically the database path and the input file paths. It writes its output
tables into the database it was given. Capture them with `python3 {knowledge}/collect_sqlite.py <db> {out}
<TABLE,...>` (the script next to this file).

**Legacy (company).** The real Delphi programs do not run on the migration machine. Two ways to get their output,
chosen per project:

- *Recorded*: run the legacy program once per input case on a test system, export each output table to
  `<TABLE>.csv` with the export script of the test environment, and keep the files in the input case folder under
  `recorded/`. Capture then only copies them: `cp {input}/recorded/*.csv {out}/`. Mark the legacy side as recorded:
  the proof cannot exceed PARTLY PROVEN, because the fresh inputs cannot be run on the legacy.
- *CSV build*: a copy of the legacy program changed only to write each output table to CSV at the end of the run,
  built where Delphi is available. Its run command writes straight into the capture folder.

**New program.** Java 8 (`JAVA_HOME` of a 1.8 JDK; on the testbed machine `/home/linuxbrew/.linuxbrew/opt/openjdk@8`).
Build: `mvn -q -o -f <project>/pom.xml package -DskipTests` (drop `-o` when the local repository lacks a
dependency). Run: `"$JAVA_HOME/bin/java" -cp "<project>/target/classes:<project>/target/lib/*" etl.BatchRun
<case>/etl.properties`, where `etl.properties` sets `jdbc.url` to the case's database, `table.suffix=_NEW`, and
every input file path the legacy took from `ParamStr`. It writes its output to `<TABLE>_NEW` in that database;
capture with `python3 {knowledge}/collect_sqlite.py <db> {out} <TABLE,...> --suffix _NEW`. Tests:
`mvn -q -o -f <project>/pom.xml test` (its exit code is the result).

## Not covered here (ask; unattended defaults in brackets)

Scheduling [run on demand], logging configuration [`java.util.logging` defaults], deployment and packaging
[the template's jar plus `target/lib`].
