# app.py
import streamlit as st
import pandas as pd
import unicodedata
from pathlib import Path

# =========================
# 기본 설정/경로
# =========================
st.set_page_config(page_title="스마트컵", layout="wide")

DATA_DIR = Path(__file__).parent
CSV_PATH = DATA_DIR / "smartcup_final_6.csv"
IMG_DIR  = DATA_DIR / "images"   # images/{카페명}_{음료명}.jpg 또는 {카페명}_{온도} {음료명}.jpg

# 세션 상태 초기화
st.session_state.setdefault("page", "cover")
st.session_state.setdefault("detail_row", None)
st.session_state.setdefault("page_num", 1)
st.session_state.setdefault("filters", {})         # 프리셋 저장용
st.session_state.setdefault("recent", [])          # 최근 본 음료 (id 리스트)
st.session_state.setdefault("favorites", set())    # 즐겨찾기 (id 집합)
st.session_state.setdefault("_prev_q", "")         # 검색어 변경 감지

# 🔽 모바일 고려해 페이지당 카드 수 축소 (6)
PAGE_SIZE = 6
HAS_MODAL  = hasattr(st, "modal")
HAS_DIALOG = hasattr(st, "dialog")

# =========================
# 유틸
# =========================
def safe_filename(text: str) -> str:
    return str(text).replace(" ", "_").replace("/", "-").replace("\\", "-").strip()

def _norm_key(s: str) -> str:
    """검색/파일명 비교용: 한글 포함 공백/언더스코어/하이픈 제거 + 소문자 + 유니코드 정규화"""
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = s.lower().strip()
    return s.replace(" ", "").replace("_", "").replace("-", "")

# --- 교체된 이미지 탐색 함수 ---
def find_image_path(cafe: str, name: str, temp: str = ""):
    """
    images/ 폴더에서 실제 파일들을 순회하며 느슨하게 매칭:
    - 후보: 1) Cafe_Name, 2) Cafe_Temp Name
    - 비교 시 공백/밑줄/하이픈 제거, 소문자화, 유니코드 정규화
    - 확장자 대/소문자 허용 (.jpg/.jpeg/.png)
    """
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

    # 1차: 원문 스템 기반
    for p in IMG_DIR.iterdir():
        if not p.is_file() or p.suffix not in allow_ext:
            continue
        if _norm_key(p.stem) in cand_keys:
            return p

    # 2차: safe_filename 버전
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
    """모바일에서 모달이 안닫히는 케이스 방지용"""
    st.session_state.detail_row = None
    try:
        st.rerun()
    except:  # Streamlit 버전에 따라 호출 불가일 수 있음
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
    left_sp, center_col, right_sp = st.columns([3, 1, 2])
    with center_col:
        if st.button("🚀 시작하기", key="start_btn"):
            st.session_state.page = "main"

# =========================
# 메인(필터 + 정렬 + 카드 + 상세)
# =========================
def render_main():
    df = pd.read_csv(CSV_PATH)

    # ===== 전역 스타일 보강 (간격/배지/온도 색상) =====
