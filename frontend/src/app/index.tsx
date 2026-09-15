import { Brain, Sparkles } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function HomeScreen() {
  return (
    <SafeAreaView className="flex-1 bg-brand-cream">
      <View className="flex-1 items-center justify-center gap-6 px-8">
        <View className="h-20 w-20 items-center justify-center rounded-3xl bg-brand-gold">
          <Brain size={40} color="#3D2B1F" />
        </View>

        <View className="items-center gap-2">
          <Text className="text-3xl font-black tracking-tight text-brand-ink">
            NeuroKnots
          </Text>
          <Text className="text-center text-base font-medium text-brand-muted">
            읽는 것만으로 단단해지는 뇌
          </Text>
        </View>

        <Pressable className="mt-4 flex-row items-center gap-2 rounded-full bg-brand-gold px-6 py-4 active:opacity-80">
          <Sparkles size={18} color="#3D2B1F" />
          <Text className="text-base font-black text-brand-ink">학습 시작하기</Text>
        </Pressable>

        <Text className="mt-2 text-xs text-brand-faint">NativeWind 파이프라인 정상 ✓</Text>
      </View>
    </SafeAreaView>
  );
}
