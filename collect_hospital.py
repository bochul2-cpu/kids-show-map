"""국립중앙의료원 "전국 병·의원 찾기 서비스"/"전국 약국 정보 조회 서비스" API로 전국의
소아과·일반의원·응급실·약국을 모아서 data/hospitals.json으로 저장한다.
"아이가 아파요" 페이지 전용 데이터라 기존 나들이용 data/places.json과는 완전히
분리한다 - 필터링 방식(진료시간 기반 지금 열림 여부)도, 화면(hospital.html)도 다르기 때문.

원래는 부천 20km 반경 안 지역만 수집했는데, 메인 지도(build_map.py)를 "부천 고정"에서
"현재 위치 기준 20km"로 바꾼 것과 같은 이유로 이쪽도 전국으로 넓혔다 - 수집은 전국으로
하고, 거리 필터는 화면(hospital.html의 JS)에서 사용자 위치 기준으로 매번 계산한다.

병상 가용 현황 같은 실시간 숫자는 응급의료기관 API가 제공하는 필드(hvec/hvgc 등)의
정확한 의미를 공식 문서로 확인하지 못해서 일부러 안 쓴다 - 의료 상황에서 잘못된 숫자를
보여주는 것보다 이름/주소/전화번호까지만 보여주고 전화로 확인하게 하는 게 안전하다.
"""
import json
import time
from datetime import datetime, timezone, timedelta

import requests

from config import TOUR_API_KEY

REQUEST_DELAY = 0.1
NUM_OF_ROWS = 100
KST = timezone(timedelta(hours=9))

HOSPITAL_URL = "http://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire"
PHARMACY_URL = "http://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyListInfoInqire"

