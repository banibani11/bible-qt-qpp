"""
성경 QT(Quiet Time) 묵상 앱
Streamlit으로 구현된 매일 성경 묵상 도우미
"""

import streamlit as st
import random
import calendar
import re
from datetime import date

# ─────────────────────────────────────────────
# 1. 성경책 약어 → 전체 이름 매핑
# ─────────────────────────────────────────────
BOOK_NAMES = {
    "창": "창세기", "출": "출애굽기", "레": "레위기", "민": "민수기", "신": "신명기",
    "수": "여호수아", "삿": "사사기", "룻": "룻기", "삼상": "사무엘상", "삼하": "사무엘하",
    "왕상": "열왕기상", "왕하": "열왕기하", "대상": "역대상", "대하": "역대하",
    "스": "에스라", "느": "느헤미야", "에": "에스더", "욥": "욥기", "시": "시편",
    "잠": "잠언", "전": "전도서", "아": "아가", "사": "이사야", "렘": "예레미야",
    "애": "예레미야애가", "겔": "에스겔", "단": "다니엘", "호": "호세아", "욜": "요엘",
    "암": "아모스", "옵": "오바댜", "욘": "요나", "미": "미가", "나": "나훔",
    "합": "하박국", "습": "스바냐", "학": "학개", "슥": "스가랴", "말": "말라기",
    "마": "마태복음", "막": "마가복음", "눅": "누가복음", "요": "요한복음", "행": "사도행전",
    "롬": "로마서", "고전": "고린도전서", "고후": "고린도후서", "갈": "갈라디아서",
    "엡": "에베소서", "빌": "빌립보서", "골": "골로새서", "살전": "데살로니가전서",
    "살후": "데살로니가후서", "딤전": "디모데전서", "딤후": "디모데후서", "딛": "디도서",
    "몬": "빌레몬서", "히": "히브리서", "약": "야고보서", "벧전": "베드로전서",
    "벧후": "베드로후서", "요일": "요한일서", "요이": "요한이서", "요삼": "요한삼서",
    "유": "유다서", "계": "요한계시록",
}


# ─────────────────────────────────────────────
# 2. 성경 데이터 로드
# ─────────────────────────────────────────────
@st.cache_data
def load_bible():
    """
    개역성경.txt(EUC-KR)를 읽어 {책약어: {장: {절: 본문}}} 딕셔너리 반환
    """
    bible = {}
    try:
        with open("개역성경.txt", "rb") as f:
            raw = f.read()
        lines = raw.decode("euc-kr").strip().split("\r\n")
    except Exception:
        with open("개역성경.txt", "r", encoding="utf-8") as f:
            lines = f.read().strip().splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        colon = line.find(":")
        if colon == -1:
            continue
        ref_part = line[:colon]                    # 예: "창1"
        rest     = line[colon + 1:]               # 예: "1 태초에..."

        m_verse = re.match(r"(\d+)\s*(.*)", rest)
        if not m_verse:
            continue
        verse_num  = int(m_verse.group(1))
        verse_text = m_verse.group(2).strip()

        m_book = re.match(r"([가-힣]+)(\d+)", ref_part)
        if not m_book:
            continue
        book_abbr  = m_book.group(1)
        chap_num   = int(m_book.group(2))

        bible.setdefault(book_abbr, {}).setdefault(chap_num, {})[verse_num] = verse_text

    return bible


def get_random_passage(bible):
    """같은 장의 연속 3~5절을 랜덤 선택하여 반환"""
    valid = [
        (book, chap)
        for book, chapters in bible.items()
        for chap, verses in chapters.items()
        if len(verses) >= 3
    ]
    if not valid:
        return None

    book_abbr, chap_num = random.choice(valid)
    verse_nums = sorted(bible[book_abbr][chap_num].keys())
    length     = random.randint(3, min(5, len(verse_nums)))
    start_idx  = random.randint(0, len(verse_nums) - length)
    selected   = verse_nums[start_idx: start_idx + length]

    return (
        book_abbr,
        chap_num,
        selected[0],
        selected[-1],
        [(v, bible[book_abbr][chap_num][v]) for v in selected],
    )


