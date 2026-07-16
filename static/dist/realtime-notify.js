import{C as f}from"./chunks/chatWebSocket-DnabIQIh.js";const d=window.APP_REALTIME||{},p=6e3,m=4,u={new_message:"fas fa-message",new_comment:"fas fa-comment-dots",comment_reply:"fas fa-reply",new_follower:"fas fa-user-plus",profile_liked:"fas fa-heart",note_copied:"fas fa-copy",note_revision_restored:"fas fa-clock-rotate-left",report_received:"fas fa-shield-halved",report_resolved:"fas fa-shield-halved",sanction_applied:"fas fa-ban",sanction_revoked:"fas fa-circle-check",appeal_submitted:"fas fa-scale-balanced",appeal_resolved:"fas fa-scale-balanced"};function y(){if(document.getElementById("rt-notify-styles"))return;const e=document.createElement("style");e.id="rt-notify-styles",e.textContent=`
#rt-notify-container {
  position: fixed;
  top: 72px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(340px, calc(100vw - 32px));
  pointer-events: none;
}
.rt-notify-toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(64, 158, 255, 0.35);
  background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.16);
  cursor: pointer;
  pointer-events: auto;
  animation: rt-notify-in 0.25s ease-out;
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.rt-notify-toast.leaving {
  opacity: 0;
  transform: translateX(24px);
}
[data-theme="dark"] .rt-notify-toast {
  background: rgba(30, 41, 59, 0.97);
  border-color: rgba(64, 158, 255, 0.45);
}
.rt-notify-icon {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
  font-size: 14px;
}
.rt-notify-copy {
  min-width: 0;
  flex: 1;
}
.rt-notify-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
[data-theme="dark"] .rt-notify-title { color: #e2e8f0; }
.rt-notify-body {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
[data-theme="dark"] .rt-notify-body { color: #94a3b8; }
.rt-notify-close {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 4px;
}
@keyframes rt-notify-in {
  from { opacity: 0; transform: translateX(24px); }
  to { opacity: 1; transform: translateX(0); }
}
`,document.head.appendChild(e)}function h(){let e=document.getElementById("rt-notify-container");return e||(e=document.createElement("div"),e.id="rt-notify-container",document.body.appendChild(e)),e}function b(e){const t=e.data||{};return typeof t.url=="string"&&t.url.startsWith("/")?t.url:t.note_id?`/knowledge/?note=${t.note_id}`:t.group_id||t.message_id||e.kind==="new_message"?"/messages/":""}function c(e){e.dataset.leaving||(e.dataset.leaving="1",e.classList.add("leaving"),setTimeout(()=>e.remove(),320))}function g(e){y();const t=h();for(;t.children.length>=m;)t.firstElementChild.remove();const n=document.createElement("div");n.className="rt-notify-toast";const r=document.createElement("span");r.className="rt-notify-icon",r.innerHTML=`<i class="${u[e.kind]||"fas fa-bell"}"></i>`;const a=document.createElement("div");a.className="rt-notify-copy";const s=document.createElement("p");if(s.className="rt-notify-title",s.textContent=e.title||"系统通知",a.appendChild(s),e.body){const i=document.createElement("p");i.className="rt-notify-body",i.textContent=e.body,a.appendChild(i)}const o=document.createElement("button");o.className="rt-notify-close",o.type="button",o.setAttribute("aria-label","关闭通知"),o.innerHTML='<i class="fas fa-xmark"></i>',o.addEventListener("click",i=>{i.stopPropagation(),c(n)}),n.appendChild(r),n.appendChild(a),n.appendChild(o);const l=b(e);l&&n.addEventListener("click",()=>{window.location.href=l}),t.appendChild(n),setTimeout(()=>c(n),p)}function x(e){return!(e.kind==="new_message"&&window.location.pathname.startsWith("/messages"))}function w(e){!e||e.type!=="notification"||!e.notification||(window.dispatchEvent(new CustomEvent("app:notification",{detail:e})),x(e.notification)&&g(e.notification))}if(d.enabled&&"WebSocket"in window){const e=new f({path:d.wsPath||"/ws/messages/",onEvent:w});e.connect(),window.addEventListener("beforeunload",()=>e.close())}
