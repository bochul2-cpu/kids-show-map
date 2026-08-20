"""data/places.json 을 읽어 Leaflet 지도 기반의 반응형 index.html 을 생성한다.
공연 상세(기간/가격/포스터/링크)를 팝업에 담고, 확대 정도에 따라 마커가
클러스터 -> 개별 핀으로 펼쳐지도록 구성한다."""
import json

from config import DATA_PATH, MAP_OUTPUT_PATH

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>어린이 공연 지도</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
<style>
  html, body {{ height: 100%; margin: 0; font-family: -apple-system, "Malgun Gothic", sans-serif; }}
  #map {{ height: 100%; width: 100%; }}
  .info-bar {{
    position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
    z-index: 1000; background: white; padding: 6px 14px; border-radius: 20px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.3); font-size: 13px; color: #333;
  }}
  .prf-popup {{ width: 240px; }}
  .prf-popup img {{ width: 100%; height: 140px; object-fit: cover; border-radius: 6px; margin-bottom: 6px; }}
  .prf-popup h3 {{ font-size: 15px; margin: 0 0 4px; line-height: 1.3; }}
  .prf-popup .genre {{
    display: inline-block; font-size: 11px; background: #eef2ff; color: #3b4bcc;
    padding: 2px 8px; border-radius: 10px; margin-bottom: 6px;
  }}
  .prf-popup dl {{ margin: 6px 0 0; font-size: 12.5px; color: #444; }}
  .prf-popup dt {{ font-weight: 600; float: left; width: 44px; clear: left; color: #888; }}
  .prf-popup dd {{ margin: 0 0 3px 48px; }}
  .prf-popup a.link-btn {{
    display: block; text-align: center; margin-top: 8px; padding: 6px 0;
    background: #3b4bcc; color: white; border-radius: 6px; text-decoration: none; font-size: 13px;
  }}
</style>
</head>
<body>
<div id="map"></div>
<div class="info-bar">공연 {count}건 · 업데이트 {updated_at}</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
  const places = {places_json};

  const map = L.map('map').setView([37.5665, 126.9780], 10);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);

  const clusters = L.markerClusterGroup({{ maxClusterRadius: 50 }});

  places.forEach(p => {{
    const marker = L.marker([p.lat, p.lon]);
    const posterHtml = p.poster ? `<img src="${{p.poster}}" alt="${{p.title}} 포스터">` : '';
    const linkHtml = p.link ? `<a class="link-btn" href="${{p.link}}" target="_blank">예매/상세보기</a>` : '';

    marker.bindPopup(
      `<div class="prf-popup">` +
        posterHtml +
        `<span class="genre">${{p.genre}}</span>` +
        `<h3>${{p.title}}</h3>` +
        `<dl>` +
          `<dt>기간</dt><dd>${{p.start_date}} ~ ${{p.end_date}}</dd>` +
          `<dt>장소</dt><dd>${{p.venue}}<br>${{p.address}}</dd>` +
          (p.age ? `<dt>연령</dt><dd>${{p.age}}</dd>` : '') +
          (p.price ? `<dt>가격</dt><dd>${{p.price}}</dd>` : '') +
          (p.schedule ? `<dt>시간</dt><dd>${{p.schedule}}</dd>` : '') +
          (p.telephone ? `<dt>전화</dt><dd>${{p.telephone}}</dd>` : '') +
        `</dl>` +
        linkHtml +
      `</div>`,
      {{ maxWidth: 260 }}
    );
    clusters.addLayer(marker);
  }});

  map.addLayer(clusters);

  if (places.length > 0) {{
    map.fitBounds(clusters.getBounds().pad(0.1));
  }}
</script>
</body>
</html>
"""


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    html = HTML_TEMPLATE.format(
        count=data["count"],
        updated_at=data["updated_at"][:16].replace("T", " "),
        places_json=json.dumps(data["places"], ensure_ascii=False),
    )

    with open(MAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"지도 생성 완료 -> {MAP_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
