package dev.viper.idea

import com.intellij.execution.ExecutionException
import com.intellij.execution.ExecutionManager
import com.intellij.execution.Executor
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.execution.executors.DefaultRunExecutor
import com.intellij.execution.runners.ExecutionEnvironmentBuilder
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.components.service
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VfsUtilCore
import com.intellij.openapi.vfs.VirtualFile
import java.nio.file.Path
import kotlin.io.path.absolutePathString
import kotlin.io.path.exists
import kotlin.io.path.isRegularFile

enum class ViperExecutionMode {
    RUN,
    COMPILE,
}

data class ViperRuntimeEntrypoints(
    val python: PythonCommand,
    val compiler: Path,
    val interpreter: Path,
)

object ViperExecutionSupport {
    fun projectFilePath(project: Project, file: VirtualFile): String {
        val filePath = VfsUtilCore.virtualToIoFile(file).toPath().toAbsolutePath().normalize()
        val projectRoot = project.basePath
            ?.let { Path.of(it).toAbsolutePath().normalize() }
            ?: return filePath.absolutePathString()

        return if (filePath.startsWith(projectRoot)) {
            projectRoot.relativize(filePath).toString()
        } else {
            filePath.absolutePathString()
        }
    }

    fun resolveProjectPath(project: Project, path: String): Path {
        if (path.isBlank()) {
            throw ExecutionException("No Viper source file path is set for this run configuration.")
        }

        val rawPath = Path.of(path)
        val resolvedPath = if (rawPath.isAbsolute) {
            rawPath
        } else {
            val projectRoot = project.basePath
                ?: throw ExecutionException("Project base path is not available.")
            Path.of(projectRoot).resolve(rawPath)
        }

        return resolvedPath.toAbsolutePath().normalize()
    }

    fun isViperFile(file: VirtualFile?): Boolean {
        if (file == null || file.isDirectory) {
            return false
        }

        if (file.extension.equals("vp", ignoreCase = true)) {
            return true
        }

        return file.fileType == ViperFileType.INSTANCE
    }

    fun findViperFile(event: AnActionEvent): VirtualFile? {
        val psiFile = event.getData(CommonDataKeys.PSI_FILE)
        if (isViperFile(psiFile?.virtualFile)) {
            return psiFile?.virtualFile
        }

        val virtualFile = event.getData(CommonDataKeys.VIRTUAL_FILE)
        if (isViperFile(virtualFile)) {
            return virtualFile
        }

        return event.getData(CommonDataKeys.VIRTUAL_FILE_ARRAY)
            ?.firstOrNull(::isViperFile)
    }

    fun findCurrentViperFile(event: AnActionEvent): VirtualFile? {
        val psiFile = event.getData(CommonDataKeys.PSI_FILE)
        if (isViperFile(psiFile?.virtualFile)) {
            return psiFile?.virtualFile
        }

        val virtualFile = event.getData(CommonDataKeys.VIRTUAL_FILE)
        if (isViperFile(virtualFile)) {
            return virtualFile
        }

        return null
    }

    fun ensureRuntime(project: Project): ViperRuntimeEntrypoints {
        val stateService = service<ViperRuntimeStateService>()
        val python = ViperPythonSupport.detect()
            ?: throw ExecutionException("Python 3 was not found. Checked PATH, common install locations, and login-shell resolution.")

        val projectRoot = project.basePath?.let { Path.of(it).toAbsolutePath().normalize() }
        val compiler: Path
        val interpreter: Path
        val projectRuntime = projectRoot?.let { root ->
            listOf(
                root.resolve(VIPER_COMPILER_NAME) to root.resolve(VIPER_INTERPRETER_NAME),
                root.resolve("Viper_compiler/main.py") to root.resolve("Viper_interpreter/Viper/main.py"),
                root.resolve("compiler.py") to root.resolve("interpreter.py"),
            ).firstOrNull { (candidateCompiler, candidateInterpreter) ->
                candidateCompiler.exists() &&
                    candidateCompiler.isRegularFile() &&
                    candidateInterpreter.exists() &&
                    candidateInterpreter.isRegularFile()
            }
        }

        if (projectRuntime != null) {
            compiler = projectRuntime.first
            interpreter = projectRuntime.second
        } else {
            val installDir = stateService.state.runtimeInstallDir
                ?: throw ExecutionException("Viper runtime is not installed yet. Restart the IDE and let startup sync complete.")

            val runtimeDir = Path.of(installDir)
            compiler = runtimeDir.resolve(VIPER_COMPILER_NAME)
            interpreter = runtimeDir.resolve(VIPER_INTERPRETER_NAME)
        }

        if (!compiler.exists() || !compiler.isRegularFile()) {
            throw ExecutionException("Viper compiler runtime is missing at $compiler")
        }

        if (!interpreter.exists() || !interpreter.isRegularFile()) {
            throw ExecutionException("Viper interpreter runtime is missing at $interpreter")
        }

        if (!ViperPythonSupport.hasLark(python)) {
            val details = ViperPythonSupport.describeMissingLark(python)
            throw ExecutionException("Python is available (${python.displayName}), but 'lark' is unavailable. $details")
        }

        return ViperRuntimeEntrypoints(
            python = python,
            compiler = compiler,
            interpreter = interpreter,
        )
    }

    fun createCommandLine(project: Project, mode: ViperExecutionMode, inputPath: String): GeneralCommandLine {
        val filePath = resolveProjectPath(project, inputPath)
        if (!filePath.exists() || !filePath.isRegularFile()) {
            throw ExecutionException("Viper source file does not exist at $filePath")
        }

        val runtime = ensureRuntime(project)
        val script = when (mode) {
            ViperExecutionMode.RUN -> runtime.interpreter
            ViperExecutionMode.COMPILE -> runtime.compiler
        }

        val scriptPath = script.toAbsolutePath().normalize().toString()
        val sourcePath = filePath.toString()
        return GeneralCommandLine(runtime.python.command + listOf(scriptPath, sourcePath))
            .withWorkDirectory(project.basePath ?: filePath.parent?.toString())
    }

    fun saveOpenFiles(project: Project) {
        ApplicationManager.getApplication().invokeAndWait {
            WriteCommandAction.runWriteCommandAction(project) {
                FileDocumentManager.getInstance().saveAllDocuments()
            }
        }
    }

    fun runConfiguration(project: Project, configuration: ViperRunConfiguration, executor: Executor = DefaultRunExecutor.getRunExecutorInstance()) {
        saveOpenFiles(project)
        val environment = ExecutionEnvironmentBuilder.create(project, executor, configuration).build()
        ExecutionManager.getInstance(project).restartRunProfile(environment)
    }
}
