import datetime
import altair as alt
import pandas as pd
import pytz
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 오스카(Gold & Black) 커스텀 CSS 적용
# -----------------------------------------------------------------------------
st.set_page_config(page_title="ACADEMY BOX OFFICE", layout="wide")

# 오스카 시상식 느낌의 폰트(Cinzel) 및 골드/블랙 럭셔리 스타일링
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;900&family=Noto+Sans+KR:wght@300;400;600;700&display=swap');

    /* 전체 배경 및 기본 폰트 */
    .stApp {
        background-color: #0E0E10;
        color: #E6E6E6;
        font-family: 'Noto Sans KR', sans-serif;
    }

    /* 오스카 헤더 타이틀 (클래식 골드) */
    h1, h2, h3 {
        font-family: 'Cinzel', 'Noto Sans KR', serif !important;
        color: #D4AF37 !important;
        letter-spacing: 2px;
        font-weight: 700;
        text-transform: uppercase;
    }

    /* 카드(Metric) 메인 박스 스타일링 - 은은한 골드 테두리 */
    div[data-testid="stMetric"] {
        background-color: #16161A;
        border: 1px solid #2A261A;
        border-left: 4px solid #D4AF37;
        padding: 18px 22px;
        border-radius: 4px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
    }

    div[data-testid="stMetricValue"] {
        color: #F8F5E6 !important;
        font-weight: 700;
        font-size: 1.6rem !important;
    }

    div[data-testid="stMetricLabel"] {
        color: #C5A059 !important;
        font-size: 0.85rem !important;
        letter-spacing: 1px;
        margin-bottom: 4px;
    }

    /* 구분선 컬러 (다크 골드/브론즈 톤) */
    hr {
        border-color: #2A2415 !important;
    }

    /* 날짜 선택 박스 스타일링 */
    .stDateInput > div {
        background-color: #16161A;
        border: 1px solid #3A321F;
        color: #FFFFFF;
        border-radius: 4px;
    }

    /* 서브 캡션 색상 */
    .stCaption {
        color: #9A8A6B !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("DAILY BOX OFFICE")

# -----------------------------------------------------------------------------
# 2. 한국 시간(KST) 기준 날짜 선택 (어제 날짜까지 선택 가능)
# -----------------------------------------------------------------------------
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
yesterday_kst = (now_kst - datetime.timedelta(days=1)).date()

selected_date = st.date_input(
    "조회 날짜 선택 (오늘 날짜는 집계 전입니다)",
    value=yesterday_kst,
    max_value=yesterday_kst,
)

target_dt = selected_date.strftime("%Y%m%d")
st.caption(f"조회 기준일: {selected_date.strftime('%Y년 %m월 %d일')}")

# -----------------------------------------------------------------------------
# 3. API Key 지정
# -----------------------------------------------------------------------------
api_key = "37743c31b2564c533a1fde24bb8558ab"

# -----------------------------------------------------------------------------
# 4. KOBIS API 데이터 요청
# -----------------------------------------------------------------------------
api_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt}

try:
    response = requests.get(api_url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    st.error("네트워크 또는 API 서버 통신 오류가 발생했습니다.")
    st.info(f"확인 사항: 인터넷 연결 상태 및 KOBIS 서버 응답 상태 ({e})")
    st.stop()

# -----------------------------------------------------------------------------
# 5. API 응답 검증 및 예외 처리
# -----------------------------------------------------------------------------
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("API 인증 오류가 발생했습니다.")
    st.info(
        f"오류 메시지: {fault.get('message', '알 수 없는 오류')} (코드: {fault.get('errorCode', 'N/A')})"
    )
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("선택하신 날짜의 박스오피스 데이터가 존재하지 않습니다.")
    st.info("그날은 아직 집계 전입니다.")
    st.stop()

# -----------------------------------------------------------------------------
# 6. 데이터 전처리
# -----------------------------------------------------------------------------
df = pd.DataFrame(daily_list)

# 숫자형 컬럼 변환
numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# 전날 대비 순위 증감 텍스트 처리
def format_rank_inten(val):
    if val > 0:
        return f"▲ {val}"
    elif val < 0:
        return f"▼ {abs(val)}"
    else:
        return "-"


df["순위변동"] = df["rankInten"].apply(format_rank_inten)

# -----------------------------------------------------------------------------
# 7. 대시보드 화면 구성
# -----------------------------------------------------------------------------

# [지표 카드 3장] 1위 영화 하이라이트
top_1 = df.iloc[0]
st.subheader("TOP MOVIE")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="1위 영화", value=top_1["movieNm"])
with col2:
    st.metric(label="당일 관객 수", value=f"{top_1['audiCnt']:,} 명")
with col3:
    st.metric(label="누적 관객 수", value=f"{top_1['audiAcc']:,} 명")

st.divider()

# [막대그래프] 관객 수 상위 5편 (황금색 막대, 고정 높이)
st.subheader("TOP 5 AUDIENCE CHART")
top5_df = df.head(5)[["movieNm", "audiCnt"]].copy()
top5_df.rename(
    columns={"movieNm": "영화명", "audiCnt": "당일관객수"}, inplace=True
)

chart = (
    alt.Chart(top5_df)
    .mark_bar(color="#D4AF37", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    .encode(
        x=alt.X(
            "영화명:N",
            sort=None,
            axis=alt.Axis(
                labelAngle=0, labelColor="#CCCCCC", title=None, labelFontSize=12
            ),
        ),
        y=alt.Y(
            "당일관객수:Q",
            axis=alt.Axis(
                labelColor="#CCCCCC",
                title="관객 수 (명)",
                titleColor="#9A8A6B",
                gridColor="#2A2415",
            ),
        ),
        tooltip=["영화명", "당일관객수"],
    )
    .properties(height=300)
    .configure_view(strokeWidth=0)
    .configure_background(background="transparent")
)

st.altair_chart(chart, use_container_width=True)

st.divider()

# [표] 전체 순위 목록
st.subheader("BOX OFFICE RANKING")

display_df = df[
    ["rank", "순위변동", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()
display_df.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]

st.dataframe(
    display_df.style.format(
        {"관객수": "{:,}명", "누적관객": "{:,}명", "스크린수": "{:,}개"}
    ),
    use_container_width=True,
    hide_index=True,
)
