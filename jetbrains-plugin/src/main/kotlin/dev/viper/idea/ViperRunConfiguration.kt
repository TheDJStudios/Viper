package dev.viper.idea

import com.intellij.execution.ExecutionException
import com.intellij.execution.Executor
import com.intellij.execution.configurations.CommandLineState
import com.intellij.execution.configurations.ConfigurationFactory
import com.intellij.execution.configurations.ConfigurationType
import com.intellij.execution.configurations.ConfigurationTypeUtil
import com.intellij.execution.configurations.LocatableConfigurationBase
import com.intellij.execution.configurations.RunConfigurationOptions
import com.intellij.execution.configurations.RuntimeConfigurationError
import com.intellij.execution.configurations.RuntimeConfigurationException
import com.intellij.execution.configurations.RunProfileState
import com.intellij.execution.executors.DefaultRunExecutor
import com.intellij.execution.filters.TextConsoleBuilderFactory
import com.intellij.execution.process.KillableProcessHandler
import com.intellij.execution.runners.ExecutionEnvironment
import com.intellij.execution.runners.ProgramRunner
import com.intellij.execution.actions.ConfigurationContext
import com.intellij.execution.actions.LazyRunConfigurationProducer
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.options.SettingsEditor
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.Ref
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.PsiElement
import org.jdom.Element
import java.awt.GridBagConstraints
import java.awt.GridBagLayout
import javax.swing.JComboBox
import javax.swing.JComponent
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.JTextField
import kotlin.io.path.Path
import kotlin.io.path.exists

class ViperRunConfigurationType : ConfigurationType {
    private val factory = ViperRunConfigurationFactory(this)

    override fun getDisplayName(): String = "Viper"

    override fun getConfigurationTypeDescription(): String = "Run or compile Viper files"

    override fun getIcon() = ViperIcons.FILE

    override fun getId(): String = "ViperRunConfiguration"

    override fun getConfigurationFactories(): Array<ConfigurationFactory> = arrayOf(factory)
}

class ViperRunConfigurationFactory(type: ConfigurationType) : ConfigurationFactory(type) {
    override fun getId(): String = "ViperRunConfigurationFactory"

    override fun createTemplateConfiguration(project: Project): ViperRunConfiguration =
        ViperRunConfiguration(project, this, "Viper")
}

class ViperRunConfiguration(
    project: Project,
    factory: ConfigurationFactory,
    name: String,
) : LocatableConfigurationBase<RunConfigurationOptions>(project, factory, name) {
    var inputPath: String = ""
    var modeName: String = ViperExecutionMode.RUN.name

    var mode: ViperExecutionMode
        get() = ViperExecutionMode.valueOf(modeName)
        set(value) {
            modeName = value.name
        }

    override fun suggestedName(): String {
        val fileName = inputPath.substringAfterLast('/').ifBlank { "Viper" }
        return when (mode) {
            ViperExecutionMode.RUN -> "Run $fileName"
            ViperExecutionMode.COMPILE -> "Compile $fileName"
        }
    }

    override fun getConfigurationEditor(): SettingsEditor<out ViperRunConfiguration> =
        ViperRunConfigurationEditor()

    override fun getState(executor: Executor, environment: ExecutionEnvironment): RunProfileState =
        ViperCommandLineState(environment, this)

    override fun readExternal(element: Element) {
        super.readExternal(element)
        inputPath = element.getAttributeValue(INPUT_PATH_ATTRIBUTE).orEmpty()
        modeName = element.getAttributeValue(MODE_ATTRIBUTE) ?: ViperExecutionMode.RUN.name
    }

    override fun writeExternal(element: Element) {
        super.writeExternal(element)
        element.setAttribute(INPUT_PATH_ATTRIBUTE, inputPath)
        element.setAttribute(MODE_ATTRIBUTE, modeName)
    }

    override fun checkConfiguration() {
        if (inputPath.isBlank()) {
            throw RuntimeConfigurationError("Viper file path is not set.")
        }

        val path = Path(inputPath)
        val resolvedPath = if (path.isAbsolute) {
            path
        } else {
            val projectBasePath = project.basePath
                ?: throw RuntimeConfigurationError("Project base path is not available.")
            Path(projectBasePath).resolve(path)
        }

        if (!resolvedPath.exists()) {
            throw RuntimeConfigurationError("Viper file does not exist: $inputPath")
        }

        if (!inputPath.endsWith(".vp")) {
            throw RuntimeConfigurationError("Viper run configurations require a .vp file.")
        }
    }

    companion object {
        private const val INPUT_PATH_ATTRIBUTE = "viperInputPath"
        private const val MODE_ATTRIBUTE = "viperMode"
    }
}

private class ViperRunConfigurationEditor : SettingsEditor<ViperRunConfiguration>() {
    private val inputField = JTextField()
    private val modeBox = JComboBox(ViperExecutionMode.entries.toTypedArray())
    private val panel = JPanel(GridBagLayout()).apply {
        val constraints = GridBagConstraints().apply {
            anchor = GridBagConstraints.WEST
            fill = GridBagConstraints.HORIZONTAL
            weightx = 1.0
            gridx = 0
            gridy = 0
        }

        add(JLabel("File"), constraints)
        constraints.gridy = 1
        add(inputField, constraints)
        constraints.gridy = 2
        add(JLabel("Mode"), constraints)
        constraints.gridy = 3
        add(modeBox, constraints)
    }

