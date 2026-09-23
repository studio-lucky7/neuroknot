import { Text, View } from 'react-native';

// 온보딩 상단 단계 표시 (1: 카테고리, 2: 레벨)
export function StepIndicator({ current }: { current: 1 | 2 }) {
  return (
    <View className="flex-row gap-2">
      {([1, 2] as const).map((step) => {
        const active = step === current;
        return (
          <View
            key={step}
            className={`h-8 w-8 items-center justify-center rounded-full ${active ? 'bg-brand-gold' : 'bg-brand-fog'}`}>
            <Text className={`text-sm font-bold ${active ? 'text-white' : 'text-brand-disabled'}`}>
              {step}
            </Text>
          </View>
        );
      })}
    </View>
  );
}
