"""여러 키워드로 NAVER 지역 검색 API를 호출해 어린이 공연장 데이터를 모으고
data/places.json 으로 저장한다. 하루 1회 배치 실행을 염두에 둔 스크립트."""
import json
import re
import time
from datetime import datetime, timezone, timedelta

import requests

from config import NAVER_API_URL, NAVER_HEADERS, KEYWORDS, DATA_PATH

TAG_RE = re.compile(r"<[^<]+?>")


def strip_tags(text: str) -> str:
    return TAG_RE.sub("", text)


def fetch_keyword(keyword: str) -> list[dict]:
    # 지역 검색 API는 키워드당 display 최대 5, start는 페이지네이션 미지원(고정 1)
    response = requests.get(
        NAVER_API_URL,
        headers=NAVER_HEADERS,
        params={"query": keyword, "display": 5, "start": 1, "sort": "random"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("items", [])


def to_place(item: dict, keyword: str) -> dict:
    return {
        "title": strip_tags(item["title"]),
        "category": item.get("category", ""),
        "address": item.get("address", ""),
        "road_address": item.get("roadAddress", ""),
        "telephone": item.get("telephone", ""),
        "link": item.get("link", ""),
        "lon": int(item["mapx"]) / 10_000_000,
        "lat": int(item["mapy"]) / 10_000_000,
        "keyword": keyword,
    }


def collect() -> list[dict]:
    seen = set()
    places = []
    for keyword in KEYWORDS:
        try:
            items = fetch_keyword(keyword)
        except requests.RequestException as e:
            print(f"[경고] '{keyword}' 검색 실패: {e}")
            continue

        for item in items:
            place = to_place(item, keyword)
            # 같은 장소가 여러 키워드에 중복으로 잡히는 걸 좌표+이름 기준으로 제거
            key = (place["title"], round(place["lat"], 5), round(place["lon"], 5))
            if key in seen:
                continue
            seen.add(key)
            places.append(place)

        time.sleep(0.2)  # API 호출 간 간격

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

    print(f"{len(places)}개 장소 수집 완료 -> {DATA_PATH}")


if __name__ == "__main__":
    main()
