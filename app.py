"""
성경 QT(Quiet Time) 묵상 앱
Streamlit으로 구현된 매일 성경 묵상 도우미
"""

import json
import os
import re
import random
import calendar
from datetime import date, datetime

import streamlit as st

# ─────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────
QT_RECORDS_FILE = "qt_records.json"

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
# 1. QT 기록 영구 저장/로드 (Notion 우선, 없으면 로컬 JSON)
# ─────────────────────────────────────────────
import requests as _requests

NOTION_API = "https://api.notion.com/v1"


def _notion_headers():
    token = st.secrets.get("NOTION_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }


def _notion_ok():
    return bool(st.secrets.get("NOTION_TOKEN", "") and st.secrets.get("NOTION_DATABASE_ID", ""))


def load_qt_records() -> dict:
    if _notion_ok():
        try:
            db_id    = st.secrets.get("NOTION_DATABASE_ID", "")
            response = _requests.post(
                f"{NOTION_API}/databases/{db_id}/query",
                headers=_notion_headers(),
                json={},
            ).json()

            records = {}
            for page in response.get("results", []):
                title_list = page["properties"].get("Name", {}).get("title", [])
                date_str   = title_list[0]["plain_text"] if title_list else ""
                if not date_str:
                    continue

                blocks   = _requests.get(
                    f"{NOTION_API}/blocks/{page['id']}/children",
                    headers=_notion_headers(),
                ).json()
                raw_json = ""
                for block in blocks.get("results", []):
                    if block["type"] == "paragraph":
                        for rt in block["paragraph"]["rich_text"]:
                            raw_json += rt["plain_text"]
                if raw_json:
                    try:
                        records[date_str] = json.loads(raw_json)
                    except Exception:
                        pass
            return records
        except Exception as e:
            st.warning(f"Notion 로드 실패, 로컬 파일 사용: {e}")

    if os.path.exists(QT_RECORDS_FILE):
        try:
            with open(QT_RECORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_qt_records(records: dict):
    if _notion_ok():
        try:
            db_id       = st.secrets.get("NOTION_DATABASE_ID", "")
            latest_date = max(records.keys())
            data_json   = json.dumps(records[latest_date], ensure_ascii=False)
            chunks      = [data_json[i:i+2000] for i in range(0, len(data_json), 2000)]
            children    = [
                {
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": c}}]},
                }
                for c in chunks
            ]

            # 기존 페이지 조회
            existing = _requests.post(
                f"{NOTION_API}/databases/{db_id}/query",
                headers=_notion_headers(),
                json={"filter": {"property": "Name", "title": {"equals": latest_date}}},
            ).json()

            if existing.get("results"):
                page_id    = existing["results"][0]["id"]
                old_blocks = _requests.get(
                    f"{NOTION_API}/blocks/{page_id}/children",
                    headers=_notion_headers(),
                ).json()
                for b in old_blocks.get("results", []):
                    _requests.delete(f"{NOTION_API}/blocks/{b['id']}", headers=_notion_headers())
                _requests.patch(
                    f"{NOTION_API}/blocks/{page_id}/children",
                    headers=_notion_headers(),
                    json={"children": children},
                )
            else:
                _requests.post(
                    f"{NOTION_API}/pages",
                    headers=_notion_headers(),
                    json={
                        "parent": {"database_id": db_id},
                        "properties": {"Name": {"title": [{"text": {"content": latest_date}}]}},
                        "children": children,
                    },
                )
            return
        except Exception as e:
            st.warning(f"Notion 저장 실패, 로컬 파일에 저장: {e}")

    with open(QT_RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# 2. 성경 데이터 로드
# ─────────────────────────────────────────────
@st.cache_data
def load_bible():
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
        ref_part = line[:colon]
        rest     = line[colon + 1:]

        m_verse = re.match(r"(\d+)\s*(.*)", rest)
        if not m_verse:
            continue
        verse_num  = int(m_verse.group(1))
        verse_text = m_verse.group(2).strip()

        m_book = re.match(r"([가-힣]+)(\d+)", ref_part)
        if not m_book:
            continue
        book_abbr = m_book.group(1)
        chap_num  = int(m_book.group(2))

        bible.setdefault(book_abbr, {}).setdefault(chap_num, {})[verse_num] = verse_text

    return bible


def get_random_passage(bible, seed=None):
    """같은 장의 연속 3~5절을 랜덤 선택. seed가 있으면 동일 결과 보장."""
    valid = [
        (book, chap)
        for book, chapters in bible.items()
        for chap, verses in chapters.items()
        if len(verses) >= 3
    ]
    if not valid:
        return None

    rng = random.Random(seed)
    book_abbr, chap_num = rng.choice(valid)
    verse_nums = sorted(bible[book_abbr][chap_num].keys())
    length     = rng.randint(3, min(5, len(verse_nums)))
    start_idx  = rng.randint(0, len(verse_nums) - length)
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

    except Exception as e:
        st.warning(f"⚠️ AI 질문 생성 실패 (기본 질문으로 대체): `{e}`")
        return get_default_questions()


# ─────────────────────────────────────────────
# 4. 달력 렌더링 (완료 날짜 클릭 가능)
# ─────────────────────────────────────────────
def render_calendar():
    today      = date.today()
    year, month = today.year, today.month
    prefix     = f"{year}-{month:02d}-"

    records         = st.session_state.qt_records
    completed_days  = {
        int(d.split("-")[2])
        for d, v in records.items()
        if d.startswith(prefix) and v.get("is_completed", False)
    }

    st.markdown(f"### 📅 {year}년 {month}월 묵상 달력")

    # 요일 헤더
    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    header_cols = st.columns(7)
    for i, dn in enumerate(day_names):
        header_cols[i].markdown(
            f"<div style='text-align:center;font-weight:bold;color:#8B6F47;font-size:0.9rem'>{dn}</div>",
            unsafe_allow_html=True,
        )

    # 날짜 행
    for week in calendar.monthcalendar(year, month):
        week_cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                week_cols[i].write("")
            elif day in completed_days:
                date_str = f"{year}-{month:02d}-{day:02d}"
                if week_cols[i].button(
                    f"✅\n{day}",
                    key=f"cal_{date_str}",
                    use_container_width=True,
                    help=f"{date_str} 묵상 기록 보기",
                ):
                    st.session_state.view_date = (
                        None if st.session_state.get("view_date") == date_str else date_str
                    )
                    st.rerun()
            elif day == today.day:
                week_cols[i].markdown(
                    f"<div style='text-align:center;background:#FFF9C4;border:2px solid #F9A825;"
                    f"border-radius:8px;padding:4px 0;font-weight:bold;color:#5D4037'>{day}</div>",
                    unsafe_allow_html=True,
                )
            else:
                week_cols[i].markdown(
                    f"<div style='text-align:center;color:#5D4037;padding:4px 0'>{day}</div>",
                    unsafe_allow_html=True,
                )


# ─────────────────────────────────────────────
# 5. 저장된 QT 기록 표시
# ─────────────────────────────────────────────
def render_qt_record(date_str: str):
    record = st.session_state.qt_records.get(date_str)
    if not record:
        st.info("해당 날짜의 기록이 없습니다.")
        return

    d = datetime.strptime(date_str, "%Y-%m-%d")
    weekday_kr = ["월","화","수","목","금","토","일"][d.weekday()]
    st.markdown(
        f"<h4 style='color:#5D4037'>📖 {d.year}년 {d.month}월 {d.day}일 ({weekday_kr}) 묵상 기록</h4>",
        unsafe_allow_html=True,
    )

    # 구절
    st.markdown(
        f"<div class='verse-card'>"
        f"<div class='verse-ref'>📜 {record['passage_ref']}</div>"
        f"{record['passage_html']}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 묵상 질문
    if record.get("questions"):
        st.markdown("**💭 묵상 질문**")
        for i, q in enumerate(record["questions"], 1):
            st.markdown(
                f"<div class='question-card'>❓ <b>질문 {i}.</b> {q}</div>",
                unsafe_allow_html=True,
            )

    # 나의 묵상
    if record.get("meditation"):
        st.markdown("**✍️ 나의 묵상**")
        st.markdown(
            f"<div style='background:#FFF8E1;border-left:4px solid #FFB300;border-radius:8px;"
            f"padding:1rem 1.2rem;color:#3E2723;white-space:pre-wrap'>{record['meditation']}</div>",
            unsafe_allow_html=True,
        )

    # 감사기도
    gratitudes = [g for g in record.get("gratitude", []) if g]
    if gratitudes:
        st.markdown("**🙏 감사기도**")
        for emoji, g in zip(["🌱", "🌻", "✨"], gratitudes):
            st.markdown(
                f"<div style='background:#E8F5E9;border-radius:8px;padding:0.5rem 1rem;"
                f"margin:0.3rem 0;color:#2E7D32'>{emoji} {g}</div>",
                unsafe_allow_html=True,
            )

    if st.button("닫기", key=f"close_{date_str}"):
        st.session_state.view_date = None
        st.rerun()


# ─────────────────────────────────────────────
# 6. 메인
# ─────────────────────────────────────────────
def main():
    st.set_page_config(page_title="성경 QT 묵상", page_icon="✝️", layout="centered")

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
    if "qt_records" not in st.session_state:
        st.session_state.qt_records = load_qt_records()
    if "passage" not in st.session_state:
        today_seed = int(date.today().strftime("%Y%m%d"))
        st.session_state.passage             = get_random_passage(st.session_state.bible, seed=today_seed)
        st.session_state.questions           = None
        st.session_state.extra_passage_count = 0
    if "gemini_api_key" not in st.session_state:
        st.session_state.gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
    if "view_date" not in st.session_state:
        st.session_state.view_date = None

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
    st.markdown("### 🔑 Gemini API 키 설정")
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
        if st.button("저장", use_container_width=True, key="save_api_key"):
            if new_key != st.session_state.gemini_api_key:
                st.session_state.gemini_api_key = new_key
                st.session_state.questions = None
                st.rerun()
    if st.session_state.gemini_api_key:
        st.success("✅ API 키가 설정되어 있습니다. AI가 구절에 맞는 질문을 생성합니다.")
    else:
        st.warning("⚠️ API 키 없이는 기본 질문이 표시됩니다. [API 키 발급](https://aistudio.google.com/app/apikey)")
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

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

    # passage_html: 절별 텍스트 (저장용 + 화면 표시용 공용)
    passage_html = "".join(f"<b>{v_num}절</b> {v_text}<br>" for v_num, v_text in verses)

    html = f"<div class='verse-card'><div class='verse-ref'>📜 {ref_str}</div>{passage_html}</div>"
    st.markdown(html, unsafe_allow_html=True)

    # 다른 구절 버튼
    today_str    = today.isoformat()
    today_record = st.session_state.qt_records.get(today_str, {})
    already_done = today_record.get("is_completed", False)

    if not already_done:
        _, c, _ = st.columns([1, 2, 1])
        with c:
            if st.button("🔄 다른 구절 받기", use_container_width=True):
                st.session_state.extra_passage_count += 1
                new_seed = int(date.today().strftime("%Y%m%d")) + st.session_state.extra_passage_count
                st.session_state.passage   = get_random_passage(st.session_state.bible, seed=new_seed)
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

    # ── 나의 묵상 나누기 ──
    st.markdown("### ✍️ 나의 묵상 나누기")
    st.markdown(
        "<p style='color:#8D6E63;font-size:0.9rem'>말씀을 통해 받은 감동, 깨달음, 결단을 자유롭게 적어보세요.</p>",
        unsafe_allow_html=True,
    )
    meditation_value = today_record.get("meditation", "")
    st.text_area(
        label="나의 묵상",
        value=meditation_value if (already_done or meditation_value) else None,
        placeholder="여기에 묵상을 적어보세요.",
        height=250,
        key="my_meditation_single",
        disabled=already_done,
    )
    if not already_done:
        _, c, _ = st.columns([1, 2, 1])
        with c:
            if st.button("💾 묵상 저장", use_container_width=True, key="save_meditation"):
                draft = {
                    **today_record,
                    "passage_ref":  ref_str,
                    "passage_html": passage_html,
                    "questions":    st.session_state.questions or [],
                    "meditation":   st.session_state.get("my_meditation_single", ""),
                    "is_completed": False,
                }
                st.session_state.qt_records[today_str] = draft
                save_qt_records(st.session_state.qt_records)
                st.success("💾 묵상이 저장되었습니다!")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── 감사기도 ──
    st.markdown("### 🙏 오늘의 감사기도")
    st.markdown(
        "<p style='color:#8D6E63;font-size:0.9rem'>오늘 감사한 것 3가지를 하나님께 고백해보세요.</p>",
        unsafe_allow_html=True,
    )
    saved_gratitude = st.session_state.qt_records.get(today_str, {}).get("gratitude", ["", "", ""])
    st.text_input("첫 번째 감사 🌱", placeholder="오늘 하나님께 감사한 것을 적어보세요...",
                  key="gratitude_1", value=saved_gratitude[0] if already_done else None,
                  disabled=already_done)
    st.text_input("두 번째 감사 🌻", placeholder="또 다른 감사 제목이 있나요?",
                  key="gratitude_2", value=saved_gratitude[1] if already_done else None,
                  disabled=already_done)
    st.text_input("세 번째 감사 ✨", placeholder="작은 것도 괜찮아요. 하나님은 모든 감사를 기뻐하세요.",
                  key="gratitude_3", value=saved_gratitude[2] if already_done else None,
                  disabled=already_done)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── 완료 버튼 ──
    if already_done:
        st.markdown(
            "<div class='done-badge'>🎉 오늘의 QT를 완료했어요! 하나님과 함께한 아름다운 하루를 보내세요.</div>",
            unsafe_allow_html=True,
        )
    else:
        _, c, _ = st.columns([1, 2, 1])
        with c:
            if st.button("✅ 오늘의 QT 완료!", use_container_width=True, type="primary"):
                # 현재 입력값 수집
                record = {
                    "passage_ref":  ref_str,
                    "passage_html": passage_html,
                    "questions":    st.session_state.questions or [],
                    "meditation":   st.session_state.get("my_meditation_single", ""),
                    "gratitude": [
                        st.session_state.get("gratitude_1", ""),
                        st.session_state.get("gratitude_2", ""),
                        st.session_state.get("gratitude_3", ""),
                    ],
                    "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "is_completed": True,
                }
                st.session_state.qt_records[today_str] = record
                save_qt_records(st.session_state.qt_records)
                st.balloons()
                st.success("🎉 오늘의 말씀 묵상을 완료했습니다! 하나님께서 기뻐하실 거예요.")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 달력 ──
    with st.expander("📅 이번 달 묵상 달력 보기", expanded=already_done):
        render_calendar()
        if st.session_state.qt_records:
            st.markdown(
                "<p style='color:#8D6E63;font-size:0.85rem;margin-top:0.5rem'>"
                "✅ 표시된 날짜를 클릭하면 그날의 묵상 기록을 볼 수 있어요.</p>",
                unsafe_allow_html=True,
            )

    # ── 선택된 날짜의 QT 기록 ──
    if st.session_state.view_date:
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        render_qt_record(st.session_state.view_date)

    # ── 푸터 ──
    st.markdown("""
    <div style='text-align:center;margin-top:2rem;padding:1rem;
                color:#BCAAA4;font-size:0.82rem;border-top:1px solid #FFCC80'>
        말씀이 육신이 되어 우리 가운데 거하시매 (요 1:14) · 개역개정 성경
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
