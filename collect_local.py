"""NAVER 지역검색 API로 키즈카페/흙놀이카페 같은 소상공인 체험 업체를 모아서
기존 data/places.json에 합쳐 저장한다. TourAPI는 정식 등록 관광지 위주라 이런 개인
업체는 아예 안 잡히는데, 네이버플레이스 인덱스 기반인 이 API는 검색된다.

collect.py, collect_tour.py 다음에 실행하는 걸 전제로 한다 (그 둘이 이미 저장해둔
데이터 위에 합침). 쿼리 하나당 최대 5건까지만 나오고 페이지네이션이 안 먹혀서,
LOCAL_SEARCH_AREAS x LOCAL_SEARCH_KEYWORDS 조합으로 여러 번 쪼개 검색한다.
"""
import hashlib
import json
import time
from datetime import datetime, timezone, timedelta

import requests

from settings import (
    NAVER_API_URL,
    LOCAL_SEARCH_AREAS,
    LOCAL_SEARCH_KEYWORDS,
    LOCAL_SEARCH_CATEGORY,
    LOCAL_DATA_PATH,
)
from config import NAVER_HEADERS
from collect import request_with_retry, region_group_from_address

REQUEST_DELAY = 0.15
ALWAYS_OPEN_START = "2000.01.01"
ALWAYS_OPEN_END = "2099.12.31"
KST = timezone(timedelta(hours=9))

# 부천시청 기준 20km - 지도(build_map.py)가 실제로 보여주는 범위와 맞춰서, 애초에
# 절대 안 보일 먼 지역 업체까지 데이터에 쌓아두지 않는다.
CENTER_LAT, CENTER_LON = 37.5034, 126.7660
MAX_RADIUS_KM = 20


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, asin, sqrt
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def strip_tags(text: str) -> str:
    return text.replace("<b>", "").replace("</b>", "")


def search_local(query: str) -> list[dict]:
    response = request_with_retry(
        NAVER_API_URL,
        {"query": query, "display": 5, "start": 1, "sort": "random"},
        headers=NAVER_HEADERS,
    )
    return response.json().get("items", [])


def build_local_place(item: dict) -> dict | None:
    try:
        lat = int(item["mapy"]) / 10_000_000
        lon = int(item["mapx"]) / 10_000_000
    except (KeyError, ValueError):
        return None
    if not lat or not lon:
        return None
    if haversine_km(CENTER_LAT, CENTER_LON, lat, lon) > MAX_RADIUS_KM:
        return None

    title = strip_tags(item.get("title", ""))
    address = item.get("roadAddress") or item.get("address", "")
    category_raw = item.get("category", "")
    genre = category_raw.split(",")[0].strip() if category_raw else "체험"

    # NAVER contentid가 따로 없어서, 매번 같은 업체는 같은 id가 나오도록(재실행해도
    # 중복/증식 안 되도록) 이름+주소 해시로 안정적인 id를 만든다.
    place_id = "loc_" + hashlib.md5(f"{title}|{address}".encode("utf-8")).hexdigest()[:12]

    return {
        "id": place_id,
        "type": "place",
        "category": LOCAL_SEARCH_CATEGORY,
        "genre": genre,
        "is_child": True,
        "title": title,
        "start_date": ALWAYS_OPEN_START,
        "end_date": ALWAYS_OPEN_END,
        "venue": title,
        "address": address,
        "region_group": region_group_from_address(address),
        "lat": lat,
        "lon": lon,
        "age": "",
        "price": "",
        "runtime": "",
        "schedule": "",
        "poster": "",
        "link": item.get("link") or f"https://search.naver.com/search.naver?query={requests.utils.quote(title)}",
        "telephone": item.get("telephone", ""),
        "approx_location": False,
        "amenities": [],
    }


def collect_local_places() -> list[dict]:
    seen_ids: set[str] = set()
    places: list[dict] = []
    for area in LOCAL_SEARCH_AREAS:
        for keyword in LOCAL_SEARCH_KEYWORDS:
            query = f"{area} {keyword}"
            try:
                items = search_local(query)
            except requests.RequestException as e:
                print(f"[경고] '{query}' 조회 실패: {e}")
                continue
            for item in items:
                place = build_local_place(item)
                if place and place["id"] not in seen_ids:
                    seen_ids.add(place["id"])
                    places.append(place)
            time.sleep(REQUEST_DELAY)
        print(f"[진행] '{area}' 완료, 누적 {len(places)}건")
    return places


def _save(places: list[dict]) -> None:
    kst = timezone(timedelta(hours=9))
    payload = {
        "updated_at": datetime.now(kst).isoformat(),
        "count": len(places),
        "places": places,
    }
    with open(LOCAL_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main():
    with open(LOCAL_DATA_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)

    other_places = [p for p in existing["places"] if not str(p.get("id", "")).startswith("loc_")]
    local_places = collect_local_places()

    combined_places = other_places + local_places
    _save(combined_places)
    print(f"NAVER 지역검색 {len(local_places)}건 (기존 대체) -> 총 {len(combined_places)}건 -> {LOCAL_DATA_PATH}")


if __name__ == "__main__":
    main()
