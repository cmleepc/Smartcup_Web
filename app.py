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
st.session_state.setdefault("filters", {})         # 프리셋 저장용
st.session_state.setdefault("recent", [])          # 최근 본 음료 (id 리스트)
st.session_state.setdefault("favorites", set())    # 즐겨찾기 (id 집합)
st.session_state.setdefault("_prev_q", "")         # 검색어 변경 감지

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
        .cover-emoji { font-size:64px; line-height:1; margin-bottom:16px; }
        .cover-title { font-size:40px; font-weight:800; margin-bottom:8px; letter-spacing:0.5px; }
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
# 메인(필터 + 정렬 + 카드 + 상세)
# =========================
def render_main():
    df = pd.read_csv(CSV_PATH)

    # 상단 캡션
    st.caption("왼쪽 사이드바의 필터를 눌러 자유롭게 필터링해보세요.")

    # ===== 상단 타이틀/검색 + 전역 스타일 =====
    st.markdown(
        """
        <style>
        .title-wrap { display:flex; flex-direction:column; gap:4px; }
        .title-row  { display:flex; align-items:center; gap:10px; }
        .title-emoji{ font-size:28px; line-height:1; }
        .title-main { font-size:32px; font-weight:900; letter-spacing:0.3px; }
        .spacer-vertical{ height:18px; }  /* '결과' 위쪽 여백 */

        /* 결과 섹션 헤딩(작게) */
        .section-title { font-size:16px; font-weight:700; margin:0; }

        /* 카드와 내부 요소 */
        .card {
          border: 1px solid #eee; border-radius: 16px; padding: 16px; margin-bottom: 12px;
          box-shadow: 0 1px 6px rgba(0,0,0,0.06); height: 100%; position: relative;
          display:flex; flex-direction:column; gap:10px; overflow:hidden;
        }
        .card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:8px; }
        .card-title { font-weight:800; font-size:18px; line-height:1.2; }
        .meta { color:#6b7280; font-size:13px; }
        .badge { display:inline-block; padding:6px 12px; border-radius:999px; font-size:12px; background:#f3f4f6; margin:4px 6px 0 0; }
        .price-row { display:flex; align-items:center; justify-content:space-between; gap:12px; }
        .price { font-weight:800; font-size:18px; }
        .star-btn button { padding:4px 8px !important; min-width:auto !important; border:1px solid #e5e7eb !important; }
        .pill {display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px; background:#f3f4f6; border:1px solid #eee; margin-right:6px;}
        .kv-wrap {display:flex; flex-wrap:wrap; gap:12px; margin-top:6px;}
        .kv-box  {background:#f9fafb; border:1px solid #eee; border-radius:12px; padding:10px 12px; min-width:130px;}
        .kv-lab  {font-size:12px; color:#6b7280; margin-bottom:2px;}
        .kv-val  {font-size:18px; font-weight:700; line-height:1.2;}
        .small   {font-size:14px; color:#374151;}
        .bold    {font-weight:700;}

        @media (max-width: 600px) {
          .title-emoji{ font-size:24px; }
          .title-main { font-size:28px; }
          .section-title { font-size:14px; }
          .card-title { font-size:16px; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    left, right = st.columns([5, 2])
    with left:
        st.markdown(
            """
            <div class="title-wrap">
              <div class="title-row">
                <span class="title-emoji">🥤</span>
                <span class="title-main">SMART CUP</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with right:
        q = st.text_input(
            " ",
            key="search_q",
            placeholder="🔎 음료명/카페/카테고리 검색",
            label_visibility="collapsed",
            help="예) 라떼, 투썸, 프라푸치노"
        )
        if st.session_state._prev_q != q:
            st.session_state.page_num = 1
            st.session_state._prev_q = q

    st.markdown('<div class="spacer-vertical"></div>', unsafe_allow_html=True)

    # ===== 사이드바: 프리셋/필터 =====
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
    selected_cafes = all_cafes if cafes_all_toggle else st.sidebar.multiselect("카페 선택 (복수 가능)", options=all_cafes, default=[])
    cats_all_toggle = st.sidebar.checkbox("카테고리 전체 보기", value=True)
    selected_category = all_cats if cats_all_toggle else st.sidebar.multiselect("카테고리 선택 (복수 가능)", options=all_cats, default=[])
    selected_temp = st.sidebar.selectbox("온도", ["전체"] + all_temps)

    # 프리셋 기본값 반영
    cal_max = st.session_state.filters.get("calorie_max", int(df["Calories (kcal)"].max()))
    sug_max = st.session_state.filters.get("sugar_g_max",   int(df["Sugar (g)"].max()))
    caf_max = st.session_state.filters.get("caffeine_mg_max", int(df["Caffeine (mg)"].max()))

    calories = st.sidebar.slider("칼로리 (kcal)", 0, int(df["Calories (kcal)"].max()), (0, cal_max))
    caffeine = st.sidebar.slider("카페인 (mg)", 0, int(df["Caffeine (mg)"].max()), (0, caf_max))
    sugar    = st.sidebar.slider("당류 (g)",     0, int(df["Sugar (g)"].max()),    (0, sug_max))
    fat      = st.sidebar.slider("지방 (g)",     0, int(df["Fat (g)"].max()),      (0, int(df["Fat (g)"].max())))
    sodium   = st.sidebar.slider("나트륨 (mg)",  0, int(df["Sodium (mg)"].max()),  (0, int(df["Sodium (mg)"].max())))
    price    = st.sidebar.slider("가격 (원)",     0, int(df["Price (KRW)"].max()),  (0, int(df["Price (KRW)"].max())))

    fav_only = st.sidebar.checkbox("⭐ 즐겨찾기만 보기", value=False)

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

    # ===== 필터링 =====
    filtered = df.copy()
    if q:
        mask_q = (
            filtered["Name"].str.contains(q, case=False, na=False) |
            filtered["Cafe"].str.contains(q, case=False, na=False) |
            filtered["Category"].str.contains(q, case=False, na=False)
        )
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

    # ===== 결과 + 정렬 =====
    st.markdown('<h3 class="section-title">결과</h3>', unsafe_allow_html=True)

    sort_options = [
        "칼로리 낮은 순",
        "가격 낮은 순",
        "당류 낮은 순",
        "당류 높은 순",
        "카페인 낮은 순",
        "카페인 높은 순",
    ]
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
        # Cafe 컬럼을 가장 왼쪽으로
        if "Cafe" in filtered.columns:
            left_first_cols = ["Cafe"] + [c for c in filtered.columns if c != "Cafe"]
            preview_df = filtered[left_first_cols].reset_index(drop=True)
        else:
            preview_df = filtered.reset_index(drop=True)
        st.dataframe(preview_df, use_container_width=True)

    # ===== 페이지네이션 =====
    st.markdown("---")
    total = len(filtered)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    st.session_state.page_num = min(max(1, st.session_state.page_num), pages)
    start = (st.session_state.page_num - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_df = filtered.iloc[start:end].reset_index(drop=True)

    # ===== 상세 모달 =====
    def close_detail():
        st.session_state.detail_row = None

    def detail_body(row: pd.Series):
        item_id = make_item_id(row)
        mark_as_viewed(item_id)

        img_path = find_image_path(row["Cafe"], row["Name"])
        col1, col2 = st.columns([1,1])

        with col1:
            if img_path:
                st.image(str(img_path), caption=row["Name"], use_column_width=True)
            else:
                st.info("이미지가 없습니다. (images/ 폴더에 {카페명}_{음료명}.jpg 저장)")

            st.markdown(f"<div class='small'><span class='bold'>카페</span>: {row['Cafe']}</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='small'>"
                f"<span class='pill'>카테고리: {row['Category']}</span>"
                f"<span class='pill'>온도: {row['Temperature']}</span>"
                f"</div>", unsafe_allow_html=True
            )

            st.markdown("<div class='kv-wrap'>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='kv-box'><div class='kv-lab'>용량 (ml)</div>"
                f"<div class='kv-val'>{int(row['Volume (ml)'])}</div></div>", unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='kv-box'><div class='kv-lab'>가격 (원)</div>"
                f"<div class='kv-val'>{int(row['Price (KRW)']):,}</div></div>", unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("<div class='kv-wrap'>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='kv-box'><div class='kv-lab'>칼로리 (kcal)</div>"
                f"<div class='kv-val'>{int(row['Calories (kcal)'])}</div></div>", unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='kv-box'><div class='kv-lab'>카페인 (mg)</div>"
                f"<div class='kv-val'>{int(row['Caffeine (mg)'])}</div></div>", unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='kv-box'><div class='kv-lab'>당류 (g)</div>"
                f"<div class='kv-val'>{int(row['Sugar (g)'])}</div></div>", unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='kv-box'><div class='kv-lab'>지방 (g)</div>"
                f"<div class='kv-val'>{int(row['Fat (g)'])}</div></div>", unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='kv-box'><div class='kv-lab'>나트륨 (mg)</div>"
                f"<div class='kv-val'>{int(row['Sodium (mg)'])}</div></div>", unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        st.caption("Tip: 슬라이더를 조절해 더 깐깐하게 필터링해보세요!")

    def open_detail(row: pd.Series):
        title = f"🍹 {row['Name']} 상세 정보"
        if HAS_MODAL:
            with st.modal(title, key=f"modal-{row.name}"):
                detail_body(row)
                st.button("닫기", on_click=close_detail, use_container_width=True)
        elif HAS_DIALOG:
            @st.dialog(title)
            def _dlg():
                detail_body(row)
                st.button("닫기", on_click=close_detail, use_container_width=True)
            _dlg()
        else:
            st.markdown(f"### {title}")
            detail_body(row)
            st.button("닫기", on_click=close_detail)

    # ===== 카드 렌더링 =====
    cols_per_row = 3
    rows = (len(page_df) + cols_per_row - 1) // cols_per_row
    for r in range(rows):
        cols = st.columns(cols_per_row)
        for c in range(cols_per_row):
            i = r * cols_per_row + c
            if i >= len(page_df):
                continue

            row = page_df.iloc[i]
            title_text = format_title(str(row['Cafe']), str(row['Temperature']), str(row['Name']))
            item_id = make_item_id(row)
            is_fav = item_id in st.session_state.favorites

            badges = (
                f"<span class='badge'>칼로리 {int(row['Calories (kcal)'])}kcal</span>"
                f"<span class='badge'>카페인 {int(row['Caffeine (mg)'])}mg</span>"
                f"<span class='badge'>당 {int(row['Sugar (g)'])}g</span>"
                f"<span class='badge'>나트륨 {int(row['Sodium (mg)'])}mg</span>"
                f"<span class='badge'>지방 {int(row['Fat (g)'])}g</span>"
            )

            with cols[c]:
                st.markdown('<div class="card">', unsafe_allow_html=True)

                # 헤드: 제목 + 작아진 별 버튼
                head_cols = st.columns([1, 0.18])
                with head_cols[0]:
                    st.markdown(f'<div class="card-head"><div class="card-title">{title_text}</div></div>', unsafe_allow_html=True)
                with head_cols[1]:
                    st.markdown('<div class="star-btn">', unsafe_allow_html=True)
                    star_label = "⭐" if is_fav else "☆"
                    if st.button(star_label, key=f"favstar_{item_id}", help="즐겨찾기"):
                        toggle_fav(item_id)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                # 메타: 카테고리 · 용량
                st.markdown(
                    f"<div class='meta'>카테고리: {row['Category']} &nbsp;·&nbsp; 용량: {int(row['Volume (ml)'])} ml</div>",
                    unsafe_allow_html=True
                )

                # 성분 뱃지
                st.markdown(f"<div style='margin:4px 0 2px 0;'>{badges}</div>", unsafe_allow_html=True)

                # 가격(좌) · 자세히 보기(우) — 같은 줄
                st.markdown('<div class="price-row">', unsafe_allow_html=True)
                st.markdown(f"<div class='price'>{int(row['Price (KRW)']):,} 원</div>", unsafe_allow_html=True)
                if st.button("자세히 보기", key=f"detail_{item_id}"):
                    st.session_state.detail_row = row
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('</div>', unsafe_allow_html=True)

    # 페이지 입력(우측)
    right_spacer, right_ctrl = st.columns([5, 1])
    with right_ctrl:
        st.number_input("페이지", min_value=1, max_value=pages, value=st.session_state.page_num, step=1, key="page_num")

    # 상세 표시
    if st.session_state.detail_row is not None:
        open_detail(st.session_state.detail_row)

# =========================
# 라우팅
# =========================
if st.session_state.page == "cover":
    render_cover()
else:
    render_main()


