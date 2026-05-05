package dev.viper.idea

import com.intellij.codeInsight.completion.CompletionContributor
import com.intellij.codeInsight.completion.CompletionParameters
import com.intellij.codeInsight.completion.CompletionProvider
import com.intellij.codeInsight.completion.CompletionResultSet
import com.intellij.codeInsight.completion.CompletionType
import com.intellij.codeInsight.completion.InsertHandler
import com.intellij.codeInsight.completion.PrioritizedLookupElement
import com.intellij.codeInsight.lookup.LookupElementBuilder
import com.intellij.icons.AllIcons
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.patterns.PlatformPatterns.psiElement
import com.intellij.util.PlatformIcons
import com.intellij.util.ProcessingContext

class ViperCompletionContributor : CompletionContributor() {
    init {
        extend(
            CompletionType.BASIC,
            psiElement(),
            object : CompletionProvider<CompletionParameters>() {
                override fun addCompletions(
                    parameters: CompletionParameters,
                    context: ProcessingContext,
                    result: CompletionResultSet,
                ) {
                    val file = parameters.originalFile
                    val symbols = ViperSymbols.collect(file)
                    val caretOffset = parameters.offset
                    val sourceText = file.text
                    val completionContext = CompletionContext.from(sourceText, caretOffset)

                    when {
                        completionContext.inImportString -> {
                            addImportCompletions(file, completionContext, result)
                            return
                        }

                        completionContext.afterTypeSeparator -> {
                            addTypes(result)
                            return
                        }

                        completionContext.afterVariableSigil -> {
                            addVariables(symbols, result, stripSigil = true)
                            return
                        }
                    }

                    addKeywords(result)
                    addTypes(result)
                    addBuiltins(result)
                    addVariables(symbols, result, stripSigil = false)
                    addFunctions(symbols, result)
                    addSnippets(result)
                }
            }
        )
    }

    private fun addKeywords(result: CompletionResultSet) {
        ViperCompletionData.KEYWORDS.forEach { keyword ->
            result.addElement(
                PrioritizedLookupElement.withPriority(
                    LookupElementBuilder.create(keyword)
                        .withBoldness(true)
                        .withTypeText("keyword", true),
                    70.0,
                )
            )
        }
    }

    private fun addTypes(result: CompletionResultSet) {
        ViperCompletionData.TYPES.forEach { type ->
            result.addElement(
                PrioritizedLookupElement.withPriority(
                    LookupElementBuilder.create(type)
                        .withTypeText("type", true)
                        .withIcon(PlatformIcons.CLASS_ICON),
                    80.0,
                )
            )
        }
    }

    private fun addBuiltins(result: CompletionResultSet) {
        ViperCompletionData.BUILTINS.forEach { builtin ->
            val builder = LookupElementBuilder.create(builtin)
                .withTypeText("builtin", true)
                .withIcon(AllIcons.Nodes.Function)

            result.addElement(
                PrioritizedLookupElement.withPriority(
                    if (builtin == "print") builder.withInsertHandler(FunctionInsertHandler) else builder,
                    90.0,
                )
            )
        }
    }

    private fun addVariables(
        symbols: ViperCollectedSymbols,
        result: CompletionResultSet,
        stripSigil: Boolean,
    ) {
        symbols.variables.forEach { variable ->
            val lookupText = if (stripSigil) variable.removePrefix("$") else variable
            result.addElement(
                PrioritizedLookupElement.withPriority(
                    LookupElementBuilder.create(lookupText)
                        .withPresentableText(variable)
                        .withTypeText("variable", true)
                        .withIcon(AllIcons.Nodes.Variable),
                    85.0,
                )
            )
        }
    }

    private fun addFunctions(symbols: ViperCollectedSymbols, result: CompletionResultSet) {
        symbols.functions.forEach { function ->
            result.addElement(
                PrioritizedLookupElement.withPriority(
                    LookupElementBuilder.create(function)
                        .withTailText("()", true)
                        .withTypeText("function", true)
                        .withIcon(AllIcons.Nodes.Function)
                        .withInsertHandler(FunctionInsertHandler),
                    95.0,
                )
            )
        }
    }

