"""index.html/hospital.html에 똑같이 들어가는 "문의하기" 모달(Firebase Firestore 연동)을
한 곳에서 만들어서 두 build 스크립트가 같이 쓴다. 예전엔 카카오톡 오픈채팅 링크였는데,
답장을 못 남기고 채팅방 관리가 번거로워서 Firestore에 바로 저장하는 방식으로 바꿨다.

npm/번들러가 없는 순수 정적 사이트라 Firebase SDK는 CDN의 ES 모듈(gstatic.com)을
<script type="module">로 바로 불러와서 쓴다 - 빌드 단계가 필요 없다.

Firebase 웹 config의 apiKey는 시크릿이 아니다(구글 공식 문서에도 명시) - 실제 접근 제어는
Firestore 보안 규칙이 하므로 공개 저장소에 커밋해도 안전하다.
"""
import json


def render_contact_widget(accent_color: str, page_source: str) -> dict:
    """반환값의 'css'는 <style> 블록 안에, 'block'은 </body> 직전에 넣는다.
    문의하기 버튼 자체는 이미 있는 .contact-link 스타일을 그대로 쓰므로
    호출하는 쪽에서 <button id="contactOpenBtn" class="contact-link">로 배치하면 된다.
    """
    css = f"""
  .contact-overlay {{
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.45);
    z-index: 300; align-items: center; justify-content: center; padding: 16px;
  }}
  .contact-overlay.open {{ display: flex; }}
  .contact-modal {{
    background: white; border-radius: 16px; padding: 20px; max-width: 360px; width: 100%;
    box-shadow: 0 10px 30px rgba(0,0,0,0.25);
  }}
  .contact-modal-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }}
  .contact-modal-header h3 {{ margin: 0; font-size: 16px; color: #333; }}
  .contact-close {{ background: none; border: none; font-size: 18px; color: #999; cursor: pointer; padding: 4px; line-height: 1; }}
  .contact-modal-desc {{ font-size: 12.5px; color: #888; margin: 0 0 12px; line-height: 1.5; }}
  .contact-modal textarea, .contact-modal input {{
    width: 100%; border: 1.5px solid #eee; border-radius: 10px; padding: 10px; font-size: 13.5px;
    font-family: inherit; margin-bottom: 8px; box-sizing: border-box; resize: vertical;
  }}
  .contact-modal textarea:focus, .contact-modal input:focus {{ outline: none; border-color: {accent_color}; }}
  .contact-modal-actions {{ display: flex; justify-content: flex-end; margin-top: 4px; }}
  .contact-submit {{
    background: {accent_color}; color: white; border: none; border-radius: 10px; padding: 9px 18px;
    font-size: 13.5px; font-weight: 700; cursor: pointer;
  }}
  .contact-submit:disabled {{ opacity: 0.5; cursor: default; }}
  .contact-status {{ font-size: 12px; color: #888; margin: 8px 0 0; min-height: 16px; }}
  .contact-status.error {{ color: #c0392b; }}
  .contact-status.success {{ color: #1a8a4a; }}
"""

    firebase_config_json = json.dumps(
        {
            "apiKey": "AIzaSyDrI4N4e1zh8HyoElmGTtFjWWqxT_D3qWY",
            "authDomain": "my-apps-hub-6ec61.firebaseapp.com",
            "projectId": "my-apps-hub-6ec61",
            "storageBucket": "my-apps-hub-6ec61.firebasestorage.app",
            "messagingSenderId": "436032614068",
            "appId": "1:436032614068:web:d34d075f0e85e6132831e1",
        }
    )

    block = f"""
<div class="contact-overlay" id="contactOverlay">
  <div class="contact-modal">
    <div class="contact-modal-header">
      <h3>문의하기</h3>
      <button type="button" class="contact-close" id="contactCloseBtn">✕</button>
    </div>
    <p class="contact-modal-desc">불편한 점, 잘못된 정보, 추가됐으면 하는 기능 등 편하게 남겨주세요.</p>
    <textarea id="contactMessageInput" rows="5" placeholder="문의 내용을 입력해주세요"></textarea>
    <input type="text" id="contactReplyInput" placeholder="답장 받을 연락처(선택, 이메일/전화번호)">
    <div class="contact-modal-actions">
      <button type="button" class="contact-submit" id="contactSubmitBtn">보내기</button>
    </div>
    <p class="contact-status" id="contactStatusText"></p>
  </div>
</div>
<script type="module">
  import {{ initializeApp }} from "https://www.gstatic.com/firebasejs/10.13.2/firebase-app.js";
  import {{ getFirestore, collection, addDoc, serverTimestamp }} from "https://www.gstatic.com/firebasejs/10.13.2/firebase-firestore.js";

  const firebaseApp = initializeApp({firebase_config_json});
  const db = getFirestore(firebaseApp);

  const overlay = document.getElementById('contactOverlay');
  const openBtn = document.getElementById('contactOpenBtn');
  const closeBtn = document.getElementById('contactCloseBtn');
  const submitBtn = document.getElementById('contactSubmitBtn');
  const messageInput = document.getElementById('contactMessageInput');
  const replyInput = document.getElementById('contactReplyInput');
  const statusText = document.getElementById('contactStatusText');

  function openModal() {{
    overlay.classList.add('open');
    statusText.textContent = '';
    statusText.className = 'contact-status';
    messageInput.focus();
  }}
  function closeModal() {{ overlay.classList.remove('open'); }}

  openBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', e => {{ if (e.target === overlay) closeModal(); }});

  submitBtn.addEventListener('click', async () => {{
    const message = messageInput.value.trim();
    if (!message) {{
      statusText.textContent = '문의 내용을 입력해주세요';
      statusText.className = 'contact-status error';
      return;
    }}
    submitBtn.disabled = true;
    statusText.textContent = '보내는 중...';
    statusText.className = 'contact-status';
    try {{
      await addDoc(collection(db, 'inquiries'), {{
        message,
        reply: replyInput.value.trim(),
        source: '{page_source}',
        createdAt: serverTimestamp(),
        userAgent: navigator.userAgent,
      }});
      statusText.textContent = '문의가 접수됐어요. 감사합니다!';
      statusText.className = 'contact-status success';
      messageInput.value = '';
      replyInput.value = '';
      setTimeout(closeModal, 1500);
    }} catch (e) {{
      statusText.textContent = '전송에 실패했어요. 잠시 후 다시 시도해주세요.';
      statusText.className = 'contact-status error';
    }} finally {{
      submitBtn.disabled = false;
    }}
  }});
</script>
"""

    return {"css": css, "block": block}
