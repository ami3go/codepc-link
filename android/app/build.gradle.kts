plugins {
    id("com.android.application")
}

android {
    namespace = "com.codepc.link"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.codepc.link"
        minSdk = 28
        targetSdk = 36
        versionCode = 3
        versionName = "0.2.0-hid-debug.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}
