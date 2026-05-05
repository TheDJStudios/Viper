package dev.viper.idea

import com.intellij.lang.BracePair
import com.intellij.lang.PairedBraceMatcher
import com.intellij.psi.PsiFile
import com.intellij.psi.tree.IElementType

class ViperBraceMatcher : PairedBraceMatcher {
    override fun getPairs(): Array<BracePair> = arrayOf(
        BracePair(ViperTokenTypes.LPAREN, ViperTokenTypes.RPAREN, false),
        BracePair(ViperTokenTypes.LBRACE, ViperTokenTypes.RBRACE, true),
        BracePair(ViperTokenTypes.LBRACKET, ViperTokenTypes.RBRACKET, false),
    )

    override fun isPairedBracesAllowedBeforeType(lbraceType: IElementType, contextType: IElementType?): Boolean = true

    override fun getCodeConstructStart(file: PsiFile, openingBraceOffset: Int): Int = openingBraceOffset
}
