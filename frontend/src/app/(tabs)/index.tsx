import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import { ChevronRight } from 'lucide-react-native';
import { useEffect } from 'react';
import { Text, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { DecorCircle } from '@/components/DecorCircle';
import { PrimaryButton } from '@/components/PrimaryButton';
import { brand } from '@/constants/brand';
import { useAppState } from '@/lib/app-state';

export default function DashboardScreen() {
  const router = useRouter();
  const { studyDone } = useAppState();
  const streak = studyDone ? 1 : 0; // 연속 학습 기록은 백엔드 연동 후 교체

  const dateString = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  });

  // 너트가 위아래로 천천히 떠다니는 모션 (모션 줄이기 설정이면 멈춤)
  const reduceMotion = useReducedMotion();
  const floatY = useSharedValue(0);
  useEffect(() => {
    if (reduceMotion) return;
    const ease = Easing.inOut(Easing.ease);
    floatY.set(
      withRepeat(
        withSequence(
          withTiming(-10, { duration: 2000, easing: ease }),
          withTiming(0, { duration: 2000, easing: ease })
        ),
        -1
      )
    );
  }, [floatY, reduceMotion]);
  const floatStyle = useAnimatedStyle(() => ({ transform: [{ translateY: floatY.get() }] }));

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: brand.cream }}>
      <DecorCircle opacity={0.5} />

      {/* 1. 날짜 · 연속 학습 */}
      <View className="flex-row items-center justify-between px-6 pt-4">
        <Text className="text-sm font-bold text-brand-muted">{dateString}</Text>
        <View className="flex-row items-center gap-1">
          <Text className="text-sm font-bold text-brand-muted">
            연속 학습: <Text className="text-brand-gold">{streak} 일</Text>
          </Text>
          <ChevronRight size={16} color={brand.muted} />
        </View>
      </View>

      {/* 2. 요일별 학습 상태 */}
      <View className="mt-5 items-center px-6">
        <Image
          source={
            studyDone
              ? require('@/assets/images/week-after.png')
              : require('@/assets/images/week-before.png')
          }
          style={{ width: '100%', maxWidth: 500, aspectRatio: 1124 / 224 }}
          contentFit="contain"
          accessibilityLabel="이번 주 학습 상태"
        />
      </View>

      {/* 3. 캐릭터 · 시작 버튼 */}
      <View className="flex-1 items-center justify-center px-6 pb-8">
        <Animated.View style={[{ width: 200, height: 200, marginBottom: 32 }, floatStyle]}>
          <Image
            source={
              studyDone
                ? require('@/assets/images/nut-after.png')
                : require('@/assets/images/nut.png')
            }
            style={{ width: '100%', height: '100%' }}
            contentFit="contain"
            accessibilityLabel="메인 캐릭터 너트"
          />
        </Animated.View>

        <Text className="mb-8 text-xl font-black tracking-tight text-brand-ink">
          {studyDone ? '오늘의 학습 완료했습니다!' : '오늘의 학습을 시작할까요?'}
        </Text>

        <PrimaryButton
          label={studyDone ? '추가 학습하기' : '학습 시작하기'}
          onPress={() => router.push('/reading')}
          className="px-16"
        />
      </View>
    </SafeAreaView>
  );
}
