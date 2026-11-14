package com.v2ray.ang.handler

import com.v2ray.ang.dto.GitHubRelease

/** APK selection is separate from networking so device fallbacks can be tested. */
internal object ReleaseAssetSelector {
    fun shouldCheck(now: Long, last: Long): Boolean = last <= 0 || now < last || now - last >= 86_400_000L

    fun select(release: GitHubRelease, abis: List<String>): String? {
        val version = release.tagName.removePrefix("v")
        if (!Regex("[0-9]+\\.[0-9]+\\.[0-9]+").matches(version)) return null
        val prefix = "https://github.com/hidooch980/MLH-VPN/releases/download/${release.tagName}/"
        for (abi in abis + "universal") {
            if (abi !in setOf("arm64-v8a", "armeabi-v7a", "x86", "x86_64", "universal")) continue
            val name = "MLHVPN_${version}-fdroid_${abi}.apk"
            val asset = release.assets.singleOrNull { it.name == name && it.browserDownloadUrl == prefix + name }
            if (asset != null) return asset.browserDownloadUrl
        }
        return null
    }
}
