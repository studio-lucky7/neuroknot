import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import { ExternalLink, Lightbulb, Star } from 'lucide-react-native';
import { useState } from 'react';
import { Linking, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import Animated, { FadeIn, FadeInRight } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BackButton } from '@/components/BackButton';
import { DecorCircle } from '@/components/DecorCircle';
import { NutBubble } from '@/components/NutBubble';
import { PrimaryButton } from '@/components/PrimaryButton';
import { brand } from '@/constants/brand';
import { useAppState } from '@/lib/app-state';

const KOGL_TYPE1_URL = 'https://www.kogl.or.kr/info/licenseType1.do';

// 지문 및 퀴즈 데이터 (퀴즈·해설 생성 API가 붙으면 교체)
const MOCK_DATA = {
  category: '자연과학',
  difficulty: 4,
  content: `이번 연구는 꽃송이버섯의 비만 억제 효과를 분석한 결과로, 기존에 알려진 면역 증진 효능을 넘어 비만 관련 신호경로를 조절하고 에너지 대사를 개선할 수 있는 새로운 가능성을 제시했다.

연구팀은 MAPK, PI3K/AKT, JAK/STAT, AMPK, TGF-β, Wnt/β-catenin 등 비만 병태생리와 관련된 핵심 대사 신호경로를 분석하여, 이들 경로가 식욕 조절·지방세포 분화·염증반응·열 생성 등에 관여하는 역할을 규명했다. 또한 꽃송이버섯의 sparalide B가 이러한 경로를 조절하는 중요한 천연물질임을 함께 제시했다.

꽃송이버섯은 건조물 기준 베타글루칸 함량이 40% 이상인 고기능성 버섯으로, 일본과 중국 등의 시장에서는 이미 건강식품 원료로 활용되고 있다. 이번 연구는 꽃송이버섯을 면역 소재로 보던 기존의 인식을 넘어, 대사 건강 및 비만 관리 분야에서도 활용될 수 있다는 과학적 기반을 마련했다는 데 큰 의미가 있다.

…

산림청 국립산림과학원 산림미생물이용연구과 이경태 박사는 “꽃송이버섯은 대사 건강 분야에서 활용 가능성이 큰 천연 소재”라며, “이번 연구성과를 바탕으로 실용화 연구를 지속하고 현장 보급을 적극적으로 추진하겠다”고 전했다.`,
  quiz: {
    question: `다음에서 빈칸에 들어갈 말이 무엇인가요?
꽃송이버섯은 건조물 기준 ______ 함량이 40% 이상인 고기능성 버섯이다.`,
    options: ['비타민C', '베타글루칸', '셀레늄', '콜라겐'],
    answerIndex: 1,
  },
  explanation: `정답은 '베타글루칸'입니다.\n\n지문의 세 번째 단락에 따르면, 꽃송이버섯은 건조물 기준 베타글루칸 함량이 40% 이상인 고기능성 버섯이라고 명시되어 있습니다. 꽃송이버섯은 이러한 높은 베타글루칸 함량 덕분에 기존에는 주로 면역 증진 소재로 주목받아 왔습니다.`,
};

type Mode = 'reading' | 'quiz' | 'explanation';

