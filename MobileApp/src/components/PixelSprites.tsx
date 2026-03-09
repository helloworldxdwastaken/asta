import React, { useEffect, useRef } from "react";
import { Animated, View, StyleSheet } from "react-native";
import Svg, { Rect } from "react-native-svg";

const SHAPES = {
  cross: [
    [0, 1, 0], [1, 1, 1], [0, 1, 0],
  ],
  diamond: [
    [0, 0, 1, 0, 0],
    [0, 1, 1, 1, 0],
    [1, 1, 1, 1, 1],
    [0, 1, 1, 1, 0],
    [0, 0, 1, 0, 0],
  ],
  heart: [
    [0, 1, 0, 1, 0],
    [1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1],
    [0, 1, 1, 1, 0],
    [0, 0, 1, 0, 0],
  ],
  star: [
    [0, 0, 1, 0, 0],
    [0, 1, 1, 1, 0],
    [1, 1, 1, 1, 1],
    [0, 1, 1, 1, 0],
    [0, 1, 0, 1, 0],
  ],
  block: [
    [1, 1, 1], [1, 0, 1], [1, 1, 1],
  ],
};

type ShapeName = keyof typeof SHAPES;

const SPRITE_CONFIGS = [
  { shape: "cross" as ShapeName, color: "#FF6B2C", x: "10%", y: "20%", size: 4, delay: 0 },
  { shape: "diamond" as ShapeName, color: "#A78BFA", x: "80%", y: "15%", size: 3, delay: 1500 },
  { shape: "heart" as ShapeName, color: "#FF3D7F", x: "65%", y: "60%", size: 3, delay: 800 },
  { shape: "star" as ShapeName, color: "#FFD700", x: "20%", y: "70%", size: 3, delay: 2200 },
  { shape: "block" as ShapeName, color: "#FF6B2C", x: "50%", y: "35%", size: 4, delay: 500 },
  { shape: "cross" as ShapeName, color: "#8B5CF6", x: "85%", y: "45%", size: 3, delay: 1800 },
];

function PixelShape({ shape, color, pixelSize }: { shape: ShapeName; color: string; pixelSize: number }) {
  const grid = SHAPES[shape];
  const w = grid[0].length * pixelSize;
  const h = grid.length * pixelSize;

  return (
    <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      {grid.map((row, ry) =>
        row.map((cell, rx) =>
          cell ? (
            <Rect
              key={`${ry}-${rx}`}
              x={rx * pixelSize}
              y={ry * pixelSize}
              width={pixelSize}
              height={pixelSize}
              fill={color}
            />
          ) : null
        )
      )}
    </Svg>
  );
}

function FloatingSprite({ shape, color, x, y, size, delay }: typeof SPRITE_CONFIGS[0]) {
  const translateY = useRef(new Animated.Value(0)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Fade in
    const fadeIn = Animated.timing(opacity, {
      toValue: 0.6,
      duration: 1000,
      delay,
      useNativeDriver: true,
    });

    // Float animation
    const float = Animated.loop(
      Animated.sequence([
        Animated.timing(translateY, { toValue: -12, duration: 3000, useNativeDriver: true }),
        Animated.timing(translateY, { toValue: 12, duration: 3000, useNativeDriver: true }),
        Animated.timing(translateY, { toValue: 0, duration: 3000, useNativeDriver: true }),
      ])
    );

    fadeIn.start(() => float.start());
    return () => { fadeIn.stop(); float.stop(); };
  }, []);

  return (
    <Animated.View
      style={[
        styles.sprite,
        { left: x as any, top: y as any, transform: [{ translateY }], opacity },
      ]}
    >
      <PixelShape shape={shape} color={color} pixelSize={size} />
    </Animated.View>
  );
}

export function PixelSprites() {
  return (
    <View style={styles.container} pointerEvents="none">
      {SPRITE_CONFIGS.map((cfg, i) => (
        <FloatingSprite key={i} {...cfg} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    overflow: "hidden",
  },
  sprite: {
    position: "absolute",
  },
});
