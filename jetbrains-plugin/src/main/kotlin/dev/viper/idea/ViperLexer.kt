package dev.viper.idea

import com.intellij.lexer.LexerBase
import com.intellij.psi.TokenType
import com.intellij.psi.tree.IElementType

class ViperLexer : LexerBase() {
    private var buffer: CharSequence = ""
    private var startOffset: Int = 0
    private var endOffset: Int = 0
    private var state: Int = 0
    private var tokenStart: Int = 0
    private var tokenEnd: Int = 0
    private var tokenType: IElementType? = null

    override fun start(buffer: CharSequence, startOffset: Int, endOffset: Int, initialState: Int) {
        this.buffer = buffer
        this.startOffset = startOffset
        this.endOffset = endOffset
        this.state = initialState
        tokenStart = startOffset
        tokenEnd = startOffset
        tokenType = null
        locateToken()
    }

    override fun getState(): Int = state

    override fun getTokenType(): IElementType? = tokenType

    override fun getTokenStart(): Int = tokenStart

    override fun getTokenEnd(): Int = tokenEnd

    override fun advance() {
        if (tokenType == null) {
            return
        }
        tokenStart = tokenEnd
        locateToken()
    }

    override fun getBufferSequence(): CharSequence = buffer

    override fun getBufferEnd(): Int = endOffset

    private fun locateToken() {
        if (tokenStart >= endOffset) {
            tokenType = null
            tokenEnd = tokenStart
            return
        }

        var index = tokenStart
        val current = buffer[index]

        if (current.isWhitespace()) {
            while (index < endOffset && buffer[index].isWhitespace()) {
                index++
            }
            tokenEnd = index
            tokenType = TokenType.WHITE_SPACE
            return
        }

        if (current == '%') {
            index++
            while (index < endOffset && buffer[index] != '\n' && buffer[index] != '\r') {
                index++
            }
            tokenEnd = index
            tokenType = ViperTokenTypes.COMMENT
            return
        }

        if (current == '#' && tokenStart + 1 < endOffset && buffer[tokenStart + 1] == '"') {
            tokenEnd = scanDoubleQuotedString(tokenStart + 1)
            tokenType = ViperTokenTypes.STRING
            return
        }

        if (current == '"') {
            tokenEnd = scanDoubleQuotedString(tokenStart)
            tokenType = ViperTokenTypes.STRING
            return
        }

        if (current == '\'') {
            index++
            var escaped = false
            while (index < endOffset) {
                val c = buffer[index]
                if (escaped) {
                    escaped = false
                } else if (c == '\\') {
                    escaped = true
                } else if (c == '\'') {
                    index++
                    break
                }
                index++
            }
            tokenEnd = index.coerceAtMost(endOffset)
            tokenType = ViperTokenTypes.CHAR
            return
        }

        if (current.isDigit()) {
            index++
            var seenDot = false
            while (index < endOffset) {
                val c = buffer[index]
                if (c.isDigit()) {
                    index++
                    continue
                }
                if (c == '.' && !seenDot) {
                    seenDot = true
                    index++
                    continue
                }
                break
            }
            tokenEnd = index
            tokenType = ViperTokenTypes.NUMBER
            return
        }

        if (current == '$') {
            index++
            while (index < endOffset && buffer[index].isWhitespace()) {
                index++
            }
            val identifierStart = index
            while (index < endOffset && buffer[index].isIdentifierPart()) {
                index++
            }
            tokenEnd = if (identifierStart == index) tokenStart + 1 else index
            val text = buffer.subSequence(tokenStart, tokenEnd).toString().replace(" ", "")
            tokenType = when (text) {
                "\$argc", "\$args" -> ViperTokenTypes.BUILTIN
                "$" -> ViperTokenTypes.DOLLAR
                else -> ViperTokenTypes.VARIABLE
            }
            return
        }

        if (current.isIdentifierStart()) {
            index++
            while (index < endOffset && buffer[index].isIdentifierPart()) {
                index++
            }
            tokenEnd = index
            val text = buffer.subSequence(tokenStart, tokenEnd).toString()
            tokenType = when {
                CONTROL_KEYWORDS.contains(text) -> ViperTokenTypes.KEYWORD
                TYPES.contains(text) -> ViperTokenTypes.TYPE
                BOOLEAN_LITERALS.contains(text) -> ViperTokenTypes.BOOLEAN
                text == "none" -> ViperTokenTypes.NONE
                BUILTINS.contains(text) -> ViperTokenTypes.BUILTIN
                nextNonWhitespace(index) == '(' -> ViperTokenTypes.FUNCTION
                else -> ViperTokenTypes.IDENTIFIER
            }
            return
        }

        val pair = if (tokenStart + 1 < endOffset) buffer.subSequence(tokenStart, tokenStart + 2).toString() else ""
        if (pair in TWO_CHAR_OPERATORS) {
            tokenEnd = tokenStart + 2
            tokenType = ViperTokenTypes.OPERATOR
            return
        }

        tokenEnd = tokenStart + 1
        tokenType = when (current) {
            '+', '-', '*', '/', '=', '<', '>' -> ViperTokenTypes.OPERATOR
            '(' -> ViperTokenTypes.LPAREN
            ')' -> ViperTokenTypes.RPAREN
            '{' -> ViperTokenTypes.LBRACE
            '}' -> ViperTokenTypes.RBRACE
            '[' -> ViperTokenTypes.LBRACKET
            ']' -> ViperTokenTypes.RBRACKET
            ',' -> ViperTokenTypes.COMMA
            ':' -> ViperTokenTypes.COLON
            ';' -> ViperTokenTypes.SEMICOLON
            else -> ViperTokenTypes.BAD_CHARACTER
        }
    }

    private fun scanDoubleQuotedString(quoteOffset: Int): Int {
        var index = quoteOffset + 1
        var escaped = false
        while (index < endOffset) {
            val c = buffer[index]
            if (escaped) {
                escaped = false
            } else if (c == '\\') {
                escaped = true
            } else if (c == '"') {
                index++
                break
            }
            index++
        }
        return index.coerceAtMost(endOffset)
    }

    private fun Char.isIdentifierStart(): Boolean = this == '_' || isLetter()

    private fun Char.isIdentifierPart(): Boolean = this == '_' || isLetterOrDigit()

    private fun nextNonWhitespace(index: Int): Char? {
        var cursor = index
        while (cursor < endOffset) {
            val candidate = buffer[cursor]
            if (!candidate.isWhitespace()) {
                return candidate
            }
            cursor++
        }
        return null
    }

    companion object {
        private val CONTROL_KEYWORDS = setOf("import", "if", "else", "try", "return", "and")
        private val TYPES = ViperCompletionData.TYPES.toSet()
        private val BUILTINS = setOf("print", "collect")
        private val BOOLEAN_LITERALS = setOf("true", "false")

        private val TWO_CHAR_OPERATORS = setOf("==", "!=", "<=", ">=")
    }
}
