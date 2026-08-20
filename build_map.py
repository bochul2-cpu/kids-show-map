"""data/places.json 을 읽어 Leaflet 지도 기반의 반응형 index.html 을 생성한다."""
import json

from config import DATA_PATH, MAP_OUTPUT_PATH

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>어린이 공연 지도</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  html, body {{ height: 100%; margin: 0; font-family: -apple-system, "Malgun Gothic", sans-serif; }}
  #map {{ height: 100%; width: 100%; }}
  .info-bar {{
    position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
    z-index: 1000; background: white; padding: 6px 14px; border-radius: 20px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.3); font-size: 13px; color: #333;
  }}
</style>
</head>
<body>
<div id="map"></div>
<div class="info-bar">공연장 {count}곳 · 업데이트 {updated_at}</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const places = {places_json};

  const map = L.map('map').setView([37.5665, 126.9780], 11);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);

  const markers = [];
  places.forEach(p => {{
    const marker = L.marker([p.lat, p.lon]).addTo(map);
    marker.bindPopup(
      `<strong>${{p.title}}</strong><br>` +
      `${{p.category}}<br>` +
      `${{p.road_address || p.address}}<br>` +
      (p.telephone ? `${{p.telephone}}<br>` : '') +
      (p.link ? `<a href="${{p.link}}" target="_blank">홈페이지</a>` : '')
    );
    markers.push(marker);
  }});

  if (markers.length > 0) {{
    const group = L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.1));
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
