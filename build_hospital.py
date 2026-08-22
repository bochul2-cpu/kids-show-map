"""아이랑 병원 페이지(hospital.html)를 생성한다. "아이가 아파요" 같은 급한 상황에
쓰는 페이지라 지도 없이 목록만 빠르게 뜨도록 만든다(네이버 지도 API 로딩 자체를
건너뛴다). 소아과는 진료시간 기준으로 "지금 열려있는 곳만" 보여주고, 응급실은
항상 전체를 보여준다(전화로 확인하고 가는 게 맞는 영역이라 필터링하지 않는다).
"""
from settings import GA_MEASUREMENT_ID

HOSPITAL_OUTPUT_PATH = "hospital.html"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>아이랑 병원 - 부천·인천 소아과/응급실 찾기</title>
<meta name="description" content="아이가 아파요? 부천·인천 근교 지금 열려있는 소아과, 응급실을 바로 찾아보세요">
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#e0507a">
<link rel="icon" href="icons/icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="아이랑 병원">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:title" content="아이랑 병원">
<meta property="og:description" content="아이가 아파요? 부천·인천 근교 지금 열려있는 소아과, 응급실을 바로 찾아보세요">
<meta property="og:image" content="https://bucheonkids.com/icons/og-image.png">
<meta property="og:url" content="https://bucheonkids.com/hospital.html">
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
    margin: 0; font-family: -apple-system, "Malgun Gothic", sans-serif;
    background: #fff5f7;
  }}
  .topbar {{
    background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.08); padding: 12px 16px;
  }}
  .topbar-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }}
  .brand {{ display: flex; align-items: center; gap: 6px; }}
  .brand .logo {{ font-size: 18px; }}
  .brand h1 {{ font-size: 15px; margin: 0; color: #333; font-weight: 800; }}
  .header-actions {{ display: flex; align-items: center; gap: 8px; }}
  .nav-link, .contact-link {{
    flex-shrink: 0; font-size: 12px; text-decoration: none; font-weight: 700;
    border-radius: 14px; padding: 5px 11px; white-space: nowrap;
  }}
  .nav-link {{ color: #666; border: 1.5px solid #eee; }}
  .contact-link {{ color: #e0507a; border: 1.5px solid #ffcbd8; }}
  .nav-link:hover {{ background: #f8f8f8; }}
  .contact-link:hover {{ background: #fff0f4; }}

  .tagline {{ font-size: 12px; color: #999; margin: 0 0 10px; }}

  .tab-row {{ display: flex; gap: 6px; margin-bottom: 8px; }}
  .tab-btn {{
    flex: 1; border: 1.5px solid #eee; background: white; color: #666;
    border-radius: 10px; padding: 10px; font-size: 13.5px; font-weight: 700; cursor: pointer;
  }}
  .tab-btn.active {{ background: #e0507a; border-color: #e0507a; color: white; }}

  .locate-row {{ display: flex; align-items: center; gap: 8px; }}
  .locate-btn {{
    border: 1.5px solid #ffcbd8; background: white; color: #e0507a;
    border-radius: 10px; padding: 6px 12px; font-size: 12.5px; cursor: pointer; white-space: nowrap;
  }}
  .locate-status {{ font-size: 11.5px; color: #999; }}

  .list-items {{ padding: 10px 12px 40px; max-width: 640px; margin: 0 auto; }}
  .empty-msg {{ text-align: center; color: #bbb; font-size: 13.5px; padding: 60px 20px; line-height: 1.6; }}

  .h-card {{
    background: white; border-radius: 12px; padding: 14px; margin-bottom: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }}
  .h-card .badge {{
    display: inline-block; font-size: 10.5px; font-weight: 700; padding: 2px 8px; border-radius: 8px;
    margin-bottom: 6px;
  }}
  .badge.open {{ background: #e6f7ec; color: #1a8a4a; }}
  .badge.general {{ background: #fff4e0; color: #b26a00; }}
  .badge.er {{ background: #fdeaea; color: #c0392b; }}
  .h-card h4 {{ font-size: 15px; margin: 0 0 4px; }}
  .h-card .meta {{ font-size: 12.5px; color: #888; margin-bottom: 2px; }}
  .h-card .dist {{ font-size: 11.5px; color: #bbb; }}
  .h-card .btn-row {{ display: flex; gap: 6px; margin-top: 10px; }}
  .h-card .btn-row a {{
    flex: 1; text-align: center; padding: 9px 0; border-radius: 8px; text-decoration: none;
    font-size: 13px; font-weight: 700;
  }}
  .call-btn {{ background: #e0507a; color: white; }}
  .directions-btn {{ background: #fff0f4; color: #c0392b; }}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-header">
    <div class="brand"><span class="logo">🏥</span><h1>아이랑 병원</h1></div>
    <div class="header-actions">
      <a class="nav-link" href="index.html">🧸 가볼까</a>
      <a class="contact-link" href="https://open.kakao.com/o/gQPB54Ji" target="_blank" rel="noopener">💬 문의하기</a>
    </div>
  </div>
  <p class="tagline">아이가 아파요? 부천 근교 20km, 지금 갈 수 있는 곳만 보여드려요</p>
  <div class="tab-row">
    <button type="button" class="tab-btn active" data-cat="소아과">🧒 병원 (지금 열린 곳)</button>
    <button type="button" class="tab-btn" data-cat="응급실">🚑 응급실</button>
  </div>
  <div class="locate-row">
    <button type="button" class="locate-btn" id="locateBtn">📍 내 위치에서 가까운 순</button>
    <span class="locate-status" id="locateStatus"></span>
  </div>
</div>
<div class="list-items" id="listItems"></div>
<script>
  const CENTER = [37.5034, 126.7660]; // 부천시청 - 기본 정렬 기준점
  let refPoint = CENTER;
  let allHospitals = [];
  let activeCat = '소아과';

  function haversineKm(lat1, lon1, lat2, lon2) {{
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }}

  // hours의 day: 1=월 ... 7=일, 8=공휴일(공휴일 달력까진 반영 안 함 - 평일/토/일만 정확)
  // JS Date.getDay(): 0=일 ... 6=토
  function isOpenNow(hours) {{
    if (!hours || hours.length === 0) return false;
    const now = new Date();
    const jsDay = now.getDay();
    const todayCode = jsDay === 0 ? 7 : jsDay;
    const slot = hours.find(h => h.day === todayCode);
    if (!slot) return false;
    const nowVal = now.getHours() * 100 + now.getMinutes();
    const start = Number(slot.start);
    const end = Number(slot.end);
    return nowVal >= start && nowVal <= end;
  }}

  function fmtHours(h) {{
    return `${{h.slice(0,2)}}:${{h.slice(2)}}`;
  }}

  function todayHoursText(hours) {{
    const now = new Date();
    const jsDay = now.getDay();
    const todayCode = jsDay === 0 ? 7 : jsDay;
    const slot = hours && hours.find(h => h.day === todayCode);
    if (!slot) return '오늘 진료시간 정보 없음';
    return `오늘 ${{fmtHours(slot.start)}} ~ ${{fmtHours(slot.end)}}`;
  }}

  window.openDirections = function (lat, lon, encodedName) {{
    const appUrl = `nmap://route/car?dlat=${{lat}}&dlng=${{lon}}&dname=${{encodedName}}&appname=kidsshowmap.bochul2`;
    const webUrl = `https://map.naver.com/p?title=${{encodedName}}&lat=${{lat}}&lng=${{lon}}`;
    const start = Date.now();
    window.location.href = appUrl;
    setTimeout(() => {{
      if (Date.now() - start < 2000) window.location.href = webUrl;
    }}, 1200);
  }};

  function render() {{
    const container = document.getElementById('listItems');
    // 소아과 탭엔 공식 소아과뿐 아니라 일반의원(가정의학과/내과 등, 이름에 전문과목이
    // 안 붙은 경우 포함)도 같이 보여준다 - "부천연세365의원"처럼 소아청소년과로 등록은
    // 안 돼있어도 실제로 아이를 봐주는 동네의원이 많아서다. 대신 일반의원은 소아과가
    // 아니라는 걸 명확히 배지로 표시해서, 전화로 먼저 확인하고 가게 유도한다.
    let list = activeCat === '소아과'
      ? allHospitals.filter(h => h.category === '소아과' || h.category === '일반의원')
      : allHospitals.filter(h => h.category === activeCat);

    if (activeCat === '소아과') {{
      list = list.filter(h => isOpenNow(h.hours));
    }}

    list = list.map(h => ({{ ...h, _dist: haversineKm(refPoint[0], refPoint[1], h.lat, h.lon) }}));
    list.sort((a, b) => a._dist - b._dist);

    if (list.length === 0) {{
      const msg = activeCat === '소아과'
        ? '지금 문 연 병원이 없어요 😢<br>응급실 탭을 확인해보세요'
        : '주변에 응급실 정보가 없어요';
      container.innerHTML = `<div class="empty-msg">${{msg}}</div>`;
      return;
    }}

    container.innerHTML = list.map(h => {{
      let badge;
      if (h.category === '소아과') {{
        badge = `<span class="badge open">🟢 소아과 진료중 · ${{todayHoursText(h.hours)}}</span>`;
      }} else if (h.category === '일반의원') {{
        badge = `<span class="badge general">⚠️ 소아과 아님 · 전화로 진료 가능 여부 확인 필요</span>`;
      }} else {{
        badge = `<span class="badge er">🚑 응급실</span>`;
      }}
      return (
        `<div class="h-card">` +
          badge +
          `<h4>${{h.title}}</h4>` +
          `<div class="meta">${{h.address}}</div>` +
          (h.telephone ? `<div class="meta">${{h.telephone}}</div>` : '') +
          `<div class="dist">약 ${{h._dist.toFixed(1)}}km</div>` +
          `<div class="btn-row">` +
            (h.telephone ? `<a class="call-btn" href="tel:${{h.telephone}}">📞 전화하기</a>` : '') +
            `<a class="directions-btn" href="#" onclick="event.preventDefault(); openDirections(${{h.lat}}, ${{h.lon}}, '${{encodeURIComponent(h.title)}}')">🚗 길찾기</a>` +
          `</div>` +
        `</div>`
      );
    }}).join('');
  }}

  document.querySelectorAll('.tab-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
      activeCat = btn.dataset.cat;
      render();
    }});
  }});

  document.getElementById('locateBtn').addEventListener('click', () => {{
    const statusEl = document.getElementById('locateStatus');
    if (!navigator.geolocation) {{
      statusEl.textContent = '위치 기능을 지원하지 않는 브라우저예요';
      return;
    }}
    statusEl.textContent = '위치 확인 중...';
    navigator.geolocation.getCurrentPosition(
      pos => {{
        refPoint = [pos.coords.latitude, pos.coords.longitude];
        statusEl.textContent = '내 위치 기준으로 정렬했어요';
        render();
      }},
      () => {{ statusEl.textContent = '위치 정보를 가져올 수 없어요'; }},
      {{ timeout: 5000 }}
    );
  }});

  fetch('data/hospitals.json')
    .then(res => res.json())
    .then(data => {{
      allHospitals = data.hospitals;
      render();
    }})
    .catch(() => {{
      document.getElementById('listItems').innerHTML = '<div class="empty-msg">데이터를 불러오지 못했습니다</div>';
    }});
</script>
</body>
</html>
"""


def main():
    html = HTML_TEMPLATE.format(ga_measurement_id=GA_MEASUREMENT_ID)
    with open(HOSPITAL_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"병원 페이지 생성 완료 -> {HOSPITAL_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
