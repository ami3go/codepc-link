plugins {
    id("com.android.application")
}

android {
    namespace = "com.codepc.link"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.codepc.link"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0-dev"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}
