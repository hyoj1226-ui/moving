import datetime
import pandas as pd
import pytz
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 타이틀
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="일별 박스오피스 순위", page_icon="🎬", layout="wide"
)

st.title("🎬 일별 박스오피스 순위 조회")

# -----------------------------------------------------------------------------
# 2. 한국 시간(KST) 기준 날짜 선택 (오늘 자 미집계로 '어제'까지 선택 가능)
# -----------------------------------------------------------------------------
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
yesterday_kst = (now_kst - datetime.timedelta(days=1)).date()

# 달력(date_input)에서 조회할 날짜 선택 (최대 '어제' 날짜까지만 선택 가능하도록 설정)
selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요 (오늘 날짜는 아직 집계 전입니다)",
    value=yesterday_kst,
    max_value=yesterday_kst,
)

target_dt = selected_date.strftime("%Y%m%d")

st.caption(f"📌 선택한 조회 기준 날짜: {selected_date.strftime('%Y년 %m월 %d일')}")

# -----------------------------------------------------------------------------
# 3. API Key 지정 (방법 3: 코드 직접 지정)
# -----------------------------------------------------------------------------
api_key = "37743c31b2564c533a1fde24bb8558ab"

# -----------------------------------------------------------------------------
# 4. KOBIS API 데이터 요청하기
# -----------------------------------------------------------------------------
api_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt}

try:
    response = requests.get(api_url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    st.error("🚨 네트워크 또는 API 서버 통신 오류가 발생했습니다.")
    st.info(
        f"""
    **확인 항목:**
    - 인터넷 연결 상태를 확인해 주세요.
    - KOBIS 서버 점검 중일 수 있습니다.
    - 상세 에러 내용: `{e}`
    """
    )
    st.stop()

# -----------------------------------------------------------------------------
# 5. API 응답 검증 및 오류 처리 (faultInfo 및 빈 데이터 검사)
# -----------------------------------------------------------------------------
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("🚨 API 인증 오류가 발생했습니다.")
    st.info(
        f"""
    **확인 항목:**
    - **오류 메시지:** `{fault.get('message', '알 수 없는 오류')}` (코드: `{fault.get('errorCode', 'N/A')}`)
    - 코드에 입력된 `api_key` 값이 정확한지 확인해 주세요.
    - [KOBIS 개발자 센터](https://www.kobis.or.kr/kobisopenapi)에서 키 상태를 체크해 주세요.
    """
    )
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 선택한 날짜의 영화 목록이 비어 있는 경우 예외 처리
if not daily_list:
    st.warning("⚠️ 선택하신 날짜의 박스오피스 데이터가 존재하지 않습니다.")
    st.info("💡 그날은 아직 집계 전입니다.")
    st.stop()

# -----------------------------------------------------------------------------
# 6. 데이터 전처리 (숫자 변환, 순위 증감 화살표, 누적관객 100만 트로피)
# -----------------------------------------------------------------------------
df = pd.DataFrame(daily_list)

# 문자열 데이터를 정수형으로 변환
numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# [기능 1] 전날 대비 순위 증감(rankInten) 화살표 변환 함수
# 양수: 빨간 위 화살표(🔺), 음수: 파란 아래 화살표(🔹), 0: 변동 없음(-)
def format_rank_inten(val):
    if val > 0:
        return f"🔺 {val}"
    elif val < 0:
        return f"🔹 {abs(val)}"
    else:
        return "-"


df["순위변동"] = df["rankInten"].apply(format_rank_inten)


# [기능 2] 누적관객 1,000,000명 이상 영화명 옆에 🏆 이모지 추가 함수
def add_trophy(row):
    movie_name = row["movieNm"]
    if row["audiAcc"] >= 1000000:
        return f"{movie_name} 🏆"
    return movie_name


df["영화명_표시"] = df.apply(add_trophy, axis=1)

# -----------------------------------------------------------------------------
# 7. 대시보드 화면 구성
# -----------------------------------------------------------------------------

# [지표 카드 3장] 1위 영화 하이라이트
top_1 = df.iloc[0]
st.subheader("🥇 1위 영화 하이라이트")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="🏆 1위 영화", value=top_1["영화명_표시"])
with col2:
    st.metric(label="🍿 당일 관객 수", value=f"{top_1['audiCnt']:,} 명")
with col3:
    st.metric(label="🎬 누적 관객 수", value=f"{top_1['audiAcc']:,} 명")

st.divider()

# [막대그래프] 관객 수 상위 5편
st.subheader("📊 관객 수 상위 5개 영화 비교")
top5_df = df.head(5)[["영화명_표시", "audiCnt"]].copy()
top5_df.rename(
    columns={"영화명_표시": "영화명", "audiCnt": "당일 관객수"}, inplace=True
)
top5_df.set_index("영화명", inplace=True)

st.bar_chart(top5_df)

st.divider()

# [표] 박스오피스 전체 순위 (10위까지)
st.subheader("📋 전체 순위 목록")

display_df = df[
    ["rank", "순위변동", "영화명_표시", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
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

# 관객수/누적관객/스크린수 천 단위 쉼표 표기
st.dataframe(
    display_df.style.format(
        {"관객수": "{:,}명", "누적관객": "{:,}명", "스크린수": "{:,}개"}
    ),
    use_container_width=True,
    hide_index=True,
)
