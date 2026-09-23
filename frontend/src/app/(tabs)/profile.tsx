import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import { ChevronRight, Settings, SlidersHorizontal } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import Svg, {
  Circle,
  Defs,
  Line,
  LinearGradient,
  Path,
  Stop,
  Text as SvgText,
} from 'react-native-svg';
import { SafeAreaView } from 'react-native-safe-area-context';

import { brand } from '@/constants/brand';
import { categoryLabel } from '@/constants/categories';
import { levelLabel } from '@/constants/levels';
import { useAppState } from '@/lib/app-state';

// 주간 학습량 (학습 기록 API가 붙으면 교체)
const WEEKLY_TOTAL_DATA = [
  { day: 'SUN', count: 40 },
  { day: 'MON', count: 0 },
  { day: 'TUE', count: 0 },
  { day: 'WED', count: 0 },
  { day: 'THU', count: 0 },
  { day: 'FRI', count: 0 },
  { day: 'SAT', count: 0 },
];

const SUBSCRIPTION_DAYS_LEFT = 28;

export default function ProfileScreen() {
  const router = useRouter();
  const { profile, studyDone } = useAppState();
  const streak = studyDone ? 1 : 0;

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: brand.cream }}>
      <ScrollView contentContainerClassName="gap-4 px-5 pb-10 pt-6">
        {/* 1. 프로필 헤더 */}
        <View className="mb-2 flex-row items-center gap-5">
          <View className="h-24 w-24 items-center justify-center overflow-hidden rounded-full border-2 border-brand-border bg-white">
            <Image
              source={require('@/assets/images/nut.png')}
              style={{ width: 64, height: 64 }}
              contentFit="contain"
              accessibilityLabel="프로필 캐릭터"
            />
          </View>
          <View className="flex-1 gap-2">
            <View className="flex-row items-center gap-2">
              <Text className="text-xl font-black text-brand-ink">뉴로넛 님</Text>
              {profile && (
                <View className="rounded-full bg-brand-gold px-3 py-1">
                  <Text className="text-[11px] font-black tracking-tighter text-white">
                    {levelLabel(profile.level)}
                  </Text>
                </View>
              )}
            </View>
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push('/settings')}
              className="flex-row items-center gap-1.5 self-start py-1">
              <Text className="text-[15px] font-bold text-brand-muted">설정</Text>
              <Settings size={17} color={brand.muted} />
            </Pressable>
          </View>
        </View>

        {/* 2. 카테고리 */}
        <View className="rounded-[28px] border border-brand-border bg-white p-6">
          <View className="mb-5 flex-row items-center justify-between">
            <Text className="text-[15px] font-black text-brand-ink">카테고리</Text>
            <View className="flex-row items-center gap-1">
              <Text className="text-xs font-black text-brand-muted">필터</Text>
              <SlidersHorizontal size={13} color={brand.muted} />
            </View>
          </View>
          <View className="flex-row flex-wrap gap-2">
            {(profile?.categories ?? []).map((id) => (
              <View key={id} className="rounded-full border border-brand-line bg-white px-4 py-2">
                <Text className="text-sm font-bold text-brand-muted">{categoryLabel(id)}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* 3. 연속 학습 · 구독 */}
        <View className="flex-row gap-4">
          <StatCard title="연속 학습" value={streak} />
          <StatCard title="구독 남은 기간" value={SUBSCRIPTION_DAYS_LEFT} />
        </View>

        {/* 4. 주간 활동 차트 */}
        <View className="rounded-[32px] border border-brand-border bg-white px-4 py-6">
          <WeeklyChart />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function StatCard({ title, value }: { title: string; value: number }) {
  return (
    <View className="flex-1 justify-between gap-4 rounded-[28px] border border-brand-border bg-white p-5">
      <View className="flex-row items-center justify-between">
        <Text className="text-[14px] font-black text-brand-ink">{title}</Text>
        <ChevronRight size={18} color={brand.faint} />
      </View>
      <Text className="self-end text-[25px] font-black tracking-tighter text-brand-gold">
        {value} 일
      </Text>
    </View>
  );
}

const CHART_HEIGHT = 210;
const PAD = { top: 14, right: 14, bottom: 30, left: 36 };

function WeeklyChart() {
  const [width, setWidth] = useState(0);
  const innerWidth = Math.max(width - PAD.left - PAD.right, 0);
  const innerHeight = CHART_HEIGHT - PAD.top - PAD.bottom;
  const baseline = PAD.top + innerHeight;
  const step = innerWidth / (WEEKLY_TOTAL_DATA.length - 1);

  const points = WEEKLY_TOTAL_DATA.map((d, i) => ({
    x: PAD.left + i * step,
    y: baseline - (d.count / 100) * innerHeight,
  }));
  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${baseline} L ${points[0].x} ${baseline} Z`;

  return (
    <View
      style={{ height: CHART_HEIGHT }}
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
      accessible
      accessibilityLabel="요일별 학습량 차트">
      {width > 0 && (
        <Svg width={width} height={CHART_HEIGHT}>
          <Defs>
            <LinearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0%" stopColor={brand.gold} stopOpacity={0.15} />
              <Stop offset="100%" stopColor={brand.gold} stopOpacity={0} />
            </LinearGradient>
          </Defs>

          {/* 그리드 · 수치 라벨 */}
          {[100, 50, 0].map((val) => {
            const y = baseline - (val / 100) * innerHeight;
            return (
              <Line
                key={val}
                x1={PAD.left}
                y1={y}
                x2={PAD.left + innerWidth}
                y2={y}
                stroke="#F5F5F5"
                strokeWidth={1.5}
              />
            );
          })}
          {[100, 50, 0].map((val) => (
            <SvgText
              key={val}
              x={PAD.left - 10}
              y={baseline - (val / 100) * innerHeight + 4}
              textAnchor="end"
              fontSize={11}
              fill={brand.muted}>
              {val}
            </SvgText>
          ))}

          <Path d={areaPath} fill="url(#chartGradient)" />
          <Path
            d={linePath}
            fill="none"
            stroke={brand.gold}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {points.map((p, i) => (
            <Circle key={i} cx={p.x} cy={p.y} r={4} fill={brand.gold} stroke="#FFFFFF" strokeWidth={2.5} />
          ))}

          {/* X축 요일 */}
          {WEEKLY_TOTAL_DATA.map((d, i) => (
            <SvgText
              key={d.day}
              x={points[i].x}
              y={CHART_HEIGHT - 8}
              textAnchor="middle"
              fontSize={11}
              fill={brand.ink}>
              {d.day}
            </SvgText>
          ))}
        </Svg>
      )}
    </View>
  );
}
