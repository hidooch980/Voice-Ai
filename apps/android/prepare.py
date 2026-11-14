#!/usr/bin/env python3
"""Apply the MLH branding and community-subscription overlay to an exact, clean upstream checkout.

WireGuard import compatibility is patched; transport, routing and VPN service stay upstream.
The generated Android application retains upstream's GPL-3.0 license.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / 'upstream.lock.json').read_text())
REPOSITORY = 'https://github.com/hidooch980/MLH-VPN'
WARP_GUIDE = 'https://developers.cloudflare.com/warp-client/get-started/android/'


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f'Upstream source changed: expected one occurrence of {old!r}')
    return text.replace(old, new, 1)


def prepare(root: Path) -> None:
    if git(root, 'rev-parse', 'HEAD') != LOCK['commit']:
        raise ValueError('Wrong upstream commit; use upstream.lock.json')
    if git(root, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Refusing to modify an already modified upstream checkout')
    revision = os.environ.get('GITHUB_SHA') or git(HERE.parents[1], 'rev-parse', 'HEAD')
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Invalid source revision')
    project = root / 'V2rayNG'
    changes: dict[Path, str] = {}
    gradle = project / 'app/build.gradle.kts'
    content = gradle.read_text()
    for old, new in [
        ('applicationId = "com.v2ray.ang"', f'applicationId = "{LOCK["application_id"]}"'),
        ('versionCode = 755', f'versionCode = {LOCK["application_version_code"]}'),
        ('versionName = "2.3.15"', f'versionName = "{LOCK["application_version"]}"'),
        ('compileSdk = 37', f'compileSdk = 37\n    ndkVersion = "{LOCK["ndk"]}"'),
    ]:
        content = replace_once(content, old, new)
    content = content.replace('"v2rayNG_${variant.versionName}', '"MLHVPN_${variant.versionName}')
    changes[gradle] = content

    for flavor, old_name, new_name in [
        ('main', 'v2rayNG', 'MLH VPN'),
        ('fdroid', 'v2rayNG (F-Droid)', 'MLH VPN'),
    ]:
        path = project / f'app/src/{flavor}/res/values/strings.xml'
        changes[path] = replace_once(path.read_text(), f'>{old_name}</string>', f'>{new_name}</string>')

    path = project / 'app/src/main/java/com/v2ray/ang/AppConfig.kt'
    content = path.read_text()
    for old, new in [
        ('const val APP_URL = "$GITHUB_URL/2dust/v2rayNG"', f'const val APP_URL = "{REPOSITORY}/tree/{revision}"'),
        ('const val APP_ISSUES_URL = "$APP_URL/issues"', f'const val APP_ISSUES_URL = "{REPOSITORY}/issues"'),
        ('const val APP_API_URL = "https://api.github.com/repos/2dust/v2rayNG/releases"',
         'const val APP_API_URL = "https://api.github.com/repos/hidooch980/MLH-VPN/releases"'),
        ('const val APP_WIKI_MODE = "$APP_URL/wiki/Mode"',
         'const val APP_WIKI_MODE = "https://github.com/2dust/v2rayNG/wiki/Mode"'),
        ('const val APP_PRIVACY_POLICY = "$GITHUB_RAW_URL/2dust/v2rayNG/master/CR.md"',
         f'const val APP_PRIVACY_POLICY = "{REPOSITORY}/blob/{revision}/apps/android/PRIVACY.md"'),
        ('const val APP_PROMOTION_URL = "aHR0cHM6Ly85LjIzNDQ1Ni54eXovYWJjLmh0bWw="',
         f'const val APP_PROMOTION_URL = "{base64.b64encode(WARP_GUIDE.encode()).decode()}"'),
    ]:
        content = replace_once(content, old, new)
    changes[path] = content

    # Replace the promotional menu with official WARP setup guidance in every locale.
    warp_labels = {
        'values': 'WARP setup', 'values-fa': 'راهنمای WARP',
        'values-ar': 'إعداد WARP', 'values-az': 'WARP quraşdırılması',
        'values-bn': 'WARP সেটআপ', 'values-bqi-rIR': 'راهنمای WARP',
        'values-ru': 'Настройка WARP', 'values-vi': 'Thiết lập WARP',
        'values-zh-rCN': 'WARP 设置', 'values-zh-rTW': 'WARP 設定',
    }
    for locale, label in warp_labels.items():
        path = project / f'app/src/main/res/{locale}/strings.xml'
        content = changes.get(path, path.read_text())
        content, count = re.subn(r'(<string name="title_pref_promotion">).*?(</string>)',
                                lambda match: match[1] + label + match[2], content)
        if count != 1:
            raise ValueError(f'Missing WARP menu resource in {locale}')
        # Keep upstream attribution in licenses, while removing upstream product
        # branding from every user-visible locale.
        content = content.replace('v2rayNG', 'MLH VPN')
        changes[path] = content

    path = project / 'app/src/main/java/com/v2ray/ang/util/HttpUtil.kt'
    changes[path] = replace_once(path.read_text(),
        '"v2rayNG/${BuildConfig.VERSION_NAME}"',
        '"MLHVPN/${BuildConfig.VERSION_NAME}"')
    path = project / 'app/src/main/java/com/v2ray/ang/ui/logcat/LogcatActivity.kt'
    changes[path] = replace_once(path.read_text(),
        '"v2rayNG_logcat_$timestamp.txt"',
        '"MLHVPN_logcat_$timestamp.txt"')

    # Provider-exported WireGuard files can begin with comments (e.g. Proton).
    path = project / 'app/src/main/java/com/v2ray/ang/handler/AngConfigManager.kt'
    content = replace_once(path.read_text(),
        'server.startsWith("[Interface]") && server.contains("[Peer]")',
        'WireguardFmt.isWireguardConfFile(server)')
    changes[path] = replace_once(content, '            LogUtil.i(AppConfig.TAG, url)',
        '            LogUtil.i(AppConfig.TAG, "Updating subscription id=${it.guid}")')

    path = project / 'app/src/main/java/com/v2ray/ang/handler/SubscriptionUpdater.kt'
    content = path.read_text()
    content = replace_once(content,
        '.filter { it.subscription.autoUpdate && it.subscription.url.isNotEmpty() }',
        '.filter { SubscriptionRefreshPolicy.shouldSchedule(it.subscription) }')
    content = replace_once(content, 'if (!subItem.autoUpdate) {',
        'if (!SubscriptionRefreshPolicy.shouldSchedule(subItem)) {')
    content = replace_once(content,
        '            updateLastUpdatedAndReschedule(applicationContext, subId)',
        '            if (!SubscriptionRefreshPolicy.shouldSchedule(MmkvManager.decodeSubscription(subId))) {\n'
        '                cancelOne(applicationContext, subId)\n'
        '                return Result.success()\n'
        '            }\n'
        '            // Only the successful import owns lastUpdated; periodic work already bounds retries.')
    changes[path] = content

    # Seed public sources in the existing lifecycle-owned IO initialization path.
    path = project / 'app/src/main/java/com/v2ray/ang/handler/SettingsManager.kt'
    method = (HERE / 'settings_method.kt.txt').read_text()
    content = replace_once(path.read_text(), '    private fun ensureDefaultSubscription() {',
                                 method + '\n    private fun ensureDefaultSubscription() {')
    content = replace_once(content,
        '        val value = MmkvManager.decodeSettingsString(AppConfig.PREF_REAL_PING_CONCURRENCY)?.toIntOrNull() ?: 16\n'
        '        return value.coerceIn(1, 128)',
        '        return boundedRealPingConcurrency(MmkvManager.decodeSettingsString(AppConfig.PREF_REAL_PING_CONCURRENCY))')
    changes[path] = content
    path = project / 'app/src/main/java/com/v2ray/ang/ui/main/MainRepository.kt'
    changes[path] = replace_once(path.read_text(), '    override fun syncSubscriptions() {',
                                 '    override fun syncSubscriptions() {\n        SettingsManager.ensureCommunitySubscriptions()')
    path = project / 'app/src/main/java/com/v2ray/ang/ui/main/MainViewModel.kt'
    changes[path] = replace_once(path.read_text(), '                dataSource.syncSubscriptions()',
                                 '                dataSource.syncSubscriptions()\n                withContext(Dispatchers.Main) { setupGroupTab() }')

    # Validate all replacements before writing any source file. Keep Kotlin namespace
    # unchanged: the HEV JNI entry points depend on com.v2ray.ang.service.
    for path, content in changes.items():
        path.write_text(content)
    for source in (HERE / 'overlay').rglob('*'):
        if source.is_file():
            target = project / source.relative_to(HERE / 'overlay')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    assets = project / 'app/src/main/assets'
    assets.mkdir(parents=True, exist_ok=True)
    (assets / 'mlh_upstream_license.txt').write_text((root / 'LICENSE').read_text())
    (assets / 'mlh_build.json').write_text(json.dumps(LOCK, indent=2) + '\n')
    print(f'Prepared MLH VPN {LOCK["application_version"]} from v2rayNG {LOCK["version"]}')


def download_core(root: Path) -> None:
    if git(root / 'AndroidLibXrayLite', 'rev-parse', 'HEAD') != LOCK['core_commit']:
        raise ValueError('Unexpected native core source revision')
    if git(root / 'hev-socks5-tunnel', 'rev-parse', 'HEAD') != LOCK['hev_commit']:
        raise ValueError('Unexpected HEV source revision')
    target = root / 'V2rayNG/app/libs/libv2ray.aar'
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == LOCK['core_sha256']:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.download')
    try:
        with urllib.request.urlopen(LOCK['core_url'], timeout=120) as response, temporary.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != LOCK['core_sha256']:
            raise ValueError('Native core checksum mismatch')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def notices(root: Path) -> None:
    """Append original app license after Gradle generates third-party notices."""
    path = root / 'V2rayNG/app/src/main/assets/open_source_licenses.html'
    current = path.read_text() if path.exists() else '<html><body></body></html>'
    marker = '<!-- MLH VPN notices -->'
    if marker in current:
        return
    notice = (marker + '<section><h2>MLH VPN / v2rayNG</h2>'
              '<p>MLH VPN is a modified build of v2rayNG, copyright its contributors. '
              'Branding/build modifications: MLH VPN contributors, 2026-11-13. '
              'Distributed under GNU GPL version 3, WITHOUT ANY WARRANTY. '
              'You may modify and redistribute it under that license.</p>'
              f'<p>Corresponding source and build scripts: {html.escape(REPOSITORY)}. '
              f'Upstream revision: {LOCK["commit"]}.</p><pre>'
              + html.escape((root / 'LICENSE').read_text()) + '</pre></section>')
    path.write_text(current.replace('</body>', notice + '</body>') if '</body>' in current else current + notice)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    parser.add_argument('--download-core', action='store_true')
    parser.add_argument('--notices', action='store_true')
    args = parser.parse_args()
    if args.download_core:
        download_core(args.checkout.resolve())
    elif args.notices:
        notices(args.checkout.resolve())
    else:
        prepare(args.checkout.resolve())
