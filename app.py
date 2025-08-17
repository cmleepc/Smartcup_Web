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

# 고정: 페이지당 카드 수
PAGE_SIZE = 12

# 호환성: modal/dialog 존재 확인
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
    """이름이 이미 ICE/HOT로 시작하면 중복 방지."""
    nm = str(name).strip()
    nm_u = nm.upper()
    starts_with_temp = nm_u.startswith("ICE ") or nm_u.startswith("HOT ")
    prefix = "" if starts_with_temp else (temp.strip() + " ") if temp else ""
    return f"{cafe}: {prefix}{nm}".strip()

def make_item_id(row: pd.Series) -> str:
    """데이터에 고유 ID 컬럼이 없다면 Cafe+Name 조합으로 식별자 생성"""
    return f"{row['Cafe']}||{row['Name']}"

def mark_as_viewed(item_id: str):
    rec = list(st.session_state.recent)
    if item_id in rec:
        rec.remove(item_id)
    rec.insert(0, item_id)
    st.session_state.recent = rec[:20]  # 최대 20개만

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
    # 컵/타이틀을 살짝 오른쪽으로 이동(전체 레이아웃 유지)
    st.markdown(
        """
        <style>
        .cover-shift { transform: translateX(24px); } /* 약간만 오른쪽으로 */
        .cover-emoji { font-size: 64px; line-height: 1; }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown('<div class="cover-emoji cover-shift">🥤</div>', unsafe_allow_html=True)
        st.markdown('<h2 class="cover-shift">스마트컵</h2>', unsafe_allow_html=True)
        st.markdown('<h4 class="cover-shift">건강한 음료 선택을 도와드립니다.</h4>', unsafe_allow_html=True)
        st.markdown('<div class="cover-shift">카페별 영양성분을 비교하고, 목표에 맞는 음료를 빠르게 찾아보세요.</div>', unsafe_allow_html=True)
        st.markdown("---")
        if st.button("🚀 시작하기", use_container_width=True):
            st.session_state.page = "main"

# =========================
# 메인(필터 + 정렬 + 카드 + 상세)
# =========================
def render_main():
    df = pd.read_csv(CSV_PATH)

    # 상단 타이틀 + 오른쪽 정렬 검색창
    left, right = st.columns([5, 2])
    with left:
        st.title("🥤 스마트컵 - 건강한 음료 선택 도우미")
    with right:
        q = st.text_input(
            " ",  # 라벨 숨김용
            key="search_q",
            placeholder="🔎 음료명/카페/카테고리 검색",
            label_visibility="collapsed",
            help="예) 라떼, 투썸, 프라푸치노"
        )
        # 검색어 변경 시 1페이지로 이동
        if st.session_state._prev_q != q:
            st.session_state.page_num = 1
            st.session_state._prev_q = q

    # -------- 사이드바: 프리셋/필터 --------
    st.sidebar.header("🧭 추천/가이드 모드")
    c1, c2, c3 = st.sidebar.columns(3)
    if c1.button("저칼로리"):
        st.session_state.filters = {"calorie_max": 120}
    if c2.button("당 줄이기"):
        st.session_state.filters = {"sugar_g_max": 10}
    if c3.button("카페인 줄이기"):
        st.session_state.filters = {"caffeine_mg_max": 50}

    st.sidebar.header("📋 필터 선택")
    all_cafes = sorted(df["Cafe"].unique())
    all_cats  = sorted(df["Category"].unique())
    all_temps = sorted(df["Temperature"].unique())

    cafes_all_toggle = st.sidebar.checkbox("카페 전체 보기", value=True)
    selected_cafes = all_cafes if cafes_all_toggle else st.sidebar.multiselect("카페 선택 (복수 가능)", options=all_cafes, default=[])

    cats_all_toggle = st.sidebar.checkbox("카테고리 전체 보기", value=True)
    selected_category = all_cats if cats_all_toggle else st.sidebar.multiselect("카테고리 선택 (복수 가능)", options=all_cats, default=[])

    selected_temp = st.sidebar.selectbox("온도", ["전체"] + all_temps)

    # 프리셋 기본값 반영 (없으면 최대치로)
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

    # 최근/즐겨찾기 사이드 요약
    with st.sidebar.expander("🕘 최근 본 음료"):
        if st.session_state.recent:
            for iid in st.session_state.recent[:8]:
                cafe, name = iid.split("||", 1)
                st.caption(f"- {cafe} | {name}")
        else:
            st.caption("아직 없음")

    with st.sidebar.expander("⭐ 즐겨찾기"):
        if st.session_state.favorites:
            for iid in list(st.session_state.favorites)[:8]:
                cafe, name = iid.split("||", 1)
                st.caption(f"- {cafe} | {name}")
        else:
            st.caption("아직 없음")

    # -------- 필터링 --------
    filtered = df.copy()

    # (A) 검색어 필터: 음료명/카페/카테고리에 부분일치
    if q:
        mask_q = (
            filtered["Name"].str.contains(q, case=False, na=False) |
            filtered["Cafe"].str.contains(q, case=False, na=False) |
            filtered["Category"].str.contains(q, case=False, na=False)
        )
        filtered = filtered[mask_q]

    # (B) 일반 필터
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
        # 즐겨찾기만 보기
        filtered_ids = filtered.apply(make_item_id, axis=1)
        mask = filtered_ids.isin(st.session_state.favorites)
        filtered = filtered[mask]

    # -------- 정렬 --------
    st.markdown("### 결과")
    sort_key = st.selectbox("정렬 기준", ["칼로리 낮은 순", "가격 낮은 순", "카페인 높은 순"], key="sort_key")
    sort_map = {
        "칼로리 낮은 순": ("Calories (kcal)", True),
        "가격 낮은 순": ("Price (KRW)", True),
        "카페인 높은 순": ("Caffeine (mg)", False),
    }
    sort_col, asc = sort_map[sort_key]
    filtered = filtered.sort_values(sort_col, ascending=asc)

    # -------- 결과 숫자 + 미니 테이블(옵션) --------
    st.markdown(f"🔎 **{len(filtered)}개 음료가 조건에 부합합니다.**")
    with st.expander("결과 데이터 미리보기 (선택)"):
        st.dataframe(filtered.reset_index(drop=True), use_container_width=True)

    # -------- 공통 스타일 --------
    st.markdown("""
    <style>
    /* 카드 */
    .card {
      border: 1px solid #eee; border-radius: 16px; padding: 14px; margin-bottom: 12px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.06); height: 100%; position: relative;
    }
    .badge {
      display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px; background:#f3f4f6; margin:4px 6px 0 0;
    }
    .name { font-weight:700; font-size:16px; margin-bottom:4px; }
    .meta { color:#6b7280; font-size:13px; }
    .price { font-weight:700; }
    .fav-btn { position:absolute; right:12px; top:10px; font-size:18px; }

    /* 모달 내부 꾸미기 */
    .pill {display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px;
           background:#f3f4f6; border:1px solid #eee; margin-right:6px;}
    .kv-wrap {display:flex; flex-wrap:wrap; gap:12px; margin-top:6px;}
    .kv-box  {background:#f9fafb; border:1px solid #eee; border-radius:12px; padding:10px 12px; min-width:130px;}
    .kv-lab  {font-size:12px; color:#6b7280; margin-bottom:2px;}
    .kv-val  {font-size:18px; font-weight:700; line-height:1.2;}
    .small   {font-size:14px; color:#374151;}
    .bold    {font-weight:700;}
    </style>
    """, unsafe_allow_html=True)

    # -------- 페이지네이션 --------
    st.markdown("---")
    total = len(filtered)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    st.session_state.page_num = min(max(1, st.session_state.page_num), pages)

    start = (st.session_state.page_num - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_df = filtered.iloc[start:end].reset_index(drop=True)

    def close_detail():
        st.session_state.detail_row = None

    def detail_body(row: pd.Series):
        # 최근 본 음료 기록
        item_id = make_item_id(row)
        mark_as_viewed(item_id)

        img_path = find_image_path(row["Cafe"], row["Name"])
        col1, col2 = st.columns([1,1])

        with col1:
            if img_path:
                st.image(str(img_path), caption=row["Name"], use_column_width=True)
            else:
                st.info("이미지가 없습니다. (images/ 폴더에 {카페명}_{음료명}.jpg 저장)")

            # 기본 정보: 카페 Bold, 카테고리/온도 pill
            st.markdown(f"<div class='small'><span class='bold'>카페</span>: {row['Cafe']}</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='small'>"
                f"<span class='pill'>카테고리: {row['Category']}</span>"
                f"<span class='pill'>온도: {row['Temperature']}</span>"
                f"</div>", unsafe_allow_html=True
            )

            # 용량/가격 박스
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
            # 영양성분 5개 박스
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
        if HAS_MODAL:                      # 최신 Streamlit
            with st.modal(title, key=f"modal-{row.name}"):
                detail_body(row)
                st.button("닫기", on_click=close_detail, use_container_width=True)
        elif HAS_DIALOG:                   # 일부 버전
            @st.dialog(title)
            def _dlg():
                detail_body(row)
                st.button("닫기", on_click=close_detail, use_container_width=True)
            _dlg()
        else:                              # 완전 폴백
            st.markdown(f"### {title}")
            detail_body(row)
            st.button("닫기", on_click=close_detail)

    # -------- 카드 렌더링 (즐겨찾기 토글/상세) --------
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
                f"<span class='badge'>용량 {int(row['Volume (ml)'])}ml</span>"
                f"<span class='badge'>나트륨 {int(row['Sodium (mg)'])}mg</span>"
                f"<span class='badge'>지방 {int(row['Fat (g)'])}g</span>"
            )

            with cols[c]:
                st.markdown(
                    f"""
                    <div class="card">
                      <div class="fav-btn">{'⭐' if is_fav else '☆'}</div>
                      <div class="name">{title_text}</div>
                      <div class="meta">카테고리: {row['Category']}</div>
                      <div style="margin:8px 0;">{badges}</div>
                      <div style="margin-top:8px;" class="price">{int(row['Price (KRW)']):,} 원</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                # 즐겨찾기 토글 버튼 & 상세 버튼
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("⭐ 즐겨찾기", key=f"fav_{i}_{item_id}"):
                        toggle_fav(item_id)
                with cc2:
                    if st.button("자세히 보기", key=f"detail_{i}_{item_id}"):
                        st.session_state.detail_row = row

    # 페이지 선택(카드 아래 오른쪽, 12개 고정)
    right_spacer, right_ctrl = st.columns([5, 1])
    with right_ctrl:
        st.number_input(
            "페이지",
            min_value=1, max_value=pages,
            value=st.session_state.page_num, step=1, key="page_num"
        )

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



