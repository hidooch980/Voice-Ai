#!/usr/bin/env bash
set -euo pipefail
checkout="${1:?prepared checkout required}"
tools="$ANDROID_HOME/build-tools/37.0.0"
mkdir -p unsigned
for abi in universal arm64-v8a armeabi-v7a; do
  mapfile -t files < <(find "$checkout/V2rayNG/app/build/outputs/apk/fdroid/release" -name "*_${abi}.apk")
  test "${#files[@]}" -eq 1
  "$tools/zipalign" -f -P 16 4 "${files[0]}" "unsigned/$(basename "${files[0]}")"
done
# Strip debug test signatures by rebuilding ZIP entries, then align before local signing.
python3 - "$checkout" <<'PY'
from pathlib import Path
import sys, zipfile
files = list(Path(sys.argv[1]).glob('V2rayNG/app/build/outputs/apk/androidTest/fdroid/debug/*.apk'))
assert len(files) == 1
with zipfile.ZipFile(files[0]) as source, zipfile.ZipFile('unsigned/test-unaligned.apk', 'w') as target:
    for item in source.infolist():
        name = item.filename.upper()
        if name.startswith('META-INF/') and (name.endswith(('.RSA','.DSA','.EC','.SF')) or name == 'META-INF/MANIFEST.MF'):
            continue
        target.writestr(item, source.read(item))
PY
"$tools/zipalign" -f -P 16 4 unsigned/test-unaligned.apk unsigned/MLHVPN-androidTest.apk
rm unsigned/test-unaligned.apk
