import React, { useRef, useEffect } from "react";
import { TouchableOpacity, Animated, StyleSheet } from "react-native";
import { colors } from "../theme/colors";

interface Props {
  value: boolean;
  onValueChange: (v: boolean) => void;
  activeColor?: string;
}

export default function Toggle({ value, onValueChange, activeColor = colors.accent }: Props) {
  const v = !!value;
  const anim = useRef(new Animated.Value(v ? 1 : 0)).current;

  useEffect(() => {
    Animated.spring(anim, { toValue: v ? 1 : 0, useNativeDriver: false, tension: 60, friction: 8 }).start();
  }, [v]);

  const trackBg = anim.interpolate({
    inputRange: [0, 1],
    outputRange: [colors.white10, activeColor],
  });

  const thumbX = anim.interpolate({
    inputRange: [0, 1],
    outputRange: [2, 20],
  });

  return (
    <TouchableOpacity activeOpacity={0.8} onPress={() => onValueChange(!value)}>
      <Animated.View style={[styles.track, { backgroundColor: trackBg }]}>
        <Animated.View style={[styles.thumb, { transform: [{ translateX: thumbX }] }]} />
      </Animated.View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  track: {
    width: 42, height: 24, borderRadius: 12,
    justifyContent: "center",
  },
  thumb: {
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: "#fff",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.3,
    shadowRadius: 2,
    elevation: 3,
  },
});
