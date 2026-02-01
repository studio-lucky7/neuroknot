'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { 
  Settings, 
  ChevronRight, 
  SlidersHorizontal,
  Activity
} from 'lucide-react';
import Image from 'next/image';

const WEEKLY_TOTAL_DATA = [
  { day: 'SUN', count: 40 },
  { day: 'MON', count: 0 },
  { day: 'TUE', count: 0 },
  { day: 'WED', count: 0 },
  { day: 'THU', count: 0 },
  { day: 'FRI', count: 0 },
  { day: 'SAT', count: 0 },
];

const SELECTED_CATEGORIES = ["컴퓨터/IT", "사회/정치", "자연과학"];

export default function ProfilePage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const style = document.createElement('style');
    style.textContent = `
      body {
        background-color: #FFF9F0 !important;
        font-family: 'Pretendard', sans-serif;
      }
    `;
    document.head.appendChild(style);
    return () => { document.head.removeChild(style); };
  }, []);

  // 차트 사이즈 수치 보정 (기본 코드 기준)
  const chartWidth = 800;
  const chartHeight = 280;
  const padding = 50;
  const innerWidth = chartWidth - padding * 2;
  const innerHeight = chartHeight - padding * 2;

  const points = WEEKLY_TOTAL_DATA.map((d, i) => ({
    x: padding + (i * (innerWidth / (WEEKLY_TOTAL_DATA.length - 1))),
    y: (padding + innerHeight) - (d.count / 100) * innerHeight
  }));

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${padding + innerHeight} L ${points[0].x} ${padding + innerHeight} Z`;

  if (!mounted) return null;

  return (
    <div className="flex min-h-screen bg-[#FFF9F0] !text-[#3D2B1F]">
      
      {/* 1. 사이드바 영역 확보 및 중앙 정렬 */}
      <main className="flex-1 max-w-4xl mx-auto min-h-screen p-12 flex flex-col items-center relative z-10">
        <div className="max-w-5xl mx-auto w-full">
          
          {/* 2. 상단 프로필 헤더 (텍스트 크기: 3xl / 굵기: font-black) */}
          <header className="flex items-start gap-6 mb-10 px-4 mt-6">
            <div className="w-28 h-28 rounded-full border-2 border-[#F0E5D8] bg-white flex items-center justify-center text-5xl shadow-sm overflow-hidden flex-shrink-0 relative">
               <Image 
                src="/images/너트.png" 
                alt="Profile Nutty" 
                fill 
                className="object-contain p-4"
              />
            </div>
            <div className="pt-2">
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-[20px] font-black !text-[#3D2B1F]">뉴로넛 님</h1>
                <span className="bg-[#FFB800] text-white text-[11px] font-black px-3 py-1 rounded-full uppercase tracking-tighter shadow-sm">
                  주행 중
                </span>
              </div>
              <button className="flex items-center gap-2 !text-[#8C7B6E] hover:!text-[#3D2B1F] transition-colors font-bold text-[15px]">
                설정 <Settings size={18} />
              </button>
            </div>
          </header>

          {/* 3. 통계 그리드 섹션 */}
          <section className="grid grid-cols-1 lg:grid-cols-12 gap-5 mb-5">
            {/* 카테고리 카드 */}
            <div className="lg:col-span-6 bg-white rounded-[32px] p-8 border border-[#F0E5D8] shadow-sm">
              <div className="flex justify-between items-center mb-6">
                <h3 className="font-black text-[15px] !text-[#3D2B1F]">카테고리</h3>
                <button className="flex items-center gap-1.5 text-[12px] font-black !text-[#8C7B6E] hover:!text-[#3D2B1F] transition-colors">
                  필터 <SlidersHorizontal size={14} />
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {SELECTED_CATEGORIES.map(cat => (
                  <span key={cat} className="px-5 py-2.5 rounded-full border border-[#E5E5E5] !text-[#8C7B6E] font-bold text-sm bg-white hover:bg-[#FFF9F0] transition-colors cursor-default">
                    {cat}
                  </span>
                ))}
              </div>
            </div>

            {/* 연속 학습 카드 (텍스트 크기: 5xl) */}
            <div className="lg:col-span-3 bg-white rounded-[32px] p-8 border border-[#F0E5D8] shadow-sm flex flex-col justify-between">
              <div className="flex justify-between items-center">
                <h3 className="font-black text-[15px] !text-[#3D2B1F]">연속 학습</h3>
                <ChevronRight size={20} className="!text-[#C2B7A8]" />
              </div>
              <div className="mt-4 flex items-baseline justify-end gap-1">
                <span className="text-[25px] font-black !text-[#FFB800] tracking-tighter">1</span>
                <span className="text-[25px] font-black !text-[#FFB800]">일</span>
              </div>
            </div>

            {/* 구독 정보 카드 (텍스트 크기: 5xl) */}
            <div className="lg:col-span-3 bg-white rounded-[32px] p-8 border border-[#F0E5D8] shadow-sm flex flex-col justify-between">
              <div className="flex justify-between items-center">
                <h3 className="font-black text-[15px] !text-[#3D2B1F]">구독 남은 기간</h3>
                <ChevronRight size={20} className="!text-[#C2B7A8]" />
              </div>
              <div className="mt-4 flex items-baseline justify-end gap-1">
                <span className="text-[25px] font-black !text-[#FFB800] tracking-tighter">28</span>
                <span className="text-[25px] font-black !text-[#FFB800]">일</span>
              </div>
            </div>
          </section>

          {/* 4. 활동 차트 카드 (라인 두께: 4 / 포인트: 6 / 텍스트: 14px) */}
          <section className="bg-white rounded-[40px] p-10 border border-[#F0E5D8] shadow-sm">
            <div className="relative w-full h-[400px]">
              <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full h-full overflow-visible">
                {/* 그리드 라인 & 수치 라벨 */}
                {[100, 50, 0].map((val) => {
                  const y = (padding + innerHeight) - (val / 100) * innerHeight;
                  return (
                    <g key={val}>
                      <line x1={padding} y1={y} x2={padding + innerWidth} y2={y} stroke="#F5F5F5" strokeWidth="1.5" />
                      <text x={padding - 20} y={y + 5} textAnchor="end" className="text-[12px] !fill-[#8C7B6E]">{val}</text>
                    </g>
                  );
                })}

                <motion.path d={areaPath} fill="url(#chartGradient)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1 }} />

                {/* 메인 라인: strokeWidth="4" */}
                <motion.path
                  d={linePath}
                  fill="none"
                  stroke="#FFB800"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 1.5, ease: "easeInOut" }}
                />

                {/* 데이터 포인트: r="6" / strokeWidth="3" */}
                {points.map((p, i) => (
                  <motion.circle 
                    key={i} cx={p.x} cy={p.y} r="4" fill="#FFB800" stroke="white" strokeWidth="3"
                    initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.5 + i * 0.1 }}
                  />
                ))}

                {/* X축 요일 라벨: 14px font-black */}
                {WEEKLY_TOTAL_DATA.map((d, i) => (
                  <text 
                    key={d.day} 
                    x={padding + (i * (innerWidth / (WEEKLY_TOTAL_DATA.length - 1)))} 
                    y={chartHeight - 5} 
                    textAnchor="middle" 
                    className="text-[12px] !fill-[#3D2B1F]"
                  >
                    {d.day}
                  </text>
                ))}

                <defs>
                  <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FFB800" stopOpacity="0.15" />
                    <stop offset="100%" stopColor="#FFB800" stopOpacity="0" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
          </section>
        </div>

    
      </main>
    </div>
  );
}