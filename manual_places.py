"""자동 수집(TourAPI/NAVER 지역검색)으로는 안 잡히는 곳들을 웹 검색/직접 확인 후
수동으로 등록해서 유지한다.

collect.py가 매 실행마다 data/places.json을 완전히 새로 쓰기 때문에(KOPIS 데이터만
남기고 기존 내용을 보존하지 않음), 수동으로 한 번 추가해도 다음 파이프라인 실행 때
조용히 사라진다 - 실제로 2026-08-23에 추가한 4곳이 이후 재실행들에서 전부 사라졌던
것을 2026-08-26에 뒤늦게 발견했다. 그래서 collect_local.py 다음 단계로 반드시
이 스크립트를 실행해서 매번 다시 채워 넣어야 한다(로컬 실행도, daily.yml 자동
실행도 동일).
"""
import json
from datetime import datetime, timezone, timedelta

from settings import DATA_PATH

KST = timezone(timedelta(hours=9))

MANUAL_PLACES = [
    # 2026-08-23 추가 - 체인 브랜드 검색으론 안 잡히는 개별 업체, NAVER 지역검색으로 좌표 확인
    {
        "id": "manual_wow_i_kitchen",
        "type": "place",
        "category": "식당·카페",
        "genre": "음식점",
        "is_child": True,
        "title": "와우아이키친 송내역본점",
        "start_date": "2000.01.01",
        "end_date": "2099.12.31",
        "venue": "와우아이키친 송내역본점",
        "address": "경기도 부천시 원미구 상일로145번길 6",
        "region_group": "수도권",
        "lat": 37.491135,
        "lon": 126.7587977,
        "age": "",
        "price": "",
        "runtime": "",
        "schedule": "",
        "poster": "",
        "link": "https://search.naver.com/search.naver?query=%EC%99%80%EC%9A%B0%EC%95%84%EC%9D%B4%ED%82%A4%EC%B9%9C%20%EC%86%A1%EB%82%B4%EC%97%AD%EB%B3%B8%EC%A0%90",
        "telephone": "",
        "approx_location": False,
        "amenities": [],
    },
    {
        # "아이기뻐"의 NAVER 등록 링크가 광고성 URL이라 검색 링크로 대체
        "id": "manual_i_gibbeo",
        "type": "place",
        "category": "식당·카페",
        "genre": "카페",
        "is_child": True,
        "title": "아이기뻐 힐스테이트중동",
        "start_date": "2000.01.01",
        "end_date": "2099.12.31",
        "venue": "아이기뻐 힐스테이트중동",
        "address": "경기도 부천시 원미구 길주로 234 힐스테이트중동 101동 1층 1096호",
        "region_group": "수도권",
        "lat": 37.5030025,
        "lon": 126.7676509,
        "age": "",
        "price": "",
        "runtime": "",
        "schedule": "",
        "poster": "",
        "link": "https://search.naver.com/search.naver?query=%EC%95%84%EC%9D%B4%EA%B8%B0%EB%BB%90%20%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8%EC%A4%91%EB%8F%99",
        "telephone": "",
        "approx_location": False,
        "amenities": [],
    },
    {
        "id": "manual_i_got_everything",
        "type": "place",
        "category": "식당·카페",
        "genre": "카페",
        "is_child": True,
        "title": "아이갓에브리씽 부천우체국점",
        "start_date": "2000.01.01",
        "end_date": "2099.12.31",
        "venue": "아이갓에브리씽 부천우체국점",
        "address": "경기도 부천시 원미구 소향로 103",
        "region_group": "수도권",
        "lat": 37.5029201,
        "lon": 126.7594033,
        "age": "",
        "price": "",
        "runtime": "",
        "schedule": "",
        "poster": "",
        "link": "https://search.naver.com/search.naver?query=%EC%95%84%EC%9D%B4%EA%B0%93%EC%97%90%EB%B8%8C%EB%A6%AC%EC%94%BD%20%EB%B6%80%EC%B2%9C%EC%9A%B0%EC%B2%B4%EA%B5%AD%EC%A0%90",
        "telephone": "",
        "approx_location": False,
        "amenities": [],
    },
    {
        "id": "manual_terry_berry_coffee",
        "type": "place",
        "category": "식당·카페",
        "genre": "카페",
        "is_child": True,
        "title": "테리베리커피 오정점",
        "start_date": "2000.01.01",
        "end_date": "2099.12.31",
        "venue": "테리베리커피 오정점",
        "address": "경기도 부천시 오정구 산업로 126",
        "region_group": "수도권",
        "lat": 37.5335877,
        "lon": 126.7869012,
        "age": "",
        "price": "",
        "runtime": "",
        "schedule": "",
        "poster": "",
        "link": "https://search.naver.com/search.naver?query=%ED%85%8C%EB%A6%AC%EB%B2%A0%EB%A6%AC%EC%BB%A4%ED%94%BC%20%EC%98%A4%EC%A0%95%EC%A0%90",
        "telephone": "",
        "approx_location": False,
        "amenities": [],
    },
    # 2026-08-26 추가 - TourAPI엔 등록이 아예 없고(확인함) NAVER 지역검색에만 있는
    # 소규모 지역 박물관이라, LOCAL_SEARCH_KEYWORDS를 "박물관"까지 넓히는 대신
    # (노이즈가 너무 커질 것 같아서) 개별 확인 후 직접 추가
    {
        "id": "manual_sudogugsan_museum",
        "type": "place",
        "category": "전시",
        "genre": "박물관",
        "is_child": True,
        "title": "수도국산달동네박물관",
        "start_date": "2000.01.01",
        "end_date": "2099.12.31",
        "venue": "수도국산달동네박물관",
        "address": "인천광역시 제물포구 솔빛로 51",
        "region_group": "수도권",
        "lat": 37.4778795,
        "lon": 126.6392973,
        "age": "",
        "price": "",
        "runtime": "",
        "schedule": "",
        "poster": "",
        "link": "https://search.naver.com/search.naver?query=%EC%88%98%EB%8F%84%EA%B5%AD%EC%82%B0%EB%8B%AC%EB%8F%99%EB%84%A4%EB%B0%95%EB%AC%BC%EA%B4%80",
        "telephone": "",
        "approx_location": False,
        "amenities": [],
    },
]


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)

    existing_ids = {p["id"] for p in existing["places"]}
    added = 0
    for place in MANUAL_PLACES:
        if place["id"] not in existing_ids:
            existing["places"].append(place)
            added += 1

    existing["updated_at"] = datetime.now(KST).isoformat()
    existing["count"] = len(existing["places"])
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"수동 등록 {added}건 신규 추가 (총 {len(MANUAL_PLACES)}건 확인) -> 총 {len(existing['places'])}건 -> {DATA_PATH}")


if __name__ == "__main__":
    main()
