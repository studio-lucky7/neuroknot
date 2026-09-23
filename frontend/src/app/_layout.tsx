import '@/global.css';

import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';

import { brand } from '@/constants/brand';
import { AppStateProvider, useAppState } from '@/lib/app-state';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  return (
    <AppStateProvider>
      <RootStack />
    </AppStateProvider>
  );
}

function RootStack() {
  const { ready, profile } = useAppState();
  const onboarded = profile !== null;

  useEffect(() => {
    if (ready) SplashScreen.hideAsync();
  }, [ready]);

  // 저장된 온보딩 정보를 읽는 동안은 스플래시 화면을 유지
  if (!ready) return null;

  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: brand.cream } }}>
        {/* 온보딩을 마친 사용자만: 하단 탭 + 탭 없이 전체 화면을 쓰는 읽기·설정 */}
        <Stack.Protected guard={onboarded}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="reading" options={{ animation: 'slide_from_bottom' }} />
          <Stack.Screen name="settings" />
        </Stack.Protected>

        {/* 처음 실행하면 온보딩부터 */}
        <Stack.Protected guard={!onboarded}>
          <Stack.Screen name="(onboarding)" />
        </Stack.Protected>
      </Stack>
    </>
  );
}