# (시도, 시군구) - 이 API는 페이지네이션이 정상 동작해서 NAVER 지역검색과 달리
# 구 단위로 잘게 쪼갤 필요 없이 시 단위로 조회하면 된다(수원/성남/고양처럼 구가 있는
# 시도 시 이름 하나로 충분 - 실제로 확인함). 광역시(서울/부산/대구/인천/광주/대전/울산)는
# 구/군이 Q1이라 그 밑 구/군 전체를 나열해야 한다. 강원/전북은 2023~2024년 개편으로
# 이름이 "강원특별자치도"/"전북특별자치도"로 바뀌었는데, 이 API는 신 명칭만 인식하고
# 구 명칭("강원도"/"전라북도")으론 0건이 나와서 신 명칭으로 넣었다(직접 조회해서 확인함).
# 세종은 기초자치단체 구분이 없는 광역단체라 Q1을 빈 문자열로 둬야 정상 응답이 온다.
# 인천 서구는 검단구/서해구로 개편됐는데 API에 세 이름이 다 남아있어(잔존 데이터 포함)
# 셋 다 조회해서 합친다.
AREAS = [
    # 서울 25개구
    ("서울특별시", "종로구"), ("서울특별시", "중구"), ("서울특별시", "용산구"),
    ("서울특별시", "성동구"), ("서울특별시", "광진구"), ("서울특별시", "동대문구"),
    ("서울특별시", "중랑구"), ("서울특별시", "성북구"), ("서울특별시", "강북구"),
    ("서울특별시", "도봉구"), ("서울특별시", "노원구"), ("서울특별시", "은평구"),
    ("서울특별시", "서대문구"), ("서울특별시", "마포구"), ("서울특별시", "양천구"),
    ("서울특별시", "강서구"), ("서울특별시", "구로구"), ("서울특별시", "금천구"),
    ("서울특별시", "영등포구"), ("서울특별시", "동작구"), ("서울특별시", "관악구"),
    ("서울특별시", "서초구"), ("서울특별시", "강남구"), ("서울특별시", "송파구"),
    ("서울특별시", "강동구"),
    # 부산 16개 구/군
    ("부산광역시", "중구"), ("부산광역시", "서구"), ("부산광역시", "동구"),
    ("부산광역시", "영도구"), ("부산광역시", "부산진구"), ("부산광역시", "동래구"),
    ("부산광역시", "남구"), ("부산광역시", "북구"), ("부산광역시", "해운대구"),
    ("부산광역시", "사하구"), ("부산광역시", "금정구"), ("부산광역시", "강서구"),
    ("부산광역시", "연제구"), ("부산광역시", "수영구"), ("부산광역시", "사상구"),
    ("부산광역시", "기장군"),
    # 대구
    ("대구광역시", "중구"), ("대구광역시", "동구"), ("대구광역시", "서구"),
    ("대구광역시", "남구"), ("대구광역시", "북구"), ("대구광역시", "수성구"),
    ("대구광역시", "달서구"), ("대구광역시", "달성군"), ("대구광역시", "군위군"),
    # 인천
    ("인천광역시", "중구"), ("인천광역시", "동구"), ("인천광역시", "미추홀구"),
    ("인천광역시", "연수구"), ("인천광역시", "남동구"), ("인천광역시", "부평구"),
    ("인천광역시", "계양구"), ("인천광역시", "서구"), ("인천광역시", "검단구"),
    ("인천광역시", "서해구"), ("인천광역시", "강화군"), ("인천광역시", "옹진군"),
    # 광주
    ("광주광역시", "동구"), ("광주광역시", "서구"), ("광주광역시", "남구"),
    ("광주광역시", "북구"), ("광주광역시", "광산구"),
    # 대전
    ("대전광역시", "동구"), ("대전광역시", "중구"), ("대전광역시", "서구"),
    ("대전광역시", "유성구"), ("대전광역시", "대덕구"),
    # 울산
    ("울산광역시", "중구"), ("울산광역시", "남구"), ("울산광역시", "동구"),
    ("울산광역시", "북구"), ("울산광역시", "울주군"),
    # 세종
    ("세종특별자치시", ""),
    # 경기도 31개 시/군
    ("경기도", "수원시"), ("경기도", "성남시"), ("경기도", "의정부시"),
    ("경기도", "안양시"), ("경기도", "부천시"), ("경기도", "광명시"),
    ("경기도", "평택시"), ("경기도", "동두천시"), ("경기도", "안산시"),
    ("경기도", "고양시"), ("경기도", "과천시"), ("경기도", "구리시"),
    ("경기도", "남양주시"), ("경기도", "오산시"), ("경기도", "시흥시"),
    ("경기도", "군포시"), ("경기도", "의왕시"), ("경기도", "하남시"),
    ("경기도", "용인시"), ("경기도", "파주시"), ("경기도", "이천시"),
    ("경기도", "안성시"), ("경기도", "김포시"), ("경기도", "화성시"),
    ("경기도", "광주시"), ("경기도", "양주시"), ("경기도", "포천시"),
    ("경기도", "여주시"), ("경기도", "연천군"), ("경기도", "가평군"),
    ("경기도", "양평군"),
    # 강원특별자치도
    ("강원특별자치도", "춘천시"), ("강원특별자치도", "원주시"), ("강원특별자치도", "강릉시"),
    ("강원특별자치도", "동해시"), ("강원특별자치도", "태백시"), ("강원특별자치도", "속초시"),
    ("강원특별자치도", "삼척시"), ("강원특별자치도", "홍천군"), ("강원특별자치도", "횡성군"),
    ("강원특별자치도", "영월군"), ("강원특별자치도", "평창군"), ("강원특별자치도", "정선군"),
    ("강원특별자치도", "철원군"), ("강원특별자치도", "화천군"), ("강원특별자치도", "양구군"),
    ("강원특별자치도", "인제군"), ("강원특별자치도", "고성군"), ("강원특별자치도", "양양군"),
    # 충청북도
    ("충청북도", "청주시"), ("충청북도", "충주시"), ("충청북도", "제천시"),
    ("충청북도", "보은군"), ("충청북도", "옥천군"), ("충청북도", "영동군"),
    ("충청북도", "증평군"), ("충청북도", "진천군"), ("충청북도", "괴산군"),
    ("충청북도", "음성군"), ("충청북도", "단양군"),
    # 충청남도
    ("충청남도", "천안시"), ("충청남도", "공주시"), ("충청남도", "보령시"),
    ("충청남도", "아산시"), ("충청남도", "서산시"), ("충청남도", "논산시"),
    ("충청남도", "계룡시"), ("충청남도", "당진시"), ("충청남도", "금산군"),
    ("충청남도", "부여군"), ("충청남도", "서천군"), ("충청남도", "청양군"),
    ("충청남도", "홍성군"), ("충청남도", "예산군"), ("충청남도", "태안군"),
    # 전북특별자치도
    ("전북특별자치도", "전주시"), ("전북특별자치도", "군산시"), ("전북특별자치도", "익산시"),
    ("전북특별자치도", "정읍시"), ("전북특별자치도", "남원시"), ("전북특별자치도", "김제시"),
    ("전북특별자치도", "완주군"), ("전북특별자치도", "진안군"), ("전북특별자치도", "무주군"),
    ("전북특별자치도", "장수군"), ("전북특별자치도", "임실군"), ("전북특별자치도", "순창군"),
    ("전북특별자치도", "고창군"), ("전북특별자치도", "부안군"),
    # 전라남도
    ("전라남도", "목포시"), ("전라남도", "여수시"), ("전라남도", "순천시"),
    ("전라남도", "나주시"), ("전라남도", "광양시"), ("전라남도", "담양군"),
    ("전라남도", "곡성군"), ("전라남도", "구례군"), ("전라남도", "고흥군"),
    ("전라남도", "보성군"), ("전라남도", "화순군"), ("전라남도", "장흥군"),
    ("전라남도", "강진군"), ("전라남도", "해남군"), ("전라남도", "영암군"),
    ("전라남도", "무안군"), ("전라남도", "함평군"), ("전라남도", "영광군"),
    ("전라남도", "장성군"), ("전라남도", "완도군"), ("전라남도", "진도군"),
    ("전라남도", "신안군"),
    # 경상북도
    ("경상북도", "포항시"), ("경상북도", "경주시"), ("경상북도", "김천시"),
    ("경상북도", "안동시"), ("경상북도", "구미시"), ("경상북도", "영주시"),
    ("경상북도", "영천시"), ("경상북도", "상주시"), ("경상북도", "문경시"),
    ("경상북도", "경산시"), ("경상북도", "의성군"), ("경상북도", "청송군"),
    ("경상북도", "영양군"), ("경상북도", "영덕군"), ("경상북도", "청도군"),
    ("경상북도", "고령군"), ("경상북도", "성주군"), ("경상북도", "칠곡군"),
    ("경상북도", "예천군"), ("경상북도", "봉화군"), ("경상북도", "울진군"),
    ("경상북도", "울릉군"),
    # 경상남도
    ("경상남도", "창원시"), ("경상남도", "진주시"), ("경상남도", "통영시"),
    ("경상남도", "사천시"), ("경상남도", "김해시"), ("경상남도", "밀양시"),
    ("경상남도", "거제시"), ("경상남도", "양산시"), ("경상남도", "의령군"),
    ("경상남도", "함안군"), ("경상남도", "창녕군"), ("경상남도", "고성군"),
    ("경상남도", "남해군"), ("경상남도", "하동군"), ("경상남도", "산청군"),
    ("경상남도", "함양군"), ("경상남도", "거창군"), ("경상남도", "합천군"),
    # 제주
    ("제주특별자치도", "제주시"), ("제주특별자치도", "서귀포시"),
]

