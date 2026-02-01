'use client';

import { motion } from 'framer-motion';

interface Props {
  label: string;
  isSelected: boolean;
  onClick: () => void;
}

export default function CategoryCard({ label, isSelected, onClick }: Props) {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className={`
        cursor-pointer p-6 border transition-all duration-300
        ${isSelected 
          ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)]' 
          : 'border-zinc-800 bg-zinc-900/30 text-zinc-500 hover:border-zinc-400 hover:text-zinc-200'}
      `}
    >
      <span className="font-mono text-xs mb-2 block opacity-50">
        {isSelected ? '[ SELECTED ]' : '[ ARCHIVE ]'}
      </span>
      <h3 className="text-lg font-bold tracking-tight">{label}</h3>
    </motion.div>
  );
}