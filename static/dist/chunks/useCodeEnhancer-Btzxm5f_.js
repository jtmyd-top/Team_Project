const c={copy:`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
  </svg>`,copied:`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="20 6 9 17 4 12"></polyline>
  </svg>`,expand:`<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="6 9 12 15 18 9"></polyline>
  </svg>`},l={collapseThreshold:5,defaultCollapsed:!0,copiedDuration:2e3,enhancedClass:"code-block-enhanced",longCodeClass:"long-code",collapsedClass:"collapsed"};async function s(e){if(navigator.clipboard&&navigator.clipboard.writeText)try{return await navigator.clipboard.writeText(e),!0}catch{}try{const n=document.createElement("textarea");n.value=e,n.style.position="fixed",n.style.left="-999999px",n.style.top="-999999px",document.body.appendChild(n),n.focus(),n.select();const t=document.execCommand("copy");return document.body.removeChild(n),t}catch{return!1}}function p(e){if(!e)return 0;try{const t=e.textContent.split(`
`);return t.length>1?t.length:(e.innerHTML&&e.innerHTML.match(/<br\s*\/?>/gi)||[]).length+1}catch{return 0}}function d(e,n){if(!e)return null;const t=document.createElement("button");t.className="copy-btn";try{t.innerHTML=`${c.copy}<span>复制</span>`}catch{return null}return t.setAttribute("aria-label","复制代码"),t.addEventListener("click",async o=>{o.preventDefault(),o.stopPropagation();const r=e.textContent;if(await s(r)){t.classList.add("copied");try{t.innerHTML=`${c.copied}<span>已复制</span>`}catch{}setTimeout(()=>{try{t&&t.classList&&(t.classList.remove("copied"),t.innerHTML=`${c.copy}<span>复制</span>`)}catch{}},n.copiedDuration)}}),t}function m(e,n){if(!e)return null;const t=document.createElement("button");t.className="collapse-btn";try{t.innerHTML=`${c.expand}<span>展开代码</span>`}catch{return null}return t.setAttribute("aria-label","展开代码"),t.addEventListener("click",o=>{if(o.preventDefault(),o.stopPropagation(),!e||!e.parentNode)return;e.classList.contains(n.collapsedClass)?(e.classList.remove(n.collapsedClass),t.innerHTML=`${c.expand}<span>收起代码</span>`,t.setAttribute("aria-label","收起代码")):(e.classList.add(n.collapsedClass),t.innerHTML=`${c.expand}<span>展开代码</span>`,t.setAttribute("aria-label","展开代码"))}),t}function h(e,n){if(e&&e.parentNode&&!e.classList.contains(n.enhancedClass))try{let t=e.querySelector("code");if(!t){const a=e.innerHTML;e.innerHTML=`<code>${a}</code>`,t=e.querySelector("code")}if(!t)return;if(e.classList.add("line"),!t.querySelector("span.line-content")&&!t.querySelector("br")&&!t.querySelector("div")&&!t.querySelector("p")){const a=t.innerHTML;t.innerHTML=`<span class="line-content">${a}</span>`}e.classList.add(n.enhancedClass);const r=p(t);r>n.collapseThreshold&&(e.classList.add(n.longCodeClass),n.defaultCollapsed&&e.classList.add(n.collapsedClass));const i=d(t,n);if(i&&e.parentNode&&e.appendChild(i),r>n.collapseThreshold){const a=m(e,n);a&&e.parentNode&&e.appendChild(a)}}catch{}}function u(e,n={}){if(!e)return;const t={...l,...n};try{const o=e.querySelectorAll("pre");if(!o)return;o.forEach(r=>{try{h(r,t)}catch{}})}catch{}}function b(e={}){const n={...l,...e};return{enhance:(o,r={})=>{u(o,{...n,...r})},copyToClipboard:s}}function g(e=!1){return`
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
    background: ${e?"rgba(255,255,255,0.15)":"rgba(0,0,0,0.08)"} !important;
    color: ${e?"#ccc":"#555"} !important;
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
    background: ${e?"rgba(64, 158, 255, 0.4)":"rgba(64, 158, 255, 0.2)"} !important;
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
      ${e?"#2d2d2d":"#f5f5f5"} 100%
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
    background: ${e?"rgba(255,255,255,0.08)":"rgba(0,0,0,0.05)"} !important;
    color: ${e?"#aaa":"#666"} !important;
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
    border-top: 1px solid ${e?"rgba(255,255,255,0.1)":"rgba(0,0,0,0.08)"} !important;
  }

  pre.code-block-enhanced .collapse-btn:hover {
    background: ${e?"rgba(64, 158, 255, 0.25)":"rgba(64, 158, 255, 0.12)"} !important;
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
