package dev.viper.idea

import com.intellij.lang.ASTNode
import com.intellij.lang.ParserDefinition
import com.intellij.lang.PsiParser
import com.intellij.extapi.psi.ASTWrapperPsiElement
import com.intellij.lexer.Lexer
import com.intellij.openapi.project.Project
import com.intellij.psi.FileViewProvider
import com.intellij.psi.PsiElement
import com.intellij.psi.TokenType
import com.intellij.psi.tree.IFileElementType
import com.intellij.psi.tree.TokenSet

class ViperParserDefinition : ParserDefinition {
    override fun createLexer(project: Project?): Lexer = ViperLexer()

    override fun createParser(project: Project?): PsiParser = PsiParser { root, builder ->
        val marker = builder.mark()
        while (!builder.eof()) {
            builder.advanceLexer()
        }
        marker.done(root)
        builder.treeBuilt
    }

    override fun getFileNodeType(): IFileElementType = ViperTokenTypes.FILE

    override fun getCommentTokens(): TokenSet = ViperTokenTypes.COMMENTS

    override fun getStringLiteralElements(): TokenSet = ViperTokenTypes.STRINGS

    override fun createElement(node: ASTNode): PsiElement = ASTWrapperPsiElement(node)

    override fun createFile(viewProvider: FileViewProvider) = ViperFile(viewProvider)

    override fun spaceExistenceTypeBetweenTokens(left: ASTNode, right: ASTNode): ParserDefinition.SpaceRequirements =
        when {
            left.elementType == TokenType.WHITE_SPACE || right.elementType == TokenType.WHITE_SPACE ->
                ParserDefinition.SpaceRequirements.MAY
            else -> ParserDefinition.SpaceRequirements.MAY
        }
}
