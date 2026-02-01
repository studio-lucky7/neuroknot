'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ChevronRight } from 'lucide-react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

export default function DashboardPage() {
  const router = useRouter();
  const [done, setDone] = useState(false);
  const [streak, setStreak] = useState(0);

  useEffect(() => {
    // 1. 학습 완료 여부 및 연속 학습 데이터 확인 (localStorage)
    const isStudyCompleted = localStorage.getItem('isStudyDone') === 'true';
    
    if (isStudyCompleted) {
      setDone(true);
      setStreak(1); // 학습 완료 시 1일로 표시
    } else {
      setDone(false);
      setStreak(0);
    }

    // 2. 배경색 테마 유지
    const style = document.createElement('style');
    style.textContent = `
      body {
        background-color: #FFF9F0 !important;
      }
    `;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  const today = new Date('2026-02-01');
  const dateString = today.toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  });

  return (
    <div className="flex flex-col min-h-screen bg-[#FFF9F0] text-[#3D2B1F] font-sans">
      
      {/* 1. 상단 헤더 영역 */}
      <header className="max-w-4xl mx-auto w-full px-6 md:px-12 pt-12 flex justify-between items-center text-sm font-bold text-[#8C7B6E]">
        <div>{dateString}</div>
        <div className="flex items-center gap-2 cursor-pointer hover:text-[#3D2B1F] transition-colors">
          연속 학습: <span className="text-[#FFB800]">{streak} 일</span>
          <ChevronRight size={16} />
        </div>
      </header>

      {/* 2. 상태 인디케이터 섹션 */}
      <section className="max-w-4xl mx-auto w-full px-6 md:px-12 mt-6 flex justify-center">
        <Image 
          src={done ? "/images/학습후후.png" : "/images/학습전.png"} 
          alt="학습 상태 인디케이터"
          width={500}
          height={100}
          priority
          className="object-contain"
        />
      </section>

      {/* 3. 메인 캐릭터 & 인터랙션 영역 */}
      <section className="flex-1 flex flex-col items-center justify-center relative z-10 -mt-10">
        <motion.div 
          animate={{ y: [0, -10, 0] }}
          transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
          className="mb-8 relative w-56 h-56" 
        >
          {/* ✅ 학습 완료 여부에 따라 너트 이미지 교체 */}
          <Image 
            src={done ? "/images/학습후너트.png" : "/images/너트.png"} 
            alt="메인 캐릭터 너트"
            fill 
            priority 
            className="object-contain"
          />
        </motion.div>

        <div className="text-center mb-10">
          <h2 className="text-xl font-black text-[#4A3427] tracking-tight uppercase">
            {done ? "오늘의 학습 완료했습니다!" : "오늘의 학습을 시작할까요?"}
          </h2>
        </div>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => router.push('/reading')}
          className="bg-[#FFB800] hover:bg-[#FFA500] text-white px-16 py-5 rounded-3xl font-black text-lg shadow-lg shadow-orange-200/50 transition-all"
        >
          {done ? "추가 학습하기" : "학습 시작하기"}
        </motion.button>
      </section>

      {/* 하단 장식 배경 */}
      <div className="fixed bottom-[-150px] left-1/2 -translate-x-1/2 w-[120%] aspect-square bg-white rounded-full z-0 opacity-50 pointer-events-none" />
    </div>
  );
}