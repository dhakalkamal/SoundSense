package com.soundsense.app  // ← replace with your actual application package name

import com.facebook.react.ReactPackage
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.uimanager.ViewManager

/**
 * ReactPackage wrapper — registers AudioCaptureModule with the React Native bridge.
 * Add an instance of this class to the packages list in MainApplication.kt (see README).
 */
class AudioCapturePackage : ReactPackage {
    override fun createNativeModules(ctx: ReactApplicationContext) =
        listOf(AudioCaptureModule(ctx))

    override fun createViewManagers(ctx: ReactApplicationContext): List<ViewManager<*, *>> =
        emptyList()
}
