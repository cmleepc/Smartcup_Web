import streamlit as st
import pandas as pd
import unicodedata
from pathlib import Path

# =========================
# 기본 설정/경로
# =========================
st.set_page_config(page_title="스마트컵", layout="wide")

# ✅ 모바일(≤600px)에서만 전역 폰트 확대
st.markdown("""
<style>
@media (max-width: 600px){
  html, body, [class*="css"] { font-size: 18px !important; line-height: 1.45 !important; }

  /* 기본 컨트롤 확대 */
  .stTextInput input,
  .stSelectbox div[data-baseweb="select"] div,
  textarea, select { font-size: 17px !important; }

  .stButton button { font-size: 18px !important; padding: 10px 14px !important; }
  .stCheckbox, .stRadio, .stSlider { font-size: 18px !important; }

  .stDataFrame div, .stDataFrame table { font-size: 15px !important; }
  .stExpanderHeader, .streamlit-expanderHeader { font-size: 18px !important; }
  .stCaption, .st-emotion-cache-1low4of { font-size: 16px !important; }
}
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path(__file__).parent
CSV_PATH = DATA_DIR / "smartcup_final_6.csv"
IMG_DIR  = DATA_DIR / "images"

# 세션 상태 초기화
st.session_state.setdefault("page", "cover")
st.session_state.setdefault("detail_row", None)
st.session_state.setdefault("page_num", 1)
st.session_state.setdefault("filters", {})
st.session_state.setdefault("recent", [])
st.session_state.setdefault("favorites", set())
st.session_state.setdefault("_prev_q", "")

PAGE_SIZE = 6
HAS_MODAL  = hasattr(st, "modal")
HAS_DIALOG = hasattr(st, "dialog")

# =========================
# 유틸
# =========================
def safe_filename(text: str) -> str:
    return str(text).replace(" ", "_").replace("/", "-").replace("\\", "-").strip()

def _norm_key(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = s.lower().strip()
    return s.replace(" ", "").replace("_", "").replace("-", "")

def find_image_path(cafe: str, name: str, temp: str = ""):
    cafe_raw = str(cafe or "").strip()
    name_raw = str(name or "").strip()
    temp_raw = str(temp or "").strip()

    candidate_stems = [f"{cafe_raw}_{name_raw}"]
    if temp_raw:
        candidate_stems.append(f"{cafe_raw}_{temp_raw} {name_raw}")

    cand_keys = [_norm_key(stem) for stem in candidate_stems]
    allow_ext = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

    if not IMG_DIR.exists():
        return None

    for p in IMG_DIR.iterdir():
        if not p.is_file() or p.suffix not in allow_ext:
            continue
        if _norm_key(p.stem) in cand_keys:
            return p

    cafe_s = safe_filename(cafe_raw)
    name_s = safe_filename(name_raw)
    temp_s = safe_filename(temp_raw) if temp_raw else ""

    candidate_stems2 = [f"{cafe_s}_{name_s}"]
    if temp_s:
        candidate_stems2.append(f"{cafe_s}_{temp_s}_{name_s}")

    cand_keys2 = [_norm_key(stem) for stem in candidate_stems2]
    for p in IMG_DIR.iterdir():
        if not p.is_file() or p.suffix not in allow_ext:
            continue
        if _norm_key(p.stem) in cand_keys2:
            return p
    return None

def format_title(cafe: str, temp: str, name: str) -> str:
    nm = str(name).strip()
    nm_u = nm.upper()
    starts_with_temp = nm_u.startswith("ICE ") or nm_u.startswith("HOT ")
    prefix = "" if starts_with_temp else (temp.strip() + " ") if temp else ""
    return f"{cafe}: {prefix}{nm}".strip()

def make_item_id(row: pd.Series) -> str:
    return f"{row['Cafe']}||{row['Name']}"

def mark_as_viewed(item_id: str):
    rec = list(st.session_state.recent)
    if item_id in rec:
        rec.remove(item_id)
    rec.insert(0, item_id)
    st.session_state.recent = rec[:20]

def toggle_fav(item_id: str):
    fav = set(st.session_state.favorites)
    if item_id in fav:
        fav.remove(item_id)
    else:
        fav.add(item_id)
    st.session_state.favorites = fav

def close_and_rerun():
    st.session_state.detail_row = None
    try:
        st.rerun()
    except:
        pass

# =========================
# 표지 페이지
# =========================
def render_cover():
    st.markdown(
        """
        <style>
        .cover-wrap { text-align:center; display:flex; flex-direction:column; align-items:center; }
        .cover-emoji { font-size:64px; line-height:1; margin-bottom:16px; }
        .cover-title { font-size:40px; font-weight:800; margin-bottom:8px; letter-spacing:0.5px; }
        .cover-sub   { font-size:18px; color:#374151; margin-bottom:12px; }
        .cover-desc  { font-size:15px; color:#4b5563; line-height:1.5; margin-bottom:10px; }

        @media (max-width: 600px) {
            .cover-emoji { font-size:72px; }
            .cover-title { font-size:44px; }
            .cover-sub   { font-size:20px; }
            .cover-desc  { font-size:17px; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="cover-wrap">
          <div class="cover-emoji">🥤</div>
          <div class="cover-title">SMART CUP</div>
          <div class="cover-sub">당신의 건강을 위한 똑똑한 음료 선택 도우미</div>
          <div class="cover-desc">
            카페별 영양성분을 비교하고,<br/>
            목표에 맞는 음료를 빠르게 찾아보세요.
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")
    left_sp, center_col, right_sp = st.columns([3, 1, 2.5])
    with center_col:
        if st.button("🚀 시작하기", key="start_btn"):
            st.session_state.page = "main"

# =========================
# 메인 페이지
# =========================
def render_main():
    df = pd.read_csv(CSV_PATH)

    st.markdown("""
    <style>
    .card-title{ font-size:20px; font-weight:700; line-height:1.2; margin:0 0 6px 0; }
    .meta{ font-size:14px; color:#4b5563; margin-top:2px; }
    .title-row{ display:flex; align-items:center; gap:12px; margin-bottom:12px; }
    .title-emoji{ font-size:48px; line-height:1; }
    .title-main{ font-size:36px; font-weight:800; letter-spacing:0.5px; }
    .price{ font-size:20px; font-weight:600; }
    .pill{ font-size:15px; padding:6px 12px; }

    /* 모바일 전용 확대 */
    @media (max-width: 600px){
      .title-emoji{ font-size:52px; }
      .title-main{ font-size:38px; }
      .card-title{ font-size:21px; }
      .meta{ font-size:15px; }
      .price{ font-size:21px; }
      .pill{ font-size:16px; padding:8px 12px; }
    }
    </style>
    """, unsafe_allow_html=True)

    # (나머지 필터, 카드, 상세 모달 코드는 기존과 동일)
    # ...
    # 그대로 두시면 됩니다!
    # -----------------------
    # 필터링/카드/상세 로직 생략
    # -----------------------

# =========================
# 라우팅
# =========================
if st.session_state.page == "cover":
    render_cover()
else:
    render_main()





