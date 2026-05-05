package dev.viper.idea

import com.intellij.ide.BrowserUtil
import com.intellij.ide.plugins.PluginManagerCore
import com.intellij.ide.plugins.PluginNode
import com.intellij.notification.NotificationAction
import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.PathManager
import com.intellij.openapi.components.service
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.extensions.PluginId
import com.intellij.openapi.progress.EmptyProgressIndicator
import com.intellij.openapi.project.Project
import com.intellij.openapi.startup.StartupActivity
import com.intellij.openapi.updateSettings.impl.PluginDownloader
import com.intellij.util.text.VersionComparatorUtil
import org.json.JSONArray
import java.io.IOException
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.time.Duration
import java.time.OffsetDateTime
import java.util.Comparator
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.zip.ZipInputStream
import kotlin.io.path.absolutePathString
import kotlin.io.path.createDirectories
import kotlin.io.path.deleteIfExists
import kotlin.io.path.exists
import kotlin.io.path.inputStream
import kotlin.io.path.name

class ViperStartupActivity : StartupActivity {
    override fun runActivity(project: Project) {
        if (!started.compareAndSet(false, true)) {
            return
        }

        ApplicationManager.getApplication().executeOnPooledThread {
            val stateService = service<ViperRuntimeStateService>()
            val notifier = ViperNotifier(project)

            runCatching {
                val runtimeManager = ViperRuntimeManager(stateService, notifier)
                runtimeManager.syncLatestRuntime()
                runtimeManager.checkPythonSupport()
            }.onFailure { error ->
                LOG.warn("Failed to sync Viper runtime", error)
                notifier.warn("Failed to sync the Viper runtime: ${error.message ?: "unknown error"}")
            }

            runCatching {
                val updater = ViperPluginUpdater(stateService, notifier)
                updater.syncPluginUpdate()
            }.onFailure { error ->
                LOG.warn("Failed to check Viper plugin updates", error)
                notifier.warn("Failed to check for Viper plugin updates: ${error.message ?: "unknown error"}")
            }
        }
    }

    companion object {
        private val LOG = Logger.getInstance(ViperStartupActivity::class.java)
        private val started = AtomicBoolean(false)
    }
}

private class ViperRuntimeManager(
    private val stateService: ViperRuntimeStateService,
    private val notifier: ViperNotifier,
) {
    fun syncLatestRuntime() {
        val latestRelease = ViperGitHubReleaseClient.fetchReleases()
            .asSequence()
            .filterNot { it.prerelease }
            .filterNot { it.tagName.startsWith(PLUGIN_RELEASE_PREFIX) }
            .maxWithOrNull(compareBy<ViperRelease> { it.versionForComparison() }.thenBy { it.publishedAt })
            ?: return

        val installRoot = runtimeRoot()
        val targetDir = installRoot.resolve(latestRelease.tagName)
        val compilerTarget = targetDir.resolve(COMPILER_TARGET_NAME)
        val interpreterTarget = targetDir.resolve(INTERPRETER_TARGET_NAME)

        val installedVersion = stateService.state.runtimeVersion
        if (
            installedVersion == latestRelease.tagName &&
            compilerTarget.exists() &&
            interpreterTarget.exists()
        ) {
            return
        }

        installRoot.createDirectories()
        val tempZip = Files.createTempFile("viper-runtime-", ".zip")
        val stagingDir = Files.createTempDirectory("viper-runtime-unpack-")

        try {
            ViperGitHubReleaseClient.downloadTo(latestRelease.zipballUrl, tempZip)
            unzip(tempZip, stagingDir)

            val compilerSource = stagingDir.findRelative(COMPILER_SOURCE_PATH)
                ?: error("Compiler entrypoint not found in release ${latestRelease.tagName}")
            val interpreterSource = stagingDir.findRelative(INTERPRETER_SOURCE_PATH)
                ?: error("Interpreter entrypoint not found in release ${latestRelease.tagName}")

            Files.createDirectories(targetDir)
            Files.copy(compilerSource, compilerTarget, StandardCopyOption.REPLACE_EXISTING)
            Files.copy(interpreterSource, interpreterTarget, StandardCopyOption.REPLACE_EXISTING)

            stateService.state.runtimeVersion = latestRelease.tagName
            stateService.state.runtimeInstallDir = targetDir.absolutePathString()

            notifier.info("Updated Viper compiler/interpreter to ${latestRelease.tagName}.")
        } finally {
            tempZip.deleteIfExists()
            stagingDir.deleteRecursivelyIfExists()
        }
    }

    fun checkPythonSupport() {
        val python = ViperPythonSupport.detect()
        if (python == null) {
            notifier.warn(
                "Python was not found in PATH. Viper compiler/interpreter support needs Python 3.",
                NotificationAction.createSimple("Open Python Downloads") {
                    BrowserUtil.browse("https://www.python.org/downloads/")
                },
            )
            return
        }

        if (ViperPythonSupport.hasLark(python)) {
            return
        }

        notifier.warn(
            "Python is available (${python.displayName}), but the 'lark' package is missing.",
            NotificationAction.createSimple("Install lark") {
                ApplicationManager.getApplication().executeOnPooledThread {
                    val success = ViperPythonSupport.installLark(python)
                    if (success) {
                        notifier.info("Installed 'lark' for ${python.displayName}.")
                    } else {
                        notifier.warn("Failed to install 'lark'. Run `${python.installCommand()}` in a terminal.")
                    }
                }
            },
        )
    }

    private fun runtimeRoot(): Path =
        Path.of(PathManager.getSystemPath(), "viper-language-support", "runtime")

    companion object {
        private const val COMPILER_SOURCE_PATH = "Viper_compiler/main.py"
        private const val INTERPRETER_SOURCE_PATH = "Viper_interpreter/Viper/main.py"
        private const val COMPILER_TARGET_NAME = "compiler.py"
        private const val INTERPRETER_TARGET_NAME = "interpreter.py"
    }
}

