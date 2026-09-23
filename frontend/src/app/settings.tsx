import { ChevronRight, CircleHelp, LogOut, Settings } from 'lucide-react-native';
import type { ReactNode } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BackButton } from '@/components/BackButton';
import { brand } from '@/constants/brand';
import { useAppState } from '@/lib/app-state';

// 웹 버전 사이드바의 "더보기" 메뉴 + 하단 로그아웃 버튼을 합친 화면
export default function SettingsScreen() {
  const { reset } = useAppState();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: brand.cream }}>
      <View className="h-16 flex-row items-center gap-3 px-5">
        <BackButton />
        <Text className="text-lg font-black text-brand-ink">설정</Text>
      </View>

      <ScrollView contentContainerClassName="px-5 pb-10 pt-2">
        <View className="overflow-hidden rounded-[28px] border border-brand-border bg-white py-2">
          <MenuRow icon={<Settings size={19} color={brand.faint} />} label="세팅" />
          <MenuRow icon={<CircleHelp size={19} color={brand.faint} />} label="고객지원센터" />
          <View className="mx-5 my-2 h-px bg-brand-border" />
          {/* 계정 기능 전까지는 기기에 저장된 온보딩·학습 기록을 지우고 처음 화면으로 */}
          <MenuRow
            icon={<LogOut size={19} color={brand.danger} />}
            label="로그아웃"
            danger
            onPress={reset}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function MenuRow({
  icon,
  label,
  danger = false,
  onPress,
}: {
  icon: ReactNode;
  label: string;
  danger?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      className={`flex-row items-center gap-3 px-5 py-4 ${danger ? 'active:bg-red-50' : 'active:bg-brand-sand'}`}>
      {icon}
      <Text
        className={`flex-1 text-[15px] font-bold ${danger ? 'text-red-400' : 'text-brand-muted'}`}>
        {label}
      </Text>
      {!danger && <ChevronRight size={18} color={brand.faint} />}
    </Pressable>
  );
}
