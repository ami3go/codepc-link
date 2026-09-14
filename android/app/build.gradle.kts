plugins {
    id("com.android.application")
}

android {
    namespace = "com.codepc.link"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.codepc.link"
        minSdk = 23
        targetSdk = 36
        versionCode = 2
        versionName = "0.1.0-debug.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}
