'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Star, ChevronLeft, Lightbulb } from 'lucide-react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

// 지문 및 퀴즈 데이터
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
    options: ["비타민C", "베타글루칸", "셀레늄", "콜라겐"],
    answer: "베타글루칸"
  },
  explanation: `정답은 '베타글루칸'입니다.\n\n지문의 세 번째 단락에 따르면, 꽃송이버섯은 건조물 기준 베타글루칸 함량이 40% 이상인 고기능성 버섯이라고 명시되어 있습니다. 꽃송이버섯은 이러한 높은 베타글루칸 함량 덕분에 기존에는 주로 면역 증진 소재로 주목받아 왔습니다.`
};

export default function ReadingPage() {
  const router = useRouter();
  const [isQuizMode, setIsQuizMode] = useState(false);
  const [isExplanationMode, setIsExplanationMode] = useState(false);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);

  // 배경색 유지 및 테마 강제 적용
  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = `body { background-color: #FFF9F0 !important; }`;
    document.head.appendChild(style);
    return () => { document.head.removeChild(style); };
  }, []);

  // 정답 확인 로직
  const handleCheckAnswer = () => {
    if (!selectedOption) return;
    const correct = selectedOption === MOCK_DATA.quiz.answer;
    setIsCorrect(correct);
    setShowResult(true);
  };

  // ✅ [핵심 기능] 학습 완료 처리: localStorage에 상태 기록 후 대시보드로 이동
  const handleFinishStudy = () => {
    localStorage.setItem('isStudyDone', 'true'); // 대시보드에서 이 값을 감지합니다.
    router.push('/dashboard');
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#FFF9F0] text-[#3D2B1F] font-sans pb-32">
      
      {/* 1. 상단 헤더 */}
      <header className="max-w-4xl mx-auto w-full px-6 md:px-12 pt-12 flex justify-between items-center h-20 relative z-20">
        <button 
            onClick={() => router.back()} 
            aria-label="이전 페이지로 돌아가기"
            className="w-10 h-10 flex items-center justify-center rounded-full bg-white shadow-sm hover:bg-[#FDF4E7] transition-colors text-[#8C7B6E]"
        >
            <ChevronLeft size={24} />
        </button>
        
        <div className="flex flex-col items-center">
          <span className="text-[20px] font-black text-[#FFB800] tracking-widest uppercase mb-1">
            {MOCK_DATA.category}
          </span>
          <div className="flex gap-0.5">
            {[...Array(5)].map((_, i) => (
              <Star key={i} size={15} fill={i < MOCK_DATA.difficulty ? "#FFB800" : "transparent"} strokeWidth={3} className="text-[#FFB800]" />
            ))}
          </div>
        </div>
        
        <div className="w-10" />
      </header>

      {/* 2. 메인 아티클 카드 (너비 85% 중앙 집중형) */}
      <article className="max-w-4xl mx-auto w-full px-6 md:px-12 mt-6 flex-1 flex flex-col relative z-10">
        <div className="w-[85%] mx-auto bg-white rounded-[40px] p-8 md:p-14 shadow-sm border border-[#F0E5D8] flex-1 relative flex flex-col min-h-[500px]">
          
          <AnimatePresence mode="wait">
            {isExplanationMode ? (
              // [해설 모드]
              <motion.div key="explanation" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col h-full">
                <div className="flex items-center gap-3 mb-8 text-[#FFB800]">
                  <Lightbulb size={24} strokeWidth={3} />
                  <span className="text-sm font-black tracking-widest uppercase">독해 요약 분석</span>
                </div>
                <h1 className="text-2xl font-black text-[#3D2B1F] mb-6">해설 분석</h1>
                <div className="space-y-6 text-lg leading-relaxed text-[#5D4B3E] whitespace-pre-wrap font-medium">
                  {MOCK_DATA.explanation}
                </div>
              </motion.div>
            ) : !isQuizMode ? (
              // [지문 읽기 모드]
              <motion.div key="reading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col h-full">
                 <div className="space-y-8 text-[19px] leading-[1.8] text-[#5D4B3E] font-medium">
                  {MOCK_DATA.content.split('\n\n').map((paragraph, index) => (
                    <p key={index} className="hover:text-[#3D2B1F] transition-colors duration-300 cursor-default">
                      {paragraph}
                    </p>
                  ))}
                
                {/* 저작권 표시 섹션 */}
                <div style={{ position: 'relative', marginTop: '40px' }}>
                  <div style={{ position: 'absolute' }}>
                    <a href="http://www.kogl.or.kr/info/licenseType1.do" target="_blank" rel="noopener noreferrer">
                      <img alt="제1유형" src="http://www.kogl.or.kr/open/web/images/images_2014/codetype/new_img_opentype01.png" />
                    </a>
                  </div>
                  <div style={{ paddingLeft: '195px', fontSize: '14px', color: '#8C7B6E', lineHeight: '1.6' }}>
                    본 저작물은 "공공누리" <a href="http://www.kogl.or.kr/info/licenseType1.do" target="_blank" rel="noopener noreferrer" className="underline">제1유형:출처표시</a> 조건에 따라 이용 할 수 있습니다.
                  </div>
                </div>
                </div>
              </motion.div>
            ) : (
              // [퀴즈 모드: 너트_채팅 캐릭터 적용]
              <motion.div key="quiz" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="flex flex-col items-center justify-center h-full">
                <div className="flex items-start gap-6 mb-12 w-full">
                  <div className="w-16 h-16 bg-[#FFF9F0] rounded-full border border-[#F0E5D8] flex items-center justify-center shadow-sm overflow-hidden flex-shrink-0 relative">
                    <Image src="/images/너트_채팅.png" alt="Nutty" fill className="object-contain p-2" />
                  </div>
                  
                  <div className="relative bg-[#FDF4E7] rounded-3xl p-6 border border-[#F0E5D8] shadow-sm max-w-lg">
                    <p className="text-[#3D2B1F] font-bold leading-relaxed text-lg">
                      {MOCK_DATA.quiz.question}
                    </p>
                    <div className="absolute top-6 -left-2 w-4 h-4 bg-[#FDF4E7] border-l border-b border-[#F0E5D8] rotate-45" />
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 w-full max-w-xl">
                  {MOCK_DATA.quiz.options.map((option) => (
                    <button
                      key={option}
                      onClick={() => setSelectedOption(option)}
                      className={`
                        py-5 px-8 rounded-3xl border-2 font-black text-lg transition-all text-left
                        ${selectedOption === option 
                          ? 'border-[#FFB800] bg-[#FFB800]/5 text-[#3D2B1F] shadow-sm' 
                          : 'border-[#E5E5E5] bg-white text-[#8C7B6E] hover:border-[#FFB800]/30 hover:bg-[#FFF9F0]'
                        }
                      `}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* 3. 하단 액션 버튼 영역 */}
        <div className="mt-10 flex justify-center pb-20">
          {isExplanationMode ? (
            <ActionButton onClick={handleFinishStudy} label="학습 완료" />
          ) : !isQuizMode ? (
            <ActionButton onClick={() => setIsQuizMode(true)} label="읽기 완료" />
          ) : (
            <ActionButton onClick={handleCheckAnswer} label="정답 확인" disabled={!selectedOption} />
          )}
        </div>
      </article>

      {/* 4. 결과 모달 */}
      <AnimatePresence>
        {showResult && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-[#3D2B1F]/60 backdrop-blur-sm flex items-center justify-center p-6">
            <motion.div initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} className="bg-white rounded-[40px] p-10 md:p-12 max-w-md w-full flex flex-col items-center text-center shadow-2xl border border-[#F0E5D8]">
              
              {/* ✅ 이모지 대신 이미지 적용 */}
              <div className="relative w-40 h-40 mb-6">
                <Image 
                  src={isCorrect ? "/images/ok.png" : "/images/no.png"} 
                  alt={isCorrect ? "Correct" : "Incorrect"} 
                  fill 
                  className="object-contain"
                />
              </div>

              <h3 className={`text-3xl font-black mb-10 uppercase tracking-tighter ${isCorrect ? 'text-[#FFB800]' : 'text-red-400'}`}>
                {isCorrect ? '정답!' : '오답'}
              </h3>

              <div className="flex flex-col gap-3 w-full">
                {isCorrect ? (
                  <>
                    <button onClick={() => { setShowResult(false); setIsExplanationMode(true); }} className="w-full py-4 bg-[#FFB800] text-white rounded-2xl font-black text-lg shadow-lg shadow-orange-200/50 hover:bg-[#FFA500] transition-colors">해설 보기</button>
                    <button onClick={handleFinishStudy} className="w-full py-4 border-2 border-[#E5E5E5] text-[#8C7B6E] rounded-2xl font-black text-lg hover:bg-zinc-50 transition-colors">학습 완료</button>
                  </>
                ) : (
                  <>
                    <button onClick={() => setShowResult(false)} className="w-full py-4 bg-[#FFB800] text-white rounded-2xl font-black text-lg shadow-lg shadow-orange-200/50 hover:bg-[#FFA500] transition-colors">다시 풀기</button>
                    <button onClick={() => { setShowResult(false); setIsExplanationMode(true); }} className="w-full py-4 border-2 border-[#E5E5E5] text-[#8C7B6E] rounded-2xl font-black text-lg hover:bg-zinc-50 transition-colors">해설 보기</button>
                  </>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 배경 장식 원형 */}
      <div className="fixed bottom-[-150px] left-1/2 -translate-x-1/2 w-[120%] aspect-square bg-white rounded-full z-0 opacity-40 pointer-events-none" />
    </div>
  );
}

/**
 * 공통 액션 버튼 컴포넌트
 */
const ActionButton = ({ onClick, label, disabled = false }: { onClick: () => void, label: string, disabled?: boolean }) => (
  <motion.button
    whileHover={!disabled ? { scale: 1.05 } : {}}
    whileTap={!disabled ? { scale: 0.95 } : {}}
    onClick={onClick}
    disabled={disabled}
    className={`
      px-20 py-5 rounded-[24px] font-black text-xl shadow-xl transition-all
      ${disabled 
        ? 'bg-[#CCCCCC] text-white cursor-not-allowed shadow-none opacity-50' 
        : 'bg-[#FFB800] text-white shadow-orange-200/30 hover:bg-[#FFA500]'
      }
    `}
  >
    {label}
  </motion.button>
);