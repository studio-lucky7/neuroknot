'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Trophy, Zap, ShieldCheck, AlertTriangle, ChevronRight, Lock } from 'lucide-react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

const TIERS = [
  { name: "브론즈", id: "bronze" },
  { name: "SILVER", id: "silver" },
  { name: "GOLD", id: "gold" },
  { name: "PLATINUM", id: "platinum" },
  { name: "DIAMOND", id: "diamond" },
];

const SYSTEM_NAMES = [
  "캐스넛유저", "데이터햄스터", "로직고양이", "사이버문어", "네오펭귄",
  "조용한올빼미", "스텔스다람쥐", "공허거북이", "크롬여우", "이진곰",
  "유령강아지", "메타오리", "코발트팬더", "루트사용자", "노드친구"
];

type NutType = '너트' | '파마너트' | '선글라스너트';

// 점수 생성 및 이미지 배정
function generateLeagueUsers() {
  const topPool = Array.from({ length: (550 - 50) / 10 + 1 }, (_, i) => 50 + i * 10);
  const topScores = topPool.sort(() => Math.random() - 0.5).slice(0, 9).sort((a, b) => b - a);

  const bottomPool = [10, 15, 20, 25, 30, 35];
  const bottomScores = bottomPool.sort(() => Math.random() - 0.5).slice(0, 5).sort((a, b) => b - a);

  const finalUsers: { id: string; isMe: boolean; name: string; score: number; nut: NutType }[] = [];

  // 상위권 유저 (1~9위, 파마너트 6명, 나머지 선글라스너트)
  for (let i = 0; i < 9; i++) {
    finalUsers.push({
      id: `top-${i}`,
      isMe: false,
      name: SYSTEM_NAMES[i % SYSTEM_NAMES.length],
      score: topScores[i],
      nut: i < 6 ? '파마너트' : '선글라스너트'
    });
  }

  // 10위 뉴로넛 (너트)
  finalUsers.push({
    id: 'me',
    isMe: true,
    name: "뉴로넛 (YOU)",
    score: 40,
    nut: '너트'
  });

  // 하위권 유저 (11~15위, 선글라스너트)
  for (let i = 0; i < 5; i++) {
    finalUsers.push({
      id: `bottom-${i}`,
      isMe: false,
      name: SYSTEM_NAMES[(i + 9) % SYSTEM_NAMES.length],
      score: bottomScores[i],
      nut: '선글라스너트'
    });
  }

  return finalUsers;
}

