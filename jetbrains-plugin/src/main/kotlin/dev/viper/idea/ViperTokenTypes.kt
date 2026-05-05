package dev.viper.idea

import com.intellij.psi.TokenType
import com.intellij.psi.tree.IFileElementType
import com.intellij.psi.tree.TokenSet

object ViperTokenTypes {
    val FILE = IFileElementType(ViperLanguage)

    val WHITE_SPACE = TokenType.WHITE_SPACE
    val BAD_CHARACTER = TokenType.BAD_CHARACTER

    val KEYWORD = ViperTokenType("KEYWORD")
    val IDENTIFIER = ViperTokenType("IDENTIFIER")
    val NUMBER = ViperTokenType("NUMBER")
    val STRING = ViperTokenType("STRING")
    val COMMENT = ViperTokenType("COMMENT")
    val OPERATOR = ViperTokenType("OPERATOR")
    val DOLLAR = ViperTokenType("DOLLAR")
    val LPAREN = ViperTokenType("LPAREN")
    val RPAREN = ViperTokenType("RPAREN")
    val LBRACE = ViperTokenType("LBRACE")
    val RBRACE = ViperTokenType("RBRACE")
    val LBRACKET = ViperTokenType("LBRACKET")
    val RBRACKET = ViperTokenType("RBRACKET")
    val COMMA = ViperTokenType("COMMA")
    val COLON = ViperTokenType("COLON")
    val SEMICOLON = ViperTokenType("SEMICOLON")

    val COMMENTS = TokenSet.create(COMMENT)
    val STRINGS = TokenSet.create(STRING)
}
