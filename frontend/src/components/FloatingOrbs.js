import React, { useRef, useEffect } from 'react';
import { View, Animated, StyleSheet, Dimensions } from 'react-native';

const { width: W, height: H } = Dimensions.get('window');

const ORBS = [
  { rx: 0.12, ry: 0.10, size: 160, dur: 4200, delay: 0    },
  { rx: 0.80, ry: 0.06, size: 100, dur: 5600, delay: 800  },
  { rx: 0.50, ry: 0.40, size: 190, dur: 3900, delay: 400  },
  { rx: 0.05, ry: 0.68, size: 120, dur: 6100, delay: 1200 },
  { rx: 0.88, ry: 0.52, size: 140, dur: 4700, delay: 600  },
  { rx: 0.38, ry: 0.88, size: 110, dur: 5200, delay: 1600 },
];

/**
 * Softly pulsing, drifting circle orbs rendered behind content.
 * lightMode=true → very faint indigo on white/light background
 * lightMode=false → slightly brighter on dark background
 */
export default function FloatingOrbs({ lightMode = false }) {
  const anims = useRef(ORBS.map((_, i) => new Animated.Value(i % 2 === 0 ? 0 : 1))).current;

  useEffect(() => {
    const loops = anims.map((anim, i) => {
      const start = i % 2 === 0 ? 0 : 1;
      const end   = 1 - start;
      return Animated.loop(
        Animated.sequence([
          Animated.delay(ORBS[i].delay),
          Animated.timing(anim, { toValue: end,   duration: ORBS[i].dur, useNativeDriver: true }),
          Animated.timing(anim, { toValue: start, duration: ORBS[i].dur, useNativeDriver: true }),
        ])
      );
    });
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, []);

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      {ORBS.map((orb, i) => (
        <Animated.View
          key={i}
          style={{
            position: 'absolute',
            left:   orb.rx * W - orb.size / 2,
            top:    orb.ry * H - orb.size / 2,
            width:  orb.size,
            height: orb.size,
            borderRadius: orb.size / 2,
            backgroundColor: lightMode ? '#0F766E' : '#2DD4BF',
            opacity: anims[i].interpolate({
              inputRange:  [0, 1],
              outputRange: lightMode ? [0.025, 0.055] : [0.05, 0.13],
            }),
            transform: [
              {
                translateY: anims[i].interpolate({
                  inputRange: [0, 1], outputRange: [0, -22],
                }),
              },
              {
                scale: anims[i].interpolate({
                  inputRange: [0, 1], outputRange: [0.82, 1.18],
                }),
              },
            ],
          }}
        />
      ))}
    </View>
  );
}
