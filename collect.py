"""KOPIS(공연예술통합전산망) API로 전국 아동 공연 목록을 모으고 data/places.json 으로 저장한다.
매일 배치 실행을 염두에 둔 스크립트. (아동 서비스로 좁혀서 child=Y 인 것만 남긴다)

흐름: 지역(16개 권역코드)별로 전체 장르를 페이지네이션으로 훑어 후보를 모으고 ->
     공연 상세(가격/연령/포스터/시설ID/아동여부) 조회 -> child=Y 인 것만 통과 ->
     시설 상세(정확한 주소/좌표) 조회, 실패 시 NAVER 지역검색으로 대략 위치 보정
"""
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import requests

from settings import (
    KOPIS_BASE_URL,
    NAVER_API_URL,
    REGIONS,
    DAYS_AHEAD,
    DATA_PATH,
)
from config import KOPIS_SERVICE_KEY, NAVER_HEADERS

REQUEST_DELAY = 0.1
RETRY_ATTEMPTS = 3

ADDRESS_PREFIX_TO_GROUP = [
    ("서울", "수도권"),
    ("인천", "수도권"),
    ("경기", "수도권"),
    ("대전", "충청권"),
    ("세종", "충청권"),
    ("충청북도", "충청권"),
    ("충북", "충청권"),
    ("충청남도", "충청권"),
    ("충남", "충청권"),
    ("강원", "강원권"),
    ("전남광주", "호남권"),
    ("전라남도", "호남권"),
    ("광주", "호남권"),
    ("전북", "호남권"),
    ("전라북도", "호남권"),
    ("대구", "영남권"),
    ("경상북도", "영남권"),
    ("경북", "영남권"),
    ("부산", "영남권"),
    ("울산", "영남권"),
    ("경상남도", "영남권"),
    ("경남", "영남권"),
    ("제주", "제주권"),
]


def region_group_from_address(address: str) -> str:
    for prefix, group in ADDRESS_PREFIX_TO_GROUP:
        if address.startswith(prefix):
            return group
    return "기타"


def request_with_retry(url: str, params: dict) -> requests.Response:
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            last_error = e
            time.sleep(0.5 * (attempt + 1))
    raise last_error


