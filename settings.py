"""비밀값이 아닌 설정. 인증키 등 비밀값은 config.py(로컬)/GitHub Actions 시크릿에서 온다."""
KOPIS_BASE_URL = "http://www.kopis.or.kr/openApi/restful"
NAVER_API_URL = "https://naverapihub.apigw.ntruss.com/search/v1/local"

# 공연명에 이 키워드가 포함된 것을 검색 대상으로 모은다 (보조 수단 - 아래 장르 검색이 주력)
SHOW_KEYWORDS = ["어린이", "아동", "키즈", "인형극"]

# 제목에 "어린이" 등이 없는 캐릭터 콘서트 등도 잡기 위해, 아동공연이 많이 속하는
# 장르 x 지역(서울/경기)으로 폭넓게 후보를 모은 뒤 공식 아동(child=Y) 플래그로 거른다
KOPIS_GENRES = ["AAAA", "GGGA", "EEEB"]  # 연극, 뮤지컬, 서커스/마술
KOPIS_REGION_CODES = ["11", "41"]  # 서울, 경기

# 오늘부터 몇 일 뒤까지의 공연을 모을지 (매일 배치로 실행하면서 창이 굴러감)
DAYS_AHEAD = 90

# 수집 후 이 접두어로 시작하는 주소만 남긴다 (서울/경기권 한정)
ALLOWED_ADDRESS_PREFIXES = ("서울", "경기")

DATA_PATH = "data/places.json"
MAP_OUTPUT_PATH = "index.html"
