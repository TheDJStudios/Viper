package dev.viper.idea

data class ViperSnippet(
    val label: String,
    val insertText: String,
    val tailText: String,
)

object ViperSnippets {
    val items = listOf(
        ViperSnippet(
            label = "if",
            insertText = "if () {\n    \n}",
            tailText = " control flow",
        ),
        ViperSnippet(
            label = "else if",
            insertText = "else if () {\n    \n}",
            tailText = " control flow",
        ),
        ViperSnippet(
            label = "else",
            insertText = "else {\n    \n}",
            tailText = " control flow",
        ),
        ViperSnippet(
            label = "print",
            insertText = "print();",
            tailText = " builtin",
        ),
        ViperSnippet(
            label = "import",
            insertText = "import \"\";",
            tailText = " statement",
        ),
        ViperSnippet(
            label = "variable",
            insertText = "\$ name: int = ;",
            tailText = " declaration",
        ),
        ViperSnippet(
            label = "function",
            insertText = "int name() {\n    return 0;\n}",
            tailText = " definition",
        ),
        ViperSnippet(
            label = "main",
            insertText = "int main() {\n    return 0;\n}",
            tailText = " entrypoint",
        ),
    )
}
