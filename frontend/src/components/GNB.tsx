'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  BookOpen, 
  Trophy, 
  User, 
  MoreHorizontal, 
  Settings, 
  HelpCircle, 
  LogOut 
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Image from 'next/image';

const NavItem = ({ 
  icon, 
  label, 
  href,
  active = false, 
  onClick 
}: { 
  icon: React.ReactNode, 
  label: string, 
  href?: string,
  active?: boolean,
  onClick?: () => void
}) => {
  const content = (
    <div 
      onClick={onClick}
      className={`
        flex items-center gap-4 py-3.5 px-4 rounded-2xl cursor-pointer transition-all relative group
        ${active ? 'text-[#FFB800]' : 'text-[#8C7B6E] hover:text-[#3D2B1F] hover:bg-[#FDF4E7]'}
      `}
    >
      {active && (
        <motion.div 
          layoutId="activeIndicator"
          className="absolute left-[-32px] top-1/2 -translate-y-1/2 w-1.5 h-8 bg-[#FFB800] rounded-r-full" 
        />
      )}
      <div className={`${active ? 'text-[#FFB800]' : 'text-[#C2B7A8] group-hover:text-[#8C7B6E]'} transition-colors`}>
        {icon}
      </div>
      <span className="font-black text-lg tracking-tight">{label}</span>
    </div>
  );

  return href ? <Link href={href}>{content}</Link> : content;
};

export default function GNB() {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);

  const menuItems = [
    { name: '학습', path: '/dashboard', icon: <BookOpen size={24} /> },
    { name: '리그', path: '/league', icon: <Trophy size={24} /> },
    { name: '프로필', path: '/profile', icon: <User size={24} /> },
  ];

  return (
    <aside className="w-64 bg-white border-r border-[#F0E5D8] flex flex-col p-8 fixed h-full z-40 select-none font-sans">
      {/* 1. 로고 섹션 */}
      <div className="mb-14 relative w-full h-16 flex items-center justify-start">
        <Image 
            src="/images/logo.png" 
            alt="로고"
            width={180}
            height={60}
            className="object-contain"
            priority 
        />
      </div>

      {/* 2. 메뉴 리스트 섹션 */}
      <nav className="flex-1 flex flex-col gap-2">
        {menuItems.map((item) => (
          <NavItem 
            key={item.name}
            href={item.path}
            icon={item.icon} 
            label={item.name} 
            active={pathname === item.path}
          />
        ))}

        {/* 3. 더보기 (Hover Trigger) */}
        <div 
          className="relative"
          onMouseEnter={() => setMoreOpen(true)}
          onMouseLeave={() => setMoreOpen(false)}
        >
          <NavItem 
            icon={<MoreHorizontal size={24} />} 
            label="더보기" 
            active={moreOpen}
          />

          <AnimatePresence>
            {moreOpen && (
              <motion.div
                initial={{ opacity: 0, x: -10, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -10, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className="absolute left-full top-0 ml-2 w-52 bg-white border border-[#F0E5D8] rounded-2xl shadow-xl shadow-orange-900/5 py-3 z-50 overflow-hidden"
              >
                {/* 투명한 브릿지: 사이드바와 메뉴 사이의 간격을 메워 마우스 이동 시 닫힘 방지 */}
                <div className="absolute top-0 -left-2 w-2 h-full bg-transparent" />
                
                <ul className="flex flex-col text-sm font-bold text-[#8C7B6E]">
                  <li className="flex items-center gap-3 px-5 py-3 hover:bg-[#FDF4E7] hover:text-[#3D2B1F] cursor-pointer transition-colors">
                    <Settings size={18} className="text-[#C2B7A8]" /> 세팅
                  </li>
                  <li className="flex items-center gap-3 px-5 py-3 hover:bg-[#FDF4E7] hover:text-[#3D2B1F] cursor-pointer transition-colors">
                    <HelpCircle size={18} className="text-[#C2B7A8]" /> 고객지원센터
                  </li>
                  <div className="h-[1px] bg-[#F0E5D8] my-2 mx-4" />
                  <li className="flex items-center gap-3 px-5 py-3 text-red-400 hover:bg-red-50 transition-all">
                    <LogOut size={18} /> 로그아웃
                  </li>
                </ul>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </nav>

      {/* 4. 하단 인증 섹션 */}
      <div className="mt-auto flex flex-col gap-3">
        <button className="w-full py-3 px-4 border border-[#E5E5E5] rounded-2xl text-sm font-black text-[#3D2B1F] hover:bg-[#FDF4E7] hover:border-[#F0E5D8] transition-all">
          로그아웃
        </button>
      </div>
    </aside>
  );
}