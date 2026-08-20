"""한국관광공사 TourAPI로 아이와 갈 만한 장소(나들이/체험/동물원/캠핑/놀이공원/축제 등)를
모아서 기존 data/places.json(KOPIS 공연 데이터)에 합쳐 저장한다.

collect.py 다음에 실행하는 걸 전제로 한다 (KOPIS 데이터가 이미 저장돼 있어야 그 위에 합침).
"""
import json
import time
import re
from datetime import datetime, timezone, timedelta

import requests

from settings import (
    TOUR_API_BASE_URL,
    TOUR_AREA_CODES,
    TOUR_AREA_TO_REGION_GROUP,
    TOUR_CATEGORY_TARGETS,
    TOUR_FESTIVAL_CONTENT_TYPE,
    TOUR_PRIORITY_KEYWORD_TARGETS,
    TOUR_KEYWORD_TARGETS,
    TOUR_DATA_PATH,
)
from config import TOUR_API_KEY
from collect import request_with_retry, clean_telno, to_https

REQUEST_DELAY = 0.05
ALWAYS_OPEN_START = "2000.01.01"
ALWAYS_OPEN_END = "2099.12.31"
KST = timezone(timedelta(hours=9))


def tour_request(endpoint: str, params: dict) -> dict:
    full_params = {
        "serviceKey": TOUR_API_KEY,
        "MobileOS": "ETC",
        "MobileApp": "KidsShowMap",
        "_type": "json",
        **params,
    }
    response = request_with_retry(f"{TOUR_API_BASE_URL}/{endpoint}", full_params)
    return response.json()["response"]["body"]


def as_list(items) -> list[dict]:
    if not items:
        return []
    return [items] if isinstance(items, dict) else items


def fetch_area_category(content_type_id: int, area_code: str, cat1: str, cat2: str, cat3: str = "") -> list[dict]:
    results = []
    page = 1
    params = {
        "contentTypeId": content_type_id,
        "areaCode": area_code,
        "cat1": cat1,
        "cat2": cat2,
    }
    if cat3:
        params["cat3"] = cat3
    while True:
        body = tour_request("areaBasedList2", {
            "numOfRows": 100,
            "pageNo": page,
            **params,
        })
        items = as_list(body["items"].get("item") if body["items"] else None)
        results.extend(items)
        if len(items) < 100:
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    return results


def fetch_area_festivals(area_code: str) -> list[dict]:
    # searchFestival2는 eventStartDate 필터가 기대만큼 안 걸려서(0건), 이미 검증된
    # areaBasedList2 + cat2=A0207(문화관광축제/일반축제)로 대신한다
    return fetch_area_category(TOUR_FESTIVAL_CONTENT_TYPE, area_code, "A02", "A0207", "")


def fetch_keyword(keyword: str) -> list[dict]:
    results = []
    page = 1
    while True:
        body = tour_request("searchKeyword2", {
            "numOfRows": 100,
            "pageNo": page,
            "keyword": keyword,
        })
        items = as_list(body["items"].get("item") if body["items"] else None)
        results.extend(items)
        if len(items) < 100:
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    return results


def fetch_detail_intro(content_id: str, content_type_id: int) -> dict:
    try:
        body = tour_request("detailIntro2", {"contentId": content_id, "contentTypeId": content_type_id})
    except (requests.RequestException, KeyError, ValueError):
        return {}
    items = as_list(body["items"].get("item") if body.get("items") else None)
    return items[0] if items else {}


def fmt_tour_date(raw: str) -> str:
    if not raw or len(raw) != 8:
        return ""
    return f"{raw[0:4]}.{raw[4:6]}.{raw[6:8]}"


def region_group_from_area(area_code: str) -> str:
    return TOUR_AREA_TO_REGION_GROUP.get(area_code, "기타")


def build_link(item: dict) -> str:
    homepage = item.get("eventhomepage") or ""
    homepage = re.sub(r"<[^>]+>", "", homepage).strip()
    if homepage.startswith("http"):
        return homepage
    title = item.get("title", "")
    return f"https://search.naver.com/search.naver?query={requests.utils.quote(title)}"


