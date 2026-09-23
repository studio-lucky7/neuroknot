import { Stack } from 'expo-router';

import { brand } from '@/constants/brand';

export const unstable_settings = {
  initialRouteName: 'categories',
};

export default function OnboardingLayout() {
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: brand.cream } }}>
      <Stack.Screen name="categories" />
      <Stack.Screen name="levels" />
    </Stack>
  );
}
