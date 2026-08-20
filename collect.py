"""KOPIS(공연예술통합전산망) API로 아동 공연 목록을 모으고 data/places.json 으로 저장한다.
하루 1회 배치 실행을 염두에 둔 스크립트.

흐름: 키워드로 공연 목록 검색 -> 공연 상세(가격/연령/포스터/시설ID) 조회 ->
     시설 상세(정확한 주소/좌표) 조회 -> 서울/경기 + 아동공연(child=Y)만 필터링
"""
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import requests

from config import (
    KOPIS_SERVICE_KEY,
    KOPIS_BASE_URL,
    SHOW_KEYWORDS,
    DAYS_AHEAD,
    ALLOWED_ADDRESS_PREFIXES,
    DATA_PATH,
)

REQUEST_DELAY = 0.1


def parse_dbs(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    # 자식이 없는(텍스트만 있는) 태그만 평탄화해서 dict로 만든다
    return [
        {child.tag: (child.text or "").strip() for child in db if len(child) == 0}
        for db in root.findall("db")
    ]


def search_performances(keyword: str, stdate: str, eddate: str) -> list[dict]:
    results = []
    cpage = 1
    while True:
        params = {
            "service": KOPIS_SERVICE_KEY,
            "stdate": stdate,
            "eddate": eddate,
            "cpage": cpage,
            "rows": 100,
            "shprfnm": keyword,
        }
        response = requests.get(f"{KOPIS_BASE_URL}/pblprfr", params=params, timeout=15)
        response.raise_for_status()
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
    params = {"service": KOPIS_SERVICE_KEY}
    response = requests.get(f"{KOPIS_BASE_URL}/pblprfr/{mt20id}", params=params, timeout=15)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    db = root.find("db")
    if db is None:
        return {}

    detail = {child.tag: (child.text or "").strip() for child in db if len(child) == 0}
    link = db.find("./relates/relate/relateurl")
    detail["link"] = link.text.strip() if link is not None and link.text else ""
    return detail


def fetch_facility(mt10id: str) -> dict:
    params = {"service": KOPIS_SERVICE_KEY}
    response = requests.get(f"{KOPIS_BASE_URL}/prfplc/{mt10id}", params=params, timeout=15)
    response.raise_for_status()
    items = parse_dbs(response.text)
    return items[0] if items else {}


def build_place(detail: dict, facility: dict) -> dict:
    return {
        "id": detail.get("mt20id", ""),
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
        "link": detail.get("link", ""),
        "telephone": facility.get("telno", ""),
    }


def collect() -> list[dict]:
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst)
    stdate = today.strftime("%Y%m%d")
    eddate = (today + timedelta(days=DAYS_AHEAD)).strftime("%Y%m%d")

    seen_ids = set()
    candidate_ids = []
    for keyword in SHOW_KEYWORDS:
        try:
            items = search_performances(keyword, stdate, eddate)
        except requests.RequestException as e:
            print(f"[경고] '{keyword}' 검색 실패: {e}")
            continue

        for item in items:
            mt20id = item.get("mt20id")
            if mt20id and mt20id not in seen_ids:
                seen_ids.add(mt20id)
                candidate_ids.append(mt20id)
        time.sleep(REQUEST_DELAY)

    facility_cache: dict[str, dict] = {}
    places = []
    for mt20id in candidate_ids:
        try:
            detail = fetch_detail(mt20id)
            time.sleep(REQUEST_DELAY)
        except requests.RequestException as e:
            print(f"[경고] 상세 조회 실패({mt20id}): {e}")
            continue

        if detail.get("child") != "Y":
            continue  # 아동 공연으로 분류된 것만 남긴다

        mt10id = detail.get("mt10id")
        if not mt10id:
            continue

        if mt10id not in facility_cache:
            try:
                facility_cache[mt10id] = fetch_facility(mt10id)
                time.sleep(REQUEST_DELAY)
            except requests.RequestException as e:
                print(f"[경고] 시설 조회 실패({mt10id}): {e}")
                facility_cache[mt10id] = {}
        facility = facility_cache[mt10id]

        address = facility.get("adres", "")
        if not address.startswith(ALLOWED_ADDRESS_PREFIXES):
            continue
        if not facility.get("la") or not facility.get("lo"):
            continue

        places.append(build_place(detail, facility))

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