def build_tour_place(item: dict, category: str, genre_label: str, detail: dict, region_group: str, is_festival: bool) -> dict | None:
    try:
        lat = float(item["mapy"])
        lon = float(item["mapx"])
    except (KeyError, ValueError):
        return None
    if not lat or not lon:
        return None

    if is_festival:
        start_date = fmt_tour_date(detail.get("eventstartdate", ""))
        end_date = fmt_tour_date(detail.get("eventenddate", ""))
        if not start_date or not end_date:
            # 실제 기간을 못 구한 축제는 "상시 운영"처럼 보이는 가짜 기간(2000~2099)을
            # 보여주느니 아예 빼는 게 낫다 (detailIntro2 실패 시 - 대개 TourAPI 일일
            # 트래픽 한도 초과 - 여기 걸린다)
            return None
        try:
            end_dt = datetime.strptime(end_date, "%Y.%m.%d").date()
        except ValueError:
            return None
        if end_dt < datetime.now(KST).date():
            # 이미 끝난 축제는 실제 기간이 확인돼도 지금 시점엔 의미가 없다 (TourAPI
            # 목록엔 지난 축제가 안 지워지고 계속 남아있는 경우가 있다)
            return None
        price = detail.get("usetimefestival", "")
        schedule = detail.get("playtime", "")
        age = detail.get("agelimit", "")
    else:
        start_date = ALWAYS_OPEN_START
        end_date = ALWAYS_OPEN_END
        price = detail.get("usefee", "")
        schedule = detail.get("usetimeculture", "") or detail.get("usetime", "")
        schedule = re.sub(r"<[^>]+>", " ", schedule).strip()
        age = detail.get("expagerange", "")

    return {
        "id": f"tour_{item.get('contentid', '')}",
        "type": "place",
        "category": category,
        "genre": genre_label,
        "is_child": True,
        "title": item.get("title", ""),
        "start_date": start_date,
        "end_date": end_date,
        "venue": item.get("title", ""),
        "address": (item.get("addr1", "") + " " + item.get("addr2", "")).strip(),
        "region_group": region_group,
        "lat": lat,
        "lon": lon,
        "age": age,
        "price": price,
        "runtime": "",
        "schedule": schedule,
        "poster": to_https(item.get("firstimage", "")),
        "link": build_link({**item, **detail}),
        "telephone": clean_telno(item.get("tel", "")),
        "approx_location": False,
        "amenities": [],  # 기저귀교환대/수유실/주차장/유모차대여 등 - 자동 수집 안 됨, 수동 보강용
    }


def _make_add_place(seen_ids, places):
    def add_place(item, category, genre_label, needs_detail, is_festival, region_group):
        content_id = item.get("contentid")
        if not content_id or content_id in seen_ids:
            return
        seen_ids.add(content_id)

        detail = {}
        if needs_detail or is_festival:
            try:
                detail = fetch_detail_intro(content_id, int(item.get("contenttypeid", 0)))
            except requests.RequestException as e:
                print(f"[경고] 상세 조회 실패({content_id}): {e}")
            time.sleep(REQUEST_DELAY)

        place = build_tour_place(item, category, genre_label, detail, region_group, is_festival)
        if place:
            places.append(place)
    return add_place


def collect_festivals(seen_ids: set | None = None) -> list[dict]:
    """축제만 모은다. TourAPI 일일 트래픽 한도 초과로 축제 상세(기간)를 못 가져왔을 때,
    전체(카테고리+키워드까지)를 다시 돌리지 않고 축제만 적은 요청 수로 복구하는 용도로도 쓴다."""
    places: list[dict] = []
    add_place = _make_add_place(seen_ids if seen_ids is not None else set(), places)
    for area_code in TOUR_AREA_CODES:
        try:
            items = fetch_area_festivals(area_code)
        except requests.RequestException as e:
            print(f"[경고] 축제/{area_code} 조회 실패: {e}")
            continue
        region_group = region_group_from_area(area_code)
        for item in items:
            add_place(item, "축제", "축제", False, True, region_group)
        time.sleep(REQUEST_DELAY)
    print(f"[진행] 축제 완료, 누적 {len(places)}건")
    return places