PEDIATRIC_KEYWORDS = ["소아청소년과", "소아과", "어린이"]

# "부천연세365의원"처럼 이름에 전문과목이 안 붙은 일반의원(가정의학과/내과 계열이 많음)은
# 소아청소년과로 공식 등록은 안 돼있어도 실제로 아이를 봐주는 경우가 많다. 그렇다고
# dutyDiv=='C'(의원) 전체를 넣으면 산부인과/피부과처럼 아이 진료와 무관한 곳까지 다
# 섞여서, 이름으로 봤을 때 명백히 무관한 과만 제외하고 나머지는 "일반의원"으로 넣는다.
# 이 경우 화면에서 "소아과 아님, 전화로 확인 필요" 안내를 반드시 같이 보여준다.
IRRELEVANT_KEYWORDS = [
    "산부인과", "비뇨기과", "비뇨의학과", "피부과", "정신건강의학과", "정신과",
    "마취통증의학과", "성형외과", "정형외과", "안과", "영상의학과", "진단검사의학과",
    "재활의학과", "신경외과", "신경과", "흉부외과", "심장내과", "남성", "미용",
]

DATA_PATH = "data/hospitals.json"


RETRY_ATTEMPTS = 3
# 전국 231개 지역 x (병원+약국) 2개 API를 훑다 보니 429(트래픽 한도 초과)가 자주 나는데,
# 재시도 없이 그냥 넘어가면(과거에 실제로 겪음) 뒤쪽 지역(전북/전남/경북/경남/제주)의
# 병원 데이터가 통째로 누락된다. collect_tour.py와 같은 패턴으로 30초 대기 후 재시도한다.
BACKOFF_429_SECONDS = 30