    private fun addSnippets(result: CompletionResultSet) {
        ViperSnippets.items.forEach { snippet ->
            result.addElement(
                PrioritizedLookupElement.withPriority(
                    LookupElementBuilder.create(snippet.lookupText)
                        .withPresentableText(snippet.label)
                        .withTailText(snippet.tailText, true)
                        .withTypeText("snippet", true)
                        .withIcon(AllIcons.Actions.ListFiles)
                        .withInsertHandler(SnippetInsertHandler(snippet.insertText)),
                    60.0,
                )
            )
        }
    }

    private fun addImportCompletions(
        file: com.intellij.psi.PsiFile,
        context: CompletionContext,
        result: CompletionResultSet,
    ) {
        val virtualFile = file.virtualFile ?: return
        val baseDir = virtualFile.parent ?: return
        val currentPrefix = context.importPathPrefix
        val slashIndex = currentPrefix.lastIndexOf('/')
        val directoryPrefix = if (slashIndex >= 0) currentPrefix.substring(0, slashIndex + 1) else ""
        val filePrefix = currentPrefix.substring(slashIndex + 1)
        val lookupDirPath = baseDir.toNioPath().resolve(directoryPrefix).normalize()
        val lookupDir = LocalFileSystem.getInstance().findFileByNioFile(lookupDirPath) ?: return

        lookupDir.children
            .sortedBy { it.name.lowercase() }
            .filter { child ->
                child.isDirectory || child.extension == "vp"
            }
            .filter { child ->
                child.name.startsWith(filePrefix)
            }
            .forEach { child ->
                val relativeName = directoryPrefix + child.name + if (child.isDirectory) "/" else ""
                result.addElement(
                    PrioritizedLookupElement.withPriority(
                        LookupElementBuilder.create(relativeName)
                            .withTypeText(if (child.isDirectory) "dir" else "import", true)
                            .withIcon(if (child.isDirectory) PlatformIcons.FOLDER_ICON else ViperIcons.FILE),
                        if (child.isDirectory) 110.0 else 100.0,
                    )
                )
            }
    }

    private data class CompletionContext(
        val afterVariableSigil: Boolean,
        val afterTypeSeparator: Boolean,
        val inImportString: Boolean,
        val importPathPrefix: String,
    ) {
        companion object {
            fun from(text: String, offset: Int): CompletionContext {
                val safeOffset = offset.coerceIn(0, text.length)
                val prefix = text.substring(0, safeOffset)
                val trimmedPrefix = prefix.trimEnd()
                val afterVariableSigil = trimmedPrefix.endsWith("$")
                val afterTypeSeparator = trimmedPrefix.endsWith(":")
                val importQuoteIndex = prefix.lastIndexOf("import \"")
                val inImportString = importQuoteIndex >= 0 && prefix.indexOf('"', importQuoteIndex + 8) == -1
                val importPathPrefix = if (inImportString) prefix.substring(importQuoteIndex + 8) else ""

                return CompletionContext(
                    afterVariableSigil = afterVariableSigil,
                    afterTypeSeparator = afterTypeSeparator,
                    inImportString = inImportString,
                    importPathPrefix = importPathPrefix,
                )
            }
        }
    }

    private object FunctionInsertHandler : InsertHandler<com.intellij.codeInsight.lookup.LookupElement> {
        override fun handleInsert(
            context: com.intellij.codeInsight.completion.InsertionContext,
            item: com.intellij.codeInsight.lookup.LookupElement,
        ) {
            val document = context.document
            val tailOffset = context.tailOffset
            val chars = document.charsSequence

            if (tailOffset < chars.length && chars[tailOffset] == '(') {
                context.editor.caretModel.moveToOffset(tailOffset + 1)
                return
            }

            document.insertString(tailOffset, "()")
            context.editor.caretModel.moveToOffset(tailOffset + 1)
        }
    }

    private class SnippetInsertHandler(private val insertText: String) :
        InsertHandler<com.intellij.codeInsight.lookup.LookupElement> {
        override fun handleInsert(
            context: com.intellij.codeInsight.completion.InsertionContext,
            item: com.intellij.codeInsight.lookup.LookupElement,
        ) {
            val startOffset = context.startOffset
            val tailOffset = context.tailOffset
            context.document.replaceString(startOffset, tailOffset, insertText)
            val placeholderOffset = insertText.indexOf("()")
            val caretOffset = when {
                placeholderOffset >= 0 -> startOffset + placeholderOffset + 1
                else -> startOffset + insertText.length
            }
            context.editor.caretModel.moveToOffset(caretOffset)
        }
    }
}
