'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { ChevronRight } from 'lucide-react';
import Image from 'next/image';

/**
 * 독해 엔진 레벨 정의
 */
const ENGINE_LEVELS = [
  { id: 'warming', label: '예열 중', desc: '한 문장 한 문장 해석하는 데 에너지가 많이 쓰임.' },
  { id: 'driving', label: '주행 중', desc: '흐름은 따라가지만 가끔 모르는 단어에서 멈칫함.' },
  { id: 'highspeed', label: '고속 주행', desc: '문단 단위로 정보가 훅훅 들어오고 구조가 눈에 보임.' },
  { id: 'autopilot', label: '자율 주행', desc: '읽는 동시에 관련 지식들이 머릿속에서 연결됨.' },
];

export default function LevelSelectPage() {
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#FFF9F0] flex flex-col items-center justify-center p-6 md:p-12 font-sans">
      <div className="max-w-5xl w-full">
        
        {/* 1. Step Indicator (레벨 선택은 온보딩의 시작점인 Step 1) */}
        <div className="flex gap-2 mb-6 px-2">
          <div className="w-8 h-8 rounded-full bg-[#F2F2F2] flex items-center justify-center text-sm font-bold text-[#CCCCCC]">1</div>
          <div className="w-8 h-8 rounded-full bg-[#FFB800] flex items-center justify-center text-sm font-bold text-white shadow-sm">2</div>
        </div>

        {/* 2. 메인 카드 컨테이너 */}
        <div className="bg-[#F8F8F8] rounded-[40px] p-8 md:p-16 min-h-[500px] relative flex flex-col border border-[#F0E5D8] shadow-sm">
          
          {/* 캐릭터 & 질문 섹션 */}
          <div className="flex items-start gap-6 mb-12">
            <div className="w-20 h-20 bg-white rounded-full border border-[#E5E5E5] flex items-center justify-center shadow-sm flex-shrink-0 relative overflow-hidden">
                <Image 
                    src="/images/너트_채팅.png" 
                    alt="너트 캐릭터"
                    fill // 부모 컨테이너(w-20 h-20)를 가득 채웁니다.
                    className="object-contain p-2" // 이미지 비율 유지 및 약간의 여백
                    priority // 온보딩의 핵심 요소이므로 우선 로딩
                />
            </div>
            
            <div className="relative bg-white rounded-3xl p-6 border border-[#E5E5E5] shadow-sm max-w-md">
              <p className="text-[#3D2B1F] font-bold leading-relaxed">
                반가워요! 당신의 <span className="text-[#FFB800]">독해 엔진</span>은<br />
                평소 어떤 상태로 작동하나요?
              </p>
              {/* 말풍선 꼬리 */}
              <div className="absolute top-8 -left-2 w-4 h-4 bg-white border-l border-b border-[#E5E5E5] rotate-45" />
            </div>
          </div>

          {/* 레벨 선택 리스트 (수직 배치) */}
          <div className="mt-auto flex justify-end">
            <div className="flex flex-col gap-3 max-w-2xl w-full">
              {ENGINE_LEVELS.map((level) => (
                <motion.div
                  key={level.id}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => setSelectedLevel(level.id)}
                  className={`
                    flex items-center gap-4 px-8 py-5 rounded-full border cursor-pointer transition-all bg-white shadow-sm
                    ${selectedLevel === level.id 
                      ? 'border-[#FFB800] ring-1 ring-[#FFB800] text-[#3D2B1F]' 
                      : 'border-[#E5E5E5] text-[#8C7B6E] hover:border-[#CCCCCC]'
                    }
                  `}
                >
                  <span className="font-bold text-[15px] md:text-[16px] leading-tight">
                    <span className={selectedLevel === level.id ? "text-[#FFB800]" : "text-[#3D2B1F]"}>
                      {level.label}:
                    </span> 
                    <span className="ml-2 font-medium opacity-90">{level.desc}</span>
                  </span>
                </motion.div>
              ))}
            </div>
          </div>
        </div>

        {/* 3. 하단 액션 버튼 */}
        <div className="mt-10 flex justify-end">
          <motion.button
            whileHover={selectedLevel ? { scale: 1.05 } : {}}
            whileTap={selectedLevel ? { scale: 0.95 } : {}}
            disabled={!selectedLevel}
            onClick={() => router.push('/dashboard')}
            className={`flex items-center gap-2 px-16 py-4 rounded-3xl font-black text-lg shadow-lg transition-all ${
              selectedLevel 
              ? 'bg-[#FFB800] text-white shadow-orange-200/50 cursor-pointer' 
              : 'bg-[#CCCCCC] text-white cursor-not-allowed opacity-50'
            }`}
          >
            다음 단계로 <ChevronRight size={20} />
          </motion.button>
        </div>
      </div>
    </div>
  );
}