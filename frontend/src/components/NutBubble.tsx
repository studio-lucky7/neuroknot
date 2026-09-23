import { Image } from 'expo-image';
import type { ReactNode } from 'react';
import { View } from 'react-native';

const TONES = {
  white: 'bg-white border-brand-line',
  sand: 'bg-brand-sand border-brand-border',
} as const;

type Props = {
  children: ReactNode;
  tone?: keyof typeof TONES;
};

// 너트 캐릭터 + 말풍선 (온보딩 질문, 퀴즈 문제)
export function NutBubble({ children, tone = 'white' }: Props) {
  return (
    <View className="flex-row items-start gap-3">
      <View className="h-14 w-14 items-center justify-center overflow-hidden rounded-full border border-brand-line bg-white">
        <Image
          source={require('@/assets/images/nut-chat.png')}
          style={{ width: 40, height: 40 }}
          contentFit="contain"
          accessibilityLabel="너트 캐릭터"
        />
      </View>

      <View className={`relative flex-1 rounded-3xl border p-5 ${TONES[tone]}`}>
        {/* 말풍선 꼬리 */}
        <View
          className={`absolute -left-[7px] top-5 h-3.5 w-3.5 rotate-45 border-b border-l ${TONES[tone]}`}
        />
        {children}
      </View>
    </View>
  );
}
