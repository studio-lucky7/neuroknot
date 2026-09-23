import { useRouter } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';
import { Pressable } from 'react-native';

import { brand } from '@/constants/brand';

export function BackButton() {
  const router = useRouter();

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="이전 화면으로 돌아가기"
      onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))}
      className="h-10 w-10 items-center justify-center rounded-full bg-white active:bg-brand-sand"
      style={{ boxShadow: '0 1px 3px rgba(61, 43, 31, 0.08)' }}>
      <ChevronLeft size={24} color={brand.muted} />
    </Pressable>
  );
}
