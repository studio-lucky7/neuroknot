import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

// 백엔드가 붙기 전까지 온보딩 선택과 오늘의 학습 여부를 기기에 저장합니다.
// (웹 버전의 localStorage 'isStudyDone'을 대체)
const PROFILE_KEY = 'neuroknot:profile';
const STUDY_DONE_KEY = 'neuroknot:studyDoneOn';

export type Profile = {
  categories: string[];
  level: string;
};

type AppState = {
  ready: boolean;
  profile: Profile | null;
  studyDone: boolean;
  completeOnboarding: (profile: Profile) => Promise<void>;
  markStudyDone: () => Promise<void>;
  reset: () => Promise<void>;
};

const AppStateContext = createContext<AppState | null>(null);

// 기기 로컬 날짜 기준 'YYYY-MM-DD'
function todayKey() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [studyDoneOn, setStudyDoneOn] = useState<string | null>(null);

  useEffect(() => {
    AsyncStorage.multiGet([PROFILE_KEY, STUDY_DONE_KEY])
      .then(([[, savedProfile], [, savedDate]]) => {
        if (savedProfile) setProfile(JSON.parse(savedProfile));
        setStudyDoneOn(savedDate);
      })
      .catch(() => {
        // 저장소를 못 읽으면 처음 실행한 것처럼 온보딩부터 시작
      })
      .finally(() => setReady(true));
  }, []);

  const value: AppState = {
    ready,
    profile,
    studyDone: studyDoneOn === todayKey(),
    completeOnboarding: async (next) => {
      await AsyncStorage.setItem(PROFILE_KEY, JSON.stringify(next));
      setProfile(next);
    },
    markStudyDone: async () => {
      const today = todayKey();
      await AsyncStorage.setItem(STUDY_DONE_KEY, today);
      setStudyDoneOn(today);
    },
    reset: async () => {
      await AsyncStorage.multiRemove([PROFILE_KEY, STUDY_DONE_KEY]);
      setStudyDoneOn(null);
      setProfile(null);
    },
  };

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const state = useContext(AppStateContext);
  if (!state) throw new Error('useAppState는 AppStateProvider 안에서만 쓸 수 있습니다');
  return state;
}
