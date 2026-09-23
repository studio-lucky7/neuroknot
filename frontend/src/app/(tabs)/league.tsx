import { Image } from 'expo-image';
import { Lock, ShieldCheck, TriangleAlert, Trophy, Zap } from 'lucide-react-native';
import { Fragment, useState, type ReactNode } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { DecorCircle } from '@/components/DecorCircle';
import { brand } from '@/constants/brand';

const TIERS = [
  { name: '브론즈', id: 'bronze' },
  { name: 'SILVER', id: 'silver' },
  { name: 'GOLD', id: 'gold' },
  { name: 'PLATINUM', id: 'platinum' },
  { name: 'DIAMOND', id: 'diamond' },
];

const SYSTEM_NAMES = [
  '캐스넛유저', '데이터햄스터', '로직고양이', '사이버문어', '네오펭귄',
  '조용한올빼미', '스텔스다람쥐', '공허거북이', '크롬여우', '이진곰',
  '유령강아지', '메타오리', '코발트팬더', '루트사용자', '노드친구',
];

const NUT_IMAGES = {
  nut: require('@/assets/images/nut.png'),
  perm: require('@/assets/images/nut-perm.png'),
  sunglasses: require('@/assets/images/nut-sunglasses.png'),
};

const RANK_IMAGES = [
  require('@/assets/images/rank-1.png'),
  require('@/assets/images/rank-2.png'),
  require('@/assets/images/rank-3.png'),
];

type LeagueUser = {
  id: string;
  isMe: boolean;
  name: string;
  score: number;
  nut: keyof typeof NUT_IMAGES;
};

// 점수 생성 및 캐릭터 배정 (리그 API가 붙으면 교체)
function generateLeagueUsers(): LeagueUser[] {
  const shuffle = <T,>(arr: T[]) => [...arr].sort(() => Math.random() - 0.5);

  const topPool = Array.from({ length: (550 - 50) / 10 + 1 }, (_, i) => 50 + i * 10);
  const topScores = shuffle(topPool).slice(0, 9).sort((a, b) => b - a);
  const bottomScores = shuffle([10, 15, 20, 25, 30, 35]).slice(0, 5).sort((a, b) => b - a);

  const users: LeagueUser[] = [];

  // 상위권 1~9위: 파마너트 6명, 나머지 선글라스너트
  for (let i = 0; i < 9; i++) {
    users.push({
      id: `top-${i}`,
      isMe: false,
      name: SYSTEM_NAMES[i % SYSTEM_NAMES.length],
      score: topScores[i],
      nut: i < 6 ? 'perm' : 'sunglasses',
    });
  }

  // 10위: 나
  users.push({ id: 'me', isMe: true, name: '뉴로넛 (YOU)', score: 40, nut: 'nut' });

  // 하위권 11~15위
  for (let i = 0; i < 5; i++) {
    users.push({
      id: `bottom-${i}`,
      isMe: false,
      name: SYSTEM_NAMES[(i + 9) % SYSTEM_NAMES.length],
      score: bottomScores[i],
      nut: 'sunglasses',
    });
  }

  return users;
}

