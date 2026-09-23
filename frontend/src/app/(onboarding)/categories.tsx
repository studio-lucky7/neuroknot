import { useRouter } from 'expo-router';
import { ChevronRight, CircleAlert, CircleCheck } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import Animated, { FadeIn, FadeOut } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { NutBubble } from '@/components/NutBubble';
import { PrimaryButton } from '@/components/PrimaryButton';
import { StepIndicator } from '@/components/StepIndicator';
import { brand } from '@/constants/brand';
import { CATEGORIES, MAX_CATEGORIES } from '@/constants/categories';

export default function CategorySelectScreen() {
  const router = useRouter();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [showWarning, setShowWarning] = useState(false);

  // 최대 개수 초과 경고는 2초 뒤 자동으로 사라짐
  useEffect(() => {
    if (!showWarning) return;
    const timer = setTimeout(() => setShowWarning(false), 2000);
    return () => clearTimeout(timer);
  }, [showWarning]);

  const toggleCategory = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((i) => i !== id));
      setShowWarning(false);
      return;
    }
    if (selectedIds.length >= MAX_CATEGORIES) {
      setShowWarning(true);
      return;
    }
    setSelectedIds([...selectedIds, id]);
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: brand.cream }}>
      <ScrollView contentContainerClassName="gap-5 px-5 pb-6 pt-4">
        <StepIndicator current={1} />

        <View className="gap-6 rounded-[32px] border border-brand-border bg-brand-mist p-5">
          <NutBubble>
            <Text lineBreakStrategyIOS="hangul-word" className="text-[15px] font-bold leading-6 text-brand-ink">
              어려운 비문학 지문이나 전공 서적을 읽을 때, 당신의{' '}
              <Text className="text-brand-gold">독해 엔진</Text>은 어떤 데이터를 탐색할까요?
            </Text>
            <Text className="mt-2 text-xs font-medium italic text-brand-muted">
              * 최대 {MAX_CATEGORIES}개의 관심 분야를 선택해 주세요.
            </Text>
          </NutBubble>

          {showWarning && (
            <Animated.View entering={FadeIn} exiting={FadeOut} style={{ alignSelf: 'center' }}>
              <View className="flex-row items-center gap-2 rounded-full border border-red-100 bg-red-50 px-4 py-2">
                <CircleAlert size={14} color={brand.danger} />
                <Text className="text-xs font-bold text-red-500">
                  최대 {MAX_CATEGORIES}개까지만 선택 가능합니다.
                </Text>
              </View>
            </Animated.View>
          )}

          <View className="flex-row flex-wrap justify-between gap-y-3">
            {CATEGORIES.map((cat) => (
              <CategoryCard
                key={cat.id}
                label={cat.label}
                isSelected={selectedIds.includes(cat.id)}
                onPress={() => toggleCategory(cat.id)}
              />
            ))}
          </View>
        </View>
      </ScrollView>

      <View className="px-5 pb-3 pt-2">
        <PrimaryButton
          label="데이터 동기화 시작하기"
          icon={<ChevronRight size={20} color="#FFFFFF" />}
          disabled={selectedIds.length === 0}
          onPress={() =>
            router.push({ pathname: '/levels', params: { categories: selectedIds.join(',') } })
          }
        />
      </View>
    </SafeAreaView>
  );
}

function CategoryCard({
  label,
  isSelected,
  onPress,
}: {
  label: string;
  isSelected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked: isSelected }}
      onPress={onPress}
      className={`w-[48.5%] flex-row items-center gap-2 rounded-full border-2 bg-white px-4 py-3.5 active:bg-brand-cream ${
        isSelected ? 'border-brand-gold' : 'border-brand-line'
      }`}>
      <CircleCheck
        size={20}
        color={isSelected ? '#FFFFFF' : brand.line}
        fill={isSelected ? brand.gold : 'transparent'}
        strokeWidth={isSelected ? 2.5 : 2}
      />
      <Text
        numberOfLines={1}
        className={`flex-1 text-sm font-bold ${isSelected ? 'text-brand-ink' : 'text-brand-muted'}`}>
        {label}
      </Text>
    </Pressable>
  );
}
