/*
 * Stub library for React Native 0.83.
 *
 * In RN 0.83, libreact_featureflagsjni and librninstance are compiled as
 * OBJECT libraries and merged into libreactnative.so. However, SoLoader
 * still calls loadLibrary() for them by name at runtime.
 *
 * These stubs satisfy that requirement. Linking against reactnative ensures
 * libreactnative.so is loaded first, which registers all the actual JNI symbols.
 */
