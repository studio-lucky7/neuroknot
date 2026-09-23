// NeuroKnots 브랜드 팔레트 — 기존 웹(Next.js) 화면에서 쓰던 색 그대로.
// tailwind.config.js(className)와 화면 코드(아이콘 color 등)가 같이 가져다 씁니다.
const brand = {
  gold: '#FFB800', // 메인 강조, 버튼
  'gold-deep': '#FFA500', // 버튼 눌림
  cream: '#FFF9F0', // 페이지 배경
  sand: '#FDF4E7', // 말풍선, 눌림 배경
  border: '#F0E5D8', // 카드 테두리
  line: '#E5E5E5', // 선택지·버튼 테두리
  mist: '#F8F8F8', // 온보딩 카드 배경
  fog: '#F2F2F2', // 비활성 단계 표시
  disabled: '#CCCCCC',
  ink: '#3D2B1F', // 제목
  body: '#5D4B3E', // 본문
  muted: '#8C7B6E', // 보조 텍스트
  faint: '#C2B7A8', // 흐린 아이콘·텍스트
  danger: '#F87171', // 오답, 로그아웃
  safe: '#10B981', // 승급 구간
};

module.exports = { brand };
