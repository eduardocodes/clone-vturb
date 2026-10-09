import type { Video } from '../types/video'

interface EmbedCodeOptions {
  video: Video
  embedUrl: string
  embedType: 'iframe' | 'script'
  resolvedWidth: string
  resolvedHeight: string | null
  heightPreset: string
  paddingTopMap: Record<string, string>
  transparentBg?: boolean
}

/** Cookie de onde o script de embed lê o xid. Nome fora do padrão (ou ausente) cai no `_eid`. */
export const DEFAULT_XID_COOKIE = '_eid'
export function resolveXidCookieName(value: unknown): string {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(value) ? value : DEFAULT_XID_COOKIE
}

export function generateEmbedCode({
  video,
  embedUrl,
  embedType,
  resolvedWidth,
  resolvedHeight,
  heightPreset,
  paddingTopMap,
  transparentBg,
}: EmbedCodeOptions): string {
  const isFloatingEnabled = Boolean(video.player_settings?.floating_player?.enabled)
  const floatingPos = video.player_settings?.floating_player?.position || 'bottom-right'
  const floatingWidth = Number(video.player_settings?.floating_player?.width) || 320
  const isCloseable = video.player_settings?.floating_player?.closeable !== false
  const xidCookie = resolveXidCookieName(video.player_settings?.external_id_cookie)

  const listenerScript = `
<script>
(function() {
  var videoId = '${video.id}';
  var videoRatio = '${heightPreset}';
  var isFloatingConfig = ${isFloatingEnabled ? 'true' : 'false'};
  var floatingPos = '${floatingPos}';
  var floatingWidth = ${floatingWidth};
  var isCloseable = ${isCloseable ? 'true' : 'false'};
  var xidCookie = '${xidCookie}';

  var isFloatingDismissed = false;
  var isVideoPlaying = false;
  var isIntersecting = true;

  window.addEventListener('message', function(e) {
    if (!e.data) return;
    if (e.data.type === 'VTURB_PLAY_STATE') {
      isVideoPlaying = Boolean(e.data.isPlaying);
      updateFloatingState();
    }
    if (e.data.type === 'VTURB_PITCH_REACHED') {
      var sel = e.data.targetSelector || '.delay-pitch';
      document.querySelectorAll(sel).forEach(function(el) { el.style.display = 'block'; });
      if (e.data.autoScroll) {
        var first = document.querySelector(sel);
        if (first) {
          var top = first.getBoundingClientRect().top + window.pageYOffset - (e.data.scrollOffset || 50);
          window.scrollTo({ top: top, behavior: 'smooth' });
        }
      }
      if (e.data.persistence && e.data.videoId) {
        try { localStorage.setItem('vturb_pitch_' + e.data.videoId, '1'); } catch(err) {}
      }
    }
    if (e.data.type === 'VTURB_PIXEL_TRACK') {
      var evt = e.data.eventName;
      if (typeof window.fbq === 'function') window.fbq('trackCustom', evt, { video_id: e.data.videoId });
      if (typeof window.gtag === 'function') window.gtag('event', evt, { video_id: e.data.videoId });
      if (window.ttq && typeof window.ttq.track === 'function') window.ttq.track(evt, { video_id: e.data.videoId });
    }
  });

  // Inicialização autônoma de Pixels de Rastreamento (Facebook, Google, TikTok) se configurados
  var trackingConfig = ${JSON.stringify(video.player_settings?.tracking_pixels || {})};
  if (trackingConfig && trackingConfig.enabled) {
    if (trackingConfig.facebook_pixel_id && !window.fbq) {
      (function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)})(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
      window.fbq('init', trackingConfig.facebook_pixel_id);
      window.fbq('track', 'PageView');
    }
    if (trackingConfig.google_analytics_id && !window.gtag) {
      var gs = document.createElement('script'); gs.async = true; gs.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(trackingConfig.google_analytics_id); document.head.appendChild(gs);
      window.dataLayer = window.dataLayer || [];
      window.gtag = function(){window.dataLayer.push(arguments);};
      window.gtag('js', new Date());
      window.gtag('config', trackingConfig.google_analytics_id);
    }
    if (trackingConfig.tiktok_pixel_id && !window.ttq) {
      (function(w,d,t){w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];ttq.methods=["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie"];ttq.setAndDefer=function(t,e){t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}};for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);ttq.instance=function(t){for(var e=ttq._i[t]||[],n=0;n<ttq.methods.length;n++)ttq.setAndDefer(e,ttq.methods[n]);return e};ttq.load=function(e,n){var i="https://analytics.tiktok.com/i18n/pixel/events.js";ttq._i=ttq._i||{};ttq._i[e]=[];ttq._i[e]._u=i;ttq._t=ttq._t||{};ttq._t[e]=+new Date;ttq._o=ttq._o||{};ttq._o[e]=n||{};var o=document.createElement("script");o.type="text/javascript";o.async=!0;o.src=i+"?sdkid="+e+"&lib="+t;var a=document.getElementsByTagName("script")[0];a.parentNode.insertBefore(o,a)};ttq.load(trackingConfig.tiktok_pixel_id);ttq.page();})(window,document,'ttq');
    }
  }

  // Listener para desbloquear áudio de imediato na menor interação
  var unlocked = false;
  function notifyIframe() {
    if (unlocked) return;
    unlocked = true;
    var ifr = document.querySelector('iframe[src*="' + videoId + '"]');
    if (ifr && ifr.contentWindow) {
      try { ifr.contentWindow.postMessage({ type: 'VTURB_PARENT_INTERACTION' }, '*'); } catch(e) {}
    }
  }
  ['click', 'touchstart', 'scroll', 'keydown'].forEach(function(evt) {
    window.addEventListener(evt, notifyIframe, { once: true, passive: true });
  });

  function readCookie(name) {
    var parts = document.cookie ? document.cookie.split(';') : [];
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i].trim();
      if (part.indexOf(name + '=') === 0) {
        var raw = part.substring(name.length + 1);
        try { return decodeURIComponent(raw); } catch(e) { return raw; }
      }
    }
    return '';
  }

  function resolveXid() {
    var candidates = [];
    var box = document.getElementById('vturb-player-' + videoId) || document.getElementById('vturb-wrapper-' + videoId);
    if (box) candidates.push(box.getAttribute('data-xid'));
    if (window.SmartVSL) candidates.push(window.SmartVSL.xid);
    candidates.push(readCookie(xidCookie));
    for (var i = 0; i < candidates.length; i++) {
      var c = candidates[i];
      if (typeof c === 'string' && c) return /^[A-Za-z0-9_-]{1,100}$/.test(c) ? c : '';
    }
    return '';
  }

  // Sincronização de ID de visitante 1st-party (evita duplicação no Safari iOS / Instagram Ads)
  try {
    var parentSid = localStorage.getItem('vturb_visitor_id');
    if (!parentSid) {
      parentSid = 'vis_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now().toString(36);
      localStorage.setItem('vturb_visitor_id', parentSid);
    }
    var ifrSid = document.querySelector('iframe[src*="' + videoId + '"]');
    if (ifrSid && ifrSid.src) {
      var srcParams = {};
      try { new URL(ifrSid.src).searchParams.forEach(function(v, k) { srcParams[k] = true; }); } catch(e) {}
      var extra = [];
      if (!srcParams.sid) extra.push('sid=' + encodeURIComponent(parentSid));
      // Origem do espectador: xid (data-xid > window.SmartVSL.xid > cookie) e utm_* da LP
      var xid = resolveXid();
      if (xid && !srcParams.xid) extra.push('xid=' + encodeURIComponent(xid));
      try {
        var lpParams = new URLSearchParams(window.location.search);
        ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'].forEach(function(k) {
          var v = lpParams.get(k);
          if (v && !srcParams[k]) extra.push(k + '=' + encodeURIComponent(v));
        });
      } catch(e) {}
      if (extra.length) {
        ifrSid.src = ifrSid.src + (ifrSid.src.indexOf('?') !== -1 ? '&' : '?') + extra.join('&');
      }
    }
  } catch(err) {}

  try {
    if (localStorage.getItem('vturb_pitch_' + videoId) === '1') {
      var sel = '${video.player_settings?.pitch_delay?.target_css_selector || '.delay-pitch'}';
      document.querySelectorAll(sel).forEach(function(el) { el.style.display = 'block'; });
    }
  } catch(err) {}

  // Lógica do Player Flutuante e Visibilidade Real na Tela
  function setupFloatingObserver() {
    var wrapper = document.getElementById('vturb-wrapper-' + videoId);
    var ifr = document.querySelector('iframe[src*="' + videoId + '"]');
    if (wrapper && ifr && 'IntersectionObserver' in window) {
      var visObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          if (entry.isIntersecting && ifr.contentWindow) {
            try { ifr.contentWindow.postMessage({ type: 'VTURB_VISIBILITY', visible: true }, '*'); } catch(e) {}
          }
        });
      }, { threshold: 0.05 });
      visObserver.observe(wrapper);
    }
    if (!isFloatingConfig || !wrapper || !ifr) return;

    // Cria botão de fechar flutuante se não existir
    var closeBtn = document.getElementById('vturb-close-floating-' + videoId);
    if (!closeBtn && isCloseable) {
      closeBtn = document.createElement('button');
      closeBtn.id = 'vturb-close-floating-' + videoId;
      closeBtn.innerHTML = '&#x2715;';
      closeBtn.title = 'Fechar mini player';
      closeBtn.style.position = 'fixed';
      closeBtn.style.zIndex = '100000';
      closeBtn.style.width = '28px';
      closeBtn.style.height = '28px';
      closeBtn.style.borderRadius = '50%';
      closeBtn.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
      closeBtn.style.border = '1px solid rgba(255, 255, 255, 0.3)';
      closeBtn.style.color = '#ffffff';
      closeBtn.style.cursor = 'pointer';
      closeBtn.style.display = 'none';
      closeBtn.style.alignItems = 'center';
      closeBtn.style.justifyContent = 'center';
      closeBtn.style.fontSize = '14px';
      closeBtn.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.4)';
      closeBtn.onclick = function(ev) {
        ev.stopPropagation();
        isFloatingDismissed = true;
        window.updateFloatingState(false);
        try {
          if (ifr && ifr.contentWindow) {
            ifr.contentWindow.postMessage({ type: 'VTURB_COMMAND', action: 'pause' }, '*');
          }
        } catch(err) {}
      };
      document.body.appendChild(closeBtn);
    }

    var isCurrentlyFloating = false;

    window.updateFloatingState = function(forceState) {
      if (!wrapper || !ifr) return;
      var shouldFloat = (typeof forceState === 'boolean' ? forceState : isCurrentlyFloating) && isFloatingConfig && !isFloatingDismissed;
      isCurrentlyFloating = shouldFloat;

      if (shouldFloat) {
        var isVertical = videoRatio === '9:16';
        var actualWidth = isVertical ? Math.min(floatingWidth, 250) : floatingWidth;
        var floatHeight = isVertical ? Math.round((actualWidth * 16) / 9) : Math.round((actualWidth * 9) / 16);
        var marginEdge = 32;
        var marginEdgeRight = 56;
        ifr.style.position = 'fixed';
        ifr.style.top = 'auto';
        ifr.style.bottom = marginEdge + 'px';
        if (floatingPos === 'bottom-left') {
          ifr.style.left = marginEdge + 'px';
          ifr.style.right = 'auto';
        } else {
          ifr.style.right = marginEdgeRight + 'px';
          ifr.style.left = 'auto';
        }
        ifr.style.width = actualWidth + 'px';
        ifr.style.height = floatHeight + 'px';
        ifr.style.zIndex = '99999';
        ifr.style.backgroundColor = '#000000';
        ifr.style.borderRadius = '12px';
        ifr.style.boxShadow = '0 12px 35px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.15)';
        ifr.style.transition = 'box-shadow 0.2s ease, border-radius 0.2s ease';

        if (closeBtn) {
          closeBtn.style.display = 'flex';
          closeBtn.style.top = 'auto';
          closeBtn.style.bottom = (marginEdge + floatHeight - 14) + 'px';
          if (floatingPos === 'bottom-left') {
            closeBtn.style.left = (marginEdge + actualWidth - 14) + 'px';
            closeBtn.style.right = 'auto';
          } else {
            closeBtn.style.right = (marginEdgeRight - 12) + 'px';
            closeBtn.style.left = 'auto';
          }
        }
      } else {
        ifr.style.transition = 'none';
        ifr.style.position = 'absolute';
        ifr.style.top = '0';
        ifr.style.left = '0';
        ifr.style.right = 'auto';
        ifr.style.bottom = 'auto';
        ifr.style.width = '100%';
        ifr.style.height = '100%';
        ifr.style.zIndex = '1';
        ifr.style.borderRadius = '${video.player_settings?.border_radius ?? 0}px';
        ifr.style.boxShadow = 'none';

        if (closeBtn) {
          closeBtn.style.display = 'none';
        }
      }
    };

    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          var rect = entry.boundingClientRect;
          var pastTop = rect.bottom < 80;
          if (!pastTop || entry.intersectionRatio > 0.35) {
            isFloatingDismissed = false;
          }
          if (!isCurrentlyFloating) {
            if (pastTop && entry.intersectionRatio < 0.15) {
              window.updateFloatingState(true);
            }
          } else {
            if (!pastTop || entry.intersectionRatio > 0.35) {
              window.updateFloatingState(false);
            }
          }
        });
      }, { threshold: [0, 0.1, 0.2, 0.35, 0.5] });
      observer.observe(wrapper);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupFloatingObserver);
  } else {
    setupFloatingObserver();
  }
})();
</script>`

  const isTransparent = Boolean(transparentBg ?? video.player_settings?.transparent_background)
  let finalEmbedUrl = embedUrl
  if (!finalEmbedUrl.includes('transparent=')) {
    finalEmbedUrl += (finalEmbedUrl.includes('?') ? '&' : '?') + (isTransparent ? 'transparent=1' : 'transparent=0')
  }
  const bgStyle = isTransparent ? 'background:transparent;' : 'background:#000000;'
  const allowTransp = isTransparent ? ' allowtransparency="true"' : ''

  let iframeInner = ''
  let scriptInner = ''

  if (heightPreset === 'custom' && resolvedHeight) {
    iframeInner = `<div id="vturb-wrapper-${video.id}" style="max-width:${resolvedWidth};width:100%;height:${resolvedHeight};margin:0 auto;position:relative;${bgStyle}">
  <iframe src="${finalEmbedUrl}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;border-radius:${video.player_settings?.border_radius ?? 0}px;${bgStyle}" allow="autoplay *; fullscreen *; encrypted-media *" allowfullscreen${allowTransp}></iframe>
</div>`
    scriptInner = `<div id="vturb-player-${video.id}" style="max-width:${resolvedWidth};width:100%;height:${resolvedHeight};margin:0 auto;position:relative;${bgStyle}">
  <div id="vturb-wrapper-${video.id}" style="width:100%;height:100%;position:relative;${bgStyle}">
    <iframe src="${finalEmbedUrl}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;border-radius:${video.player_settings?.border_radius ?? 0}px;${bgStyle}" allow="autoplay *; fullscreen *; encrypted-media *"${allowTransp}></iframe>
  </div>
</div>`
  } else {
    const pTop = paddingTopMap[heightPreset] || '56.25%'
    iframeInner = `<div id="vturb-wrapper-${video.id}" style="max-width:${resolvedWidth};width:100%;margin:0 auto;${bgStyle}">
  <div style="position:relative;width:100%;padding-top:${pTop};${bgStyle}">
    <iframe src="${finalEmbedUrl}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;border-radius:${video.player_settings?.border_radius ?? 0}px;${bgStyle}" allow="autoplay *; fullscreen *; encrypted-media *" allowfullscreen${allowTransp}></iframe>
  </div>
</div>`
    scriptInner = `<div id="vturb-player-${video.id}" style="max-width:${resolvedWidth};width:100%;margin:0 auto;${bgStyle}">
  <div id="vturb-wrapper-${video.id}" style="position:relative;width:100%;padding-top:${pTop};${bgStyle}">
    <iframe src="${finalEmbedUrl}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;border-radius:${video.player_settings?.border_radius ?? 0}px;${bgStyle}" allow="autoplay *; fullscreen *; encrypted-media *"${allowTransp}></iframe>
  </div>
</div>`
  }

  return (embedType === 'iframe' ? iframeInner : scriptInner) + listenerScript
}