export default function ReadingScreen() {
  const router = useRouter();
  const { markStudyDone } = useAppState();
  const [mode, setMode] = useState<Mode>('reading');
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);

  // 채점은 백엔드 연동 후 서버에서 (정답을 앱으로 내려보내지 않도록)
  const handleCheckAnswer = () => {
    if (selectedIndex === null) return;
    setIsCorrect(selectedIndex === MOCK_DATA.quiz.answerIndex);
    setShowResult(true);
  };

  const openExplanation = () => {
    setShowResult(false);
    setMode('explanation');
  };

  // 학습 완료 기록 후 학습 탭으로 복귀
  const handleFinishStudy = async () => {
    setShowResult(false);
    await markStudyDone();
    if (router.canGoBack()) router.back();
    else router.replace('/');
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: brand.cream }}>
      <DecorCircle opacity={0.4} />

      {/* 1. 상단 헤더 */}
      <View className="h-16 flex-row items-center justify-between px-5">
        <BackButton />
        <View className="items-center">
          <Text className="mb-1 text-lg font-black tracking-[2px] text-brand-gold">
            {MOCK_DATA.category}
          </Text>
          <View
            className="flex-row gap-0.5"
            accessible
            accessibilityLabel={`난이도 5점 만점에 ${MOCK_DATA.difficulty}점`}>
            {Array.from({ length: 5 }, (_, i) => (
              <Star
                key={i}
                size={14}
                color={brand.gold}
                fill={i < MOCK_DATA.difficulty ? brand.gold : 'transparent'}
                strokeWidth={2.5}
              />
            ))}
          </View>
        </View>
        <View className="w-10" />
      </View>

      {/* 2. 본문 카드 */}
      <ScrollView contentContainerClassName="px-5 pb-6 pt-2" className="flex-1">
        <View className="min-h-[440px] rounded-[32px] border border-brand-border bg-white p-6">
          <Animated.View
            key={mode}
            entering={mode === 'quiz' ? FadeInRight.duration(250) : FadeIn.duration(250)}>
            {mode === 'reading' && <PassageView />}
            {mode === 'quiz' && (
              <QuizView selectedIndex={selectedIndex} onSelect={setSelectedIndex} />
            )}
            {mode === 'explanation' && <ExplanationView />}
          </Animated.View>
        </View>
      </ScrollView>

      {/* 3. 하단 액션 버튼 (화면 아래 고정) */}
      <View className="px-5 pb-3 pt-2">
        {mode === 'reading' && (
          <PrimaryButton label="읽기 완료" onPress={() => setMode('quiz')} />
        )}
        {mode === 'quiz' && (
          <PrimaryButton
            label="정답 확인"
            onPress={handleCheckAnswer}
            disabled={selectedIndex === null}
          />
        )}
        {mode === 'explanation' && <PrimaryButton label="학습 완료" onPress={handleFinishStudy} />}
      </View>

      {/* 4. 결과 모달 */}
      <Modal
        visible={showResult}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={() => setShowResult(false)}>
        <View className="flex-1 items-center justify-center bg-brand-ink/60 p-6">
          <View className="w-full max-w-sm items-center rounded-[36px] border border-brand-border bg-white p-8">
            <Image
              source={
                isCorrect
                  ? require('@/assets/images/result-ok.png')
                  : require('@/assets/images/result-no.png')
              }
              style={{ width: 140, height: 140, marginBottom: 16 }}
              contentFit="contain"
              accessibilityLabel={isCorrect ? '정답' : '오답'}
            />
            <Text
              className={`mb-8 text-3xl font-black tracking-tighter ${isCorrect ? 'text-brand-gold' : 'text-red-400'}`}>
              {isCorrect ? '정답!' : '오답'}
            </Text>

            <View className="w-full gap-3">
              {isCorrect ? (
                <>
                  <PrimaryButton label="해설 보기" onPress={openExplanation} />
                  <PrimaryButton label="학습 완료" variant="outline" onPress={handleFinishStudy} />
                </>
              ) : (
                <>
                  <PrimaryButton label="다시 풀기" onPress={() => setShowResult(false)} />
                  <PrimaryButton label="해설 보기" variant="outline" onPress={openExplanation} />
                </>
              )}
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function PassageView() {
  return (
    <View className="gap-6">
      {MOCK_DATA.content.split('\n\n').map((paragraph, index) => (
        <Text
          key={index}
          lineBreakStrategyIOS="hangul-word"
          className="text-[17px] font-medium leading-[31px] text-brand-body">
          {paragraph}
        </Text>
      ))}

      {/* 저작권 표시 (공공누리 제1유형) */}
      <Pressable
        accessibilityRole="link"
        onPress={() => Linking.openURL(KOGL_TYPE1_URL)}
        className="mt-2 flex-row items-center gap-3 rounded-2xl border border-brand-border bg-brand-cream px-4 py-3 active:bg-brand-sand">
        <View className="rounded-md bg-brand-ink px-2 py-1">
          <Text className="text-[11px] font-black text-white">공공누리 제1유형</Text>
        </View>
        <Text className="flex-1 text-xs leading-5 text-brand-muted">
          본 저작물은 &quot;공공누리&quot; 제1유형:출처표시 조건에 따라 이용할 수 있습니다.
        </Text>
        <ExternalLink size={14} color={brand.muted} />
      </Pressable>
    </View>
  );
}

function QuizView({
  selectedIndex,
  onSelect,
}: {
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}) {
  return (
    <View className="gap-8">
      <NutBubble tone="sand">
        <Text lineBreakStrategyIOS="hangul-word" className="text-[17px] font-bold leading-7 text-brand-ink">
          {MOCK_DATA.quiz.question}
        </Text>
      </NutBubble>

      <View className="gap-3">
        {MOCK_DATA.quiz.options.map((option, index) => {
          const selected = selectedIndex === index;
          return (
            <Pressable
              key={option}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              onPress={() => onSelect(index)}
              className={`rounded-3xl border-2 px-6 py-4 ${
                selected
                  ? 'border-brand-gold bg-brand-gold/5'
                  : 'border-brand-line bg-white active:bg-brand-cream'
              }`}>
              <Text
                className={`text-lg font-black ${selected ? 'text-brand-ink' : 'text-brand-muted'}`}>
                {option}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function ExplanationView() {
  return (
    <View>
      <View className="mb-6 flex-row items-center gap-2">
        <Lightbulb size={22} color={brand.gold} strokeWidth={2.5} />
        <Text className="text-sm font-black tracking-[2px] text-brand-gold">독해 요약 분석</Text>
      </View>
      <Text className="mb-5 text-2xl font-black text-brand-ink">해설 분석</Text>
      <Text
        lineBreakStrategyIOS="hangul-word"
        className="text-[17px] font-medium leading-[30px] text-brand-body">
        {MOCK_DATA.explanation}
      </Text>
    </View>
  );
}
