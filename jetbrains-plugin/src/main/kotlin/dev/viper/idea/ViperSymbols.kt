package dev.viper.idea

import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.psi.PsiFile
import java.nio.file.Path
import kotlin.io.path.absolute
import kotlin.io.path.readText

data class ViperCollectedSymbols(
    val functions: Set<String>,
    val variables: Set<String>,
)

object ViperSymbols {
    private val functionRegex = Regex(
        """\b(?:int|void|float|double|str|string|char|bool|none|char\[\]|int\[\]|float\[\]|double\[\]|str\[\]|string\[\])\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)""",
    )
    private val variableRegex = Regex("""\$\s*([A-Za-z_][A-Za-z0-9_]*)\s*:""")
    private val importRegex = Regex("""import\s+"([^"]+)";""")
    private val localReferenceRegex = Regex("""(?<!\$)\b([A-Za-z_][A-Za-z0-9_]*)\b""")

    fun collect(file: PsiFile): ViperCollectedSymbols {
        val functions = linkedSetOf<String>()
        val variables = linkedSetOf<String>()

        val virtualFile = file.virtualFile ?: return ViperCollectedSymbols(functions, variables)
        val seenFiles = linkedSetOf<String>()
        collectFromPath(virtualFile.toNioPath().absolute(), seenFiles, functions, variables)

        return ViperCollectedSymbols(functions, variables)
    }

    private fun collectFromPath(
        path: Path,
        seenFiles: MutableSet<String>,
        functions: MutableSet<String>,
        variables: MutableSet<String>,
    ) {
        val normalized = path.normalize().toString()
        if (!seenFiles.add(normalized)) {
            return
        }

        val text = runCatching { path.readText() }.getOrNull() ?: return

        functionRegex.findAll(text)
            .map { it.groupValues[1] }
            .filterNot { it == "main" }
            .forEach(functions::add)

        variableRegex.findAll(text)
            .map { "\$${it.groupValues[1]}" }
            .forEach(variables::add)

        localReferenceRegex.findAll(text)
            .map { it.groupValues[1] }
            .filterNot { it in RESERVED_WORDS }
            .forEach(variables::add)

        val parent = path.parent ?: return
        importRegex.findAll(text)
            .map { it.groupValues[1] }
            .forEach { rawImport ->
                val importPath = if (rawImport.startsWith("/")) {
                    Path.of(rawImport)
                } else {
                    parent.resolve(rawImport)
                }.normalize()

                val imported = LocalFileSystem.getInstance().findFileByNioFile(importPath)
                if (imported != null) {
                    collectFromPath(importPath, seenFiles, functions, variables)
                }
            }
    }

    private val RESERVED_WORDS = (
        ViperCompletionData.KEYWORDS +
            ViperCompletionData.TYPES +
            listOf("main")
        ).toSet()
}