# ─────────────────────────────────────────────
# 3. Gemini API로 묵상 질문 생성
# ─────────────────────────────────────────────
def get_default_questions():
    return [
        "이 구절에서 하나님은 나에게 무엇을 말씀하고 계신가요? 오늘 나의 상황과 어떻게 연결되나요?",
        "이 말씀을 오늘 하루 내 삶에 어떻게 적용할 수 있을까요? 구체적인 행동이나 태도의 변화가 있다면 무엇인가요?",
        "이 구절을 통해 하나님께 어떤 마음을 고백하고 싶으신가요? 감사, 회개, 간구 중 어떤 기도를 드리고 싶으신가요?",
    ]


def generate_qt_questions(passage_text, reference, api_key=""):
    """Gemini API로 질문 3개 생성, 실패 시 기본 질문 반환"""
    try:
        import google.generativeai as genai

        if not api_key:
            api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("API 키 없음")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"""당신은 따뜻하고 깊이 있는 성경 묵상을 도와주는 QT 가이드입니다.

다음 성경 구절을 읽고, 개인 묵상을 위한 질문 3개를 한국어로 만들어주세요.

[구절] {reference}
{passage_text}

[요청사항]
- 질문은 독자가 자신의 삶과 연결하여 깊이 생각할 수 있도록 구체적이고 따뜻하게 작성해주세요.
- 각 질문은 서로 다른 관점(말씀의 의미, 적용, 기도 방향)을 다루어주세요.
- 번호 없이 질문만 3개를 줄바꿈으로 구분하여 출력해주세요."""

        raw = model.generate_content(prompt).text.strip()
        questions = []
        for q in raw.split("\n"):
            q = re.sub(r"^[\d]+[.)]\s*", "", q.strip())
            q = re.sub(r"^[-•*]\s*", "", q).strip()
            if q:
                questions.append(q)
        return questions[:3] if len(questions) >= 3 else get_default_questions()

    except Exception:
        return get_default_questions()


# ─────────────────────────────────────────────
# 4. 달력 완료 표시
# ─────────────────────────────────────────────
def mark_today_complete():
    today_str = date.today().isoformat()
    if today_str not in st.session_state.completed_dates:
        st.session_state.completed_dates.append(today_str)


def render_calendar():
    today  = date.today()
    year, month = today.year, today.month
    prefix = f"{year}-{month:02d}-"

    completed_days = {
        int(d.split("-")[2])
        for d in st.session_state.completed_dates
        if d.startswith(prefix)
    }

    st.markdown(f"### 📅 {year}년 {month}월 묵상 달력")

    # HTML 테이블로 달력 렌더링 (모바일/PC 모두 동일하게 표시)
    html = """
    <style>
    .cal-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
    }
    .cal-table th {
        text-align: center;
        font-weight: bold;
        color: #8B6F47;
        padding: 6px 2px;
        font-size: 0.9rem;
    }
    .cal-table td {
        text-align: center;
        padding: 6px 2px;
        font-size: 0.95rem;
        color: #5D4037;
    }
    .cal-done {
        background: #C8E6C9;
        border-radius: 8px;
        display: inline-block;
        width: 32px;
        height: 32px;
        line-height: 32px;
    }
    .cal-today {
        background: #FFF9C4;
        border-radius: 8px;
        border: 2px solid #F9A825;
        display: inline-block;
        width: 32px;
        height: 32px;
        line-height: 28px;
        font-weight: bold;
    }
    .cal-day {
        display: inline-block;
        width: 32px;
        height: 32px;
        line-height: 32px;
    }
    </style>
    <table class="cal-table">
    <tr>
        <th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th>토</th><th>일</th>
    </tr>
    """

    for week in calendar.monthcalendar(year, month):
        html += "<tr>"
        for day in week:
            if day == 0:
                html += "<td></td>"
            elif day in completed_days:
                html += f"<td><span class='cal-done'>✅</span></td>"
            elif day == today.day:
                html += f"<td><span class='cal-today'>{day}</span></td>"
            else:
                html += f"<td><span class='cal-day'>{day}</span></td>"
        html += "</tr>"

    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 5. 메인