def parse_dbs(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    return [
        {child.tag: (child.text or "").strip() for child in db if len(child) == 0}
        for db in root.findall("db")
    ]


def search_region(region_code: str, stdate: str, eddate: str) -> list[dict]:
    results = []
    cpage = 1
    while True:
        params = {
            "service": KOPIS_SERVICE_KEY,
            "stdate": stdate,
            "eddate": eddate,
            "cpage": cpage,
            "rows": 100,
            "signgucode": region_code,
        }
        response = request_with_retry(f"{KOPIS_BASE_URL}/pblprfr", params)
        items = parse_dbs(response.text)
        if not items:
            break
        results.extend(items)
        if len(items) < 100:
            break
        cpage += 1
        time.sleep(REQUEST_DELAY)
    return results


def fetch_detail(mt20id: str) -> dict:
    response = request_with_retry(f"{KOPIS_BASE_URL}/pblprfr/{mt20id}", {"service": KOPIS_SERVICE_KEY})
    root = ET.fromstring(response.text)
    db = root.find("db")
    if db is None:
        return {}

    detail = {child.tag: (child.text or "").strip() for child in db if len(child) == 0}
    link = db.find("./relates/relate/relateurl")
    detail["link"] = link.text.strip() if link is not None and link.text else ""
    return detail


def fetch_facility(mt10id: str) -> dict:
    response = request_with_retry(f"{KOPIS_BASE_URL}/prfplc/{mt10id}", {"service": KOPIS_SERVICE_KEY})
    items = parse_dbs(response.text)
    return items[0] if items else {}


def naver_fallback_location(venue_name: str) -> dict | None:
    """KOPIS 시설 좌표를 못 찾았을 때 시설명으로 NAVER 지역검색을 통해 대략 위치를 구한다."""
    if not venue_name:
        return None
    try:
        response = request_with_retry(
            NAVER_API_URL,
            {"query": venue_name, "display": 1, "start": 1, "sort": "random"},
        )
    except requests.RequestException:
        return None

    items = response.json().get("items", [])
    if not items:
        return None

    item = items[0]
    return {
        "adres": item.get("roadAddress") or item.get("address", ""),
        "la": int(item["mapy"]) / 10_000_000,
        "lo": int(item["mapx"]) / 10_000_000,
        "telno": "",
        "approx": True,
    }


def to_https(url: str) -> str:
    # KOPIS 포스터가 http://로 내려오는 경우가 있다. HTTPS 페이지에 http:// <img>를
    # 그대로 박으면 Mixed Content로 브라우저에 따라 이미지가 아예 안 뜰 수 있어서
    # 스킴만 바꿔준다 (같은 호스트가 https도 지원함, www 붙은 건 https에서 리다이렉트됨).
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def build_place(detail: dict, facility: dict) -> dict:
    mt20id = detail.get("mt20id", "")
    address = facility.get("adres", "")
    return {
        "id": mt20id,
        "type": "performance",
        "category": "공연·전시",
        "title": detail.get("prfnm", ""),
        "genre": detail.get("genrenm", ""),
        "is_child": detail.get("child") == "Y",
        "start_date": detail.get("prfpdfrom", ""),
        "end_date": detail.get("prfpdto", ""),
        "venue": detail.get("fcltynm", ""),
        "address": address,
        "region_group": region_group_from_address(address),
        "lat": float(facility["la"]),
        "lon": float(facility["lo"]),
        "age": detail.get("prfage", ""),
        "price": detail.get("pcseguidance", ""),
        "runtime": detail.get("prfruntime", ""),
        "schedule": detail.get("dtguidance", ""),
        "poster": to_https(detail.get("poster", "")),
        "link": detail.get("link") or f"https://www.kopis.or.kr/mob/db/pblprfrView.do?mt20Id={mt20id}",
        "telephone": clean_telno(facility.get("telno", "")),
        "approx_location": bool(facility.get("approx")),
    }


def clean_telno(telno: str) -> str:
    # KOPIS 데이터에 지역번호 없는 대표전화(1544/1661 등) 앞에 "00-"이 잘못 붙는 경우가 있다
    if telno.startswith("00-"):
        return telno[3:]
    return telno


def collect() -> list[dict]:
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst)
    stdate = today.strftime("%Y%m%d")
    eddate = (today + timedelta(days=DAYS_AHEAD)).strftime("%Y%m%d")

    seen_ids = set()
    candidate_ids = []

    for region_code in REGIONS:
        try:
            items = search_region(region_code, stdate, eddate)
        except requests.RequestException as e:
            print(f"[경고] 지역 검색 실패({region_code}): {e}")
            continue

        for item in items:
            mt20id = item.get("mt20id")
            if mt20id and mt20id not in seen_ids:
                seen_ids.add(mt20id)
                candidate_ids.append(mt20id)
        time.sleep(REQUEST_DELAY)

    print(f"[안내] 후보 {len(candidate_ids)}건, 상세 조회 시작")

    facility_cache: dict[str, dict] = {}
    places = []
    skipped_no_location = 0

    for i, mt20id in enumerate(candidate_ids):
        try:
            detail = fetch_detail(mt20id)
        except requests.RequestException as e:
            print(f"[경고] 상세 조회 실패({mt20id}): {e}")
            continue
        time.sleep(REQUEST_DELAY)

        if not detail.get("prfnm"):
            continue
        if detail.get("child") != "Y":
            continue  # 아동 전용 서비스로 좁힌다

        mt10id = detail.get("mt10id")
        facility = {}
        if mt10id:
            if mt10id not in facility_cache:
                try:
                    facility_cache[mt10id] = fetch_facility(mt10id)
                except requests.RequestException as e:
                    print(f"[경고] 시설 조회 실패({mt10id}): {e}")
                    facility_cache[mt10id] = {}
                time.sleep(REQUEST_DELAY)
            facility = facility_cache[mt10id]

        # KOPIS 시설 좌표가 없으면 시설명으로 NAVER 지역검색을 통해 대략 위치를 보정한다
        if not facility.get("la") or not facility.get("lo"):
            fallback = naver_fallback_location(detail.get("fcltynm", ""))
            if fallback:
                facility = fallback
                time.sleep(REQUEST_DELAY)

        if not facility.get("la") or not facility.get("lo"):
            skipped_no_location += 1
            continue

        places.append(build_place(detail, facility))

        if (i + 1) % 200 == 0:
            print(f"[진행] {i + 1}/{len(candidate_ids)}건 처리")

    if skipped_no_location:
        print(f"[안내] 좌표를 못 구해 지도에 못 올린 공연 {skipped_no_location}건")

    return places


def main():
    places = collect()
    kst = timezone(timedelta(hours=9))
    payload = {
        "updated_at": datetime.now(kst).isoformat(),
        "count": len(places),
        "places": places,
    }
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"{len(places)}개 공연 수집 완료 -> {DATA_PATH}")


if __name__ == "__main__":
    main()
