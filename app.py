# app.py
import streamlit as st
import pandas as pd
from pathlib import Path

# =========================
# 기본 설정/경로
# =========================
st.set_page_config(page_title="스마트컵", layout="wide")

DATA_DIR = Path(__file__).parent
CSV_PATH = DATA_DIR / "smartcup_final_6.csv"
IMG_DIR  = DATA_DIR / "images"   # images/{카페명}_{음료명}.jpg 또는 .jpeg

# 세션 상태 초기화
st.session_state.setdefault("page", "cover")
st.session_state.setdefault("detail_row", None)
st.session_state.setdefault("page_num", 1)
st.session_state.setdefault("filters", {})
st.session_state.setdefault("recent", [])
st.session_state.setdefault("favorites", set())
st.session_state.setdefault("_prev_q", "")

PAGE_SIZE = 12

HAS_MODAL  = hasattr(st, "modal")
HAS_DIALOG = hasattr(st, "dialog")

# =========================
# 유틸
# =========================
def safe_filename(text: str) -> str:
    return str(text).replace(" ", "_").replace("/", "-").replace("\\", "-").strip()

def find_image_path(cafe: str, name: str):
    base = f"{safe_filename(cafe)}_{safe_filename(name)}"
    cand1 = IMG_DIR / f"{base}.jpg"
    cand2 = IMG_DIR / f"{base}.jpeg"
    return cand1 if cand1.exists() else (cand2 if cand2.exists() else None)

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

