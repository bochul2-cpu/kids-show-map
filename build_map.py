"""data/places.json 을 읽어 NAVER 지도 기반의 반응형 index.html 을 생성한다.
공연 상세(기간/가격/포스터/링크)를 인포윈도우에 담고, 확대 정도에 따라 마커가
클러스터 -> 개별 핀으로 펼쳐지도록 구성한다. 첫 화면은 부천 전역이 보이도록 고정."""
import json

from config import DATA_PATH, MAP_OUTPUT_PATH, NAVER_MAP_CLIENT_ID

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>어린이 공연 지도</title>
<style>
  html, body {{ height: 100%; margin: 0; font-family: -apple-system, "Malgun Gothic", sans-serif; }}
  #map {{ height: 100%; width: 100%; }}
  .info-bar {{
    position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
    z-index: 1000; background: white; padding: 6px 14px; border-radius: 20px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.3); font-size: 13px; color: #333;
  }}

  /* 커스텀 핀 마커 */
  .prf-pin {{ filter: drop-shadow(0 2px 3px rgba(0,0,0,0.35)); }}

  /* 커스텀 클러스터 배지 */
  .cluster-badge {{
    width: 36px; height: 36px; border-radius: 50%;
    background: linear-gradient(160deg, #8b7cf6, #5b4fe0);
    color: white; font-weight: 700; font-size: 13px;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 6px rgba(91,79,224,0.5); border: 2px solid white;
    cursor: pointer;
  }}

  .prf-popup {{
    width: 240px; background: white; border-radius: 10px; padding: 10px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
  }}
  .prf-popup img {{ width: 100%; height: 140px; object-fit: cover; border-radius: 6px; margin-bottom: 6px; }}
  .prf-popup h3 {{ font-size: 15px; margin: 0 0 4px; line-height: 1.3; }}
  .prf-popup .genre {{
    display: inline-block; font-size: 11px; background: #eef2ff; color: #3b4bcc;
    padding: 2px 8px; border-radius: 10px; margin-bottom: 6px;
  }}
  .prf-popup .approx {{
    display: inline-block; font-size: 11px; background: #fff4e5; color: #b26a00;
    padding: 2px 8px; border-radius: 10px; margin-bottom: 6px; margin-left: 4px;
  }}
  .prf-popup dl {{ margin: 6px 0 0; font-size: 12.5px; color: #444; }}
  .prf-popup dt {{ font-weight: 600; float: left; width: 44px; clear: left; color: #888; }}
  .prf-popup dd {{ margin: 0 0 3px 48px; }}
  .prf-popup .btn-row {{ display: flex; gap: 6px; margin-top: 8px; }}
  .prf-popup .btn-row a, .prf-popup .btn-row button {{
    flex: 1; text-align: center; padding: 6px 0; border: none; border-radius: 6px;
    text-decoration: none; font-size: 13px; cursor: pointer; font-family: inherit;
  }}
  .prf-popup .link-btn {{ background: #5b4fe0; color: white; }}
  .prf-popup .directions-btn {{ background: #eef2ff; color: #3b4bcc; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="info-bar">공연 {count}건 · 업데이트 {updated_at}</div>
<script type="text/javascript" src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId={naver_map_client_id}"></script>
<script type="text/javascript" src="https://cdn.jsdelivr.net/gh/navermaps/marker-tools.js@master/marker-clustering/src/MarkerClustering.js"></script>
<script>
  const places = {places_json};

  // 네이버지도 앱으로 "여기서부터(현재위치) 길찾기"를 연다. 앱이 없으면 웹 지도로 대체.
  window.openDirections = function (lat, lon, encodedName) {{
    const appUrl = `nmap://route/car?dlat=${{lat}}&dlng=${{lon}}&dname=${{encodedName}}&appname=kidsshowmap.bochul2`;
    const webUrl = `https://map.naver.com/p?title=${{encodedName}}&lat=${{lat}}&lng=${{lon}}`;
    const start = Date.now();
    window.location.href = appUrl;
    setTimeout(() => {{
      if (Date.now() - start < 2000) window.location.href = webUrl;
    }}, 1200);
  }};

  // 첫 화면은 부천시 전역이 보이도록 고정 (지도 조작으로 다른 지역도 볼 수 있음)
  const map = new naver.maps.Map('map', {{ zoom: 12 }});
  const BUCHEON_BOUNDS = new naver.maps.LatLngBounds(
    new naver.maps.LatLng(37.454, 126.712),
    new naver.maps.LatLng(37.578, 126.860)
  );
  map.fitBounds(BUCHEON_BOUNDS);

  const pinSvg = `<div class="prf-pin"><svg width="30" height="38" viewBox="0 0 30 38" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="pinGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#8b7cf6"/>
        <stop offset="100%" stop-color="#5b4fe0"/>
      </linearGradient>
    </defs>
    <path d="M15 0C6.716 0 0 6.716 0 15c0 11.25 15 23 15 23s15-11.75 15-23C30 6.716 23.284 0 15 0z" fill="url(#pinGrad)"/>
    <circle cx="15" cy="14" r="6" fill="white"/>
  </svg></div>`;

  const pinIcon = {{
    content: pinSvg,
    size: new naver.maps.Size(30, 38),
    anchor: new naver.maps.Point(15, 38),
  }};

  const infowindow = new naver.maps.InfoWindow({{
    content: '<div></div>',
    borderWidth: 0,
    backgroundColor: 'transparent',
    disableAnchor: true,
    pixelOffset: new naver.maps.Point(0, -10),
  }});

  const markers = places.map(p => {{
    const marker = new naver.maps.Marker({{
      position: new naver.maps.LatLng(p.lat, p.lon),
      icon: pinIcon,
    }});

    const posterHtml = p.poster ? `<img src="${{p.poster}}" alt="${{p.title}} 포스터">` : '';
    const approxHtml = p.approx_location ? `<span class="approx">위치 대략</span>` : '';

    const popupHtml =
      `<div class="prf-popup">` +
        posterHtml +
        `<span class="genre">${{p.genre}}</span>` + approxHtml +
        `<h3>${{p.title}}</h3>` +
        `<dl>` +
          `<dt>기간</dt><dd>${{p.start_date}} ~ ${{p.end_date}}</dd>` +
          `<dt>장소</dt><dd>${{p.venue}}<br>${{p.address}}</dd>` +
          (p.age ? `<dt>연령</dt><dd>${{p.age}}</dd>` : '') +
          (p.price ? `<dt>가격</dt><dd>${{p.price}}</dd>` : '') +
          (p.schedule ? `<dt>시간</dt><dd>${{p.schedule}}</dd>` : '') +
          (p.telephone ? `<dt>전화</dt><dd>${{p.telephone}}</dd>` : '') +
        `</dl>` +
        `<div class="btn-row">` +
          `<a class="link-btn" href="${{p.link}}" target="_blank" rel="noopener">예매/상세보기</a>` +
          `<button class="directions-btn" onclick="openDirections(${{p.lat}}, ${{p.lon}}, '${{encodeURIComponent(p.venue || p.title)}}')">길찾기</button>` +
        `</div>` +
      `</div>`;

    naver.maps.Event.addListener(marker, 'click', function () {{
      infowindow.setContent(popupHtml);
      infowindow.open(map, marker);
    }});

    return marker;
  }});

  new MarkerClustering({{
    minClusterSize: 2,
    maxZoom: 15,
    map: map,
    markers: markers,
    disableClickZoom: false,
    gridSize: 100,
    icons: [{{
      content: `<div class="cluster-badge"><span></span></div>`,
      size: new naver.maps.Size(36, 36),
      anchor: new naver.maps.Point(18, 18),
    }}],
    indexGenerator: [10],
    stylingFunction: function (clusterMarker, count) {{
      const el = clusterMarker.getElement();
      const span = el.querySelector('span');
      if (span) span.textContent = count;
    }},
  }});
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
        naver_map_client_id=NAVER_MAP_CLIENT_ID,
    )

    with open(MAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"지도 생성 완료 -> {MAP_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
