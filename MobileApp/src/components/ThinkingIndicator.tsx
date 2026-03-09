import React, { useEffect, useRef, useState } from "react";
import { Animated, View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";

const THINKING_WORDS = [
  "thinking", "pondering", "analyzing", "reasoning",
  "considering", "processing", "reflecting", "evaluating",
];

function BounceDot({ delay, color }: { delay: number; color: string }) {
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: -6, duration: 350, delay, useNativeDriver: true }),
        Animated.timing(anim, { toValue: 0, duration: 350, useNativeDriver: true }),
        Animated.delay(700),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, []);

  return (
    <Animated.View style={[styles.dot, { backgroundColor: color, transform: [{ translateY: anim }] }]} />
  );
}

export function ThinkingDots({ color = colors.violet }: { color?: string }) {
  return (
    <View style={styles.dotsRow}>
      <BounceDot delay={0} color={color} />
      <BounceDot delay={150} color={color} />
      <BounceDot delay={300} color={color} />
    </View>
  );
}

export function ThinkingWordAnimation() {
  const [wordIdx, setWordIdx] = useState(0);
  const opacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const interval = setInterval(() => {
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]).start();
      setWordIdx((i) => (i + 1) % THINKING_WORDS.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <View style={styles.wordRow}>
      <ThinkingDots />
      <Animated.Text style={[styles.wordText, { opacity }]}>
        {THINKING_WORDS[wordIdx]}
      </Animated.Text>
    </View>
  );
}

const styles = StyleSheet.create({
  dotsRow: { flexDirection: "row", alignItems: "center", gap: 3 },
  dot: { width: 5, height: 5, borderRadius: 2.5 },
  wordRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 4 },
  wordText: { fontSize: 12, color: colors.violetText, fontStyle: "italic" },
});
