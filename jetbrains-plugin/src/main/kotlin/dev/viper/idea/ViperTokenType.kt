package dev.viper.idea

import com.intellij.psi.tree.IElementType

open class ViperTokenType(debugName: String) : IElementType(debugName, ViperLanguage) {
    override fun toString(): String = "ViperTokenType.${super.toString()}"
}