private class ViperPluginUpdater(
    private val stateService: ViperRuntimeStateService,
    private val notifier: ViperNotifier,
) {
    private val log = Logger.getInstance(ViperPluginUpdater::class.java)

    fun syncPluginUpdate() {
        val pluginId = PluginId.getId(PLUGIN_ID)
        val currentDescriptor = PluginManagerCore.getPlugin(pluginId) ?: return
        val currentVersion = currentDescriptor.version ?: return

        val preparedVersion = stateService.state.preparedPluginVersion
        if (preparedVersion != null && VersionComparatorUtil.compare(currentVersion, preparedVersion) >= 0) {
            stateService.state.preparedPluginVersion = null
        }

        val latestPluginRelease = ViperGitHubReleaseClient.fetchReleases()
            .asSequence()
            .filterNot { it.prerelease }
            .filter { it.tagName.startsWith(PLUGIN_RELEASE_PREFIX) }
            .maxWithOrNull(compareBy<ViperRelease> { it.versionForComparison() }.thenBy { it.publishedAt })
            ?: return

        val releaseVersion = latestPluginRelease.tagName.removePrefix(PLUGIN_RELEASE_PREFIX)
        if (VersionComparatorUtil.compare(releaseVersion, currentVersion) <= 0) {
            return
        }

        if (stateService.state.preparedPluginVersion == releaseVersion) {
            return
        }

        val zipAsset = latestPluginRelease.assets.firstOrNull { it.name.endsWith(".zip") }
        if (zipAsset == null) {
            notifier.warn("Plugin release ${latestPluginRelease.tagName} has no zip asset to install.")
            return
        }

        val pluginNode = PluginNode(pluginId, "Viper Language Support", releaseVersion).apply {
            downloadUrl = zipAsset.downloadUrl
            version = releaseVersion
        }

        val downloader = PluginDownloader
            .createDownloader(pluginNode, currentVersion, PluginManagerCore.buildNumber)
            .withErrorsConsumer { message -> log.warn("Plugin update error: $message") }

        if (!downloader.prepareToInstall(EmptyProgressIndicator())) {
            notifier.warn("Found Viper plugin update $releaseVersion, but the IDE refused to prepare the install.")
            return
        }

        downloader.install()

        stateService.state.preparedPluginVersion = releaseVersion

        notifier.info(
            "Prepared Viper plugin update $releaseVersion from GitHub releases. Restart the IDE to finish installing it.",
            NotificationAction.createSimple("Restart IDE") {
                ApplicationManager.getApplication().restart()
            },
            NotificationAction.createSimple("View Release") {
                BrowserUtil.browse(latestPluginRelease.htmlUrl)
            },
        )
    }
}

private object ViperGitHubReleaseClient {
    private val httpClient: HttpClient = HttpClient.newBuilder()
        .followRedirects(HttpClient.Redirect.NORMAL)
        .connectTimeout(Duration.ofSeconds(20))
        .build()

    fun fetchReleases(): List<ViperRelease> {
        val request = HttpRequest.newBuilder()
            .uri(URI(RELEASES_API_URL))
            .timeout(Duration.ofSeconds(20))
            .header("Accept", "application/vnd.github+json")
            .header("User-Agent", "viper-jetbrains-plugin")
            .GET()
            .build()

        val response = httpClient.send(request, HttpResponse.BodyHandlers.ofString())
        if (response.statusCode() !in 200..299) {
            throw IOException("GitHub releases API returned HTTP ${response.statusCode()}")
        }

        val payload = JSONArray(response.body())
        return buildList {
            for (index in 0 until payload.length()) {
                val item = payload.getJSONObject(index)
                val assetsArray = item.getJSONArray("assets")
                val assets = buildList {
                    for (assetIndex in 0 until assetsArray.length()) {
                        val asset = assetsArray.getJSONObject(assetIndex)
                        add(
                            ViperReleaseAsset(
                                name = asset.getString("name"),
                                downloadUrl = asset.getString("browser_download_url"),
                            ),
                        )
                    }
                }

                add(
                    ViperRelease(
                        tagName = item.getString("tag_name"),
                        htmlUrl = item.getString("html_url"),
                        zipballUrl = item.getString("zipball_url"),
                        prerelease = item.getBoolean("prerelease"),
                        publishedAt = OffsetDateTime.parse(item.getString("published_at")),
                        assets = assets,
                    ),
                )
            }
        }
    }