export default function LeaguePage() {
  const router = useRouter();
  const [tier, setTier] = useState("브론즈");
  const [users, setUsers] = useState<any[]>([]);

  useEffect(() => {
    setUsers(generateLeagueUsers());

    const style = document.createElement('style');
    style.textContent = `body { background-color: #FFF9F0 !important; font-family: 'Pretendard', sans-serif; }`;
    document.head.appendChild(style);
    return () => { document.head.removeChild(style); };
  }, []);

  return (
    <div className="flex min-h-screen bg-[#FFF9F0] text-[#3D2B1F]">
      <main className="flex-1 mx-auto min-h-screen flex flex-col items-center py-12 relative z-10">
        
        {/* 상단 헤더 */}
        <header className="w-full max-w-4xl px-6 md:px-12 mb-10 flex flex-col items-center">
          <div className="w-full flex items-center gap-3 mb-10 text-[#8C7B6E]">
            <Trophy size={20} className="text-[#FFB800]" />
            <span className="text-sm font-black tracking-widest uppercase">리그</span>
          </div>

          <div className="flex gap-10 items-end justify-center w-full">
            {TIERS.map((t, idx) => {
              const isBronze = t.name === "브론즈";
              return (
                <div key={t.name} className={`flex flex-col items-center gap-3 transition-all ${!isBronze ? "opacity-30" : "opacity-100"}`}>
                  <div className={`relative ${isBronze ? "w-24 h-24 mb-2" : "w-14 h-14"}`}>
                    
                    <Image 
                      src={isBronze ? "/images/bronze.png" : "/images/silver.png"} 
                      alt={t.name}
                      fill
                      className="object-contain"
                    />
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <span className={`text-[13px] font-black tracking-tighter ${isBronze ? "text-[#3D2B1F]" : "text-[#C2B7A8]"}`}>
                      {isBronze ? t.name : "??????"}
                    </span>
                    {!isBronze && <Lock size={12} className="text-[#C2B7A8]" />}
                  </div>
                </div>
              );
            })}
          </div>
        </header>

        {/* 메인 랭킹 카드 */}
        <section className="flex-1 w-full max-w-4xl px-6 md:px-12 flex flex-col justify-center mb-20">
          <div className="bg-white rounded-[40px] p-6 md:p-8 shadow-sm border border-[#F0E5D8] min-h-[600px] flex flex-col relative overflow-hidden">
            <AnimatePresence mode="wait">
              <motion.div 
                key={tier}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col gap-1"
              >
                {users.map((user, idx) => (
                  <React.Fragment key={user.id}>
                    {idx === 5 && <Divider label="Promotion Zone" color="emerald" icon={<ShieldCheck size={14}/>} />}
                    {idx === 10 && <Divider label="Demotion Risk" color="red" icon={<AlertTriangle size={14}/>} />}

                    <motion.div
                      whileHover={user.isMe ? {} : { x: 8, backgroundColor: '#FDF4E7' }}
                      className={`
                        flex justify-between items-center px-8 py-4 rounded-[28px] transition-all
                        ${user.isMe 
                          ? "bg-[#FFB800] text-white shadow-lg shadow-orange-200/50 z-10 scale-[1.02]" 
                          : "hover:bg-[#FDF4E7] text-[#5D4B3E]"}
                      `}
                    >
                      <div className="flex gap-8 items-center">
                        <div className="w-10 h-10 flex items-center justify-center relative">
                          {idx < 3 ? (
                            /* 1, 2, 3등: 이미지 노출 */
                            <Image 
                            src={`/images/${idx + 1}.png`} 
                            alt={`${idx + 1}st`}
                            width={32}
                            height={32}
                            className="object-contain"
                            />
                        ) : (
                            /* 4등 이후: 숫자 노출 (04, 05... 형식) */
                            <span className={`text-lg font-black ${user.isMe ? "!text-white" : "!text-[#C2B7A8]"}`}>
                            {String(idx + 1).padStart(2, '0')}
                            </span>
                        )}
                          <Image 
                            src={`/images/${user.nut}.png`} // public/images/너트.png, 파마너트.png 등
                            alt={user.nut}
                            width={32} 
                            height={32} 
                            className="object-contain"
                          />
                        </div>
                        <span className={`text-base font-bold tracking-tight ${user.isMe ? "text-white" : "text-[#3D2B1F]"}`}>
                          {user.name}
                        </span>
                      </div>

                      <div className="flex gap-10 items-center">
                        <div className={`flex items-center gap-2 ${user.isMe ? "text-white" : "text-[#8C7B6E]"}`}>
                          <Zap size={16} fill={user.isMe ? "white" : "transparent"} className={user.isMe ? "animate-pulse" : ""} />
                          <span className="text-sm font-black">
                            {user.score.toLocaleString()} <span className="text-[10px] opacity-70 italic font-medium">EXP</span>
                          </span>
                        </div>
                        <ChevronRight size={18} className={user.isMe ? "text-white/40" : "text-[#F0E5D8]"} />
                      </div>
                    </motion.div>
                  </React.Fragment>
                ))}
              </motion.div>
            </AnimatePresence>
          </div>
        </section>

        {/* 하단 워터마크 */}
        <div className="max-w-4xl w-full px-12 flex justify-between text-[#C2B7A8] font-black text-[10px] tracking-[0.3em] uppercase opacity-80 pb-10">
          <span>Engine Sync: Stable</span>
          <span>League Ranking V2.0</span>
        </div>
      </main>

      <div className="fixed bottom-[-150px] right-[-100px] w-[60%] aspect-square bg-white rounded-full z-0 opacity-40 pointer-events-none" />
    </div>
  );
}

const Divider = ({ label, color, icon }: { label: string, color: 'emerald' | 'red', icon: React.ReactNode }) => (
  <div className="flex items-center gap-4 py-6 px-4">
    <div className={`flex-1 h-[1px] ${color === 'emerald' ? 'bg-[#E8F5E9]' : 'bg-[#FFEBEE]'}`} />
    <span className={`text-[10px] ${color === 'emerald' ? 'text-emerald-500' : 'text-red-400'} font-black tracking-[0.2em] flex items-center gap-1.5 uppercase`}>
      {icon} {label}
    </span>
    <div className={`flex-1 h-[1px] ${color === 'emerald' ? 'bg-[#E8F5E9]' : 'bg-[#FFEBEE]'}`} />
  </div>
);