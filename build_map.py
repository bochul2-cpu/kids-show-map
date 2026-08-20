"""정적 index.html 셸을 생성한다. 공연 데이터는 빌드 시점에 박아넣지 않고,
런타임에 data/places.json 을 fetch 해서 그린다. 아동 공연 전용 서비스.

화면 구성: 상단 필터바(검색/지역/카테고리/날짜) 아래로 좌측 목록 + 우측 지도
(데스크톱), 또는 지도 위로 올라오는 바텀시트 목록(모바일). 첫 화면은 사용자
GPS 위치 기준으로 잡고(거부 시 부천 기본값), 그 위치가 속한 권역을 필터에
자동 선택한다."""
from settings import MAP_OUTPUT_PATH, GA_MEASUREMENT_ID
from config import NAVER_MAP_CLIENT_ID

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>아이랑 가볼까</title>
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

  .search-box-row {{ margin-bottom: 8px; }}
  .search-box-row input {{
    width: 100%; border: 1.5px solid #ffe1d0; border-radius: 12px;
    padding: 9px 12px; font-size: 13px; background: #fffaf7;
  }}
  .search-box-row input:focus {{ outline: none; border-color: #ff8a65; }}

  .chip-row {{ display: flex; gap: 6px; overflow-x: auto; padding-bottom: 6px; -webkit-overflow-scrolling: touch; }}
  .chip-row::-webkit-scrollbar {{ height: 4px; }}
  .chip-row:last-child {{ padding-bottom: 0; }}
  .chip {{
    flex: 0 0 auto; border: 1.5px solid #eee; background: white; color: #666;
    border-radius: 16px; padding: 5px 12px; font-size: 12.5px; cursor: pointer; white-space: nowrap;
  }}
  .cat-row .chip.active {{ background: #ff7a50; border-color: #ff7a50; color: white; }}
  .amenity-row .chip.active {{ background: #4a90d9; border-color: #4a90d9; color: white; }}
  .radius-row .chip.active {{ background: #7b61ff; border-color: #7b61ff; color: white; }}
  .more-filters-toggle {{
    display: none; width: 100%; text-align: left; background: none; border: none;
    color: #999; font-size: 11.5px; padding: 2px 0 6px; cursor: pointer; font-family: inherit;
  }}
  .date-row {{
    display: flex; align-items: center; gap: 6px; margin-top: 6px;
    flex-wrap: nowrap; overflow-x: auto; -webkit-overflow-scrolling: touch;
  }}
  .date-row .chip, .date-row input[type=date] {{ flex-shrink: 0; }}
  .date-row .chip.active {{ background: #ffb100; border-color: #ffb100; color: white; }}
  .date-row input[type=date] {{
    border: 1.5px solid #eee; border-radius: 8px; padding: 5px 8px; font-size: 12.5px;
    accent-color: #ff7a50; color: #555; cursor: pointer; background: #fafafa;
  }}
  .date-row input[type=date]::-webkit-calendar-picker-indicator {{ cursor: pointer; }}
  .count-row {{ display: flex; align-items: center; justify-content: space-between; margin-top: 6px; gap: 8px; }}
  .count-text {{ font-size: 11.5px; color: #999; }}
  .fav-filter-btn {{
    flex-shrink: 0; border: 1.5px solid #ffcbd8; background: white; color: #e0507a;
    border-radius: 14px; padding: 4px 10px; font-size: 11.5px; cursor: pointer; white-space: nowrap;
  }}
  .fav-filter-btn.active {{ background: #ff5c8a; border-color: #ff5c8a; color: white; }}

  /* ---------- 본문: 목록 + 지도 ---------- */
  .main-layout {{ flex: 1; display: flex; position: relative; overflow: hidden; }}
  #map {{ flex: 1; height: 100%; }}

  .list-panel {{
    width: 380px; flex-shrink: 0; background: #fff8f3; overflow-y: auto;
    border-right: 1px solid #ffe1d0;
  }}
  .list-items {{ padding: 8px; }}

  .reco-section {{ padding: 10px 8px 4px; border-bottom: 1px solid #ffe9dd; }}
  .reco-title {{ font-size: 12.5px; font-weight: 700; color: #d85c30; margin-bottom: 6px; }}
  .reco-scroll {{ display: flex; gap: 8px; overflow-x: auto; -webkit-overflow-scrolling: touch; padding-bottom: 4px; }}
  .reco-card {{ flex: 0 0 auto; width: 110px; cursor: pointer; }}
  .reco-card .thumb {{ width: 110px; height: 74px; border-radius: 8px; object-fit: cover; background: #ffe9dd; display: block; }}
  .reco-card .thumb.no-img {{ display: flex; align-items: center; justify-content: center; font-size: 22px; }}
  .reco-card h5 {{ font-size: 11.5px; margin: 4px 0 0; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; color: #333; }}
  .empty-msg {{ text-align: center; color: #bbb; font-size: 13px; padding: 40px 20px; }}

  .list-card {{
    position: relative; display: flex; gap: 10px; background: white; border-radius: 12px; padding: 10px;
    margin-bottom: 8px; cursor: pointer; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    border: 1px solid transparent; transition: border-color .15s;
  }}
  .fav-btn {{
    position: absolute; top: 8px; right: 8px; width: 26px; height: 26px;
    border: none; border-radius: 50%; background: rgba(255,255,255,0.9);
    font-size: 14px; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.18);
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
    /* 편의시설/반경 필터는 자주 안 쓰는 것들이라 모바일 상단바가 너무 길어지지 않게
       기본은 접어두고, "상세 필터" 버튼으로 펼칠 수 있게 한다 (데스크톱은 그대로 펼쳐둠). */
    .more-filters-toggle {{ display: block; }}
    .extra-filters {{ display: none; }}
    .extra-filters.expanded {{ display: block; }}

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
  .prf-popup .popup-fav {{
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
    <div class="brand"><span class="logo">🧸</span><h1>아이랑 가볼까</h1><span class="tagline">공연부터 캠핑까지, 아이랑 갈 곳 찾기</span></div>
    <button type="button" class="topbar-toggle" id="topbarToggle" aria-label="메뉴 접기/펴기">▲</button>
  </div>
  <div class="topbar-body" id="topbarBody">
    <div class="search-box-row">
      <input type="text" id="searchBox" placeholder="장소명/지역명 검색">
    </div>
    <div class="chip-row cat-row" id="catChipRow"></div>
    <button type="button" class="more-filters-toggle" id="moreFiltersToggle">🔧 상세 필터 더보기 ▾</button>
    <div class="extra-filters" id="extraFilters">
      <div class="chip-row amenity-row" id="amenityChipRow"></div>
      <div class="chip-row radius-row" id="radiusRow" style="display:none;">
        <button type="button" class="chip active" data-radius="">반경 전체</button>
        <button type="button" class="chip" data-radius="5">5km</button>
        <button type="button" class="chip" data-radius="10">10km</button>
        <button type="button" class="chip" data-radius="20">20km</button>
      </div>
    </div>
    <div class="date-row">
      <button type="button" class="chip" data-quick="today">오늘</button>
      <button type="button" class="chip" data-quick="tomorrow">내일</button>
      <button type="button" class="chip" data-quick="weekend">이번 주말</button>
      <button type="button" class="chip" data-quick="all">전체보기</button>
      <input type="date" id="dateFilter">
    </div>
    <div class="count-row">
      <span class="count-text" id="countText">불러오는 중...</span>
      <button type="button" class="fav-filter-btn" id="favFilterBtn">🤍 찜한 곳만</button>
    </div>
  </div>
</div>
<div class="main-layout">
  <div class="list-panel" id="listPanel">
    <div class="sheet-handle" id="sheetHandle"><div class="bar"></div><span id="sheetLabel">목록 보기</span></div>
    <div class="reco-section" id="recoSection" style="display:none;">
      <div class="reco-title" id="recoTitle"></div>
      <div class="reco-scroll" id="recoScroll"></div>
    </div>
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

  // ---------- 익명 device id 기반 찜(즐겨찾기) ----------
  // 지금은 로그인이 없어서 device 단위로 저장한다. 나중에 로그인 붙으면 이 getDeviceId()
  // 자리만 실제 userId로 바꿔치기하면 되도록, deviceId 발급/조회를 여기 한 곳에 몰아뒀고
  // localStorage 키 이름에도 deviceId를 그대로 넣어서 나중에 마이그레이션하기 쉽게 했다.
  function getDeviceId() {{
    const KEY = 'kids_map_device_id';
    let id = localStorage.getItem(KEY);
    if (!id) {{
      id = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : 'dev-' + Date.now() + '-' + Math.random().toString(36).slice(2);
      localStorage.setItem(KEY, id);
    }}
    return id;
  }}

  function favoritesStorageKey() {{ return `kids_map_favorites_${{getDeviceId()}}`; }}

  function getFavoriteIds() {{
    try {{
      return new Set(JSON.parse(localStorage.getItem(favoritesStorageKey()) || '[]'));
    }} catch (e) {{
      return new Set();
    }}
  }}

  function isFavorite(id) {{ return getFavoriteIds().has(id); }}

  function toggleFavorite(id) {{
    const ids = getFavoriteIds();
    if (ids.has(id)) ids.delete(id); else ids.add(id);
    localStorage.setItem(favoritesStorageKey(), JSON.stringify([...ids]));
    return ids.has(id);
  }}

  // 카드/팝업의 하트 버튼에서 호출 - 아이콘만 즉시 바꾸고, "찜한 곳만 보기" 상태에서
  // 해제한 경우엔 목록에서 바로 빠지도록 필터를 다시 돌린다.
  window.toggleFavoriteUI = function (btn, id) {{
    const nowFav = toggleFavorite(id);
    if (btn) btn.textContent = nowFav ? '❤️' : '🤍';
    if (showFavoritesOnly && !nowFav) applyFilters();
  }};

  const DEFAULT_CENTER = [37.5034, 126.7660]; // 부천시청 (GPS 거부/실패 시 기본값)
  const map = new naver.maps.Map('map', {{
    zoom: 12,
    minZoom: 6,
    center: new naver.maps.LatLng(DEFAULT_CENTER[0], DEFAULT_CENTER[1]),
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

  // 대분류(9개) 아이콘 - 마커/칩에서 우선적으로 쓴다
  const CATEGORY_ICONS = {{
    '공연·전시': '🎭', '축제': '🎪', '나들이·산책': '🌳', '동물원·수족관': '🐾',
    '체험·놀이': '🙌', '물놀이': '💦', '캠핑·글램핑': '⛺', '놀이공원': '🎢',
    '스키·눈썰매': '⛷️',
  }};

  function iconFor(p) {{
    return CATEGORY_ICONS[p.category] || GENRE_ICONS[p.genre] || '🎫';
  }}

  // 계절이 지나면 어차피 텅 빈 결과만 나오는 카테고리는 칩 자체를 숨긴다
  // (예: 한겨울에 물놀이 칩을 보여줘봤자 0건이라 혼란만 줌)
  const SEASONAL_CATEGORIES = {{
    '물놀이': [4, 5, 6, 7, 8, 9, 10],
    '스키·눈썰매': [11, 12, 1, 2, 3],
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

  // 지역 칩이 없어진 뒤로는 지도를 옮기는 것 자체가 "여기 뭐 있나 보여줘"에 해당한다.
  // 드래그하는 동안 매 프레임 다시 그리면 무거우니 멈춘 뒤에만(디바운스) 반영하고,
  // 팝업이 열려있을 땐 건드리지 않는다 - 다시 그리면서 마커를 통째로 새로 만들면
  // 팝업이 앵커하고 있던 마커가 사라져서 팝업이 깨진다.
  let boundsChangeTimer = null;
  naver.maps.Event.addListener(map, 'bounds_changed', function () {{
    if (activePopupPosition) return;
    clearTimeout(boundsChangeTimer);
    boundsChangeTimer = setTimeout(applyFilters, 400);
  }});

  // 공연/축제는 "정해진 기간에 하는 것"이라 기간·정가(예매가와 다를 수 있음)·예매 라벨이 맞고,
  // 상설 장소(공원/캠핑장/동물원 등)는 항상 열려있어서 기간 대신 운영시간/입장료/상세보기가 맞는다
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
        `<button type="button" class="popup-fav" onclick="toggleFavoriteUI(this, '${{p.id}}')">${{isFavorite(p.id) ? '❤️' : '🤍'}}</button>` +
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
          `<button type="button" class="fav-btn" onclick="event.stopPropagation(); toggleFavoriteUI(this, '${{p.id}}')">${{isFavorite(p.id) ? '❤️' : '🤍'}}</button>` +
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

  function fmtDate(d) {{
    const pad = n => String(n).padStart(2, '0');
    return `${{d.getFullYear()}}-${{pad(d.getMonth() + 1)}}-${{pad(d.getDate())}}`;
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

  // 현재 지도 화면(뷰포트) 안에 있는 것만 남긴다 - 지역 칩을 없앤 뒤로는 이게 유일한
  // 지리적 범위 기준이다.
  function placesInViewport(list) {{
    const bounds = map.getBounds();
    if (!bounds) return list;
    return list.filter(p => bounds.hasLatLng(new naver.maps.LatLng(p.lat, p.lon)));
  }}

  // 이번 주말(다가오는 토~일) 범위와 겹치는 시간제한 장소(공연/축제) + 지금 계절에
  // 맞는 상시 카테고리(여름 물놀이/겨울 스키/그 외 나들이) 를 섞어서 추천 카드로 보여준다.
  // 연령대별 추천은 age 필드가 "전체 관람가"/"8세 이상" 같은 자유 텍스트라 구조화가 안 돼
  // 있어 이번엔 계절+주말 기준으로만 구성했다.
  function computeRecommendations() {{
    const inView = placesInViewport(allPlaces);

    const today = new Date();
    const addDays = (6 - today.getDay() + 7) % 7;
    const sat = new Date(today); sat.setDate(sat.getDate() + addDays); sat.setHours(0, 0, 0, 0);
    const sun = new Date(sat); sun.setDate(sun.getDate() + 1);

    const weekendPicks = inView.filter(p => {{
      if (!isTimeBound(p)) return false;
      const start = toDateObj(p.start_date), end = toDateObj(p.end_date);
      return start && end && sat <= end && sun >= start;
    }});

    const month = today.getMonth() + 1;
    let seasonalCategory = '나들이·산책';
    if (SEASONAL_CATEGORIES['물놀이'].includes(month)) seasonalCategory = '물놀이';
    else if (SEASONAL_CATEGORIES['스키·눈썰매'].includes(month)) seasonalCategory = '스키·눈썰매';
    const seasonalPicks = inView.filter(p => p.category === seasonalCategory);

    const seen = new Set();
    const combined = [];
    [...weekendPicks, ...seasonalPicks].forEach(p => {{
      if (!seen.has(p.id) && combined.length < 10) {{ seen.add(p.id); combined.push(p); }}
    }});
    return {{ combined, seasonalCategory }};
  }}

  function renderRecommendations() {{
    const {{ combined, seasonalCategory }} = computeRecommendations();
    const section = document.getElementById('recoSection');
    if (combined.length === 0) {{ section.style.display = 'none'; return; }}
    section.style.display = 'block';
    document.getElementById('recoTitle').textContent = `🌟 이번 주말 + ${{seasonalCategory}} 추천`;
    document.getElementById('recoScroll').innerHTML = combined.map((p, i) => {{
      const thumb = p.poster
        ? `<img class="thumb" src="${{p.poster}}" alt="">`
        : `<div class="thumb no-img">${{iconFor(p)}}</div>`;
      return `<div class="reco-card" data-reco-idx="${{i}}">${{thumb}}<h5>${{p.title}}</h5></div>`;
    }}).join('');
    document.getElementById('recoScroll').querySelectorAll('.reco-card').forEach(el => {{
      el.addEventListener('click', () => openFromList(combined[Number(el.dataset.recoIdx)]));
    }});
  }}

  function updateMoreFiltersLabel() {{
    const btn = document.getElementById('moreFiltersToggle');
    const expanded = document.getElementById('extraFilters').classList.contains('expanded');
    const activeCount = selectedAmenities.size + (selectedRadiusKm ? 1 : 0);
    const suffix = activeCount > 0 ? ` (${{activeCount}}개 적용됨)` : '';
    btn.textContent = `🔧 상세 필터${{suffix}} ${{expanded ? '접기 ▲' : '더보기 ▾'}}`;
  }}

  function activeValue(rowEl) {{
    const active = rowEl.querySelector('.chip.active');
    return active ? active.dataset.value : '';
  }}

  let searchQuery = '';
  let showFavoritesOnly = false;
  const AMENITIES = ['기저귀교환대', '수유실', '주차장', '유모차대여'];
  let selectedAmenities = new Set();
  let userPosition = null; // GPS 성공 시에만 채워진다 - 반경 필터의 기준점
  let selectedRadiusKm = null;

  function haversineKm(lat1, lon1, lat2, lon2) {{
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }}

  const MAX_RENDER = 500; // 지도를 너무 축소해서 결과가 이 이상 쏟아지면 확대를 유도한다

  function renderTooManyMessage(count) {{
    document.getElementById('listItems').innerHTML =
      `<div class="empty-msg">이 범위에 ${{count}}건이나 있어요 🙈<br>지도를 확대하면 하나씩 보여드릴게요</div>`;
  }}

  function applyFilters() {{
    closePopup(); // 필터가 바뀌면 이전에 열려있던 팝업은 더 이상 맞지 않으니 닫는다
    const cat = activeValue(document.getElementById('catChipRow'));
    const dateVal = document.getElementById('dateFilter').value;

    let filtered = allPlaces;
    if (cat) filtered = filtered.filter(p => p.category === cat);
    if (showFavoritesOnly) {{
      const favIds = getFavoriteIds();
      filtered = filtered.filter(p => favIds.has(p.id));
    }}
    if (selectedAmenities.size > 0) {{
      filtered = filtered.filter(p => {{
        const have = p.amenities || [];
        for (const a of selectedAmenities) {{ if (!have.includes(a)) return false; }}
        return true;
      }});
    }}
    if (selectedRadiusKm && userPosition) {{
      filtered = filtered.filter(p => haversineKm(userPosition.lat, userPosition.lon, p.lat, p.lon) <= selectedRadiusKm);
    }}
    if (dateVal) {{
      const [y, m, d] = dateVal.split('-').map(Number);
      const sel = new Date(y, m - 1, d);
      filtered = filtered.filter(p => {{
        const start = toDateObj(p.start_date);
        const end = toDateObj(p.end_date);
        return start && end && sel >= start && sel <= end;
      }});
    }}

    let tooMany = false;
    if (searchQuery) {{
      // 검색 중일 땐 지금 지도 화면 밖에 있는 것도 찾아야 의미가 있어서 뷰포트 제한을
      // 건너뛴다 - 대신 결과가 있으면 다 보이도록 지도를 맞춰준다.
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(p =>
        (p.title || '').toLowerCase().includes(q) ||
        (p.venue || '').toLowerCase().includes(q) ||
        (p.address || '').toLowerCase().includes(q)
      );
      if (filtered.length > 0 && filtered.length <= 200) {{
        const bounds = new naver.maps.LatLngBounds();
        filtered.forEach(p => bounds.extend(new naver.maps.LatLng(p.lat, p.lon)));
        map.fitBounds(bounds);
      }}
    }} else {{
      // 지역 칩이 없어진 뒤로는 "지금 지도 화면에 보이는 범위"가 유일한 지리적 기준이다.
      filtered = placesInViewport(filtered);
      if (filtered.length > MAX_RENDER) tooMany = true;
    }}

    if (tooMany) {{
      renderMarkers([]);
      renderTooManyMessage(filtered.length);
    }} else {{
      renderMarkers(filtered);
      renderList(filtered);
    }}
    renderRecommendations();
    const label = document.getElementById('sheetLabel');
    if (label) label.textContent = `목록 보기 (${{filtered.length}}건)`;
    document.getElementById('countText').textContent = tooMany
      ? `${{filtered.length}}건 - 지도를 확대해보세요`
      : `장소 ${{filtered.length}}/${{allPlaces.length}}건`;
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
    // 최대 3개월(수집 창)까지만 선택 가능하게 막는다 (일부 공연은 종료일이 훨씬 먼 오픈런이라
    // 실제 데이터의 최대 종료일 기준으로 하면 3개월을 훌쩍 넘겨버린다)
    const dateInput = document.getElementById('dateFilter');
    const today = new Date();
    const maxEnd = new Date(today);
    maxEnd.setMonth(maxEnd.getMonth() + 3);
    dateInput.min = fmtDate(today);
    dateInput.max = fmtDate(maxEnd);
    // readonly/showPicker()는 브라우저에 따라 달력 아이콘 클릭까지 막아버릴 수 있어서,
    // 대신 키보드 입력만 막아 숫자를 직접 타이핑하지 못하게 하고 달력 클릭은 그대로 둔다
    dateInput.addEventListener('keydown', (e) => e.preventDefault());
    dateInput.addEventListener('paste', (e) => e.preventDefault());

    // 카테고리는 "전체"를 없앴다 - 모든 카테고리를 한 번에 뿌리면 마커·클러스터
    // 계산량이 커서 느리기도 하고, "오늘 뭐 볼까" 용도로는 좁혀져 있는 게 더 쓸모
    // 있다. 지역 칩은 없앴다 - 이제 지도 화면(뷰포트)에 보이는 범위가 곧 필터다.
    // 카테고리는 공연·전시로 시작한다.
    const CATEGORY_ORDER = [
      '공연·전시', '축제', '나들이·산책', '동물원·수족관', '체험·놀이',
      '물놀이', '캠핑·글램핑', '놀이공원', '스키·눈썰매',
    ];
    const presentCategories = new Set(places.map(p => p.category).filter(Boolean));
    const categories = CATEGORY_ORDER.filter(c => presentCategories.has(c)).filter(isInSeason);
    const catItems = categories.map(c => ({{ value: c, label: (CATEGORY_ICONS[c] || '🎫') + ' ' + c }}));
    initChipRow(document.getElementById('catChipRow'), catItems);

    // 편의시설은 region/category와 달리 여러 개를 동시에 켤 수 있어야 해서(기저귀교환대
    // + 주차장처럼 같이 필요한 경우) initChipRow의 단일선택 구조 대신 따로 만든다.
    // 참고: 지금 수집 데이터엔 편의시설 정보가 전혀 없어서(자동 수집 불가 항목),
    // 이 필터를 켜면 당장은 결과가 0건으로 나온다 - 나중에 수동으로 채워 넣을 자리다.
    const amenityRow = document.getElementById('amenityChipRow');
    amenityRow.innerHTML = AMENITIES.map(a => `<button type="button" class="chip" data-value="${{a}}">${{a}}</button>`).join('');
    amenityRow.querySelectorAll('.chip').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const v = btn.dataset.value;
        if (selectedAmenities.has(v)) selectedAmenities.delete(v); else selectedAmenities.add(v);
        btn.classList.toggle('active');
        applyFilters();
        updateMoreFiltersLabel();
      }});
    }});

    // 반경 필터는 GPS로 실제 내 위치를 알아야 의미가 있어서, geolocation이 성공했을 때만
    // (fetch().then() 아래 콜백에서) 이 줄을 보여준다. 그 전까진 숨겨둔다.
    const radiusRow = document.getElementById('radiusRow');
    radiusRow.querySelectorAll('.chip').forEach(btn => {{
      btn.addEventListener('click', () => {{
        radiusRow.querySelectorAll('.chip').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const v = btn.dataset.radius;
        selectedRadiusKm = v ? Number(v) : null;
        applyFilters();
        updateMoreFiltersLabel();
      }});
    }});

    // 편의시설/반경은 모바일에서 기본 접혀있다 - 지금 몇 개가 적용돼 있는지 버튼
    // 라벨에 표시해서, 접힌 상태에서도 필터가 걸려있다는 걸 놓치지 않게 한다.
    const moreFiltersToggle = document.getElementById('moreFiltersToggle');
    const extraFilters = document.getElementById('extraFilters');
    moreFiltersToggle.addEventListener('click', () => {{
      extraFilters.classList.toggle('expanded');
      updateMoreFiltersLabel();
    }});
    updateMoreFiltersLabel();

    document.getElementById('dateFilter').addEventListener('change', applyFilters);
    document.querySelectorAll('.date-row .chip').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.date-row .chip').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const q = btn.dataset.quick;
        if (q === 'today') {{
          dateInput.value = fmtDate(new Date());
        }} else if (q === 'tomorrow') {{
          const d = new Date(); d.setDate(d.getDate() + 1);
          dateInput.value = fmtDate(d);
        }} else if (q === 'weekend') {{
          const d = new Date();
          const day = d.getDay();
          const addDays = (6 - day + 7) % 7;
          d.setDate(d.getDate() + addDays);
          dateInput.value = fmtDate(d);
        }} else {{
          dateInput.value = '';
        }}
        applyFilters();
      }});
    }});

    // 기본값: 오늘
    dateInput.value = fmtDate(today);
    document.querySelector('.date-row .chip[data-quick="today"]').classList.add('active');

    // 검색: 지역/카테고리/날짜 필터와 AND로 동작한다 (필터 무시하고 엉뚱한 결과로 튀던
    // 예전 검색과 달리, 이건 그냥 필터 조건 중 하나로 들어간다 - applyFilters 참고).
    // 입력마다 바로 필터링하면 수천 건 마커를 매 타이핑마다 다시 그려서 버벅이므로 debounce.
    const searchBox = document.getElementById('searchBox');
    let searchDebounceTimer = null;
    searchBox.addEventListener('input', () => {{
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {{
        searchQuery = searchBox.value.trim();
        applyFilters();
      }}, 250);
    }});

    document.getElementById('favFilterBtn').addEventListener('click', () => {{
      showFavoritesOnly = !showFavoritesOnly;
      document.getElementById('favFilterBtn').classList.toggle('active', showFavoritesOnly);
      applyFilters();
    }});
  }}

  fetch('data/places.json')
    .then(res => res.json())
    .then(data => {{
      allPlaces = data.places;
      initFilters(allPlaces);
      applyFilters();

      if (navigator.geolocation) {{
        navigator.geolocation.getCurrentPosition(
          pos => {{
            const lat = pos.coords.latitude, lon = pos.coords.longitude;
            userPosition = {{ lat, lon }};
            document.getElementById('radiusRow').style.display = 'flex';
            map.setCenter(new naver.maps.LatLng(lat, lon));
            map.setZoom(13);
            applyFilters();
          }},
          () => {{ /* 거부/실패 시 기본값(부천) 유지 */ }},
          {{ timeout: 5000 }}
        );
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
