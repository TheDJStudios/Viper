# Viper JetBrains Plugin

This plugin adds baseline Viper language support to any JetBrains IDE built on the IntelliJ Platform.

Current support:

- `.vp` file recognition
- syntax highlighting
- richer token coloring for types, builtins, variables, function calls, and literals
- line comments with `%`
- brace matching
- auto-indent on Enter, including block bodies
- context-aware completion for imports, types, functions, variables, builtins, and snippets
- basic PSI/parser wiring so files open as a real language, not plain text

## Build

From `jetbrains-plugin/`:

```sh
./gradlew buildPlugin
```

The built plugin zip will be under `build/distributions/`.

## Run In Sandbox IDE

```sh
./gradlew runIde
```

## Install

In any JetBrains IDE:

1. Open `Settings` / `Preferences`
2. Go to `Plugins`
3. Click the gear icon
4. Choose `Install Plugin from Disk...`
5. Select the built zip from `build/distributions/`
