"""
성경 QT(Quiet Time) 묵상 앱
Streamlit으로 구현된 매일 성경 묵상 도우미
"""

import streamlit as st
import random
import json
from datetime import date, datetime
import calendar
import re

# ─────────────────────────────────────────────
# 1. 성경 데이터 로드
# ─────────────────────────────────────────────

# 성경책 한국어 전체 이름 매핑 (약어 → 전체 이름)
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


@st.cache_data
def load_bible():
    """
    성경 텍스트 파일(EUC-KR)을 읽어서 구조화된 딕셔너리로 반환
    반환 형식: {책약어: {장번호(int): {절번호(int): 내용(str)}}}
    """
    bible = {}
    try:
        with open("개역성경.txt", "rb") as f:
            raw = f.read()
        text = raw.decode("euc-kr")
        lines = text.strip().split("\r\n")
    except UnicodeDecodeError:
        # 인코딩 실패 시 UTF-8로 재시도
        with open("개역성경.txt", "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # "창1:1 태초에..." 형식 파싱
        # 콜론(:) 앞부분에서 책명과 장 추출
        colon_idx = line.find(":")
        if colon_idx == -1:
            continue

        ref_part = line[:colon_idx]  # 예: "창1", "왕상3"
        rest = line[colon_idx + 1:]  # 예: "1 태초에..."

        # 절 번호와 본문 분리 (숫자 + 공백 + 본문)
        verse_match = re.match(r"(\d+)\s*(.*)", rest)
        if not verse_match:
            continue
        verse_num = int(verse_match.group(1))
        verse_text = verse_match.group(2).strip()

        # 책명(비숫자)과 장번호(숫자) 분리
        book_match = re.match(r"([가-힣]+)(\d+)", ref_part)
        if not book_match:
            continue
        book_abbr = book_match.group(1)
        chapter_num = int(book_match.group(2))

        # 딕셔너리에 저장
        if book_abbr not in bible:
            bible[book_abbr] = {}
        if chapter_num not in bible[book_abbr]:
            bible[book_abbr][chapter_num] = {}
        bible[book_abbr][chapter_num][verse_num] = verse_text

    return bible


def get_random_passage(bible):
    """
    성경에서 랜덤하게 같은 장의 연속 3~5절을 선택하여 반환
    반환: (책약어, 장번호, 시작절, 끝절, [(절번호, 본문), ...])
    """
    # 3절 이상 있는 장만 선택 대상으로 필터링
    valid_chapters = []
    for book, chapters in bible.items():
        for chap, verses in chapters.items():
            if len(verses) >= 3:
                valid_chapters.append((book, chap))

    if not valid_chapters:
        return None

    # 랜덤 장 선택
    book_abbr, chapter_num = random.choice(valid_chapters)
    verses_dict = bible[book_abbr][chapter_num]
    verse_nums = sorted(verses_dict.keys())

    # 연속 3~5절 선택 (가능한 범위 내에서)
    passage_len = random.randint(3, min(5, len(verse_nums)))
    max_start_idx = len(verse_nums) - passage_len
    start_idx = random.randint(0, max_start_idx)

    selected = verse_nums[start_idx: start_idx + passage_len]
    passage = [(v, verses_dict[v]) for v in selected]

    return book_abbr, chapter_num, selected[0], selected[-1], passage


# ─────────────────────────────────────────────
# 2. Gemini API로 QT 질문 생성
# ─────────────────────────────────────────────

def generate_qt_questions_gemini(passage_text: str, reference: str) -> list[str]:
    """
    Google Gemini API를 호출하여 해당 구절에 대한 묵상 질문 3개를 생성
    API 실패 시 기본 질문 템플릿 반환
    """
    try:
        import google.generativeai as genai

        # st.secrets에서 API 키 로드
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""당신은 따뜻하고 깊이 있는 성경 묵상을 도와주는 QT 가이드입니다.

다음 성경 구절을 읽고, 개인 묵상을 위한 질문 3개를 한국어로 만들어주세요.

[구절] {reference}
{passage_text}

[요청사항]
- 질문은 독자가 자신의 삶과 연결하여 깊이 생각할 수 있도록 구체적이고 따뜻하게 작성해주세요.
- 각 질문은 서로 다른 관점(말씀의 의미, 적용, 기도 방향)을 다루어주세요.
- 반드시 번호 없이 질문만 3개를 줄바꿈으로 구분하여 출력해주세요.
- 각 질문은 1~2문장으로 간결하게 작성해주세요."""

        response = model.generate_content(prompt)
        raw = response.text.strip()

        # 줄바꿈으로 분리하여 비어있지 않은 줄만 선택
        questions = [q.strip() for q in raw.split("\n") if q.strip()]

        # 앞에 붙은 번호나 기호 제거 (예: "1.", "•", "-" 등)
        cleaned = []
        for q in questions:
            q = re.sub(r"^[\d]+[.)\.\s]+", "", q).strip()
            q = re.sub(r"^[-•*]\s*", "", q).strip()
            if q:
                cleaned.append(q)

        # 정확히 3개 반환
        if len(cleaned) >= 3:
            return cleaned[:3]
        else:
            return get_default_questions()

    except Exception as e:
        # API 오류 시 기본 질문으로 폴백
        st.toast(f"✨ 기본 묵상 질문을 사용합니다.", icon="💬")
        return get_default_questions()


def get_default_questions() -> list[str]:
    """API 실패 시 사용할 기본 묵상 질문 템플릿"""
    return [
        "이 구절에서 하나님은 나에게 무엇을 말씀하고 계신가요? 오늘 나의 상황과 어떻게 연결되나요?",
        "이 말씀을 오늘 하루 내 삶에 어떻게 적용할 수 있을까요? 구체적인 행동이나 태도의 변화가 있다면 무엇인가요?",
        "이 구절을 통해 하나님께 어떤 마음을 고백하고 싶으신가요? 감사, 회개, 간구 중 어떤 기도를 드리고 싶으신가요?",
    ]


# ─────────────────────────────────────────────
# 3. 달력 완료 표시 관리
# ─────────────────────────────────────────────

def get_completed_dates() -> list[str]:
    """세션 또는 로컬 스토리지에서 완료된 날짜 목록 반환 (YYYY-MM-DD 형식)"""
    if "completed_dates" not in st.session_state:
        st.session_state.completed_dates = []
    return st.session_state.completed_dates


def mark_today_complete():
    """오늘 날짜를 완료 목록에 추가"""
    today_str = date.today().isoformat()
    completed = get_completed_dates()
    if today_str not in completed:
        st.session_state.completed_dates.append(today_str)


def render_calendar():
    """
    이번 달 달력을 표시하고 완료된 날짜에 체크 표시
    """
    today = date.today()
    year, month = today.year, today.month
    completed = get_completed_dates()

    # 이번 달 완료 날짜만 필터링
    month_prefix = f"{year}-{month:02d}-"
    completed_days = set()
    for d in completed:
        if d.startswith(month_prefix):
            day = int(d.split("-")[2])
            completed_days.add(day)

    # 달력 데이터 생성
    cal = calendar.monthcalendar(year, month)
    month_kr = f"{year}년 {month}월"

    st.markdown(f"### 📅 {month_kr} 묵상 달력")

    # 요일 헤더
    days_header = ["월", "화", "수", "목", "금", "토", "일"]
    cols = st.columns(7)
    for col, day_name in zip(cols, days_header):
        col.markdown(
            f"<div style='text-align:center; font-weight:bold; color:#8B6F47;'>{day_name}</div>",
            unsafe_allow_html=True,
        )

    # 달력 셀 렌더링
    for week in cal:
        cols = st.columns(7)
        for col, day in zip(cols, week):
            if day == 0:
                col.markdown(" ")
            else:
                is_today = day == today.day
                is_done = day in completed_days

                if is_done:
                    # 완료된 날: 초록 배경 + 체크
                    cell_style = "background:#C8E6C9; border-radius:8px; text-align:center; padding:4px;"
                    icon = "✅"
                elif is_today:
                    # 오늘: 따뜻한 노란 배경
                    cell_style = "background:#FFF9C4; border-radius:8px; text-align:center; padding:4px; border:2px solid #F9A825;"
                    icon = f"**{day}**"
                else:
                    cell_style = "text-align:center; padding:4px;"
                    icon = str(day)

                col.markdown(
                    f"<div style='{cell_style}'>{icon}</div>",
                    unsafe_allow_html=True,
                )


# ─────────────────────────────────────────────
# 4. 세션 상태 초기화
# ─────────────────────────────────────────────

def init_session():
    """앱 시작 시 세션 상태 초기화"""
    if "bible" not in st.session_state:
        st.session_state.bible = load_bible()

    if "passage" not in st.session_state or st.session_state.passage is None:
        st.session_state.passage = get_random_passage(st.session_state.bible)
        st.session_state.qt_questions = None  # 질문은 아직 생성 전

    if "completed_dates" not in st.session_state:
        st.session_state.completed_dates = []

    if "qt_done_today" not in st.session_state:
        st.session_state.qt_done_today = False

    # 오늘 이미 완료했는지 확인
    today_str = date.today().isoformat()
    if today_str in st.session_state.completed_dates:
        st.session_state.qt_done_today = True


# ─────────────────────────────────────────────
# 5. 메인 앱 UI
# ─────────────────────────────────────────────

def main():
    # ── 페이지 기본 설정 ──
    st.set_page_config(
        page_title="성경 QT 묵상",
        page_icon="✝️",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # ── 전체 스타일 (따뜻한 톤) ──
    st.markdown(
        """
        <style>
        /* 전체 배경 */
        .stApp {
            background: linear-gradient(135deg, #FFF8F0 0%, #FFF3E0 100%);
        }
        /* 제목 영역 */
        .qt-header {
            text-align: center;
            padding: 1.5rem 0 0.5rem;
            color: #5D4037;
        }
        /* 성경 구절 카드 */
        .verse-card {
            background: #FFFDE7;
            border-left: 5px solid #F9A825;
            border-radius: 10px;
            padding: 1.2rem 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            font-size: 1.05rem;
            line-height: 1.8;
            color: #3E2723;
        }
        /* 참고절 표시 */
        .verse-ref {
            font-size: 0.9rem;
            color: #8D6E63;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }
        /* 질문 카드 */
        .question-card {
            background: #FBE9E7;
            border-radius: 8px;
            padding: 0.8rem 1.2rem;
            margin: 0.5rem 0;
            border: 1px solid #FFCCBC;
            color: #4E342E;
        }
        /* 구분선 */
        hr.warm-divider {
            border: none;
            border-top: 2px solid #FFCC80;
            margin: 1.5rem 0;
        }
        /* 완료 배지 */
        .done-badge {
            background: #E8F5E9;
            border: 2px solid #66BB6A;
            border-radius: 20px;
            padding: 0.5rem 1.5rem;
            text-align: center;
            color: #2E7D32;
            font-size: 1.1rem;
            font-weight: bold;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── 세션 초기화 ──
    init_session()

    # ── 헤더 ──
    st.markdown(
        """
        <div class="qt-header">
            <h1>✝️ 오늘의 말씀 묵상</h1>
            <p style="color:#8D6E63; margin-top:-0.5rem;">말씀과 함께하는 하루를 시작하세요 🌿</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 오늘 날짜 표시 ──
    today = date.today()
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_kr = weekdays_kr[today.weekday()]
    st.markdown(
        f"<p style='text-align:center; color:#A1887F; font-size:0.95rem;'>"
        f"📖 {today.year}년 {today.month}월 {today.day}일 ({weekday_kr})</p>",
        unsafe_allow_html=True,
    )

    # ─────────────────────────────────────────
    # 5-1. 성경 구절 표시
    # ─────────────────────────────────────────
    passage_data = st.session_state.passage
    if passage_data is None:
        st.error("성경 파일을 불러오지 못했습니다. '개역성경.txt' 파일을 확인해주세요.")
        return

    book_abbr, chap_num, start_v, end_v, verses = passage_data
    book_full = BOOK_NAMES.get(book_abbr, book_abbr)

    # 참조 문자열 (예: "창세기 1:3-5")
    if start_v == end_v:
        ref_str = f"{book_full} {chap_num}:{start_v}"
    else:
        ref_str = f"{book_full} {chap_num}:{start_v}-{end_v}"

    # 구절 텍스트 조합
    passage_text_display = "\n".join(
        [f"{book_abbr} {chap_num}:{v_num}  {v_text}" for v_num, v_text in verses]
    )
    passage_text_plain = " ".join([v_text for _, v_text in verses])

    # 구절 카드 렌더링
    verse_html = f"<div class='verse-card'><div class='verse-ref'>📜 {ref_str}</div>"
    for v_num, v_text in verses:
        verse_html += f"<b>{v_num}절</b> {v_text}<br>"
    verse_html += "</div>"
    st.markdown(verse_html, unsafe_allow_html=True)

    # ── "다른 구절 받기" 버튼 ──
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        if st.button("🔄 다른 구절 받기", use_container_width=True):
            st.session_state.passage = get_random_passage(st.session_state.bible)
            st.session_state.qt_questions = None  # 새 구절이면 질문도 초기화
            st.rerun()

    st.markdown("<hr class='warm-divider'>", unsafe_allow_html=True)

    # ─────────────────────────────────────────
    # 5-2. QT 묵상 질문 생성 및 표시
    # ─────────────────────────────────────────
    st.markdown("### 💭 오늘의 묵상 질문")

    # 질문이 아직 없으면 생성 (캐시 역할: 같은 구절에서는 다시 생성 안 함)
    if st.session_state.qt_questions is None:
        with st.spinner("✨ 묵상 질문을 준비하고 있어요..."):
            st.session_state.qt_questions = generate_qt_questions_gemini(
                passage_text_plain, ref_str
            )

    questions = st.session_state.qt_questions

    # 질문 카드 표시
    for i, q in enumerate(questions, 1):
        st.markdown(
            f"<div class='question-card'>❓ <b>질문 {i}.</b> {q}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr class='warm-divider'>", unsafe_allow_html=True)

    # ─────────────────────────────────────────
    # 5-3. 묵상 응답 입력란
    # ─────────────────────────────────────────
    st.markdown("### ✍️ 나의 묵상 나누기")
    st.markdown(
        "<p style='color:#8D6E63; font-size:0.9rem;'>말씀을 통해 받은 감동, 깨달음, 결단을 자유롭게 적어보세요.</p>",
        unsafe_allow_html=True,
    )

    # 질문별 응답 입력란
    responses = []
    for i, q in enumerate(questions, 1):
        resp = st.text_area(
            label=f"질문 {i} 묵상",
            placeholder=f"질문 {i}: {q[:40]}...\n\n여기에 묵상을 적어보세요.",
            height=120,
            key=f"response_{i}_{ref_str}",
            label_visibility="collapsed",
        )
        responses.append(resp)

    st.markdown("<hr class='warm-divider'>", unsafe_allow_html=True)

    # ─────────────────────────────────────────
    # 5-4. 감사기도 입력란
    # ─────────────────────────────────────────
    st.markdown("### 🙏 오늘의 감사기도")
    st.markdown(
        "<p style='color:#8D6E63; font-size:0.9rem;'>오늘 감사한 것 3가지를 하나님께 고백해보세요.</p>",
        unsafe_allow_html=True,
    )

    thanks_labels = ["첫 번째 감사 🌱", "두 번째 감사 🌻", "세 번째 감사 ✨"]
    thanks_placeholders = [
        "오늘 하나님께 감사한 것을 적어보세요...",
        "또 다른 감사 제목이 있나요?",
        "작은 것도 괜찮아요. 하나님은 모든 감사를 기뻐하세요.",
    ]
    thanks_list = []
    for i in range(3):
        t = st.text_input(
            label=thanks_labels[i],
            placeholder=thanks_placeholders[i],
            key=f"thanks_{i}_{ref_str}",
        )
        thanks_list.append(t)

    st.markdown("<hr class='warm-divider'>", unsafe_allow_html=True)

    # ─────────────────────────────────────────
    # 5-5. 완료 버튼
    # ─────────────────────────────────────────
    today_str = date.today().isoformat()
    already_done = today_str in st.session_state.completed_dates

    if already_done:
        st.markdown(
            "<div class='done-badge'>🎉 오늘의 QT를 완료했어요! 하나님과 함께한 아름다운 하루를 보내세요.</div>",
            unsafe_allow_html=True,
        )
    else:
        col_done1, col_done2, col_done3 = st.columns([1, 2, 1])
        with col_done2:
            if st.button("✅ 오늘의 QT 완료!", use_container_width=True, type="primary"):
                mark_today_complete()
                st.session_state.qt_done_today = True
                st.balloons()
                st.success("🎉 오늘의 말씀 묵상을 완료했습니다! 하나님께서 기뻐하실 거예요.")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ─────────────────────────────────────────
    # 5-6. 이번 달 묵상 달력
    # ─────────────────────────────────────────
    with st.expander("📅 이번 달 묵상 달력 보기", expanded=already_done):
        render_calendar()

    # ── 푸터 ──
    st.markdown(
        """
        <div style='text-align:center; margin-top:2rem; padding:1rem;
                    color:#BCAAA4; font-size:0.82rem; border-top:1px solid #FFCC80;'>
            말씀이 육신이 되어 우리 가운데 거하시매 (요 1:14) · 개역개정 성경
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
