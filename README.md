## NeuroKnots (뉴로넛)
"읽는 것만으로 단단해지는 뇌" > AI 맞춤형 읽기 훈련 기반 뇌 건강 회복 플랫폼

> 현대인의 뇌는 숏폼과 즉각적인 자극에 중독되어 집중력과 문해력이 저하된 '팝콘 브레인' 상태에 놓여 있습니다. NeuroKnots는 단순히 스마트폰을 끄는 수동적 차단을 넘어, 전두엽을 다시 사용하는 '능동적 재활' 솔루션을 제공합니다.

## Tech Stack
> 서비스 구현에 사용된 핵심 기술 스택입니다. (UI/UX 전환은 Framer Motion 기반으로 부드럽게 설계)

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" />
  <img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=000000" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white" />
  <img src="https://img.shields.io/badge/Framer_Motion-000000?style=for-the-badge&logo=framer&logoColor=white" />
  <img src="https://img.shields.io/badge/Lucide--React-111827?style=for-the-badge&logo=svg&logoColor=white" />
</p>

### (1) Framework
- **구성**: Next.js, React  
- **목적**: 페이지 라우팅 + 컴포넌트 기반 UI로 학습 흐름을 빠르고 안정적으로 구성  
- **특징**: 학습 화면(문제/해설/리그/프로필) UI를 모듈화하여 유지보수 용이

### (2) Styling
- **구성**: Tailwind CSS  
- **목적**: 화면 단위 반복 UI를 빠르게 제작하고 일관된 디자인 시스템 유지  
- **특징**: 유틸리티 클래스 기반으로 “학습/문제/해설” 컴포넌트의 스타일 재사용성 ↑

### (3) Animation
- **구성**: Framer Motion  
- **목적**: 사용자 인지 전환(문제 → 정답/오답 → 해설) 흐름을 부드럽게 연결  
- **특징**: 전환/등장 모션을 최소한으로 적용해 몰입감 유지 + 피로도 감소

### (4) Icons
- **구성**: Lucide-React  
- **목적**: 일관된 스트로크 스타일의 아이콘으로 UI 밀도 정리  
- **특징**: React 컴포넌트 형태로 크기/색상/상태 제어가 쉬움

![카테고리1-1](https://github.com/user-attachments/assets/ff49103d-a6a1-4758-bdfb-43427894a4a2)
![카테고리1-2](https://github.com/user-attachments/assets/9b13ac4e-126d-464a-ba24-c090c0dfbb19)
![카테고리2-1](https://github.com/user-attachments/assets/c402b4af-a220-4f9e-b31a-55aa7b21377b)
![카테고리2-2](https://github.com/user-attachments/assets/aa84eb61-5904-44ae-96a5-0e664061cfd6)
![학습전](https://github.com/user-attachments/assets/50dda443-338a-40df-a14e-238c0fcc031e)
![읽기](https://github.com/user-attachments/assets/08e7fae0-e084-46eb-b1b9-899155492d49)

## NeuroKnot AI 로직 안내
이 프로젝트에는 **AI 로직 2개**가 사용됩니다.  

## (1) 문제 추천 / 난이도 조정
- **목적**: 학습 기록 기반 적절한 난이도의 문제 추천  
- **입력**: 사용자 ID, 학습 기록, 정답률  
- **출력**: 추천 문제 리스트 (문제 ID, 난이도, 카테고리)  
- **특징**: 정답률 기반 난이도 조정, 최근 학습 카테고리 우선, 반복 학습 문제 재추천
  
![문제](https://github.com/user-attachments/assets/3cf944e9-430c-4d0c-95ad-8773f070a7b1)
![오답](https://github.com/user-attachments/assets/70487f9f-89ad-4373-941c-b9f310b66a22)
![정답](https://github.com/user-attachments/assets/0d56276f-3df8-4eb9-ad86-bb65904f0f86)
![해설](https://github.com/user-attachments/assets/4723b1cc-13a3-4871-9fdd-9630fcebca8b)
---
## (2) 풀이 해설 생성 / 자동 첨삭
- **목적**: 사용자의 답안 분석 및 자동 해설 제공  
- **입력**: 문제 ID, 사용자 답안  
- **출력**: 해설 텍스트, 피드백, 관련 학습 자료 링크  
- **특징**: 오답 유형 분석, 자연어 처리 기반 해설 생성, 유사 문제 추천
---
### * 주의 사항
- AI 로직은 **참고용**이며, 실제 구현은 아직 완전히 완료되지 않았습니다.  
- 모델 버전 및 학습 데이터 출처는 추후 명시 예정입니다.
![학습후](https://github.com/user-attachments/assets/3e53af40-fa9a-48d0-9fd9-5e14bd3f0f62)
![프로필](https://github.com/user-attachments/assets/d6b2b826-c440-4354-949a-1b83bc65ee38)
![리그](https://github.com/user-attachments/assets/94904fe9-80e6-4dd1-a6c4-add1fff67e8e)
