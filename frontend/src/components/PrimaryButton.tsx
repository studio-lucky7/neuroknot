import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';

type Props = {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  variant?: 'solid' | 'outline';
  icon?: ReactNode;
  className?: string;
};

// 웹 버전의 ActionButton / 모달 버튼을 합친 공통 버튼
export function PrimaryButton({
  label,
  onPress,
  disabled = false,
  variant = 'solid',
  icon,
  className = '',
}: Props) {
  const solid = variant === 'solid';
  const tone = disabled
    ? 'bg-brand-disabled opacity-50'
    : solid
      ? 'bg-brand-gold active:bg-brand-gold-deep'
      : 'border-2 border-brand-line bg-white active:bg-brand-mist';

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      onPress={onPress}
      disabled={disabled}
      className={`items-center justify-center rounded-3xl px-8 py-4 ${tone} ${className}`}
      style={solid && !disabled ? { boxShadow: '0 8px 20px -8px rgba(255, 184, 0, 0.55)' } : undefined}>
      <View className="flex-row items-center gap-2">
        <Text className={`text-lg font-black ${solid ? 'text-white' : 'text-brand-muted'}`}>
          {label}
        </Text>
        {icon}
      </View>
    </Pressable>
  );
}