export default function LeagueScreen() {
  const [users] = useState(generateLeagueUsers);

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: brand.cream }}>
      <DecorCircle opacity={0.4} />

      <ScrollView contentContainerClassName="px-5 pb-10 pt-4">
        {/* 상단 헤더 */}
        <View className="mb-6 flex-row items-center gap-2">
          <Trophy size={20} color={brand.gold} />
          <Text className="text-sm font-black tracking-[2px] text-brand-muted">리그</Text>
        </View>

        {/* 티어 (현재 티어만 공개, 나머지는 잠김) */}
        <View className="mb-8 flex-row items-end justify-between px-1">
          {TIERS.map((tier) => {
            const current = tier.id === 'bronze';
            return (
              <View
                key={tier.id}
                className="items-center gap-2"
                style={{ opacity: current ? 1 : 0.3 }}>
                <Image
                  source={
                    current
                      ? require('@/assets/images/tier-bronze.png')
                      : require('@/assets/images/tier-silver.png')
                  }
                  style={{ width: current ? 72 : 44, height: current ? 72 : 44 }}
                  contentFit="contain"
                  accessibilityLabel={current ? tier.name : '잠긴 티어'}
                />
                <View className="items-center gap-0.5">
                  <Text
                    className={`text-[12px] font-black tracking-tighter ${current ? 'text-brand-ink' : 'text-brand-faint'}`}>
                    {current ? tier.name : '??????'}
                  </Text>
                  {!current && <Lock size={11} color={brand.faint} />}
                </View>
              </View>
            );
          })}
        </View>

        {/* 랭킹 카드 */}
        <View className="rounded-[32px] border border-brand-border bg-white p-3">
          {users.map((user, idx) => (
            <Fragment key={user.id}>
              {idx === 5 && (
                <Divider
                  label="Promotion Zone"
                  color={brand.safe}
                  icon={<ShieldCheck size={13} color={brand.safe} />}
                />
              )}
              {idx === 10 && (
                <Divider
                  label="Demotion Risk"
                  color={brand.danger}
                  icon={<TriangleAlert size={13} color={brand.danger} />}
                />
              )}
              <RankRow user={user} rank={idx + 1} />
            </Fragment>
          ))}
        </View>

        {/* 하단 워터마크 */}
        <View className="mt-6 flex-row justify-between px-2">
          <Text className="text-[10px] font-black tracking-[3px] text-brand-faint">
            ENGINE SYNC: STABLE
          </Text>
          <Text className="text-[10px] font-black tracking-[3px] text-brand-faint">
            LEAGUE RANKING V2.0
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function RankRow({ user, rank }: { user: LeagueUser; rank: number }) {
  const me = user.isMe;
  return (
    <View
      className={`flex-row items-center justify-between rounded-[22px] px-4 py-3 ${me ? 'bg-brand-gold' : ''}`}
      style={me ? { boxShadow: '0 8px 20px -8px rgba(255, 184, 0, 0.6)' } : undefined}>
      <View className="flex-1 flex-row items-center gap-3">
        <View className="w-8 items-center">
          {rank <= 3 ? (
            <Image
              source={RANK_IMAGES[rank - 1]}
              style={{ width: 26, height: 26 }}
              contentFit="contain"
              accessibilityLabel={`${rank}위`}
            />
          ) : (
            <Text className={`text-base font-black ${me ? 'text-white' : 'text-brand-faint'}`}>
              {String(rank).padStart(2, '0')}
            </Text>
          )}
        </View>
        <Image source={NUT_IMAGES[user.nut]} style={{ width: 28, height: 28 }} contentFit="contain" />
        <Text
          numberOfLines={1}
          className={`flex-1 text-[15px] font-bold tracking-tight ${me ? 'text-white' : 'text-brand-ink'}`}>
          {user.name}
        </Text>
      </View>

      <View className="flex-row items-center gap-1.5">
        <Zap size={14} color={me ? '#FFFFFF' : brand.muted} fill={me ? '#FFFFFF' : 'transparent'} />
        <Text className={`text-sm font-black ${me ? 'text-white' : 'text-brand-muted'}`}>
          {user.score.toLocaleString()}
          <Text className="text-[10px] font-medium italic opacity-70"> EXP</Text>
        </Text>
      </View>
    </View>
  );
}

function Divider({ label, color, icon }: { label: string; color: string; icon: ReactNode }) {
  return (
    <View className="flex-row items-center gap-3 px-2 py-4">
      <View className="h-px flex-1" style={{ backgroundColor: color, opacity: 0.2 }} />
      <View className="flex-row items-center gap-1">
        {icon}
        <Text className="text-[10px] font-black tracking-[2px]" style={{ color }}>
          {label.toUpperCase()}
        </Text>
      </View>
      <View className="h-px flex-1" style={{ backgroundColor: color, opacity: 0.2 }} />
    </View>
  );
}
