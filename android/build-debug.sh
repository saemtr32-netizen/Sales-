#!/usr/bin/env bash
# Reproducible SDK-tool build; no Gradle or third-party app libraries required.
set -euo pipefail
cd "$(dirname "$0")"
: "${ANDROID_HOME:?Set ANDROID_HOME to an installed Android SDK (platform 35, build-tools 35.0.0)}"
platform="$ANDROID_HOME/platforms/android-35/android.jar"
tools="${ANDROID_BUILD_TOOLS:-$ANDROID_HOME/build-tools/35.0.0}"
test -f "$platform"
test -x "$tools/aapt2"
test -x "$tools/d8"
test -x "$tools/apksigner"
build="app/build/manual-debug"
output="app/build/outputs/apk/debug"
mkdir -p "$build/classes" "$build/dex" "$output" .debug
rm -f "$build/resources.zip" "$build/unsigned.apk" "$build/classes.jar" "$build/dex/classes.dex"
find "$build/classes" -type f -name '*.class' -delete

"$tools/aapt2" compile --dir app/src/main/res -o "$build/resources.zip"
python3 - "$build" <<'PY'
import sys, xml.etree.ElementTree as ET
from pathlib import Path
ET.register_namespace('android', 'http://schemas.android.com/apk/res/android')
manifest = ET.parse('app/src/main/AndroidManifest.xml')
manifest.getroot().set('package', 'com.nexvant.engineering')
manifest.write(Path(sys.argv[1]) / 'AndroidManifest.xml', encoding='utf-8', xml_declaration=True)
PY
"$tools/aapt2" link -I "$platform" --manifest "$build/AndroidManifest.xml" \
  --min-sdk-version 26 --target-sdk-version 35 --version-code 1 --version-name 1.0 \
  --debug-mode -o "$build/unsigned.apk" "$build/resources.zip"

# ECJ_JAR is an optional locally verified Eclipse compiler, useful on JRE-only machines.
if [[ -n "${ECJ_JAR:-}" ]]; then
  java -jar "$ECJ_JAR" -8 -proc:none \
    -bootclasspath "$platform:$tools/core-lambda-stubs.jar" \
    -d "$build/classes" app/src/main/java/com/nexvant/engineering/*.java
else
  javac -source 8 -target 8 -bootclasspath "$platform:$tools/core-lambda-stubs.jar" \
    -d "$build/classes" app/src/main/java/com/nexvant/engineering/*.java
fi
python3 - "$build" <<'PY'
import sys, zipfile
from pathlib import Path
build = Path(sys.argv[1])
with zipfile.ZipFile(build / 'classes.jar', 'w', zipfile.ZIP_DEFLATED) as out:
    for path in sorted((build / 'classes').rglob('*.class')):
        out.write(path, path.relative_to(build / 'classes').as_posix())
PY
"$tools/d8" --lib "$platform" --min-api 26 --output "$build/dex" "$build/classes.jar"
python3 - "$build" <<'PY'
import sys, zipfile
from pathlib import Path
build = Path(sys.argv[1])
with zipfile.ZipFile(build / 'unsigned.apk', 'a', zipfile.ZIP_DEFLATED) as out:
    for path in sorted((build / 'dex').glob('*.dex')):
        out.write(path, path.name)
PY
"$tools/zipalign" -f -p 4 "$build/unsigned.apk" "$build/aligned.apk"
if [[ ! -f .debug/debug.keystore ]]; then
  keytool -genkeypair -keystore .debug/debug.keystore -storepass android -keypass android \
    -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 \
    -dname 'CN=Nexvant Debug, O=Nexvant Engineering, C=IN'
fi
"$tools/apksigner" sign --ks .debug/debug.keystore --ks-pass pass:android --key-pass pass:android \
  --out "$output/nexvant-debug.apk" "$build/aligned.apk"
"$tools/apksigner" verify --verbose "$output/nexvant-debug.apk"
printf '\nAPK: %s/%s/nexvant-debug.apk\n' "$PWD" "$output"
