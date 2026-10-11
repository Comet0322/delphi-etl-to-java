#!/usr/bin/env bash
# Build the migrated project and run all jobs against the configured database.
set -euo pipefail
cd "$(dirname "$0")"
export JAVA_HOME=/home/linuxbrew/.linuxbrew/opt/openjdk@8
(cd target-project && mvn -q -o package -DskipTests 2>&1 | tail -20)
$JAVA_HOME/bin/java -cp "target-project/target/classes:target-project/target/lib/*" \
  etl.core.EtlRunner target-project/etl.properties
