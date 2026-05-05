package dev.viper.idea

import com.intellij.extapi.psi.PsiFileBase
import com.intellij.psi.FileViewProvider

class ViperFile(viewProvider: FileViewProvider) : PsiFileBase(viewProvider, ViperLanguage) {
    override fun getFileType() = ViperFileType.INSTANCE

    override fun toString(): String = "Viper File"
}
