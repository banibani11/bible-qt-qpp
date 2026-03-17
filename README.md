# ✝️ 성경 QT 묵상 앱

매일 말씀 묵상을 도와주는 Streamlit 기반 성경 QT(Quiet Time) 앱입니다.
랜덤 성경 구절과 AI 묵상 질문으로 하루를 말씀과 함께 시작하세요. 🌿

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 📖 랜덤 구절 | 앱 실행 시 같은 장의 연속 3~5절 랜덤 제공 |
| 💭 AI 묵상 질문 | Google Gemini API로 구절 맞춤 질문 3개 자동 생성 |
| ✍️ 묵상 입력 | 각 질문에 대한 나의 생각 기록 |
| 🙏 감사기도 | 오늘의 감사 제목 3가지 입력 |
| ✅ 달력 완료 표시 | 이번 달 QT 완료 현황을 달력으로 시각화 |
| 🔄 구절 새로고침 | 다른 구절로 변경 가능 |

---

## 로컬 실행

### 1. 저장소 클론

```bash
git clone https://github.com/<your-username>/bible-qt-qpp.git
cd bible-qt-qpp
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. Gemini API 키 설정

`.streamlit/secrets.toml` 파일을 생성하고 아래 내용을 입력합니다.
> ⚠️ 이 파일은 `.gitignore`에 포함되어 있으므로 절대 커밋되지 않습니다.

```toml
# .streamlit/secrets.toml
GEMINI_API_KEY = "여기에_실제_API_키를_입력하세요"
```

Gemini API 키는 [Google AI Studio](https://aistudio.google.com/app/apikey)에서 무료로 발급받을 수 있습니다.

### 4. 앱 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501`로 접속하세요.

---

## Streamlit Cloud 배포

### 1. GitHub에 푸시

```bash
git add .
git commit -m "Add Bible QT app"
git push origin main
```

### 2. Streamlit Cloud 배포

1. [share.streamlit.io](https://share.streamlit.io) 접속
2. GitHub 계정 연결
3. 저장소 선택 → `app.py` 지정 → **Deploy** 클릭

### 3. Streamlit Cloud에서 API 키 설정

배포 후 **App settings → Secrets** 탭에서 아래 내용 입력:

```toml
GEMINI_API_KEY = "여기에_실제_API_키를_입력하세요"
```

> API 키 없이도 앱이 실행됩니다. 이 경우 기본 묵상 질문 템플릿이 사용됩니다.

---

## 파일 구조

```
bible-qt-qpp/
├── app.py              # 메인 Streamlit 앱
├── 개역성경.txt          # 성경 본문 (EUC-KR 인코딩, 개역개정)
├── requirements.txt    # Python 의존성
├── .gitignore          # Git 무시 파일 목록
└── README.md           # 이 문서
```

## 성경 파일 형식

`개역성경.txt`는 EUC-KR 인코딩의 개역성경 텍스트 파일이며, 아래 형식을 따릅니다:

```
창1:1 태초에 하나님이 천지를 창조하시니라
창1:2 그 땅이 혼돈하고 공허하며...
```

---

## 기술 스택

- **Frontend**: [Streamlit](https://streamlit.io/)
- **AI API**: [Google Gemini 2.0 Flash](https://ai.google.dev/)
- **성경 데이터**: 개역개정 성경

---

## 라이선스

개인 묵상 및 비상업적 용도로만 사용하세요.
성경 본문 저작권은 해당 번역 단체에 귀속됩니다.