# (render_main() 안) 전역 스타일 정의 부분 전체를 아래로 교체
    st.markdown("""
    <style>
    /* ✅ 영양성분 칩: 상자 작게, 글자 크게 */
    .k-badges { gap:4px !important; margin:4px 0 0 0 !important; }
    
    /* div로 만든 배지도 inline-flex로 강제 전환 (높이 낭비 제거) */
    .badge, .badge-pill, div.badge, div.badge-pill {
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
    
      /* 상자 크기 ↓ */
      padding: 2px 8px !important;     /* before: 6px 12px */
      border-radius: 999px !important;
      background: #f3f4f6 !important;
    
      /* 글자 크기 ↑, 줄간격 ↓ */
      font-size: 13px !important;      /* before: 11~12px */
      line-height: 1.05 !important;    /* before: 1.4~1.6 (브라우저 기본) */
    
      /* 여백 최소화 */
      margin: 0 !important;
    }
    
    /* 온도 색상 유지 */
    .temp-hot  { background:#ffe4ec !important; }
    .temp-ice  { background:#e6f3ff !important; }
    .temp-etc  { background:#f3f4f6 !important; }
    </style>
    """, unsafe_allow_html=True)


    # ===== 검색: 띄어쓰기/하이픈/언더스코어 무시 =====
    for col in ["Name", "Cafe", "Category"]:
        df[f"{col}__norm"] = df[col].astype(str).map(_norm_key)

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
            placeholder="🔎 음료명/카페/카테고리 검색 (띄어쓰기 무시)",
            label_visibility="collapsed",
            help="예) 라떼, 투썸, 프라푸치노"
        )
        if st.session_state._prev_q != q:
            st.session_state.page_num = 1
            st.session_state._prev_q = q

    st.caption("왼쪽 사이드바의 필터를 눌러 자유롭게 필터링해보세요.")
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

    # 🔽 검색어 공백/하이픈/언더스코어 무시 검색
    if q:
        q_norm = _norm_key(q)
        mask_q = (
            filtered["Name__norm"].str.contains(q_norm, na=False) |
            filtered["Cafe__norm"].str.contains(q_norm, na=False) |
            filtered["Category__norm"].str.contains(q_norm, na=False)
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
        if "Cafe" in filtered.columns:
            cols = ["Cafe"] + [c for c in filtered.columns if c != "Cafe"]
            preview_df = filtered[cols].reset_index(drop=True)
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
    def detail_body(row: pd.Series):
        item_id = make_item_id(row)
        mark_as_viewed(item_id)

        # 온도 배지 클래스
        temp_val = str(row.get("Temperature", "")).strip().upper()
        temp_cls = "temp-etc"
        if temp_val == "HOT":
            temp_cls = "temp-hot"
        elif temp_val == "ICE":
            temp_cls = "temp-ice"

        # --- 온도까지 포함해 이미지 찾기 ---
        img_path = find_image_path(row["Cafe"], row["Name"], row.get("Temperature", ""))

        # 상단: 이미지 / 주요 메타
        col1, col2 = st.columns([1,1])
        with col1:
            if img_path:
                st.image(str(img_path), caption=row["Name"], use_container_width=True)
            else:
                st.info("이미지가 없습니다. (images/ 폴더에 {카페명}_{음료명}.jpg 또는 {카페명}_{온도} {음료명}.jpg 저장)")

            # 카페/카테고리/온도 → 동일한 '회색/색상' 배지 라인에 정렬
            st.markdown('<div class="k-badges mt-12">', unsafe_allow_html=True)
            st.markdown(f"<span class='badge'>카페: {row['Cafe']}</span>", unsafe_allow_html=True)
            st.markdown(f"<span class='badge'>카테고리: {row['Category']}</span>", unsafe_allow_html=True)
            st.markdown(f"<span class='badge-pill {temp_cls}'>온도: {row['Temperature']}</span>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # 용량/가격 → 한 줄에 나란히
            c_a, c_b = st.columns(2)
            with c_a:
                st.markdown(f"<div class='badge mt-8' style='display:inline-block;'>용량 {int(row['Volume (ml)'])} ml</div>", unsafe_allow_html=True)
            with c_b:
                st.markdown(f"<div class='badge mt-8' style='display:inline-block;'>가격 {int(row['Price (KRW)']):,} 원</div>", unsafe_allow_html=True)

        with col2:
            # 영양 성분 → 3개 위, 2개 아래로 배치하여 세로 길이 단축
            top1, top2, top3 = st.columns(3)
            with top1:
                st.markdown(f"<div class='badge'>칼로리 {int(row['Calories (kcal)'])} kcal</div>", unsafe_allow_html=True)
            with top2:
                st.markdown(f"<div class='badge'>당 {int(row['Sugar (g)'])} g</div>", unsafe_allow_html=True)
            with top3:
                st.markdown(f"<div class='badge'>카페인 {int(row['Caffeine (mg)'])} mg</div>", unsafe_allow_html=True)

            bot1, bot2, _ = st.columns([1,1,1])
            with bot1:
                st.markdown(f"<div class='badge mt-8'>나트륨 {int(row['Sodium (mg)'])} mg</div>", unsafe_allow_html=True)
            with bot2:
                st.markdown(f"<div class='badge mt-8'>지방 {int(row['Fat (g)'])} g</div>", unsafe_allow_html=True)

        st.divider()
        st.caption("Tip: 슬라이더를 조절해 더 깐깐하게 필터링해보세요!")

    def open_detail(row: pd.Series):
        # 제목에서 '상세 정보' 제거 + 카페명 포함
        title = f"🍹 {row['Cafe']} · {row['Name']}"
        if HAS_MODAL:
            with st.modal(title, key=f"modal-{row.name}"):
                detail_body(row)
                # '닫기' → '확인', 클릭 시 강제 리런으로 모바일 이슈 해결
                st.button("확인", on_click=close_and_rerun, use_container_width=True)
        elif HAS_DIALOG:
            @st.dialog(title)
            def _dlg():
                detail_body(row)
                st.button("확인", on_click=close_and_rerun, use_container_width=True)
            _dlg()
        else:
            st.markdown(f"### {title}")
            detail_body(row)
            st.button("확인", on_click=close_and_rerun)

    # ===== 카드 리스트 =====
    cols_per_row = 3
    rows = (len(page_df) + cols_per_row - 1) // cols_per_row
    for r in range(rows):
        cols = st.columns(cols_per_row)
        for c in range(cols_per_row):
            i = r * cols_per_row + c
            if i >= len(page_df):
                continue

            row = page_df.iloc[i]
            item_id = make_item_id(row)
            is_fav = item_id in st.session_state.favorites
            title_text = format_title(str(row['Cafe']), str(row['Temperature']), str(row['Name']))

            with cols[c]:
                # 카드 컨테이너
                with st.container(border=True):
                    top_left, top_right = st.columns([1, 0.15])
                    with top_left:
                        st.markdown(f"### {title_text}")
                    with top_right:
                        st.markdown("<div class='tiny-star'>", unsafe_allow_html=True)
                        if st.button("⭐" if is_fav else "☆", key=f"favstar_{item_id}", help="즐겨찾기"):
                            toggle_fav(item_id)
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)

                    # 상단 메타 간격 확보
                    st.markdown(
                        f"<div class='meta mt-8'>카테고리: {row['Category']} &nbsp;·&nbsp; 용량: {int(row['Volume (ml)'])} ml</div>",
                        unsafe_allow_html=True
                    )

                    # 요약 배지 라인 (간격 확보)
                    st.markdown('<div class="k-badges mt-12">', unsafe_allow_html=True)
                    st.markdown(f"<span class='badge'>칼로리 {int(row['Calories (kcal)'])}kcal</span>", unsafe_allow_html=True)
                    st.markdown(f"<span class='badge'>카페인 {int(row['Caffeine (mg)'])}mg</span>", unsafe_allow_html=True)
                    st.markdown(f"<span class='badge'>당 {int(row['Sugar (g)'])}g</span>", unsafe_allow_html=True)
                    st.markdown(f"<span class='badge'>나트륨 {int(row['Sodium (mg)'])}mg</span>", unsafe_allow_html=True)
                    st.markdown(f"<span class='badge'>지방 {int(row['Fat (g)'])}g</span>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                    price_col, btn_col = st.columns([1, 0.6])
                    with price_col:
                        st.markdown(f"<div class='price mt-8'>{int(row['Price (KRW)']):,} 원</div>", unsafe_allow_html=True)
                    with btn_col:
                        if st.button("자세히 보기", key=f"detail_{item_id}"):
                            st.session_state.detail_row = row

    # 페이지 입력
    right_spacer, right_ctrl = st.columns([5, 1])
    with right_ctrl:
        st.number_input("페이지", min_value=1, max_value=pages, value=st.session_state.page_num, step=1, key="page_num")

    if st.session_state.detail_row is not None:
        open_detail(st.session_state.detail_row)

# =========================
# 라우팅
# =========================
if st.session_state.page == "cover":
    render_cover()
else:
    render_main()
