plugins {
    kotlin("jvm") version "1.9.24"
    id("org.jetbrains.intellij.platform") version "2.0.1"
}

group = "dev.viper"
version = "0.1.6"

repositories {
    mavenCentral()

    intellijPlatform {
        defaultRepositories()
    }
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation("org.json:json:20240303")

    intellijPlatform {
        create("IC", "2024.1.7")
        instrumentationTools()
    }
}

tasks.processResources {
    from(projectDir.parentFile.resolve("assets/logo.svg")) {
        into("META-INF")
        rename { "pluginIcon.svg" }
    }

    from(projectDir.parentFile.resolve("assets/logo.svg")) {
        into("icons")
        rename { "viper.svg" }
    }
}

intellijPlatform {
    pluginConfiguration {
        ideaVersion {
            sinceBuild = "241"
            untilBuild = "261.*"
        }
    }
}
