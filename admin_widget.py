"""index.html 전용 히든 관리자 패널 - 카테고리 칩을 특정 순서(공연3-전시3-축제7)로
누르면 로그인 창이 뜨고, Firebase Auth로 로그인하면 문의하기(inquiries) 목록을 볼 수
있다. Firebase Extensions(Cloud Functions, 유료 Blaze 필요)를 안 쓰고 무료로 알림 없이
문의를 확인하고 싶다는 요청으로 만들었다 - 콘솔에 매번 안 들어가도 되게.

"숨겨진 클릭 조합"은 UX일 뿐 진짜 보안이 아니다 - 실제 보안은 Firestore 규칙에서
request.auth != null(로그인 여부)로 건다. 로그인 안 하면 개발자도구로 직접 Firestore를
불러도 read가 막히므로, 클릭 조합을 몰라도 로그인 계정 없이는 못 본다.
"""
import json

# 매번 이메일까지 치기 귀찮다는 요청으로, 로그인 화면엔 비밀번호만 보이게 하고
# 이메일은 여기 고정값으로 넣어둔다. 이메일 자체는 비밀값이 아니라(로그인 성공
# 여부를 가르는 건 비밀번호 쪽) 코드에 그대로 노출돼도 안전하다 - 실제 접근 제어는
# Firestore 규칙의 request.auth != null 이 한다.
ADMIN_EMAIL = "bochul1@naver.com"

FIREBASE_CONFIG = {
    "apiKey": "AIzaSyDrI4N4e1zh8HyoElmGTtFjWWqxT_D3qWY",
    "authDomain": "my-apps-hub-6ec61.firebaseapp.com",
    "projectId": "my-apps-hub-6ec61",
    "storageBucket": "my-apps-hub-6ec61.firebasestorage.app",
    "messagingSenderId": "436032614068",
    "appId": "1:436032614068:web:d34d075f0e85e6132831e1",
}

# 카테고리 칩의 data-value 기준 (build_map.py의 CATEGORY_ORDER와 동일한 문자열).
# "3-3-7"이 외우기 쉽다는 요청으로 공연3번 -> 전시3번 -> 축제7번 순서로 정했다.
SECRET_SEQUENCE = ["공연"] * 3 + ["전시"] * 3 + ["축제"] * 7


