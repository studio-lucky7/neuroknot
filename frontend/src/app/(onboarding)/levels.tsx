import { useLocalSearchParams, useRouter } from 'expo-router';
import { ChevronRight } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { NutBubble } from '@/components/NutBubble';
import { PrimaryButton } from '@/components/PrimaryButton';
import { StepIndicator } from '@/components/StepIndicator';
import { brand } from '@/constants/brand';
import { ENGINE_LEVELS } from '@/constants/levels';
import { useAppState } from '@/lib/app-state';

export default function LevelSelectScreen() {
  const router = useRouter();
  const { completeOnboarding } = useAppState();
  const params = useLocalSearchParams<{ categories?: string }>();
  const categories = (params.categories ?? '').split(',').filter(Boolean);
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);

  // 저장되면 루트 레이아웃이 온보딩 완료를 감지해 학습 탭으로 넘겨줍니다
  const handleNext = () => {
    if (!selectedLevel) return;
    if (categories.length === 0) {
      router.replace('/categories');
      return;
    }
    completeOnboarding({ categories, level: selectedLevel });
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: brand.cream }}>
      <ScrollView contentContainerClassName="gap-5 px-5 pb-6 pt-4">
        <StepIndicator current={2} />

        <View className="gap-6 rounded-[32px] border border-brand-border bg-brand-mist p-5">
          <NutBubble>
            <Text lineBreakStrategyIOS="hangul-word" className="text-[15px] font-bold leading-6 text-brand-ink">
              반가워요! 당신의 <Text className="text-brand-gold">독해 엔진</Text>은 평소 어떤
              상태로 작동하나요?
            </Text>
          </NutBubble>

          <View className="gap-3">
            {ENGINE_LEVELS.map((level) => {
              const selected = selectedLevel === level.id;
              return (
                <Pressable
                  key={level.id}
                  accessibilityRole="radio"
                  accessibilityState={{ selected }}
                  onPress={() => setSelectedLevel(level.id)}
                  className={`rounded-[28px] border-2 bg-white px-5 py-4 active:bg-brand-cream ${
                    selected ? 'border-brand-gold' : 'border-brand-line'
                  }`}>
                  <Text lineBreakStrategyIOS="hangul-word" className="text-[15px] font-bold leading-6">
                    <Text className={selected ? 'text-brand-gold' : 'text-brand-ink'}>
                      {level.label}:
                    </Text>
                    <Text className="font-medium text-brand-muted"> {level.desc}</Text>
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      </ScrollView>

      <View className="px-5 pb-3 pt-2">
        <PrimaryButton
          label="다음 단계로"
          icon={<ChevronRight size={20} color="#FFFFFF" />}
          disabled={!selectedLevel}
          onPress={handleNext}
        />
      </View>
    </SafeAreaView>
  );
}