# ─────────────────────────────────────────────
def main():
    st.set_page_config(page_title="성경 QT 묵상", page_icon="✝️", layout="centered")

    # ── 스타일 ──
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #FFF8F0 0%, #FFF3E0 100%); }
    .verse-card {
        background:#FFFDE7; border-left:5px solid #F9A825; border-radius:10px;
        padding:1.2rem 1.5rem; margin:1rem 0;
        box-shadow:0 2px 8px rgba(0,0,0,0.08);
        font-size:1.05rem; line-height:1.8; color:#3E2723;
    }
    .verse-ref { font-size:0.9rem; color:#8D6E63; font-weight:bold; margin-bottom:0.5rem; }
    .question-card {
        background:#FBE9E7; border-radius:8px; padding:0.8rem 1.2rem;
        margin:0.5rem 0; border:1px solid #FFCCBC; color:#4E342E;
    }
    hr.divider { border:none; border-top:2px solid #FFCC80; margin:1.5rem 0; }
    .done-badge {
        background:#E8F5E9; border:2px solid #66BB6A; border-radius:20px;
        padding:0.5rem 1.5rem; text-align:center; color:#2E7D32;
        font-size:1.1rem; font-weight:bold;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── 세션 초기화 ──
    if "bible" not in st.session_state:
        st.session_state.bible = load_bible()
    if "passage" not in st.session_state:
        st.session_state.passage   = get_random_passage(st.session_state.bible)
        st.session_state.questions = None
    if "completed_dates" not in st.session_state:
        st.session_state.completed_dates = []
    if "gemini_api_key" not in st.session_state:
        st.session_state.gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")

    # ── 헤더 ──
    st.markdown("""
    <div style='text-align:center;padding:1.5rem 0 0.5rem;color:#5D4037'>
        <h1>✝️ 오늘의 말씀 묵상</h1>
        <p style='color:#8D6E63;margin-top:-0.5rem'>말씀과 함께하는 하루를 시작하세요 🌿</p>
    </div>
    """, unsafe_allow_html=True)

    today = date.today()
    weekday_kr = ["월","화","수","목","금","토","일"][today.weekday()]
    st.markdown(
        f"<p style='text-align:center;color:#A1887F;font-size:0.95rem'>"
        f"📖 {today.year}년 {today.month}월 {today.day}일 ({weekday_kr})</p>",
        unsafe_allow_html=True,
    )

    # ── Gemini API 키 입력 ──
    with st.expander("🔑 Gemini API 키 설정 (AI 묵상 질문 생성용)", expanded=not st.session_state.gemini_api_key):
        col1, col2 = st.columns([4, 1])
        with col1:
            new_key = st.text_input(
                "API 키",
                value=st.session_state.gemini_api_key,
                type="password",
                placeholder="AIza... 형식의 Gemini API 키를 입력하세요",
                label_visibility="collapsed",
            )
        with col2:
            if st.button("저장", use_container_width=True):
                if new_key != st.session_state.gemini_api_key:
                    st.session_state.gemini_api_key = new_key
                    st.session_state.questions = None  # 질문 재생성
                    st.rerun()
        if st.session_state.gemini_api_key:
            st.success("✅ API 키가 설정되어 있습니다. AI가 구절에 맞는 질문을 생성합니다.")
        else:
            st.warning("⚠️ API 키 없이는 기본 질문이 표시됩니다. [API 키 발급](https://aistudio.google.com/app/apikey)")

    # ── 구절 표시 ──
    passage = st.session_state.passage
    if passage is None:
        st.error("성경 파일을 불러오지 못했습니다.")
        return

    book_abbr, chap_num, start_v, end_v, verses = passage
    book_full = BOOK_NAMES.get(book_abbr, book_abbr)
    ref_str   = (
        f"{book_full} {chap_num}:{start_v}"
        if start_v == end_v
        else f"{book_full} {chap_num}:{start_v}-{end_v}"
    )

    html = f"<div class='verse-card'><div class='verse-ref'>📜 {ref_str}</div>"
    for v_num, v_text in verses:
        html += f"<b>{v_num}절</b> {v_text}<br>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    # 다른 구절 버튼
    _, c, _ = st.columns([1, 2, 1])
    with c:
        if st.button("🔄 다른 구절 받기", use_container_width=True):
            st.session_state.passage   = get_random_passage(st.session_state.bible)
            st.session_state.questions = None
            st.rerun()

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── 묵상 질문 ──
    st.markdown("### 💭 오늘의 묵상 질문")

    if st.session_state.questions is None:
        with st.spinner("✨ 묵상 질문을 준비하고 있어요..."):
            plain_text = " ".join(v for _, v in verses)
            st.session_state.questions = generate_qt_questions(plain_text, ref_str, st.session_state.gemini_api_key)

    for i, q in enumerate(st.session_state.questions, 1):
        st.markdown(
            f"<div class='question-card'>❓ <b>질문 {i}.</b> {q}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── 나의 묵상 나누기 (단일 입력란 — 질문과 무관하게 딱 1칸) ──
    st.markdown("### ✍️ 나의 묵상 나누기")
    st.markdown(
        "<p style='color:#8D6E63;font-size:0.9rem'>말씀을 통해 받은 감동, 깨달음, 결단을 자유롭게 적어보세요.</p>",
        unsafe_allow_html=True,
    )
    st.text_area(
        label="나의 묵상",
        placeholder="여기에 묵상을 적어보세요.",
        height=250,
        key="my_meditation_single",
    )

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── 감사기도 ──
    st.markdown("### 🙏 오늘의 감사기도")
    st.markdown(
        "<p style='color:#8D6E63;font-size:0.9rem'>오늘 감사한 것 3가지를 하나님께 고백해보세요.</p>",
        unsafe_allow_html=True,
    )
    st.text_input("첫 번째 감사 🌱", placeholder="오늘 하나님께 감사한 것을 적어보세요...")
    st.text_input("두 번째 감사 🌻", placeholder="또 다른 감사 제목이 있나요?")
    st.text_input("세 번째 감사 ✨", placeholder="작은 것도 괜찮아요. 하나님은 모든 감사를 기뻐하세요.")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── 완료 버튼 ──
    today_str    = today.isoformat()
    already_done = today_str in st.session_state.completed_dates

    if already_done:
        st.markdown(
            "<div class='done-badge'>🎉 오늘의 QT를 완료했어요! 하나님과 함께한 아름다운 하루를 보내세요.</div>",
            unsafe_allow_html=True,
        )
    else:
        _, c, _ = st.columns([1, 2, 1])
        with c:
            if st.button("✅ 오늘의 QT 완료!", use_container_width=True, type="primary"):
                mark_today_complete()
                st.balloons()
                st.success("🎉 오늘의 말씀 묵상을 완료했습니다! 하나님께서 기뻐하실 거예요.")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 달력 ──
    with st.expander("📅 이번 달 묵상 달력 보기", expanded=already_done):
        render_calendar()

    # ── 푸터 ──
    st.markdown("""
    <div style='text-align:center;margin-top:2rem;padding:1rem;
                color:#BCAAA4;font-size:0.82rem;border-top:1px solid #FFCC80'>
        말씀이 육신이 되어 우리 가운데 거하시매 (요 1:14) · 개역개정 성경
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
