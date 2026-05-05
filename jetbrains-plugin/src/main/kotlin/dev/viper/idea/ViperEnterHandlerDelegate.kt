package dev.viper.idea

import com.intellij.codeInsight.editorActions.enter.EnterHandlerDelegateAdapter
import com.intellij.codeInsight.editorActions.enter.EnterHandlerDelegate.Result
import com.intellij.openapi.actionSystem.DataContext
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.editor.actionSystem.EditorActionHandler
import com.intellij.openapi.util.Ref
import com.intellij.psi.PsiFile

class ViperEnterHandlerDelegate : EnterHandlerDelegateAdapter() {
    override fun preprocessEnter(
        file: PsiFile,
        editor: Editor,
        caretOffset: Ref<Int>,
        caretAdvance: Ref<Int>,
        dataContext: DataContext,
        originalHandler: EditorActionHandler?,
    ): Result {
        if (file.language != ViperLanguage) {
            return Result.Continue
        }

        val document = editor.document
        val offset = caretOffset.get()
        val text = document.charsSequence

        val lineNumber = document.getLineNumber(offset.coerceAtMost(document.textLength))
        val lineStart = document.getLineStartOffset(lineNumber)
        val lineIndent = buildString {
            var cursor = lineStart
            while (cursor < document.textLength) {
                val current = text[cursor]
                if (current == ' ' || current == '\t') {
                    append(current)
                    cursor++
                } else {
                    break
                }
            }
        }

        val before = previousNonWhitespace(text, offset - 1)
        val after = nextNonWhitespace(text, offset)
        val indentUnit = "    "

        return when {
            before == '{' && after == '}' -> {
                document.insertString(offset, "\n$lineIndent$indentUnit\n$lineIndent")
                editor.caretModel.moveToOffset(offset + 1 + lineIndent.length + indentUnit.length)
                Result.Stop
            }

            before == '{' -> {
                document.insertString(offset, "\n$lineIndent$indentUnit")
                editor.caretModel.moveToOffset(offset + 1 + lineIndent.length + indentUnit.length)
                Result.Stop
            }

            else -> {
                document.insertString(offset, "\n$lineIndent")
                editor.caretModel.moveToOffset(offset + 1 + lineIndent.length)
                Result.Stop
            }
        }
    }

    private fun previousNonWhitespace(text: CharSequence, startIndex: Int): Char? {
        var index = startIndex
        while (index >= 0) {
            val current = text[index]
            if (!current.isWhitespace()) {
                return current
            }
            index--
        }
        return null
    }

    private fun nextNonWhitespace(text: CharSequence, startIndex: Int): Char? {
        var index = startIndex
        while (index < text.length) {
            val current = text[index]
            if (!current.isWhitespace()) {
                return current
            }
            index++
        }
        return null
    }
}