    override fun resetEditorFrom(configuration: ViperRunConfiguration) {
        inputField.text = configuration.inputPath
        modeBox.selectedItem = configuration.mode
    }

    override fun applyEditorTo(configuration: ViperRunConfiguration) {
        configuration.inputPath = inputField.text.trim()
        configuration.mode = modeBox.selectedItem as ViperExecutionMode
    }

    override fun createEditor(): JComponent = panel
}

private class ViperCommandLineState(
    environment: ExecutionEnvironment,
    private val configuration: ViperRunConfiguration,
) : CommandLineState(environment) {
    init {
        consoleBuilder = TextConsoleBuilderFactory.getInstance().createBuilder(environment.project)
    }

    override fun startProcess(): KillableProcessHandler {
        val commandLine = try {
            ViperExecutionSupport.createCommandLine(environment.project, configuration.mode, configuration.inputPath)
        } catch (error: ExecutionException) {
            throw error
        }

        return KillableProcessHandler(commandLine)
    }
}

class ViperRunConfigurationProducer : LazyRunConfigurationProducer<ViperRunConfiguration>() {
    override fun getConfigurationFactory(): ConfigurationFactory =
        ConfigurationTypeUtil.findConfigurationType(ViperRunConfigurationType::class.java).configurationFactories.first()

    override fun setupConfigurationFromContext(
        configuration: ViperRunConfiguration,
        context: ConfigurationContext,
        sourceElement: Ref<PsiElement>,
    ): Boolean {
        val file = context.viperVirtualFile() ?: return false
        configuration.inputPath = ViperExecutionSupport.projectFilePath(context.project, file)
        configuration.mode = ViperExecutionMode.RUN
        configuration.name = configuration.suggestedName()
        return true
    }

    override fun isConfigurationFromContext(
        configuration: ViperRunConfiguration,
        context: ConfigurationContext,
    ): Boolean {
        val file = context.viperVirtualFile() ?: return false
        return configuration.mode == ViperExecutionMode.RUN &&
            configuration.inputPath == ViperExecutionSupport.projectFilePath(context.project, file)
    }
}

class ViperRunFileAction : com.intellij.openapi.actionSystem.AnAction(
    "Run Viper File",
    "Run the selected Viper file with the bundled Viper interpreter",
    ViperIcons.FILE,
) {
    override fun update(event: com.intellij.openapi.actionSystem.AnActionEvent) {
        event.presentation.isEnabledAndVisible = event.project != null && ViperExecutionSupport.findViperFile(event) != null
    }

    override fun actionPerformed(event: com.intellij.openapi.actionSystem.AnActionEvent) {
        val project = event.project ?: return
        val file = ViperExecutionSupport.findViperFile(event) ?: return
        ViperExecutionSupport.runConfiguration(project, createConfiguration(project, file, ViperExecutionMode.RUN))
    }
}

class ViperCompileFileAction : com.intellij.openapi.actionSystem.AnAction(
    "Compile Viper File",
    "Compile the selected Viper file with the bundled Viper compiler",
    ViperIcons.FILE,
) {
    override fun update(event: com.intellij.openapi.actionSystem.AnActionEvent) {
        event.presentation.isEnabledAndVisible = event.project != null && ViperExecutionSupport.findViperFile(event) != null
    }

    override fun actionPerformed(event: com.intellij.openapi.actionSystem.AnActionEvent) {
        val project = event.project ?: return
        val file = ViperExecutionSupport.findViperFile(event) ?: return
        ViperExecutionSupport.runConfiguration(project, createConfiguration(project, file, ViperExecutionMode.COMPILE))
    }
}

private fun createConfiguration(project: Project, file: VirtualFile, mode: ViperExecutionMode): ViperRunConfiguration {
    val factory = ConfigurationTypeUtil.findConfigurationType(ViperRunConfigurationType::class.java).configurationFactories.first()
    return ViperRunConfiguration(project, factory, file.name).apply {
        inputPath = ViperExecutionSupport.projectFilePath(project, file)
        this.mode = mode
        name = suggestedName()
    }
}

private fun ConfigurationContext.viperVirtualFile(): VirtualFile? {
    val psiFile = CommonDataKeys.PSI_FILE.getData(dataContext)
    if (ViperExecutionSupport.isViperFile(psiFile?.virtualFile)) {
        return psiFile?.virtualFile
    }

    val virtualFile = CommonDataKeys.VIRTUAL_FILE.getData(dataContext)
    if (ViperExecutionSupport.isViperFile(virtualFile)) {
        return virtualFile
    }

    return CommonDataKeys.VIRTUAL_FILE_ARRAY.getData(dataContext)
        ?.firstOrNull(ViperExecutionSupport::isViperFile)
}