    fun downloadTo(url: String, destination: Path) {
        val request = HttpRequest.newBuilder()
            .uri(URI(url))
            .timeout(Duration.ofMinutes(2))
            .header("Accept", "application/octet-stream")
            .header("User-Agent", "viper-jetbrains-plugin")
            .GET()
            .build()

        val response = httpClient.send(request, HttpResponse.BodyHandlers.ofFile(destination))
        if (response.statusCode() !in 200..299) {
            throw IOException("Download failed with HTTP ${response.statusCode()} for $url")
        }
    }
}

private data class ViperRelease(
    val tagName: String,
    val htmlUrl: String,
    val zipballUrl: String,
    val prerelease: Boolean,
    val publishedAt: OffsetDateTime,
    val assets: List<ViperReleaseAsset>,
) {
    fun versionForComparison(): String = when {
        tagName.startsWith(PLUGIN_RELEASE_PREFIX) -> tagName.removePrefix(PLUGIN_RELEASE_PREFIX)
        tagName.startsWith("v") -> tagName.removePrefix("v")
        else -> tagName
    }
}

private data class ViperReleaseAsset(
    val name: String,
    val downloadUrl: String,
)

private data class PythonCommand(
    val command: List<String>,
) {
    val displayName: String
        get() = command.joinToString(" ")

    fun installCommand(): String = "${displayName} -m pip install lark"
}

private object ViperPythonSupport {
    fun detect(): PythonCommand? {
        val candidates = listOf(
            PythonCommand(listOf("python3")),
            PythonCommand(listOf("python")),
            PythonCommand(listOf("py", "-3")),
        )

        return candidates.firstOrNull(::isAvailable)
    }

    fun hasLark(command: PythonCommand): Boolean =
        run(command.command + listOf("-c", "import lark")).exitCode == 0

    fun installLark(command: PythonCommand): Boolean =
        run(command.command + listOf("-m", "pip", "install", "lark")).exitCode == 0

    private fun isAvailable(command: PythonCommand): Boolean =
        run(command.command + "--version").exitCode == 0

    private fun run(command: List<String>): ProcessResult {
        return try {
            val process = ProcessBuilder(command)
                .redirectErrorStream(true)
                .start()

            val completed = process.waitFor(20, TimeUnit.SECONDS)
            if (!completed) {
                process.destroyForcibly()
                ProcessResult(-1, "Timed out")
            } else {
                ProcessResult(process.exitValue(), process.inputStream.bufferedReader().readText().trim())
            }
        } catch (_: IOException) {
            ProcessResult(-1, "")
        }
    }
}

private data class ProcessResult(
    val exitCode: Int,
    val output: String,
)

private class ViperNotifier(private val project: Project) {
    fun info(message: String, vararg actions: NotificationAction) {
        notify(message, NotificationType.INFORMATION, *actions)
    }

    fun warn(message: String, vararg actions: NotificationAction) {
        notify(message, NotificationType.WARNING, *actions)
    }

    private fun notify(message: String, type: NotificationType, vararg actions: NotificationAction) {
        val notification = NotificationGroupManager.getInstance()
            .getNotificationGroup(NOTIFICATION_GROUP_ID)
            .createNotification(message, type)

        actions.forEach(notification::addAction)
        notification.notify(project)
    }
}

private fun unzip(source: Path, destination: Path) {
    ZipInputStream(source.inputStream().buffered()).use { zip ->
        while (true) {
            val entry = zip.nextEntry ?: break
            val output = destination.resolve(entry.name).normalize()

            if (!output.startsWith(destination)) {
                throw IOException("Blocked zip-slip entry: ${entry.name}")
            }

            if (entry.isDirectory) {
                Files.createDirectories(output)
            } else {
                Files.createDirectories(output.parent)
                Files.copy(zip, output, StandardCopyOption.REPLACE_EXISTING)
            }

            zip.closeEntry()
        }
    }
}

private fun Path.findRelative(relativePath: String): Path? {
    val pathParts = relativePath.split('/')
    return Files.walk(this).use { stream ->
        stream
            .filter { Files.isRegularFile(it) }
            .filter { path ->
                val relativeNames = this.relativize(path)
                    .map(Path::toString)
                relativeNames.takeLast(pathParts.size) == pathParts
            }
            .findFirst()
            .orElse(null)
    }
}

private fun Path.deleteRecursivelyIfExists() {
    if (!exists()) {
        return
    }

    Files.walk(this).use { stream ->
        stream
            .sorted(Comparator.reverseOrder())
            .forEach { path -> Files.deleteIfExists(path) }
    }
}

private const val PLUGIN_ID = "dev.viper.idea"
private const val PLUGIN_RELEASE_PREFIX = "plugin-v"
private const val RELEASES_API_URL = "https://api.github.com/repos/TheDJStudios/Viper/releases"
private const val NOTIFICATION_GROUP_ID = "Viper Notifications"
