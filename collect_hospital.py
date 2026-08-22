"""국립중앙의료원 "전국 병·의원 찾기 서비스"/"전국 약국 정보 조회 서비스" API로 부천
20km 반경 안의 소아과·일반의원·응급실·약국을 모아서 data/hospitals.json으로 저장한다.
"아이가 아파요" 페이지 전용 데이터라 기존 나들이용 data/places.json과는 완전히
분리한다 - 필터링 방식(진료시간 기반 지금 열림 여부)도, 화면(hospital.html)도 다르기 때문.

병상 가용 현황 같은 실시간 숫자는 응급의료기관 API가 제공하는 필드(hvec/hvgc 등)의
정확한 의미를 공식 문서로 확인하지 못해서 일부러 안 쓴다 - 의료 상황에서 잘못된 숫자를
보여주는 것보다 이름/주소/전화번호까지만 보여주고 전화로 확인하게 하는 게 안전하다.
"""
import json
import time
from datetime import datetime, timezone, timedelta
from math import radians, sin, cos, asin, sqrt

import requests

from config import TOUR_API_KEY

REQUEST_DELAY = 0.1
NUM_OF_ROWS = 100
KST = timezone(timedelta(hours=9))

HOSPITAL_URL = "http://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire"
PHARMACY_URL = "http://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyListInfoInqire"

CENTER_LAT, CENTER_LON = 37.5034, 126.7660  # 부천시청
MAX_RADIUS_KM = 20

# (시도, 시군구) - 이 API는 페이지네이션이 정상 동작해서 NAVER 지역검색과 달리
# 구 단위로 잘게 쪼갤 필요 없이 시 단위로 조회하면 된다. 인천 서구는 검단구/서해구로
# 개편됐는데 API에 세 이름이 다 남아있어(잔존 데이터 포함) 셋 다 조회해서 합친다.
AREAS = [
    ("경기도", "부천시"),
    ("인천광역시", "부평구"), ("인천광역시", "계양구"),
    ("인천광역시", "서구"), ("인천광역시", "검단구"), ("인천광역시", "서해구"),
    ("인천광역시", "남동구"), ("인천광역시", "연수구"), ("인천광역시", "미추홀구"),
    ("서울특별시", "강서구"), ("서울특별시", "양천구"), ("서울특별시", "구로구"),
    ("서울특별시", "영등포구"), ("서울특별시", "금천구"),
    ("경기도", "시흥시"), ("경기도", "광명시"), ("경기도", "김포시"),
    ("경기도", "안양시"), ("경기도", "고양시"),
]

PEDIATRIC_KEYWORDS = ["소아청소년과", "소아과"]

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


def haversine_km(lat1, lon1, lat2, lon2):
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


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
        resp = requests.get(base_url, params=params, timeout=15)
        resp.raise_for_status()
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
    if haversine_km(CENTER_LAT, CENTER_LON, lat, lon) > MAX_RADIUS_KM:
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
