#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p app/build/address-tests
if [[ -n "${ECJ_JAR:-}" ]]; then
  java -jar "$ECJ_JAR" -8 -proc:none -d app/build/address-tests \
    app/src/main/java/com/nexvant/engineering/ServerAddress.java tests/ServerAddressTest.java
else
  javac -source 8 -target 8 -d app/build/address-tests \
    app/src/main/java/com/nexvant/engineering/ServerAddress.java tests/ServerAddressTest.java
fi
java -cp app/build/address-tests com.nexvant.engineering.ServerAddressTest
