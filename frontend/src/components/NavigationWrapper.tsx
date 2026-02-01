'use client';

import { usePathname } from 'next/navigation';
import GNB from './GNB';

export default function NavigationWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // GNB를 숨기고 싶은 경로 패턴들을 정의합니다.
  // startsWith를 사용하면 /reading/1 같은 하위 페이지도 모두 포함됩니다.
  const isExcluded = 
    pathname.startsWith('/reading') || 
    pathname.startsWith('/onboarding') || // 아까 만든 온보딩 경로
    pathname.startsWith('/onboard');      // 혹시 모를 오타 대비

  if (isExcluded) {
    return <>{children}</>; // GNB 없이 내용만 렌더링
  }

  return (
    <div className="flex min-h-screen">
      <GNB />
      <main className="flex-1 ml-64 min-h-screen overflow-y-auto">
        {children}
      </main>
    </div>
  );
}