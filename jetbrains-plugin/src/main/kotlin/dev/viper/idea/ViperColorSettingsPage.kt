package dev.viper.idea

import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.fileTypes.SyntaxHighlighter
import com.intellij.openapi.options.colors.AttributesDescriptor
import com.intellij.openapi.options.colors.ColorDescriptor
import com.intellij.openapi.options.colors.ColorSettingsPage
import javax.swing.Icon

class ViperColorSettingsPage : ColorSettingsPage {
    override fun getDisplayName(): String = "Viper"

    override fun getIcon(): Icon? = null

    override fun getHighlighter(): SyntaxHighlighter = ViperSyntaxHighlighter()

    override fun getDemoText(): String = """
        import "secondary.vp";
        
        int localValue() {
            return 4 * 5;
        }
        
        ${'$'} number: int = 5 * 3;
        ${'$'} ready: bool = true;
        
        print("Viper file successfully ran");
        print(localValue());
        
        if (ready and number == 15) {
            print("if branch");
        } else {
            % line comment
            print("else branch");
        }
    """.trimIndent()

    override fun getAdditionalHighlightingTagToDescriptorMap(): Map<String, TextAttributesKey>? = null

    override fun getAttributeDescriptors(): Array<AttributesDescriptor> = arrayOf(
        AttributesDescriptor("Keyword", ViperSyntaxHighlighter.KEYWORD),
        AttributesDescriptor("Identifier", ViperSyntaxHighlighter.IDENTIFIER),
        AttributesDescriptor("Number", ViperSyntaxHighlighter.NUMBER),
        AttributesDescriptor("String", ViperSyntaxHighlighter.STRING),
        AttributesDescriptor("Comment", ViperSyntaxHighlighter.COMMENT),
        AttributesDescriptor("Operator / sigil", ViperSyntaxHighlighter.OPERATOR),
        AttributesDescriptor("Parentheses", ViperSyntaxHighlighter.PARENTHESES),
        AttributesDescriptor("Braces / brackets", ViperSyntaxHighlighter.BRACES),
        AttributesDescriptor("Punctuation", ViperSyntaxHighlighter.PUNCTUATION),
        AttributesDescriptor("Bad character", ViperSyntaxHighlighter.BAD_CHARACTER),
    )

    override fun getColorDescriptors(): Array<ColorDescriptor> = ColorDescriptor.EMPTY_ARRAY
}
