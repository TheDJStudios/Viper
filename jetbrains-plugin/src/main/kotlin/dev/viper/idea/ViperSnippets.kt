package dev.viper.idea

data class ViperSnippet(
    val label: String,
    val lookupText: String,
    val insertText: String,
    val tailText: String,
)

object ViperSnippets {
    val items = listOf(
        ViperSnippet(
            label = "if",
            lookupText = "if",
            insertText = "if () {\n    \n}",
            tailText = " control flow",
        ),
        ViperSnippet(
            label = "else if",
            lookupText = "elif",
            insertText = "else if () {\n    \n}",
            tailText = " control flow",
        ),
        ViperSnippet(
            label = "else",
            lookupText = "else",
            insertText = "else {\n    \n}",
            tailText = " control flow",
        ),
        ViperSnippet(
            label = "print",
            lookupText = "print",
            insertText = "print();",
            tailText = " builtin",
        ),
        ViperSnippet(
            label = "import",
            lookupText = "import",
            insertText = "import \"\";",
            tailText = " statement",
        ),
        ViperSnippet(
            label = "variable",
            lookupText = "var",
            insertText = "\$ name: int = ;",
            tailText = " declaration",
        ),
        ViperSnippet(
            label = "function",
            lookupText = "fn",
            insertText = "int name() {\n    return 0;\n}",
            tailText = " definition",
        ),
        ViperSnippet(
            label = "main",
            lookupText = "main",
            insertText = "int main() {\n    return 0;\n}",
            tailText = " entrypoint",
        ),
    )
}
