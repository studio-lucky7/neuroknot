'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertCircle } from 'lucide-react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

// 카테고리 데이터
const CATEGORIES = [
  { id: 'it', label: '컴퓨터/IT' },
  { id: 'tech', label: '기술/공학' },
  { id: 'science', label: '자연과학' },
  { id: 'politics', label: '사회/정치' },
  { id: 'fashion', label: '패션/미학' },
  { id: 'philosophy', label: '인문/철학' },
  { id: 'economy', label: '경제/경영' },
  { id: 'literature', label: '언어/문학' },
  { id: 'art', label: '예술/디자인' },
];

export default function CategorySelectPage() {
  const router = useRouter();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [showWarning, setShowWarning] = useState(false);

  // 카테고리 토글 및 3개 제한 로직
  const toggleCategory = (id: string) => {
    setSelectedIds(prev => {
      if (prev.includes(id)) {
        setShowWarning(false);
        return prev.filter(i => i !== id);
      }
      if (prev.length >= 3) {
        setShowWarning(true);
        setTimeout(() => setShowWarning(false), 2000);
        return prev;
      }
      return [...prev, id];
    });
  };

  return (
    <div className="min-h-screen bg-[#FFF9F0] flex flex-col items-center justify-center p-6 md:p-12 font-sans">
      <div className="max-w-5xl w-full">
        
        {/* 1. Step Indicator (상단 단계 표시) */}
        <div className="flex gap-2 mb-6 px-2">
          <div className="w-8 h-8 rounded-full bg-[#FFB800] flex items-center justify-center text-sm font-bold text-white shadow-sm">1</div>
          <div className="w-8 h-8 rounded-full bg-[#F2F2F2] flex items-center justify-center text-sm font-bold text-[#CCCCCC]">2</div>
        </div>

        {/* 2. Main Content Card */}
        <div className="bg-[#F8F8F8] rounded-[40px] p-8 md:p-16 min-h-[550px] relative flex flex-col border border-[#F0E5D8] shadow-sm">
          
          {/* 캐릭터 및 말풍선 섹션 */}
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
                어려운 비문학 지문이나 전공 서적을 읽을 때,<br />
                당신의 <span className="text-[#FFB800]">독해 엔진</span>은 어떤 데이터를 탐색할까요?
              </p>
              <p className="text-[#8C7B6E] text-xs mt-2 font-medium italic">
                * 최대 3개의 관심 분야를 선택해 주세요.
              </p>
              {/* 말풍선 꼬리 */}
              <div className="absolute top-8 -left-2 w-4 h-4 bg-white border-l border-b border-[#E5E5E5] rotate-45" />
            </div>
          </div>

          {/* 3개 초과 선택 시 시각적 경고 */}
          <AnimatePresence>
            {showWarning && (
              <motion.div 
                initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className="absolute top-44 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 bg-red-50 text-red-500 px-4 py-2 rounded-full border border-red-100 text-xs font-bold"
              >
                <AlertCircle size={14} /> 최대 3개까지만 선택 가능합니다.
              </motion.div>
            )}
          </AnimatePresence>

          {/* 카테고리 그리드 (AI 스튜디오 디자인 반영) */}
          <div className="mt-auto flex justify-end w-full">
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 w-full max-w-2xl">
              {CATEGORIES.map((cat) => (
                <CategoryCard
                  key={cat.id}
                  label={cat.label}
                  isSelected={selectedIds.includes(cat.id)}
                  onClick={() => toggleCategory(cat.id)}
                />
              ))}
            </div>
          </div>
        </div>

        {/* 3. Footer Action (하단 버튼) */}
        <div className="mt-10 flex justify-end">
          <motion.button
            whileHover={selectedIds.length > 0 ? { scale: 1.05 } : {}}
            whileTap={selectedIds.length > 0 ? { scale: 0.95 } : {}}
            disabled={selectedIds.length === 0}
            onClick={() => router.push('/onboarding/levels')}
            className={`px-16 py-4 rounded-3xl font-black text-lg shadow-lg transition-all ${
              selectedIds.length > 0 
              ? 'bg-[#FFB800] text-white shadow-orange-200/50 cursor-pointer' 
              : 'bg-[#CCCCCC] text-white cursor-not-allowed opacity-50'
            }`}
          >
            데이터 동기화 시작하기 {'>'}
          </motion.button>
        </div>
      </div>
    </div>
  );
}

/**
 * 카테고리 개별 카드 컴포넌트
 */
function CategoryCard({ label, isSelected, onClick }: { label: string, isSelected: boolean, onClick: () => void }) {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className={`
        flex items-center gap-3 px-6 py-4 rounded-full border cursor-pointer transition-all bg-white shadow-sm
        ${isSelected 
          ? 'border-[#FFB800] ring-1 ring-[#FFB800] text-[#3D2B1F]' 
          : 'border-[#E5E5E5] text-[#8C7B6E] hover:border-[#CCCCCC]'
        }
      `}
    >
      <div className={`transition-colors ${isSelected ? 'text-[#FFB800]' : 'text-[#E5E5E5]'}`}>
        <CheckCircle2 size={20} fill={isSelected ? "currentColor" : "transparent"} strokeWidth={isSelected ? 3 : 2} />
      </div>
      <span className="font-bold text-[14px] whitespace-nowrap">{label}</span>
    </motion.div>
  );
}