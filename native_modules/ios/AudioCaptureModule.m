/**
 * AudioCaptureModule.m — Objective-C bridge file for AudioCaptureModule.swift.
 *
 * This file exposes the Swift class to the React Native bridge using the
 * RCT_EXTERN_MODULE / RCT_EXTERN_METHOD macros. Add both this file and
 * AudioCaptureModule.swift to your Xcode target (same target membership).
 *
 * If your project does not already have a bridging header, Xcode will prompt
 * you to create one when you add a .swift file to an Obj-C project — accept it.
 */

#import <React/RCTBridgeModule.h>
#import <React/RCTEventEmitter.h>

@interface RCT_EXTERN_MODULE(AudioCaptureModule, RCTEventEmitter)

RCT_EXTERN_METHOD(startCapture)
RCT_EXTERN_METHOD(stopCapture)

@end