def collect_tour_places() -> list[dict]:
    seen_ids: set = set()
    places: list[dict] = []
    add_place = _make_add_place(seen_ids, places)

    # 0) 카테고리 수집보다 먼저 선점해야 하는 키워드 (예: 스타필드가 "이색체험"
    #    카테고리로 먼저 잡혀버리는 걸 방지 - seen_ids로 중복을 거르기 때문에
    #    먼저 추가한 쪽의 category 라벨이 그대로 유지된다)
    #
    # "스타필드"로 검색하면 스타필드 안에 입점한 개별 브랜드 매장까지 다 걸린다
    # ("구찌 스타필드 하남점" 같은 게 390건 중 389건 - 실제 몰 자체는 "스타필드 하남"
    # 하나뿐). 몰/마트 이름이 제목 맨 앞에 오는 것만 실제 그 장소이고, 브랜드명이
    # 앞에 붙은 건 안에 입점한 매장이라 title이 검색어로 시작하는 것만 남긴다.
    # 이마트24/홈플러스 익스프레스처럼 완전히 다른 소형 편의점 포맷도 같이 걸려서 뺀다.
    PRIORITY_KEYWORD_EXCLUDE = ["이마트24", "홈플러스 익스프레스"]
    for category, keyword in TOUR_PRIORITY_KEYWORD_TARGETS:
        try:
            items = fetch_keyword(keyword)
        except requests.RequestException as e:
            print(f"[경고] 우선 키워드 '{keyword}' 조회 실패: {e}")
            continue
        for item in items:
            title = item.get("title", "")
            if not title.startswith(keyword):
                continue
            if any(title.startswith(ex) for ex in PRIORITY_KEYWORD_EXCLUDE):
                continue
            area_code = item.get("areacode", "")
            region_group = region_group_from_area(area_code) if area_code else "기타"
            add_place(item, category, keyword, False, False, region_group)
        time.sleep(REQUEST_DELAY)
        print(f"[진행] 우선 키워드 '{keyword}' 완료, 누적 {len(places)}건")

    # 1) 카테고리 코드 기반 수집 (지역 x 카테고리)
    for category, content_type_id, cat1, cat2, cat3, genre_label, needs_detail in TOUR_CATEGORY_TARGETS:
        for area_code in TOUR_AREA_CODES:
            try:
                items = fetch_area_category(content_type_id, area_code, cat1, cat2, cat3)
            except requests.RequestException as e:
                print(f"[경고] {category}/{genre_label}/{area_code} 조회 실패: {e}")
                continue
            region_group = region_group_from_area(area_code)
            for item in items:
                add_place(item, category, genre_label, needs_detail, False, region_group)
            time.sleep(REQUEST_DELAY)
        print(f"[진행] {category}/{genre_label} 완료, 누적 {len(places)}건")

    # 2) 축제
    places.extend(collect_festivals(seen_ids))

    # 3) 카테고리 코드가 없어 키워드로 보완하는 것들 (동물원/아쿠아리움/글램핑/워터파크)
    for category, keyword in TOUR_KEYWORD_TARGETS:
        try:
            items = fetch_keyword(keyword)
        except requests.RequestException as e:
            print(f"[경고] 키워드 '{keyword}' 조회 실패: {e}")
            continue
        for item in items:
            area_code = item.get("areacode", "")
            region_group = region_group_from_area(area_code) if area_code else "기타"
            add_place(item, category, keyword, False, False, region_group)
        time.sleep(REQUEST_DELAY)
        print(f"[진행] 키워드 '{keyword}' 완료, 누적 {len(places)}건")

    return places


