import { Tabs } from 'expo-router';
import { BookOpen, Trophy, User } from 'lucide-react-native';

import { brand } from '@/constants/brand';

// 웹 버전 왼쪽 사이드바(GNB)의 학습 · 리그 · 프로필 → 하단 탭
// 더보기(세팅 · 고객지원 · 로그아웃)는 프로필 → 설정 화면으로 옮겼습니다.
export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: brand.cream },
        tabBarActiveTintColor: brand.gold,
        tabBarInactiveTintColor: brand.faint,
        tabBarStyle: { backgroundColor: '#FFFFFF', borderTopColor: brand.border },
        tabBarLabelStyle: { fontSize: 12, fontWeight: '800' },
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: '학습',
          tabBarIcon: ({ color, size }) => <BookOpen color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="league"
        options={{
          title: '리그',
          tabBarIcon: ({ color, size }) => <Trophy color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: '프로필',
          tabBarIcon: ({ color, size }) => <User color={color} size={size} />,
        }}
      />
    </Tabs>
  );
}
