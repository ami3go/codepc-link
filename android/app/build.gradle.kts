plugins {
    id("com.android.application")
}

android {
    namespace = "com.codepc.link"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.codepc.link"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0-dev"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}
