import datetime
import pandas as pd
import pytz
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 타이틀
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="어제 자 박스오피스 순위", page_icon="🎬", layout="wide"
)

st.title("🎬 어제의 박스오피스 TOP 10")

# -----------------------------------------------------------------------------
# 2. 한국 시간(KST) 기준 '어제' 날짜 자동 계산
# -----------------------------------------------------------------------------
# 배포 서버의 시계가 해외(UTC) 기준이어도 한국 시간 기준으로 어제를 정확히 구합니다.
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
yesterday_kst = now_kst - datetime.timedelta(days=1)
target_dt = yesterday_kst.strftime("%Y%m%d")  # 예: '20261020'

st.caption(f"📅 기준 날짜: {yesterday_kst.strftime('%Y년 %m월 %d일')}")

# -----------------------------------------------------------------------------
# 3. 비밀 금고(secrets)에서 API Key 불러오기
# -----------------------------------------------------------------------------
# Streamlit Cloud의 Secrets 설정에 저장된 'KOBIS_KEY'를 읽어옵니다.
if "KOBIS_KEY" not in st.secrets:
    st.error("🚨 API 키 설정 오류")
    st.warning(
        """
    **`KOBIS_KEY` 비밀키를 찾을 수 없습니다.**
    
    **해결 방법:**
    1. Streamlit Cloud 대시보드로 이동합니다.
    2. 해당 앱의 **[Settings] -> [Secrets]** 메뉴를 클릭합니다.
    3. 아래 형식으로 API 키를 등록해 주세요:
       ```toml
       KOBIS_KEY = "발급받은_공식_API_키"
       ```
    """
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# -----------------------------------------------------------------------------
# 4. KOBIS API 데이터 요청하기
# -----------------------------------------------------------------------------
api_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt}

try:
    response = requests.get(api_url, params=params, timeout=10)
    response.raise_for_status()  # HTTP 상태 코드가 200이 아니면 예외 발생
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
# KOBIS API는 키가 틀려도 상태코드 200과 함께 'faultInfo' 응답을 전달합니다.
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("🚨 API 인증 failure가 발생했습니다.")
    st.info(
        f"""
    **확인 항목:**
    - **오류 메시지:** `{fault.get('message', '알 수 없는 오류')}` (코드: `{fault.get('errorCode', 'N/A')}`)
    - Streamlit Secrets에 입력한 `KOBIS_KEY` 값이 정확한지 확인해 주세요.
    - [KOBIS 개발자 센터](https://www.kobis.or.kr/kobisopenapi)에서 키 상태를 체크해 주세요.
    """
    )
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록이 비어 있는 경우 예외 처리
if not daily_list:
    st.warning("⚠️ 어제 자 박스오피스 데이터가 비어 있습니다.")
    st.info(
        """
    **확인 항목:**
    - KOBIS 전산망 집계 작업 중일 수 있습니다. (보통 새벽시간대에 집계가 진행됩니다.)
    - 날짜 파라미터(`targetDt`)가 정상 전달되었는지 확인해 주세요.
    """
    )
    st.stop()

# -----------------------------------------------------------------------------
# 6. 데이터 전처리 (문자열 -> 숫자 변환)
# -----------------------------------------------------------------------------
df = pd.DataFrame(daily_list)

# 숫자로 된 문자열 컬럼들을 정수(int)형으로 전환
numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# -----------------------------------------------------------------------------
# 7. 대시보드 화면 구성
# -----------------------------------------------------------------------------

# [지표 카드 3장] 1위 영화 하이라이트
top_1 = df.iloc[0]
st.subheader("🥇 1위 영화 하이라이트")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="🏆 1위 영화", value=top_1["movieNm"])
with col2:
    st.metric(label="🍿 어제 관객 수", value=f"{top_1['audiCnt']:,} 명")
with col3:
    st.metric(label="🎬 누적 관객 수", value=f"{top_1['audiAcc']:,} 명")

st.divider()

# [막대그래프] 관객 수 상위 5편
st.subheader("📊 관객 수 상위 5개 영화 비교")
top5_df = df.head(5)[["movieNm", "audiCnt"]].copy()
top5_df.rename(
    columns={"movieNm": "영화명", "audiCnt": "어제 관객수"}, inplace=True
)
top5_df.set_index("영화명", inplace=True)

st.bar_chart(top5_df)

st.divider()

# [표] 박스오피스 전체 순위 (10위까지)
st.subheader("📋 전체 순위 목록")

# 화면에 표시할 컬럼만 추출 및 이름 변경
display_df = df[
    ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]

# 관객수/누적관객/스크린수천 단위 쉼표 표기 적용
st.dataframe(
    display_df.style.format(
        {"관객수": "{:,}명", "누적관객": "{:,}명", "스크린수": "{:,}개"}
    ),
    use_container_width=True,
    hide_index=True,
)