# =========================
# 표지 페이지
# =========================
def render_cover():
    st.markdown(
        """
        <style>
        .cover-wrap { text-align:center; display:flex; flex-direction:column; align-items:center; }
        .cover-emoji { font-size:64px; margin-bottom:16px; }
        .cover-title { font-size:40px; font-weight:800; margin-bottom:8px; }
        .cover-sub   { font-size:18px; color:#374151; margin-bottom:12px; }
        .cover-desc  { font-size:15px; color:#4b5563; line-height:1.5; margin-bottom:10px; }
        @media (max-width: 600px) {
            .cover-title { font-size:32px; }
            .cover-sub   { font-size:16px; }
            .cover-desc  { font-size:14px; }
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

    left_sp, center_col, right_sp = st.columns([3, 1, 3])
    with center_col:
        if st.button("🚀 시작하기", key="start_btn"):
            st.session_state.page = "main"

# =========================
# 메인 페이지
# =========================
def render_main():
    df = pd.read_csv(CSV_PATH)

    # 상단 캡션 복원
    st.caption("왼쪽 사이드바의 필터를 눌러 자유롭게 필터링해보세요.")

    # 제목 스타일
    st.markdown(
        """
        <style>
        .title-wrap { display:flex; flex-direction:column; gap:4px; }
        .title-row  { display:flex; align-items:center; gap:10px; }
        .title-emoji{ font-size:28px; }
        .title-main { font-size:32px; font-weight:900; }
        .title-sub  { font-size:18px; color:#374151; }
        .spacer-vertical{ height:18px; }
        .section-title { font-size:20px; font-weight:800; margin:0; }
        @media (max-width: 600px) {
          .title-emoji{ font-size:24px; }
          .title-main { font-size:28px; }
          .title-sub  { font-size:16px; }
          .section-title { font-size:18px; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # 제목/검색
    left, right = st.columns([5, 2])
    with left:
        st.markdown(
            """
            <div class="title-wrap">
              <div class="title-row">
                <span class="title-emoji">🥤</span>
                <span class="title-main">SMART CUP</span>
              </div>
              <div class="title-sub">건강한 음료 선택 도우미</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with right:
        q = st.text_input(" ", key="search_q", placeholder="🔎 음료명/카페/카테고리 검색",
                          label_visibility="collapsed")
        if st.session_state._prev_q != q:
            st.session_state.page_num = 1
            st.session_state._prev_q = q

    st.markdown('<div class="spacer-vertical"></div>', unsafe_allow_html=True)

    # ==== 사이드바 ====
    st.sidebar.header("🚀 추천/가이드 MODE")
    c1, c2, c3 = st.sidebar.columns(3)
    with c1:
        if st.button("🔥 저칼로리", use_container_width=True, key="preset_lowcal"):
            st.session_state.filters = {"calorie_max": 120}
    with c2:
        if st.button("🍬 당 줄이기", use_container_width=True, key="preset_lowsugar"):
            st.session_state.filters = {"sugar_g_max": 10}
    with c3:
        if st.button("☕ 카페인 줄이기", use_container_width=True, key="preset_lowcaf"):
            st.session_state.filters = {"caffeine_mg_max": 50}

    st.sidebar.header("🧰 필터링 MODE")
    all_cafes = sorted(df["Cafe"].unique())
    all_cats  = sorted(df["Category"].unique())
    all_temps = sorted(df["Temperature"].unique())

    cafes_all_toggle = st.sidebar.checkbox("카페 전체 보기", value=True)
    selected_cafes = all_cafes if cafes_all_toggle else st.sidebar.multiselect("카페 선택", options=all_cafes)

    cats_all_toggle = st.sidebar.checkbox("카테고리 전체 보기", value=True)
    selected_category = all_cats if cats_all_toggle else st.sidebar.multiselect("카테고리 선택", options=all_cats)

    selected_temp = st.sidebar.selectbox("온도", ["전체"] + all_temps)

    # 프리셋 기본값 반영
    cal_max = st.session_state.filters.get("calorie_max", int(df["Calories (kcal)"].max()))
    sug_max = st.session_state.filters.get("sugar_g_max", int(df["Sugar (g)"].max()))
    caf_max = st.session_state.filters.get("caffeine_mg_max", int(df["Caffeine (mg)"].max()))

    calories = st.sidebar.slider("칼로리 (kcal)", 0, int(df["Calories (kcal)"].max()), (0, cal_max))
    caffeine = st.sidebar.slider("카페인 (mg)", 0, int(df["Caffeine (mg)"].max()), (0, caf_max))
    sugar    = st.sidebar.slider("당류 (g)", 0, int(df["Sugar (g)"].max()), (0, sug_max))
    fat      = st.sidebar.slider("지방 (g)", 0, int(df["Fat (g)"].max()), (0, int(df["Fat (g)"].max())))
    sodium   = st.sidebar.slider("나트륨 (mg)", 0, int(df["Sodium (mg)"].max()), (0, int(df["Sodium (mg)"].max())))
    price    = st.sidebar.slider("가격 (원)", 0, int(df["Price (KRW)"].max()), (0, int(df["Price (KRW)"].max())))

    fav_only = st.sidebar.checkbox("⭐ 즐겨찾기만 보기", value=False)

    # 즐겨찾기 / 최근 본 음료
    with st.sidebar.expander("⭐ 즐겨찾기"):
        if st.session_state.favorites:
            for iid in list(st.session_state.favorites)[:8]:
                cafe, name = iid.split("||", 1)
                st.caption(f"- {cafe} | {name}")
        else:
            st.caption("아직 없음")

    with st.sidebar.expander("🕘 최근 본 음료"):
        if st.session_state.recent:
            for iid in st.session_state.recent[:8]:
                cafe, name = iid.split("||", 1)
                st.caption(f"- {cafe} | {name}")
        else:
            st.caption("아직 없음")

    # ==== 필터링 ====
    filtered = df.copy()
    if q:
        mask_q = (filtered["Name"].str.contains(q, case=False, na=False) |
                  filtered["Cafe"].str.contains(q, case=False, na=False) |
                  filtered["Category"].str.contains(q, case=False, na=False))
        filtered = filtered[mask_q]

    if selected_cafes:
        filtered = filtered[filtered["Cafe"].isin(selected_cafes)]
    if selected_category:
        filtered = filtered[filtered["Category"].isin(selected_category)]
    if selected_temp != "전체":
        filtered = filtered[filtered["Temperature"] == selected_temp]

    filtered = filtered[
        filtered["Calories (kcal)"].between(*calories) &
        filtered["Caffeine (mg)"].between(*caffeine) &
        filtered["Sugar (g)"].between(*sugar) &
        filtered["Fat (g)"].between(*fat) &
        filtered["Sodium (mg)"].between(*sodium) &
        filtered["Price (KRW)"].between(*price)
    ]

    if fav_only:
        filtered_ids = filtered.apply(make_item_id, axis=1)
        mask = filtered_ids.isin(st.session_state.favorites)
        filtered = filtered[mask]

    # ==== 결과 ====
    st.markdown('<h3 class="section-title">결과</h3>', unsafe_allow_html=True)

    sort_options = ["칼로리 낮은 순", "가격 낮은 순", "당류 낮은 순", "당류 높은 순",
                    "카페인 낮은 순", "카페인 높은 순"]
    sort_key = st.selectbox("정렬 기준", sort_options, key="sort_key")
    sort_map = {
        "칼로리 낮은 순": ("Calories (kcal)", True),
        "가격 낮은 순": ("Price (KRW)", True),
        "당류 낮은 순": ("Sugar (g)", True),
        "당류 높은 순": ("Sugar (g)", False),
        "카페인 낮은 순": ("Caffeine (mg)", True),
        "카페인 높은 순": ("Caffeine (mg)", False),
    }
    sort_col, asc = sort_map[sort_key]
    filtered = filtered.sort_values(sort_col, ascending=asc)

    st.markdown(f"🔎 **{len(filtered)}개 음료가 조건에 부합합니다.**")
    with st.expander("결과 펼쳐보기"):
        st.dataframe(filtered.reset_index(drop=True), use_container_width=True)

    # (카드/상세 모달 부분은 이전 코드 그대로 유지)
    # ...

# =========================
# 라우팅
# =========================
if st.session_state.page == "cover":
    render_cover()
else:
    render_main()


