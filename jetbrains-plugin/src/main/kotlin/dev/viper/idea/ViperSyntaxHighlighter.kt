package dev.viper.idea

import com.intellij.lexer.Lexer
import com.intellij.openapi.editor.DefaultLanguageHighlighterColors
import com.intellij.openapi.editor.HighlighterColors
import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.fileTypes.SyntaxHighlighterBase
import com.intellij.psi.TokenType
import com.intellij.psi.tree.IElementType

class ViperSyntaxHighlighter : SyntaxHighlighterBase() {
    override fun getHighlightingLexer(): Lexer = ViperLexer()

    override fun getTokenHighlights(tokenType: IElementType): Array<TextAttributesKey> = when (tokenType) {
        ViperTokenTypes.KEYWORD -> pack(KEYWORD)
        ViperTokenTypes.IDENTIFIER -> pack(IDENTIFIER)
        ViperTokenTypes.NUMBER -> pack(NUMBER)
        ViperTokenTypes.STRING -> pack(STRING)
        ViperTokenTypes.COMMENT -> pack(COMMENT)
        ViperTokenTypes.OPERATOR,
        ViperTokenTypes.DOLLAR -> pack(OPERATOR)
        ViperTokenTypes.LPAREN,
        ViperTokenTypes.RPAREN -> pack(PARENTHESES)
        ViperTokenTypes.LBRACE,
        ViperTokenTypes.RBRACE,
        ViperTokenTypes.LBRACKET,
        ViperTokenTypes.RBRACKET -> pack(BRACES)
        ViperTokenTypes.COLON,
        ViperTokenTypes.SEMICOLON,
        ViperTokenTypes.COMMA -> pack(PUNCTUATION)
        TokenType.BAD_CHARACTER -> pack(BAD_CHARACTER)
        else -> emptyArray()
    }

    companion object {
        val KEYWORD: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_KEYWORD", DefaultLanguageHighlighterColors.KEYWORD)
        val IDENTIFIER: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_IDENTIFIER", DefaultLanguageHighlighterColors.IDENTIFIER)
        val NUMBER: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_NUMBER", DefaultLanguageHighlighterColors.NUMBER)
        val STRING: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_STRING", DefaultLanguageHighlighterColors.STRING)
        val COMMENT: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_COMMENT", DefaultLanguageHighlighterColors.LINE_COMMENT)
        val OPERATOR: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_OPERATOR", DefaultLanguageHighlighterColors.OPERATION_SIGN)
        val PARENTHESES: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_PARENTHESES", DefaultLanguageHighlighterColors.PARENTHESES)
        val BRACES: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_BRACES", DefaultLanguageHighlighterColors.BRACES)
        val PUNCTUATION: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_PUNCTUATION", DefaultLanguageHighlighterColors.COMMA)
        val BAD_CHARACTER: TextAttributesKey =
            TextAttributesKey.createTextAttributesKey("VIPER_BAD_CHARACTER", HighlighterColors.BAD_CHARACTER)
    }
}