def fetch_area(base_url: str, q0: str, q1: str) -> list[dict]:
    items = []
    page = 1
    while True:
        params = {
            "serviceKey": TOUR_API_KEY,
            "Q0": q0, "Q1": q1,
            "pageNo": page, "numOfRows": NUM_OF_ROWS,
            "_type": "json",
        }
        for attempt in range(RETRY_ATTEMPTS):
            try:
                resp = requests.get(base_url, params=params, timeout=15)
                resp.raise_for_status()
                break
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 429 and attempt < RETRY_ATTEMPTS - 1:
                    print(f"[안내] {q0} {q1} 429(트래픽 한도) - {BACKOFF_429_SECONDS}초 대기 후 재시도 ({attempt + 1}/{RETRY_ATTEMPTS})")
                    time.sleep(BACKOFF_429_SECONDS)
                else:
                    raise
        body = resp.json().get("response", {}).get("body", {})
        page_items = body.get("items", "")
        if not page_items:
            break
        page_items = page_items.get("item", [])
        if isinstance(page_items, dict):
            page_items = [page_items]
        items.extend(page_items)
        total = body.get("totalCount", 0)
        if page * NUM_OF_ROWS >= total:
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    return items


def build_hours(item: dict) -> list[dict]:
    """1(월)~7(일) + 8(공휴일) 진료시간을 정리한다. 시작/종료가 둘 다 있는 요일만 넣는다."""
    hours = []
    for day in range(1, 9):
        start = item.get(f"dutyTime{day}s")
        end = item.get(f"dutyTime{day}c")
        if start in (None, "") or end in (None, ""):
            continue
        hours.append({"day": day, "start": str(start).zfill(4), "end": str(end).zfill(4)})
    return hours


def build_entry(item: dict, category: str, id_prefix: str = "hosp") -> dict | None:
    try:
        lat = float(item.get("wgs84Lat", 0))
        lon = float(item.get("wgs84Lon", 0))
    except (TypeError, ValueError):
        return None
    if not lat or not lon:
        return None

    hpid = item.get("hpid", "")
    if not hpid:
        return None

    entry = {
        "id": f"{id_prefix}_{hpid}",
        "category": category,
        "title": item.get("dutyName", ""),
        "address": item.get("dutyAddr", ""),
        "telephone": item.get("dutyTel1", ""),
        "lat": lat,
        "lon": lon,
    }
    if category in ("소아과", "일반의원", "약국"):
        entry["hours"] = build_hours(item)
    return entry


def collect_hospitals() -> list[dict]:
    seen_ids: set[str] = set()
    entries: list[dict] = []
    for q0, q1 in AREAS:
        try:
            items = fetch_area(HOSPITAL_URL, q0, q1)
        except requests.RequestException as e:
            print(f"[경고] {q0} {q1} 병원 조회 실패: {e}")
            items = []

        for item in items:
            name = item.get("dutyName", "")
            is_pediatric = any(k in name for k in PEDIATRIC_KEYWORDS)
            is_general_clinic = (
                not is_pediatric
                and item.get("dutyDiv") == "C"
                and not any(k in name for k in IRRELEVANT_KEYWORDS)
            )
            is_er = item.get("dutyEmclsName", "응급의료기관 이외") != "응급의료기관 이외"

            for category in filter(None, [
                "소아과" if is_pediatric else None,
                "일반의원" if is_general_clinic else None,
                "응급실" if is_er else None,
            ]):
                entry = build_entry(item, category)
                if entry and entry["id"] not in seen_ids:
                    seen_ids.add(entry["id"])
                    entries.append(entry)

        try:
            pharmacy_items = fetch_area(PHARMACY_URL, q0, q1)
        except requests.RequestException as e:
            print(f"[경고] {q0} {q1} 약국 조회 실패: {e}")
            pharmacy_items = []

        for item in pharmacy_items:
            entry = build_entry(item, "약국", id_prefix="pharm")
            if entry and entry["id"] not in seen_ids:
                seen_ids.add(entry["id"])
                entries.append(entry)

        print(f"[진행] {q0} {q1} 완료, 누적 {len(entries)}건")
        time.sleep(REQUEST_DELAY)
    return entries


def main():
    entries = collect_hospitals()
    payload = {
        "updated_at": datetime.now(KST).isoformat(),
        "count": len(entries),
        "hospitals": entries,
    }
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    pediatric = sum(1 for e in entries if e["category"] == "소아과")
    general = sum(1 for e in entries if e["category"] == "일반의원")
    er = sum(1 for e in entries if e["category"] == "응급실")
    pharmacy = sum(1 for e in entries if e["category"] == "약국")
    print(f"소아과 {pediatric}건, 일반의원 {general}건, 응급실 {er}건, 약국 {pharmacy}건 -> {DATA_PATH}")


if __name__ == "__main__":
    main()
