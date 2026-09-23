import { StyleSheet, useWindowDimensions, View } from 'react-native';

// 웹 버전 화면 하단에 깔려 있던 큰 흰색 반원 장식.
// 원이 화면보다 커서 바깥으로 넘치므로, 화면 크기 컨테이너 안에서 잘라냅니다
// (자르지 않으면 웹에서 페이지 전체가 스크롤됨).
export function DecorCircle({ opacity = 0.5 }: { opacity?: number }) {
  const { width } = useWindowDimensions();
  const size = width * 1.4;

  return (
    <View style={[StyleSheet.absoluteFill, { overflow: 'hidden', pointerEvents: 'none' }]}>
      <View
        style={{
          position: 'absolute',
          width: size,
          height: size,
          borderRadius: size / 2,
          left: (width - size) / 2,
          bottom: -size * 0.62,
          backgroundColor: '#FFFFFF',
          opacity,
        }}
      />
    </View>
  );
}
