NeuroKnots (뉴로넛)
"읽는 것만으로 단단해지는 뇌" > AI 맞춤형 읽기 훈련 기반 뇌 건강 회복 플랫폼

현대인의 뇌는 숏폼과 즉각적인 자극에 중독되어 집중력과 문해력이 저하된 '팝콘 브레인' 상태에 놓여 있습니다. NeuroKnots는 단순히 스마트폰을 끄는 수동적 차단을 넘어, 전두엽을 다시 사용하는 '능동적 재활' 솔루션을 제공합니다.

![카테고리1-1](https://github.com/user-attachments/assets/ff49103d-a6a1-4758-bdfb-43427894a4a2)
![카테고리1-2](https://github.com/user-attachments/assets/9b13ac4e-126d-464a-ba24-c090c0dfbb19)
![카테고리2-1](https://github.com/user-attachments/assets/c402b4af-a220-4f9e-b31a-55aa7b21377b)
![카테고리2-2](https://github.com/user-attachments/assets/aa84eb61-5904-44ae-96a5-0e664061cfd6)
![학습전](https://github.com/user-attachments/assets/50dda443-338a-40df-a14e-238c0fcc031e)
![읽기](https://github.com/user-attachments/assets/08e7fae0-e084-46eb-b1b9-899155492d49)

# NeuroKnot AI 로직 안내
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

Tech Stack

Framework: Next.js, React

Styling: Tailwind CSS

Animation: Framer Motion (부드러운 인지 전환 효과 구현)

Icons: Lucide-React
