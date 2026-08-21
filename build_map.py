"""정적 index.html 셸을 생성한다. 공연 데이터는 빌드 시점에 박아넣지 않고,
런타임에 data/places.json 을 fetch 해서 그린다. 아동 공연 전용 서비스.

컨셉: "부천 사는 아이아빠가 주말에 어디갈지 쉽게 보려고 만든 웹" - 부천시청
기준 반경 20km 이내, 오늘부터 이번 주말까지의 데이터만 고정으로 보여준다.
지역/반경/날짜를 사용자가 직접 설정하는 UI는 없다 - 그냥 켜면 바로 결과가
뜨고 훑어보고 나가는 것이 목적이라, 카테고리 선택 말고는 설정할 게 없다."""
from settings import MAP_OUTPUT_PATH, GA_MEASUREMENT_ID
from config import NAVER_MAP_CLIENT_ID

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>아이랑 가볼까</title>
<meta name="description" content="부천 사는 아이아빠가 주말에 어디갈지 쉽게 보려고 만든 웹 - 부천 근교 20km, 오늘부터 이번 주말까지">
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#ff7a50">
<link rel="icon" href="icons/icon-192.png">
<!-- iOS Safari는 manifest.json을 거의 무시하고 이 태그들로만 홈 화면 추가를 지원한다 -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="아이랑 가볼까">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<!-- 카카오톡/문자/메신저로 공유했을 때 미리보기 카드가 뜨게. 정적 사이트라 공유된
     특정 장소별로는 못 바꾸고(og 태그는 크롤러가 JS 실행 없이 그냥 이 HTML을 읽어가서
     결정됨) 앱 전체 기준의 고정 카드만 가능하다. -->
<meta property="og:type" content="website">
<meta property="og:title" content="아이랑 가볼까">
<meta property="og:description" content="부천 사는 아이아빠가 주말에 어디갈지 쉽게 보려고 만든 웹 - 부천 근교 20km, 오늘부터 이번 주말까지">
<meta property="og:image" content="https://bochul2-cpu.github.io/kids-show-map/icons/og-image.png">
<meta property="og:url" content="https://bochul2-cpu.github.io/kids-show-map/">
<meta name="twitter:card" content="summary_large_image">
<script async src="https://www.googletagmanager.com/gtag/js?id={ga_measurement_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{ dataLayer.push(arguments); }}
  gtag('js', new Date());
  gtag('config', '{ga_measurement_id}');
