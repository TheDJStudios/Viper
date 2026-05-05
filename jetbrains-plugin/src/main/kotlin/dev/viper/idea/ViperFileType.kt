package dev.viper.idea

import com.intellij.openapi.fileTypes.LanguageFileType
import javax.swing.Icon

class ViperFileType private constructor() : LanguageFileType(ViperLanguage) {
    override fun getName(): String = "Viper"

    override fun getDescription(): String = "Viper source file"

    override fun getDefaultExtension(): String = "vp"

    override fun getIcon(): Icon = ViperIcons.FILE

    companion object {
        @JvmField
        val INSTANCE = ViperFileType()
    }
}
