cmake_minimum_required(VERSION 3.13)
project(appmodules)

# Standard React Native application setup (handles autolinking, codegen, etc.)
include(${REACT_ANDROID_DIR}/cmake-utils/ReactNative-application.cmake)

# ── Stub libraries for React Native 0.83 ──────────────────────────────────────
# In RN 0.83, libreact_featureflagsjni and librninstance are compiled as OBJECT
# libraries and their symbols are merged into libreactnative.so at build time.
# However, SoLoader still calls loadLibrary("react_featureflagsjni") and
# loadLibrary("rninstance") at runtime and crashes if those .so files are absent.
#
# These minimal stub libraries satisfy SoLoader. Linking against `reactnative`
# ensures libreactnative.so is loaded as a transitive dependency, which in turn
# registers all the actual JNI implementations.
# ──────────────────────────────────────────────────────────────────────────────

add_library(react_featureflagsjni SHARED stubs/stub.cpp)
target_link_libraries(react_featureflagsjni reactnative)

add_library(rninstance SHARED stubs/stub.cpp)
target_link_libraries(rninstance reactnative)
