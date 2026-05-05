package dev.viper.idea

import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage

@Service(Service.Level.APP)
@State(name = "ViperRuntimeState", storages = [Storage("viper-language-support.xml")])
class ViperRuntimeStateService : PersistentStateComponent<ViperRuntimeStateService.State> {
    data class State(
        var runtimeVersion: String? = null,
        var runtimeInstallDir: String? = null,
        var preparedPluginVersion: String? = null,
    )

    private var state = State()

    override fun getState(): State = state

    override fun loadState(state: State) {
        this.state = state
    }
}
