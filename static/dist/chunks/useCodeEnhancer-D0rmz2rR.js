const c={copy:`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
  </svg>`,copied:`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="20 6 9 17 4 12"></polyline>
  </svg>`,expand:`<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="6 9 12 15 18 9"></polyline>
  </svg>`},l={collapseThreshold:5,defaultCollapsed:!0,copiedDuration:2e3,enhancedClass:"code-block-enhanced",longCodeClass:"long-code",collapsedClass:"collapsed"};async function s(t){if(navigator.clipboard&&navigator.clipboard.writeText)try{return await navigator.clipboard.writeText(t),!0}catch(n){console.warn("Clipboard API 失败，尝试备用方法:",n)}try{const n=document.createElement("textarea");n.value=t,n.style.position="fixed",n.style.left="-999999px",n.style.top="-999999px",document.body.appendChild(n),n.focus(),n.select();const e=document.execCommand("copy");return document.body.removeChild(n),e}catch(n){return console.error("复制失败:",n),!1}}function p(t){if(!t)return 0;try{const e=t.textContent.split(`
`);return e.length>1?e.length:(t.innerHTML&&t.innerHTML.match(/<br\s*\/?>/gi)||[]).length+1}catch(n){return console.warn("Error counting lines:",n),0}}function d(t,n){if(!t)return null;const e=document.createElement("button");e.className="copy-btn";try{e.innerHTML=`${c.copy}<span>复制</span>`}catch(o){return console.warn("Error setting copy button innerHTML:",o),null}return e.setAttribute("aria-label","复制代码"),e.addEventListener("click",async o=>{o.preventDefault(),o.stopPropagation();const r=t.textContent;if(await s(r)){e.classList.add("copied");try{e.innerHTML=`${c.copied}<span>已复制</span>`}catch(a){console.warn("Error updating copy button:",a)}setTimeout(()=>{try{e&&e.classList&&(e.classList.remove("copied"),e.innerHTML=`${c.copy}<span>复制</span>`)}catch(a){console.warn("Error resetting copy button:",a)}},n.copiedDuration)}}),e}function m(t,n){if(!t)return null;const e=document.createElement("button");e.className="collapse-btn";try{e.innerHTML=`${c.expand}<span>展开代码</span>`}catch(o){return console.warn("Error setting collapse button innerHTML:",o),null}return e.setAttribute("aria-label","展开代码"),e.addEventListener("click",o=>{if(o.preventDefault(),o.stopPropagation(),!t||!t.parentNode){console.warn("pre element is no longer in DOM");return}t.classList.contains(n.collapsedClass)?(t.classList.remove(n.collapsedClass),e.innerHTML=`${c.expand}<span>收起代码</span>`,e.setAttribute("aria-label","收起代码")):(t.classList.add(n.collapsedClass),e.innerHTML=`${c.expand}<span>展开代码</span>`,e.setAttribute("aria-label","展开代码"))}),e}function h(t,n){if(t&&t.parentNode){if(t.classList.contains(n.enhancedClass)){console.log("[CodeEnhancer] Skipping already enhanced block");return}try{console.log("[CodeEnhancer] Enhancing code block...");let e=t.querySelector("code");if(!e){const a=t.innerHTML;t.innerHTML=`<code>${a}</code>`,e=t.querySelector("code")}if(!e)return;if(t.classList.add("line"),!e.querySelector("span.line-content")&&!e.querySelector("br")&&!e.querySelector("div")&&!e.querySelector("p")){const a=e.innerHTML;e.innerHTML=`<span class="line-content">${a}</span>`}t.classList.add(n.enhancedClass),console.log("[CodeEnhancer] Added enhanced class");const r=p(e);console.log("[CodeEnhancer] Line count:",r),r>n.collapseThreshold&&(t.classList.add(n.longCodeClass),n.defaultCollapsed&&t.classList.add(n.collapsedClass),console.log("[CodeEnhancer] Added collapse classes"));const i=d(e,n);if(i&&t.parentNode&&(t.appendChild(i),console.log("[CodeEnhancer] Added copy button")),r>n.collapseThreshold){const a=m(t,n);a&&t.parentNode&&(t.appendChild(a),console.log("[CodeEnhancer] Added collapse button"))}console.log("[CodeEnhancer] Block enhancement complete")}catch(e){console.warn("Error enhancing code block:",e)}}}function u(t,n={}){if(!t)return;const e={...l,...n};try{const o=t.querySelectorAll("pre");if(!o)return;o.forEach(r=>{try{h(r,e)}catch(i){console.warn("Error processing individual code block:",i)}})}catch(o){console.warn("Error enhancing code blocks:",o)}}function b(t={}){const n={...l,...t};return{enhance:(o,r={})=>{u(o,{...n,...r})},copyToClipboard:s}}function g(t=!1){return`
  /* 代码块增强：复制和折叠 */
  pre.code-block-enhanced {
    position: relative !important;
  }

  /* 复制按钮 - 悬浮叠加在右上角，不占用额外空间 */
  pre.code-block-enhanced .copy-btn {
    position: absolute !important;
    top: 6px !important;
    right: 6px !important;
    height: 28px !important;
    padding: 0 10px !important;
    border: none !important;
    background: ${t?"rgba(255,255,255,0.15)":"rgba(0,0,0,0.08)"} !important;
    color: ${t?"#ccc":"#555"} !important;
    border-radius: 4px !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 6px !important;
    transition: all 0.2s ease !important;
    z-index: 10 !important;
    font-size: 12px !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    line-height: 1 !important;
    opacity: 0 !important;
    backdrop-filter: blur(4px) !important;
  }

  pre.code-block-enhanced:hover .copy-btn {
    opacity: 1 !important;
  }

  pre.code-block-enhanced .copy-btn:hover {
    background: ${t?"rgba(64, 158, 255, 0.4)":"rgba(64, 158, 255, 0.2)"} !important;
    color: #409eff !important;
  }

  pre.code-block-enhanced .copy-btn.copied {
    background: #67c23a !important;
    color: white !important;
    opacity: 1 !important;
  }

  pre.code-block-enhanced .copy-btn svg {
    width: 14px !important;
    height: 14px !important;
    display: block !important;
    flex-shrink: 0 !important;
  }

  pre.code-block-enhanced .copy-btn span {
    display: inline !important;
  }

  /* 折叠状态的代码块 */
  pre.code-block-enhanced.collapsed {
    padding-bottom: 44px !important;
  }

  pre.code-block-enhanced.collapsed > code {
    display: block !important;
    max-height: 100px !important;
    overflow: hidden !important;
  }

  /* 折叠遮罩渐变 */
  pre.code-block-enhanced.collapsed::after {
    content: '' !important;
    position: absolute !important;
    bottom: 36px !important;
    left: 0 !important;
    right: 0 !important;
    height: 50px !important;
    background: linear-gradient(to bottom,
      transparent 0%,
      ${t?"#2d2d2d":"#f5f5f5"} 100%
    ) !important;
    pointer-events: none !important;
  }

  /* 折叠/展开按钮 */
  pre.code-block-enhanced .collapse-btn {
    position: absolute !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    height: 36px !important;
    border: none !important;
    background: ${t?"rgba(255,255,255,0.08)":"rgba(0,0,0,0.05)"} !important;
    color: ${t?"#aaa":"#666"} !important;
    border-radius: 0 0 8px 8px !important;
    cursor: pointer !important;
    display: none !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 6px !important;
    transition: all 0.2s ease !important;
    z-index: 10 !important;
    font-size: 13px !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    border-top: 1px solid ${t?"rgba(255,255,255,0.1)":"rgba(0,0,0,0.08)"} !important;
  }

  pre.code-block-enhanced .collapse-btn:hover {
    background: ${t?"rgba(64, 158, 255, 0.25)":"rgba(64, 158, 255, 0.12)"} !important;
    color: #409eff !important;
  }

  pre.code-block-enhanced .collapse-btn svg {
    width: 16px !important;
    height: 16px !important;
    display: block !important;
    flex-shrink: 0 !important;
    transition: transform 0.3s ease !important;
  }

  /* 折叠状态下箭头向下 */
  pre.code-block-enhanced.collapsed .collapse-btn svg {
    transform: rotate(0deg) !important;
  }

  /* 展开状态下箭头向上 */
  pre.code-block-enhanced:not(.collapsed) .collapse-btn svg {
    transform: rotate(180deg) !important;
  }

  /* 超过阈值的代码块显示折叠按钮 */
  pre.code-block-enhanced.long-code .collapse-btn {
    display: flex !important;
  }

  /* 展开状态的长代码块 */
  pre.code-block-enhanced.long-code:not(.collapsed) {
    padding-bottom: 40px !important;
  }

  pre.code-block-enhanced.long-code:not(.collapsed)::after {
    display: none !important;
  }
`}export{b as default,u as enhanceCodeBlocks,g as getCodeEnhancerStyles,b as useCodeEnhancer};