</script>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{
    height: 100%; margin: 0; font-family: -apple-system, "Malgun Gothic", sans-serif;
    display: flex; flex-direction: column; overflow: hidden; background: #fff8f3;
  }}

  /* ---------- 상단 바 ---------- */
  .topbar {{
    flex-shrink: 0; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    padding: 10px 12px; z-index: 20; position: relative;
  }}
  .topbar-header {{ display: flex; align-items: center; justify-content: space-between; }}
  .brand {{ display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }}
  .brand .logo {{ font-size: 18px; }}
  .brand h1 {{ font-size: 15px; margin: 0; color: #333; font-weight: 800; }}
  .brand .tagline {{ font-size: 11px; color: #aaa; margin-left: 4px; }}
  .topbar-toggle {{
    display: none; flex-shrink: 0; background: none; border: none; color: #bbb;
    font-size: 13px; padding: 4px 8px; cursor: pointer; margin-bottom: 8px;
  }}

  .chip-row {{ display: flex; gap: 6px; overflow-x: auto; padding-bottom: 6px; -webkit-overflow-scrolling: touch; }}
  .chip-row::-webkit-scrollbar {{ height: 4px; }}
  .chip-row:last-child {{ padding-bottom: 0; }}
  .chip {{
    flex: 0 0 auto; border: 1.5px solid #eee; background: white; color: #666;
    border-radius: 16px; padding: 5px 12px; font-size: 12.5px; cursor: pointer; white-space: nowrap;
  }}
  .cat-row .chip.active {{ background: #ff7a50; border-color: #ff7a50; color: white; }}
  .count-row {{ margin-top: 6px; }}
  .count-text {{ font-size: 11.5px; color: #999; }}

  /* ---------- 데스크톱: 넓은 화면에서 칩 줄들이 한 줄에 눌린 채로 옆에 빈 공백만
     길게 남던 문제 - 가로 스크롤 대신 줄바꿈으로 실제 너비를 채우고, 상단바
     내용물 자체도 너무 넓게 늘어지지 않게 적당한 최대 너비로 묶는다. */
  @media (min-width: 769px) {{
    .topbar-body {{ max-width: 900px; }}
    .chip-row {{ flex-wrap: wrap; overflow-x: visible; padding-bottom: 0; }}
  }}

  /* ---------- 본문: 목록 + 지도 ---------- */
  .main-layout {{ flex: 1; display: flex; position: relative; overflow: hidden; }}
  #map {{ flex: 1; height: 100%; }}

  .list-panel {{
    width: 380px; flex-shrink: 0; background: #fff8f3; overflow-y: auto;
    border-right: 1px solid #ffe1d0;
  }}
  .list-items {{ padding: 8px; }}
  .empty-msg {{ text-align: center; color: #bbb; font-size: 13px; padding: 40px 20px; }}

  .list-card {{
    position: relative; display: flex; gap: 10px; background: white; border-radius: 12px; padding: 10px;
    margin-bottom: 8px; cursor: pointer; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    border: 1px solid transparent; transition: border-color .15s;
  }}
  .share-btn {{
    position: absolute; top: 8px; right: 8px; width: 26px; height: 26px;
    border: none; border-radius: 50%; background: rgba(255,255,255,0.9);
    font-size: 13px; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.18);
    display: flex; align-items: center; justify-content: center; z-index: 1; padding: 0;
  }}
  .list-card:hover {{ border-color: #ffcbb0; }}
  .list-card .thumb {{
    width: 68px; height: 68px; border-radius: 8px; object-fit: cover; flex-shrink: 0; background: #ffe9dd;
  }}
  .list-card .thumb.no-img {{ display: flex; align-items: center; justify-content: center; font-size: 26px; }}
  .list-card .info {{ min-width: 0; flex: 1; }}
  .list-card .genre {{
    display: inline-block; font-size: 10px; background: #fff1ea; color: #d85c30;
    padding: 1px 7px; border-radius: 8px; margin-bottom: 3px;
  }}
  .list-card h4 {{ font-size: 13.5px; margin: 0 0 3px; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .list-card .meta {{ font-size: 11px; color: #888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .list-card .price {{ font-size: 11.5px; color: #ff7a50; font-weight: 700; margin-top: 2px; }}

  /* ---------- 모바일: 지도 위로 올라오는 바텀시트 ---------- */
  @media (max-width: 768px) {{
    .brand .tagline {{ display: none; }}

    /* 상단 필터 메뉴 전체를 접었다 폈다 할 수 있게 한다 (모바일 전용) - 목록을
       "목록 보기"로 펼치면 자동으로 접혀서 지도/목록에 화면을 더 내준다.
       (CSS transition 대신 JS로 display를 직접 켜고 끈다 - max-height 트랜지션은
       reflow 타이밍에 따라 미덥지 않게 굴 수 있어서, 애니메이션보다 확실히 동작하는 걸 택함) */
    .topbar-toggle {{ display: block; }}

    .list-panel {{
      position: absolute; left: 0; right: 0; bottom: 0; width: auto;
      max-height: 88%; border-right: none; border-radius: 18px 18px 0 0;
      box-shadow: 0 -4px 20px rgba(0,0,0,0.18); z-index: 30;
      transform: translateY(calc(100% - 46px)); transition: transform .28s ease;
      display: flex; flex-direction: column;
    }}
    .list-panel.expanded {{ transform: translateY(0); }}
    .sheet-handle {{
      flex-shrink: 0; text-align: center; padding: 10px; font-size: 12.5px; color: #666;
      font-weight: 600; cursor: pointer; border-bottom: 1px solid #ffe9dd;
    }}
    .sheet-handle .bar {{ width: 36px; height: 4px; background: #ffcbb0; border-radius: 2px; margin: 0 auto 6px; }}
    .list-items {{ overflow-y: auto; }}
  }}

  /* ---------- 커스텀 핀 마커 ---------- */
  .prf-pin {{ display: flex; flex-direction: column; align-items: center; filter: drop-shadow(0 3px 4px rgba(0,0,0,0.3)); }}
  .prf-pin .pin-badge {{
    width: 32px; height: 32px; border-radius: 50%; border: 2.5px solid white;
    background: linear-gradient(160deg, #ffab7a, #ff7a50);
    display: flex; align-items: center; justify-content: center; font-size: 16px; line-height: 1;
  }}
  .prf-pin .pin-tail {{ width: 0; height: 0; margin-top: -3px; border-left: 6px solid transparent; border-right: 6px solid transparent; border-top: 8px solid #ff7a50; }}

  .cluster-badge {{
    width: 36px; height: 36px; border-radius: 50%;
    background: linear-gradient(160deg, #ffab7a, #ff7a50);
    color: white; font-weight: 700; font-size: 13px;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 6px rgba(255,122,80,0.5); border: 2px solid white; cursor: pointer;
  }}

  /* ---------- 지도 팝업(인포윈도우) ---------- */
  .prf-popup {{ width: 240px; background: white; border-radius: 10px; padding: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.25); position: relative; }}
  .prf-popup .popup-close {{
    position: absolute; top: 6px; right: 6px; width: 22px; height: 22px;
    border: none; border-radius: 50%; background: rgba(0,0,0,0.06); color: #555;
    font-size: 14px; line-height: 1; cursor: pointer; z-index: 1;
  }}
  .prf-popup .popup-share {{
    position: absolute; top: 6px; right: 34px; width: 22px; height: 22px;
    border: none; border-radius: 50%; background: rgba(0,0,0,0.06);
    font-size: 12px; line-height: 1; cursor: pointer; z-index: 1;
    display: flex; align-items: center; justify-content: center; padding: 0;
  }}
  .prf-popup img {{ width: 100%; height: 140px; object-fit: cover; border-radius: 6px; margin-bottom: 6px; }}
  .prf-popup h3 {{ font-size: 15px; margin: 0 0 4px; line-height: 1.3; }}
  .prf-popup .genre {{ display: inline-block; font-size: 11px; background: #fff1ea; color: #d85c30; padding: 2px 8px; border-radius: 10px; margin-bottom: 6px; }}
  .prf-popup .approx {{ display: inline-block; font-size: 11px; background: #fff4e5; color: #b26a00; padding: 2px 8px; border-radius: 10px; margin-bottom: 6px; margin-left: 4px; }}
  .closed-badge {{ display: inline-block; font-size: 11px; background: #fdeaea; color: #c0392b; padding: 2px 8px; border-radius: 10px; margin-bottom: 6px; margin-left: 4px; }}
  .list-card .closed-note {{ font-size: 10.5px; color: #c0392b; font-weight: 600; margin-top: 2px; }}
  .prf-popup dl {{ margin: 6px 0 0; font-size: 12.5px; color: #444; }}
  .prf-popup dt {{ font-weight: 600; float: left; width: 44px; clear: left; color: #999; }}
  .prf-popup dd {{ margin: 0 0 3px 48px; }}
  .prf-popup .price-note {{ font-size: 10.5px; color: #aaa; }}
  .prf-popup .btn-row {{ display: flex; gap: 6px; margin-top: 8px; }}
  .prf-popup .btn-row a, .prf-popup .btn-row button,
  .list-card .btn-row a, .list-card .btn-row button {{
    flex: 1; text-align: center; padding: 6px 0; border: none; border-radius: 6px;
    text-decoration: none; font-size: 13px; cursor: pointer; font-family: inherit;
  }}
  .link-btn {{ background: #ff7a50; color: white; }}
  .directions-btn {{ background: #fff1ea; color: #d85c30; }}
  .list-card .btn-row {{ display: flex; gap: 6px; margin-top: 6px; }}
  .list-card .btn-row a, .list-card .btn-row button {{ font-size: 11.5px; padding: 5px 0; }}

  @media (max-width: 480px) {{
    .prf-popup {{ width: 168px; padding: 8px; }}
    .prf-popup img {{ height: 84px; margin-bottom: 4px; }}
    .prf-popup h3 {{ font-size: 12.5px; margin-bottom: 3px; }}
    .prf-popup .genre, .prf-popup .approx, .prf-popup .closed-badge {{ font-size: 9.5px; padding: 1px 6px; }}
    .prf-popup dl {{ font-size: 10.5px; }}
    .prf-popup .price-note {{ font-size: 9px; }}
    .prf-popup dt {{ width: 34px; }}
    .prf-popup dd {{ margin-left: 38px; }}
    .prf-popup .btn-row a, .prf-popup .btn-row button {{ font-size: 11px; padding: 5px 0; }}
  }}
</style>
</head>
<body>
<div class="topbar" id="topbar">
  <div class="topbar-header">
    <div class="brand"><span class="logo">🧸</span><h1>아이랑 가볼까</h1><span class="tagline">부천 사는 아이아빠가 주말에 어디갈지 쉽게 보려고 만든 웹</span></div>
    <button type="button" class="topbar-toggle" id="topbarToggle" aria-label="메뉴 접기/펴기">▲</button>
  </div>
  <div class="topbar-body" id="topbarBody">
    <div class="chip-row cat-row" id="catChipRow"></div>
    <div class="count-row">
      <span class="count-text" id="countText">불러오는 중...</span>
    </div>
  </div>
</div>
<div class="main-layout">
  <div class="list-panel" id="listPanel">
    <div class="sheet-handle" id="sheetHandle"><div class="bar"></div><span id="sheetLabel">목록 보기</span></div>
    <div class="list-items" id="listItems"></div>
  </div>
  <div id="map"></div>
</div>
<script type="text/javascript" src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId={naver_map_client_id}"></script>
<script type="text/javascript" src="https://cdn.jsdelivr.net/gh/navermaps/marker-tools.js@master/marker-clustering/src/MarkerClustering.js"></script>
<script>
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

  const DEFAULT_CENTER = [37.5034, 126.7660]; // 부천시청 - 앱의 고정 기준점
  const FIXED_RADIUS_KM = 20; // 데이터 표출 범위: 부천시청 반경 20km 고정

  // 지도를 아무리 이동해도 부천 반경 20km 언저리 밖으로는 못 나가게 막는다 - 위도 1도
  // ≈ 111km, 경도 1도는 위도 37.5도 기준 ≈ 88km. 20km보다 살짝 넉넉하게(22km) 잡아서
  // 원이 화면 가장자리에 딱 붙지 않게 여유를 둔다.
  // 주의: maxBounds는 "지도 중심 좌표"만 이 범위 안으로 묶어준다(네이버 지도 공식 문서) -
  // 화면 가장자리가 이 범위를 넘어가는 것 자체는 막지 않으므로, 너무 축소했을 때 범위
  // 밖까지 넓게 보이는 건 minZoom으로 따로 막아야 한다.
  const MAX_BOUNDS = new naver.maps.LatLngBounds(
    new naver.maps.LatLng(37.3052, 126.5162),
    new naver.maps.LatLng(37.7016, 127.0158)
  );

  const map = new naver.maps.Map('map', {{
    zoom: 12,
    minZoom: 11,
    center: new naver.maps.LatLng(DEFAULT_CENTER[0], DEFAULT_CENTER[1]),
    maxBounds: MAX_BOUNDS,
  }});

  // 클러스터 클릭 시 기본은 줌을 1단계만 올려서 여러 번 눌러야 흩어짐 - 한 번에 크게 확대되도록 오버라이드
  Cluster.prototype.enableClickZoom = function () {{
    if (this._relation) return;
    const clusterMap = this._markerClusterer.getMap();
    this._relation = naver.maps.Event.addListener(this._clusterMarker, 'click', function (e) {{
      clusterMap.morph(e.coord, Math.min(clusterMap.getZoom() + 3, 21));
    }});
  }};

  const GENRE_ICONS = {{
    '뮤지컬': '🎵', '연극': '🎭', '서양음악(클래식)': '🎻', '한국음악(국악)': '🥁',
    '대중음악': '🎤', '무용(서양/한국무용)': '💃', '대중무용': '🕺', '서커스/마술': '🎪',
    '복합': '✨',
  }};

  // 대분류 아이콘 - 마커/칩에서 우선적으로 쓴다
  const CATEGORY_ICONS = {{
    '공연': '🎭', '전시': '🖼️', '축제': '🎪', '나들이·산책': '🌳', '동물원·수족관': '🐾',
    '체험·놀이': '🙌', '물놀이': '💦', '쇼핑몰': '🛍️',
  }};

  function iconFor(p) {{
    return CATEGORY_ICONS[p.category] || GENRE_ICONS[p.genre] || '🎫';
  }}

  // 계절이 지나면 어차피 텅 빈 결과만 나오는 카테고리는 칩 자체를 숨긴다
  // (예: 한겨울에 물놀이 칩을 보여줘봤자 0건이라 혼란만 줌)
  const SEASONAL_CATEGORIES = {{
    '물놀이': [4, 5, 6, 7, 8, 9, 10],
  }};

  function isInSeason(name) {{
    const months = SEASONAL_CATEGORIES[name];
    if (!months) return true; // 계절 제한이 없는 카테고리는 항상 표시
    return months.includes(new Date().getMonth() + 1);
  }}

  function pinIconFor(p) {{
    const icon = iconFor(p);
    const html = `<div class="prf-pin"><div class="pin-badge">${{icon}}</div><div class="pin-tail"></div></div>`;
    return {{
      content: html,
      size: new naver.maps.Size(32, 40),
      anchor: new naver.maps.Point(16, 40),
    }};
  }}

  const infowindow = new naver.maps.InfoWindow({{
    content: '<div></div>',
    borderWidth: 0,
    backgroundColor: 'transparent',
    disableAnchor: true,
    pixelOffset: new naver.maps.Point(0, -10),
  }});

  // 팝업이 열려있는 동안엔 그 공연 위치를 기준으로 확대/축소가 유지되도록 추적한다
  let activePopupPosition = null;

  function openPopupAt(position, anchor, html) {{
    activePopupPosition = position;
    panForPopup(position);
    infowindow.setContent(html);
    infowindow.open(map, anchor);
  }}

  function closePopup() {{
    activePopupPosition = null;
    infowindow.close();
  }}

  window.__closeInfoWindow = function () {{ closePopup(); }};
  naver.maps.Event.addListener(map, 'click', () => closePopup());
  naver.maps.Event.addListener(map, 'zoom_changed', function (zoom) {{
    // 축소해서 마커가 클러스터로 합쳐지는 시점(클러스터 maxZoom=15 근처)에는 열려있던 팝업도 같이 닫는다
    if (zoom < 14) closePopup();
  }});

  // 공연/축제는 "정해진 기간에 하는 것"이라 기간·정가(예매가와 다를 수 있음)·예매 라벨이 맞고,
  // 상설 장소(공원/전시관/동물원 등)는 항상 열려있어서 기간 대신 운영시간/입장료/상세보기가 맞는다
  function isTimeBound(p) {{ return p.type === 'performance' || p.category === '축제'; }}

  // "09:00~18:00"처럼 시:분~시:분 형식이 명확하게 하나만 보일 때만 지금 운영시간이
  // 지났는지 판단한다. 요일별로 다르거나("화-일 10-18, 월 휴관") 예외가 섞인 복잡한
  // 문구까지 정규식으로 해석하려 들면 실제로 열려있는 곳을 잘못 닫혔다고 판단할
  // 위험이 커서, 확실한 경우가 아니면 아예 판단하지 않는다(배지를 안 띄운다).
  function parseSimpleHours(scheduleText) {{
    if (!scheduleText) return null;
    const m = scheduleText.match(/(\d{{1,2}}):(\d{{2}})\s*[~\-–]\s*(\d{{1,2}}):(\d{{2}})/);
    if (!m) return null;
    const openMin = Number(m[1]) * 60 + Number(m[2]);
    let closeMin = Number(m[3]) * 60 + Number(m[4]);
    if (closeMin <= openMin) closeMin += 24 * 60; // 자정 넘겨서 닫는 경우(예: 22:00~02:00)
    return {{ openMin, closeMin }};
  }}

  function isLikelyClosedNow(p) {{
    if (isTimeBound(p)) return false; // 공연/축제는 기간·회차가 따로 있어 여기서는 판단 안 함
    const hours = parseSimpleHours(p.schedule);
    if (!hours) return false;
    const now = new Date();
    const nowMin = now.getHours() * 60 + now.getMinutes();
    return nowMin < hours.openMin || nowMin > hours.closeMin;
  }}

  // 친구/가족한테 바로 이 장소를 보내줄 수 있게 - 그냥 홈으로 보내는 게 아니라
  // ?place=id 붙여서, 받은 사람이 열면 바로 그 장소 팝업이 뜨게(아래 초기 로드
  // 로직 참고) 한다.
  window.sharePlace = function (id) {{
    const p = allPlaces.find(x => x.id === id);
    if (!p) return;
    const url = `${{location.origin}}${{location.pathname}}?place=${{encodeURIComponent(id)}}`;
    const shareData = {{ title: p.title, text: `${{p.title}} - 아이랑 가볼까`, url }};
    if (navigator.share) {{
      navigator.share(shareData).catch(() => {{}});
    }} else if (navigator.clipboard) {{
      navigator.clipboard.writeText(url).then(() => {{
        alert('링크를 복사했어요. 붙여넣기로 공유해보세요!');
      }}).catch(() => {{
        prompt('아래 링크를 복사해서 공유해보세요', url);
      }});
    }} else {{
      prompt('아래 링크를 복사해서 공유해보세요', url);
    }}
  }};

  function buildPopupHtml(p) {{
    const timeBound = isTimeBound(p);
    const posterHtml = p.poster ? `<img src="${{p.poster}}" alt="${{p.title}} 포스터">` : '';
    const approxHtml = p.approx_location ? `<span class="approx">위치 대략</span>` : '';
    const closedHtml = isLikelyClosedNow(p) ? `<span class="closed-badge">⏰ 지금은 운영시간이 지났을 수 있어요</span>` : '';
    const priceLabel = p.type === 'performance' ? '정가' : '입장료';
    const priceNote = p.type === 'performance' ? `<br><span class="price-note">실제 예매가는 다를 수 있어요</span>` : '';
    const linkLabel = timeBound ? '예매/상세보기' : '상세보기';
    return (
      `<div class="prf-popup">` +
        `<button type="button" class="popup-close" onclick="window.__closeInfoWindow()">×</button>` +
        `<button type="button" class="popup-share" onclick="sharePlace('${{p.id}}')">🔗</button>` +
        posterHtml +
        `<span class="genre">${{p.genre}}</span>` + approxHtml + closedHtml +
        `<h3>${{p.title}}</h3>` +
        `<dl>` +
          (timeBound ? `<dt>기간</dt><dd>${{p.start_date}} ~ ${{p.end_date}}</dd>` : '') +
          `<dt>장소</dt><dd>${{p.venue}}<br>${{p.address}}</dd>` +
          (p.age ? `<dt>연령</dt><dd>${{p.age}}</dd>` : '') +
          (p.price ? `<dt>${{priceLabel}}</dt><dd>${{p.price}}${{priceNote}}</dd>` : '') +
          (p.schedule ? `<dt>${{timeBound ? '시간' : '운영시간'}}</dt><dd>${{p.schedule}}</dd>` : '') +
          (p.telephone ? `<dt>전화</dt><dd>${{p.telephone}}</dd>` : '') +
        `</dl>` +
        `<div class="btn-row">` +
          `<a class="link-btn" href="${{p.link}}" target="_blank" rel="noopener">${{linkLabel}}</a>` +
          `<button class="directions-btn" onclick="openDirections(${{p.lat}}, ${{p.lon}}, '${{encodeURIComponent(p.venue || p.title)}}')">길찾기</button>` +
        `</div>` +
      `</div>`
    );
  }}

  // 팝업이 위쪽 상단바에 가릴 때만, 가려지는 만큼만 살짝 내려서 보이게 한다.
  // (매번 화면 중앙으로 옮기면 누른 위치가 계속 확 바뀌어 불편하다는 피드백으로 최소 이동으로 변경)
  function panForPopup(position) {{
    const topbar = document.querySelector('.topbar');
    const topbarBottom = topbar ? topbar.getBoundingClientRect().bottom : 0;
    const popupH = window.innerWidth <= 480 ? 260 : 430;

    const proj = map.getProjection();
    const pt = proj.fromCoordToOffset(position);

    const popupTopY = pt.y - popupH; // 팝업은 마커 위쪽에 뜬다
    const neededTop = topbarBottom + 12;
    let shiftDown = Math.max(0, neededTop - popupTopY);
    if (shiftDown === 0) return; // 이미 안 가리면 지도를 움직이지 않는다

    const maxShift = Math.max(0, window.innerHeight - pt.y - 40); // 마커가 화면 밖 아래로 밀리지 않게 제한
    shiftDown = Math.min(shiftDown, maxShift);
    if (shiftDown === 0) return;

    const shifted = new naver.maps.Point(pt.x, pt.y - shiftDown);
    map.panTo(proj.fromOffsetToCoord(shifted));
  }}

  function buildMarker(p) {{
    const marker = new naver.maps.Marker({{
      position: new naver.maps.LatLng(p.lat, p.lon),
      icon: pinIconFor(p),
    }});
    naver.maps.Event.addListener(marker, 'click', function () {{
      openPopupAt(marker.getPosition(), marker, buildPopupHtml(p));
    }});
    return marker;
  }}

  function openFromList(p) {{
    const pos = new naver.maps.LatLng(p.lat, p.lon);
    // 목록에서 고른 항목은 현재 지도 화면 밖에 있을 수 있다 - 줌만 바꾸면 마커가
    // 화면 어딘가 엉뚱한(심지어 화면 밖) 위치에 놓인 채로 팝업 위치를 계산하게 돼서
    // 팝업이 잘리거나 엉뚱한 데 뜨는 원인이었다. 센터부터 옮기고 줌/팝업을 연다.
    if (window.innerWidth <= 768) collapseSheet();
    map.setCenter(pos);
    map.setZoom(16);
    openPopupAt(pos, pos, buildPopupHtml(p));
  }}

  function renderList(list) {{
    const container = document.getElementById('listItems');
    if (list.length === 0) {{
      container.innerHTML = '<div class="empty-msg">조건에 맞는 곳이 없어요</div>';
      return;
    }}
    container.innerHTML = list.map((p, i) => {{
      const timeBound = isTimeBound(p);
      const thumb = p.poster
        ? `<img class="thumb" src="${{p.poster}}" alt="">`
        : `<div class="thumb no-img">${{iconFor(p)}}</div>`;
      return (
        `<div class="list-card" data-idx="${{i}}">` +
          `<button type="button" class="share-btn" onclick="event.stopPropagation(); sharePlace('${{p.id}}')">🔗</button>` +
          thumb +
          `<div class="info">` +
            `<span class="genre">${{p.genre}}</span>` +
            `<h4>${{p.title}}</h4>` +
            (timeBound ? `<div class="meta">${{p.start_date}} ~ ${{p.end_date}}</div>` : '') +
            `<div class="meta">${{p.venue}}</div>` +
            (p.price ? `<div class="price">${{p.price}}</div>` : '') +
            (isLikelyClosedNow(p) ? `<div class="closed-note">⏰ 운영시간 지남</div>` : '') +
            `<div class="btn-row">` +
              `<a class="link-btn" href="${{p.link}}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${{timeBound ? '예매' : '상세'}}</a>` +
              `<button class="directions-btn" onclick="event.stopPropagation(); openDirections(${{p.lat}}, ${{p.lon}}, '${{encodeURIComponent(p.venue || p.title)}}')">길찾기</button>` +
            `</div>` +
          `</div>` +
        `</div>`
      );
    }}).join('');
    container.querySelectorAll('.list-card').forEach(el => {{
      el.addEventListener('click', () => openFromList(list[Number(el.dataset.idx)]));
    }});
  }}

  function toDateObj(s) {{
    const parts = (s || '').split('.').map(Number);
    if (parts.length < 3 || parts.some(isNaN)) return null;
    return new Date(parts[0], parts[1] - 1, parts[2]);
  }}

  let allPlaces = [];
  let currentMarkers = [];
  let currentClusterer = null;

  function renderMarkers(list) {{
    currentMarkers.forEach(m => m.setMap(null));
    if (currentClusterer) currentClusterer.setMap(null); // 이전 클러스터 말풍선 정리 (안 하면 옛 클러스터가 지도에 남음)
    currentMarkers = list.map(buildMarker);
    currentClusterer = new MarkerClustering({{
      minClusterSize: 2,
      maxZoom: 15,
      map: map,
      markers: currentMarkers,
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
  }}

  function activeValue(rowEl) {{
    const active = rowEl.querySelector('.chip.active');
    return active ? active.dataset.value : '';
  }}

  function haversineKm(lat1, lon1, lat2, lon2) {{
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }}

  function withinBucheonRadius(list) {{
    return list.filter(p => haversineKm(DEFAULT_CENTER[0], DEFAULT_CENTER[1], p.lat, p.lon) <= FIXED_RADIUS_KM);
  }}

  // "오늘부터 이번 주말까지" 창을 매번 오늘 날짜 기준으로 계산한다 - 사용자가 직접
  // 고를 수 있는 날짜 UI는 없고 항상 이 고정 창만 쓴다. 오늘이 토요일이면 이번주말은
  // 오늘~내일(일)까지, 일요일이면 이번주말은 오늘 하루(이미 토요일은 지났으므로)까지다.
  function getThisWeekendRange() {{
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const day = today.getDay(); // 0=일 ~ 6=토
    let sat;
    if (day === 6) {{
      sat = new Date(today);
    }} else if (day === 0) {{
      sat = new Date(today);
      sat.setDate(sat.getDate() - 1);
    }} else {{
      sat = new Date(today);
      sat.setDate(sat.getDate() + (6 - day));
    }}
    const sun = new Date(sat);
    sun.setDate(sun.getDate() + 1);
    return {{ today, sun }};
  }}

  // 공연/축제처럼 기간이 정해진 것만 이 창과 겹치는지 검사한다 - 상설 장소(공원/전시관 등)는
  // 항상 통과(isTimeBound가 false라서 여기서 걸러지지 않음).
  function withinThisWeekend(p) {{
    if (!isTimeBound(p)) return true;
    const start = toDateObj(p.start_date);
    const end = toDateObj(p.end_date);
    if (!start || !end) return false;
    const {{ today, sun }} = getThisWeekendRange();
    return start <= sun && end >= today;
  }}

  function applyFilters() {{
    closePopup(); // 필터가 바뀌면 이전에 열려있던 팝업은 더 이상 맞지 않으니 닫는다
    const cat = activeValue(document.getElementById('catChipRow'));

    let filtered = allPlaces;
    if (cat) filtered = filtered.filter(p => p.category === cat);
    filtered = withinBucheonRadius(filtered);
    filtered = filtered.filter(withinThisWeekend);

    renderMarkers(filtered);
    renderList(filtered);
    const label = document.getElementById('sheetLabel');
    if (label) label.textContent = `목록 보기 (${{filtered.length}}건)`;
    document.getElementById('countText').textContent = `장소 ${{filtered.length}}건`;
  }}

  function setActiveChip(rowEl, value) {{
    rowEl.querySelectorAll('.chip').forEach(b => b.classList.toggle('active', b.dataset.value === value));
  }}

  function initChipRow(rowEl, items, onSelect) {{
    rowEl.innerHTML = items.map((it, i) =>
      `<button type="button" class="chip${{i === 0 ? ' active' : ''}}" data-value="${{it.value}}">${{it.label}}</button>`
    ).join('');
    rowEl.querySelectorAll('.chip').forEach(btn => {{
      btn.addEventListener('click', () => {{
        setActiveChip(rowEl, btn.dataset.value);
        applyFilters();
        if (onSelect) onSelect(btn.dataset.value);
      }});
    }});
  }}

  // ---------- 모바일: 하단 목록 시트 + 상단 필터 메뉴 ----------
  // 목록을 펼치면 화면을 더 내주려고 상단 필터 메뉴를 같이 접고, 목록을 접으면 다시
  // 펼쳐서 되돌린다. 상단 메뉴 자체도 (목록과 별개로) 손으로 접었다 펼 수 있다.
  function setTopbarCollapsed(collapsed) {{
    if (window.innerWidth > 768) return; // 데스크톱은 항상 펼쳐진 상태 유지
    document.getElementById('topbarBody').style.display = collapsed ? 'none' : '';
    document.getElementById('topbarToggle').textContent = collapsed ? '▼' : '▲';
  }}

  function collapseSheet() {{
    document.getElementById('listPanel').classList.remove('expanded');
    setTopbarCollapsed(false);
  }}

  function expandSheet() {{
    document.getElementById('listPanel').classList.add('expanded');
    setTopbarCollapsed(true);
  }}

  document.getElementById('sheetHandle').addEventListener('click', () => {{
    const expanded = document.getElementById('listPanel').classList.contains('expanded');
    if (expanded) collapseSheet(); else expandSheet();
  }});

  document.getElementById('topbarToggle').addEventListener('click', () => {{
    const nowCollapsed = document.getElementById('topbarBody').style.display !== 'none';
    setTopbarCollapsed(nowCollapsed);
  }});

  function initFilters(places) {{
    // "전체"를 맨 앞에 두고 기본 선택값으로 삼는다(initChipRow가 첫 항목을 active로 켬).
    // 놀이공원은 컨셉에서 뺐고, 공연·전시는 공연/전시로 나눴다.
    const CATEGORY_ORDER = [
      '전체', '공연', '전시', '축제', '나들이·산책', '동물원·수족관', '체험·놀이', '쇼핑몰', '물놀이',
    ];
    const presentCategories = new Set(places.map(p => p.category).filter(Boolean));
    const categories = CATEGORY_ORDER
      .filter(c => c === '전체' || presentCategories.has(c))
      .filter(isInSeason);
    const catItems = categories.map(c => ({{
      value: c === '전체' ? '' : c,
      label: c === '전체' ? '전체' : (CATEGORY_ICONS[c] || '🎫') + ' ' + c,
    }}));
    initChipRow(document.getElementById('catChipRow'), catItems);
  }}

  fetch('data/places.json')
    .then(res => res.json())
    .then(data => {{
      allPlaces = data.places;
      initFilters(allPlaces);

      // 공유 링크(?place=id)로 들어온 경우 - 그냥 홈 화면 대신 공유받은 장소로 바로
      // 연다. 카테고리 칩도 그 장소 카테고리에 맞춰줘야 팝업 주변 목록/마커가 뜬금없지
      // 않다 (예: 전시를 공유받았는데 기본값인 전체가 아니라 다른 카테고리가 켜져있으면 이상함).
      const sharedId = new URLSearchParams(location.search).get('place');
      const sharedPlace = sharedId ? allPlaces.find(p => p.id === sharedId) : null;
      if (sharedPlace && sharedPlace.category) {{
        const catChip = document.querySelector(`#catChipRow .chip[data-value="${{CSS.escape(sharedPlace.category)}}"]`);
        if (catChip) setActiveChip(document.getElementById('catChipRow'), sharedPlace.category);
      }}

      applyFilters();

      if (sharedPlace) {{
        openFromList(sharedPlace);
      }}
    }})
    .catch(() => {{
      document.getElementById('countText').textContent = '데이터를 불러오지 못했습니다';
    }});
</script>
</body>
</html>
"""


def main():
    html = HTML_TEMPLATE.format(naver_map_client_id=NAVER_MAP_CLIENT_ID, ga_measurement_id=GA_MEASUREMENT_ID)
    with open(MAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"지도 생성 완료 -> {MAP_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
