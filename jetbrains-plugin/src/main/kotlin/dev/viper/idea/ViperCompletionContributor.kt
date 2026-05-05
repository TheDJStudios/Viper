package dev.viper.idea

import com.intellij.codeInsight.completion.CompletionContributor
import com.intellij.codeInsight.completion.CompletionParameters
import com.intellij.codeInsight.completion.CompletionProvider
import com.intellij.codeInsight.completion.CompletionResultSet
import com.intellij.codeInsight.completion.CompletionType
import com.intellij.codeInsight.lookup.LookupElementBuilder
import com.intellij.icons.AllIcons
import com.intellij.patterns.PlatformPatterns.psiElement
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

                    ViperCompletionData.KEYWORDS.forEach { keyword ->
                        result.addElement(
                            LookupElementBuilder.create(keyword)
                        )
                    }

                    ViperCompletionData.TYPES.forEach { type ->
                        result.addElement(
                            LookupElementBuilder.create(type)
                                .withTypeText("type", true)
                        )
                    }

                    ViperCompletionData.BUILTINS.forEach { builtin ->
                        result.addElement(
                            LookupElementBuilder.create(builtin)
                                .withTypeText("builtin", true)
                                .withIcon(AllIcons.Nodes.Function)
                        )
                    }

                    symbols.variables.forEach { variable ->
                        result.addElement(
                            LookupElementBuilder.create(variable)
                                .withTypeText("variable", true)
                                .withIcon(AllIcons.Nodes.Variable)
                        )
                    }

                    symbols.functions.forEach { function ->
                        result.addElement(
                            LookupElementBuilder.create("$function()")
                                .withPresentableText(function)
                                .withTailText("()", true)
                                .withTypeText("function", true)
                                .withIcon(AllIcons.Nodes.Function)
                        )
                    }

                    ViperSnippets.items.forEach { snippet ->
                        result.addElement(
                            LookupElementBuilder.create(snippet.insertText)
                                .withPresentableText(snippet.label)
                                .withTailText(snippet.tailText, true)
                                .withTypeText("snippet", true)
                        )
                    }
                }
            }
        )
    }
}
