"""KOPIS(공연예술통합전산망) API로 아동 공연 목록을 모으고 data/places.json 으로 저장한다.
하루 1회 배치 실행을 염두에 둔 스크립트.

흐름: 키워드로 공연 목록 검색 -> 공연 상세(가격/연령/포스터/시설ID) 조회 ->
     시설 상세(정확한 주소/좌표) 조회, 실패 시 NAVER 지역검색으로 대략 위치 보정 ->
     서울/경기 + 좌표가 확보된 것만 필터링 (그 외 상세 필드는 없어도 마커는 표시)
"""
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import requests

from config import (
    KOPIS_SERVICE_KEY,
    KOPIS_BASE_URL,
    NAVER_API_URL,
    NAVER_HEADERS,
    SHOW_KEYWORDS,
    KOPIS_GENRES,
    KOPIS_REGION_CODES,
    DAYS_AHEAD,
    ALLOWED_ADDRESS_PREFIXES,
    DATA_PATH,
)

REQUEST_DELAY = 0.1
RETRY_ATTEMPTS = 3


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


def search_list(extra_params: dict, stdate: str, eddate: str) -> list[dict]:
    results = []
    cpage = 1
    while True:
        params = {
            "service": KOPIS_SERVICE_KEY,
            "stdate": stdate,
            "eddate": eddate,
            "cpage": cpage,
            "rows": 100,
            **extra_params,
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


def search_performances(keyword: str, stdate: str, eddate: str) -> list[dict]:
    return search_list({"shprfnm": keyword}, stdate, eddate)


def search_by_genre_region(genre: str, region_code: str, stdate: str, eddate: str) -> list[dict]:
    return search_list({"shcate": genre, "signgucode": region_code}, stdate, eddate)


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


def build_place(detail: dict, facility: dict) -> dict:
    mt20id = detail.get("mt20id", "")
    return {
        "id": mt20id,
        "title": detail.get("prfnm", ""),
        "genre": detail.get("genrenm", ""),
        "start_date": detail.get("prfpdfrom", ""),
        "end_date": detail.get("prfpdto", ""),
        "venue": detail.get("fcltynm", ""),
        "address": facility.get("adres", ""),
        "lat": float(facility["la"]),
        "lon": float(facility["lo"]),
        "age": detail.get("prfage", ""),
        "price": detail.get("pcseguidance", ""),
        "runtime": detail.get("prfruntime", ""),
        "schedule": detail.get("dtguidance", ""),
        "poster": detail.get("poster", ""),
        "link": detail.get("link") or f"https://www.kopis.or.kr/mob/db/pblprfrView.do?mt20Id={mt20id}",
        "telephone": facility.get("telno", ""),
        "approx_location": bool(facility.get("approx")),
    }


def collect() -> list[dict]:
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst)
    stdate = today.strftime("%Y%m%d")
    eddate = (today + timedelta(days=DAYS_AHEAD)).strftime("%Y%m%d")

    seen_ids = set()
    candidate_ids = []

    def add_items(items):
        for item in items:
            mt20id = item.get("mt20id")
            if mt20id and mt20id not in seen_ids:
                seen_ids.add(mt20id)
                candidate_ids.append(mt20id)

    for keyword in SHOW_KEYWORDS:
        try:
            add_items(search_performances(keyword, stdate, eddate))
        except requests.RequestException as e:
            print(f"[경고] '{keyword}' 검색 실패: {e}")
        time.sleep(REQUEST_DELAY)

    # 제목에 "어린이" 등이 없어도 장르 x 지역으로 넓게 후보를 모으고,
    # 실제 아동공연 여부는 아래에서 공식 child 플래그로 가려낸다
    for region_code in KOPIS_REGION_CODES:
        for genre in KOPIS_GENRES:
            try:
                add_items(search_by_genre_region(genre, region_code, stdate, eddate))
            except requests.RequestException as e:
                print(f"[경고] 장르 검색 실패({region_code}/{genre}): {e}")
            time.sleep(REQUEST_DELAY)

    facility_cache: dict[str, dict] = {}
    places = []
    skipped_no_location = 0

    for mt20id in candidate_ids:
        try:
            detail = fetch_detail(mt20id)
        except requests.RequestException as e:
            print(f"[경고] 상세 조회 실패({mt20id}): {e}")
            continue
        time.sleep(REQUEST_DELAY)

        if not detail.get("prfnm"):
            continue
        if detail.get("child") != "Y":
            continue  # 아동 공연으로 공식 분류된 것만 남긴다

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

        address = facility.get("adres", "")
        if not address.startswith(ALLOWED_ADDRESS_PREFIXES):
            continue
        if not facility.get("la") or not facility.get("lo"):
            skipped_no_location += 1
            continue

        places.append(build_place(detail, facility))

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