def render_admin_widget() -> str:
    secret_sequence_json = json.dumps(SECRET_SEQUENCE, ensure_ascii=False)
    firebase_config_json = json.dumps(FIREBASE_CONFIG)
    admin_email_json = json.dumps(ADMIN_EMAIL)
    admin_email = ADMIN_EMAIL

    css = """
  .admin-overlay {
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.55);
    z-index: 400; align-items: center; justify-content: center; padding: 16px;
  }
  .admin-overlay.open { display: flex; }
  .admin-modal {
    background: white; border-radius: 16px; padding: 20px; max-width: 420px; width: 100%;
    max-height: 80vh; display: flex; flex-direction: column; box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  }
  .admin-modal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; flex-shrink: 0; }
  .admin-modal-header h3 { margin: 0; font-size: 15px; color: #333; }
  .admin-close { background: none; border: none; font-size: 18px; color: #999; cursor: pointer; padding: 4px; line-height: 1; }
  .admin-login input {
    width: 100%; border: 1.5px solid #eee; border-radius: 10px; padding: 10px; font-size: 13.5px;
    margin-bottom: 8px; box-sizing: border-box;
  }
  .admin-login button {
    width: 100%; background: #333; color: white; border: none; border-radius: 10px;
    padding: 10px; font-size: 13.5px; font-weight: 700; cursor: pointer;
  }
  .admin-login-error { font-size: 12px; color: #c0392b; margin: 6px 0 0; min-height: 14px; }
  .admin-list { overflow-y: auto; flex: 1; }
  .admin-list-empty { color: #bbb; font-size: 13px; text-align: center; padding: 30px 0; }
  .admin-item { border-bottom: 1px solid #f0f0f0; padding: 10px 0; }
  .admin-item:last-child { border-bottom: none; }
  .admin-item .admin-item-message { font-size: 13.5px; color: #333; white-space: pre-wrap; margin-bottom: 4px; }
  .admin-item .admin-item-meta { font-size: 11px; color: #aaa; }
  .admin-logout { background: none; border: none; color: #999; font-size: 11.5px; cursor: pointer; padding: 4px 0; flex-shrink: 0; text-align: right; }
"""

    block = f"""
<div class="admin-overlay" id="adminOverlay">
  <div class="admin-modal">
    <div class="admin-modal-header">
      <h3 id="adminModalTitle">관리자 로그인</h3>
      <button type="button" class="admin-close" id="adminCloseBtn">✕</button>
    </div>
    <form class="admin-login" id="adminLoginView">
      <input type="email" id="adminEmailInput" value="{admin_email}" autocomplete="username" style="display:none;" aria-hidden="true" tabindex="-1">
      <input type="password" id="adminPasswordInput" placeholder="비밀번호" autocomplete="current-password" autofocus>
      <button type="submit" id="adminLoginBtn">로그인</button>
      <p class="admin-login-error" id="adminLoginError"></p>
    </form>
    <div class="admin-list" id="adminListView" style="display:none;"></div>
    <button type="button" class="admin-logout" id="adminLogoutBtn" style="display:none;">로그아웃</button>
  </div>
</div>
<script type="module">
  import {{ initializeApp }} from "https://www.gstatic.com/firebasejs/10.13.2/firebase-app.js";
  import {{
    getAuth, signInWithEmailAndPassword, signOut, onAuthStateChanged,
  }} from "https://www.gstatic.com/firebasejs/10.13.2/firebase-auth.js";
  import {{
    getFirestore, collection, getDocs, query, orderBy,
  }} from "https://www.gstatic.com/firebasejs/10.13.2/firebase-firestore.js";

  const ADMIN_EMAIL = {admin_email_json};
  const adminApp = initializeApp({firebase_config_json}, 'adminApp');
  const adminAuth = getAuth(adminApp);
  const adminDb = getFirestore(adminApp);

  const SECRET_SEQUENCE = {secret_sequence_json};
  let secretLog = [];
  function handleSecretChipClick(value) {{
    secretLog.push(value);
    if (secretLog.length > SECRET_SEQUENCE.length) secretLog.shift();
    if (secretLog.length === SECRET_SEQUENCE.length && secretLog.every((v, i) => v === SECRET_SEQUENCE[i])) {{
      secretLog = [];
      openAdminPanel();
    }}
  }}
  window.__handleSecretChipClick = handleSecretChipClick;

  const overlay = document.getElementById('adminOverlay');
  const closeBtn = document.getElementById('adminCloseBtn');
  const loginForm = document.getElementById('adminLoginView');
  const listView = document.getElementById('adminListView');
  const logoutBtn = document.getElementById('adminLogoutBtn');
  const passwordInput = document.getElementById('adminPasswordInput');
  const loginError = document.getElementById('adminLoginError');
  const modalTitle = document.getElementById('adminModalTitle');

  function openAdminPanel() {{
    overlay.classList.add('open');
    if (adminAuth.currentUser) {{
      showList();
    }} else {{
      showLogin();
    }}
  }}
  function closeAdminPanel() {{ overlay.classList.remove('open'); }}
  closeBtn.addEventListener('click', closeAdminPanel);
  overlay.addEventListener('click', e => {{ if (e.target === overlay) closeAdminPanel(); }});

  function showLogin() {{
    modalTitle.textContent = '관리자 로그인';
    loginForm.style.display = '';
    listView.style.display = 'none';
    logoutBtn.style.display = 'none';
    loginError.textContent = '';
  }}

  function showList() {{
    modalTitle.textContent = '받은 문의';
    loginForm.style.display = 'none';
    listView.style.display = '';
    logoutBtn.style.display = '';
    loadInquiries();
  }}

  loginForm.addEventListener('submit', async (e) => {{
    e.preventDefault();
    loginError.textContent = '';
    try {{
      await signInWithEmailAndPassword(adminAuth, ADMIN_EMAIL, passwordInput.value);
      passwordInput.value = '';
      showList();
    }} catch (e) {{
      loginError.textContent = '로그인 실패 - 비밀번호를 확인해주세요';
    }}
  }});

  logoutBtn.addEventListener('click', async () => {{
    await signOut(adminAuth);
    closeAdminPanel();
  }});

  function fmtDate(ts) {{
    if (!ts || !ts.toDate) return '';
    const d = ts.toDate();
    return `${{d.getMonth() + 1}}/${{d.getDate()}} ${{String(d.getHours()).padStart(2, '0')}}:${{String(d.getMinutes()).padStart(2, '0')}}`;
  }}

  async function loadInquiries() {{
    listView.innerHTML = '<p class="admin-list-empty">불러오는 중...</p>';
    try {{
      const q = query(collection(adminDb, 'inquiries'), orderBy('createdAt', 'desc'));
      const snap = await getDocs(q);
      if (snap.empty) {{
        listView.innerHTML = '<p class="admin-list-empty">아직 문의가 없어요</p>';
        return;
      }}
      listView.innerHTML = snap.docs.map(doc => {{
        const d = doc.data();
        const reply = d.reply ? ` · 연락처: ${{d.reply}}` : '';
        return (
          '<div class="admin-item">' +
            `<div class="admin-item-message">${{(d.message || '').replace(/</g, '&lt;')}}</div>` +
            `<div class="admin-item-meta">${{fmtDate(d.createdAt)}} · ${{d.source || ''}}${{reply}}</div>` +
          '</div>'
        );
      }}).join('');
    }} catch (e) {{
      listView.innerHTML = '<p class="admin-list-empty">불러오지 못했어요</p>';
    }}
  }}
</script>
"""

    return {"css": css, "block": block}