def _save(places: list[dict]) -> None:
    kst = timezone(timedelta(hours=9))
    payload = {
        "updated_at": datetime.now(kst).isoformat(),
        "count": len(places),
        "places": places,
    }
    with open(TOUR_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main():
    with open(TOUR_DATA_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)

    # 매일 다시 돌 때 TourAPI 결과가 계속 누적/중복되지 않도록, 기존 파일에서
    # KOPIS 공연(성능 데이터)만 남기고 이전 TourAPI 항목("tour_" 접두어)은 걷어낸 뒤
    # 새로 수집한 것으로 통째로 교체한다
    kopis_places = [p for p in existing["places"] if not str(p.get("id", "")).startswith("tour_")]

    tour_places = collect_tour_places()
    combined_places = kopis_places + tour_places
    _save(combined_places)
    print(f"TourAPI {len(tour_places)}건 (기존 대체) -> 총 {len(combined_places)}건 -> {TOUR_DATA_PATH}")


def refresh_festivals_only():
    """축제만 다시 모아서 기존 데이터의 축제(tour_ 접두 + category=='축제')만 교체한다.
    TourAPI 일일 트래픽 한도 초과로 축제 상세(기간)를 못 가져왔을 때, 이미 성공한
    나머지 카테고리(박물관/캠핑/공원 등)까지 다시 돌려 요청을 낭비하지 않기 위한 용도.
    사용: python collect_tour.py --festivals-only
    """
    with open(TOUR_DATA_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)

    other_places = [
        p for p in existing["places"]
        if not (str(p.get("id", "")).startswith("tour_") and p.get("category") == "축제")
    ]
    festival_places = collect_festivals()
    combined_places = other_places + festival_places
    _save(combined_places)
    print(f"축제 {len(festival_places)}건 재수집 -> 총 {len(combined_places)}건 -> {TOUR_DATA_PATH}")


def backfill_missing_details():
    """price/schedule/age가 비어있는 기존 TourAPI 항목(주로 박물관/기념관/전시관/미술관-
    상세조회가 필요한 카테고리)만 골라 detailIntro2를 다시 호출해 채운다.
    목록(areaBasedList2)은 이미 성공해서 항목 자체는 다 있으니 다시 부르지 않고,
    상세가 빠진 항목의 콘텐츠ID로만 바로 요청해서 - 트래픽 한도 초과로 상세만
    실패했던 걸 최소 요청으로 복구한다.
    사용: python collect_tour.py --backfill-details
    """
    content_type_by_category = {
        category: content_type_id
        for category, content_type_id, *_rest, needs_detail in TOUR_CATEGORY_TARGETS
        if needs_detail
    }

    with open(TOUR_DATA_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)

    updated = 0
    checked = 0
    for p in existing["places"]:
        pid = str(p.get("id", ""))
        if not pid.startswith("tour_"):
            continue
        content_type_id = content_type_by_category.get(p.get("category"))
        if content_type_id is None:
            continue
        if p.get("price") or p.get("schedule"):
            continue  # 이미 채워져 있으면 건너뜀
        checked += 1
        content_id = pid[len("tour_"):]
        try:
            detail = fetch_detail_intro(content_id, content_type_id)
        except requests.RequestException as e:
            print(f"[경고] 상세 재조회 실패({content_id}): {e}")
            continue
        time.sleep(REQUEST_DELAY)
        if not detail:
            continue

        schedule = detail.get("usetimeculture", "") or detail.get("usetime", "")
        schedule = re.sub(r"<[^>]+>", " ", schedule).strip()
        price = detail.get("usefee", "")
        age = detail.get("expagerange", "")
        if price or schedule or age:
            p["price"] = price or p.get("price", "")
            p["schedule"] = schedule or p.get("schedule", "")
            p["age"] = age or p.get("age", "")
            updated += 1

    _save(existing["places"])
    print(f"상세 보충: {checked}건 시도, {updated}건 업데이트 -> {TOUR_DATA_PATH}")


if __name__ == "__main__":
    import sys
    if "--festivals-only" in sys.argv:
        refresh_festivals_only()
    elif "--backfill-details" in sys.argv:
        backfill_missing_details()
    else:
        main()
