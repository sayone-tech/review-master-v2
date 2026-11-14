/* Ported from the approved prototype (option A, "The book"). Kept as a style
   string rendered by the widget so the 3D leaf rules ship with the island
   without a separate stylesheet link in the page template. */
export const BOOK_CSS = `
.ib { --ib-y:#FACC15; --ib-k:#0A0A0A; --ib-paper:#151515; --ib-paper2:#1B1B1B; --ib-t1:#FAFAFA; --ib-t2:#A1A1AA; --ib-t3:#8B8B94; --ib-neg:#F87171;
  font-family:"Geist",-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif; color:var(--ib-t1); text-align:left; }
.ib *, .ib *::before, .ib *::after { box-sizing:border-box; }
.ib p, .ib h2, .ib h3 { margin:0; }
.ib-stage { background:var(--ib-k); border-radius:12px; padding:30px 16px 18px; border:1px solid #1f1f1f; display:flex; flex-direction:column; align-items:center; gap:18px; min-height:520px; justify-content:center; }
.ib-ctrl { display:flex; align-items:center; gap:14px; font-size:12.5px; color:var(--ib-t2); }
.ib-pos { min-width:104px; text-align:center; font-variant-numeric:tabular-nums; }
.ib-nb { width:38px; height:38px; border-radius:50%; border:1px solid #333; background:#161616; color:#fff; display:inline-flex; align-items:center; justify-content:center; cursor:pointer; padding:0; }
.ib-nb:hover:not(:disabled), .ib-nb:focus-visible { border-color:var(--ib-y); color:var(--ib-y); outline:none; }
.ib-nb:focus-visible { box-shadow:0 0 0 2px var(--ib-k), 0 0 0 4px var(--ib-y); }
.ib-nb:disabled { opacity:.35; cursor:default; }

.ib-book { position:relative; width:min(820px, calc(100% - 34px)); margin-right:34px; aspect-ratio:820/420; min-height:360px; perspective:2400px; touch-action:pan-y; user-select:none; -webkit-user-select:none; cursor:grab; outline:none; }
.ib-book:active { cursor:grabbing; }
.ib-book::before { content:""; position:absolute; inset:-10px -12px -14px; background:#060606; border-radius:14px; box-shadow:0 30px 60px rgba(0,0,0,.6); }
.ib-book:focus-visible::before { box-shadow:0 0 0 2px var(--ib-y), 0 30px 60px rgba(0,0,0,.6); }
.ib-bed { position:absolute; top:0; bottom:0; background:var(--ib-paper); }
.ib-bed-left { left:0; width:50%; border-radius:10px 0 0 10px; }
.ib-bed-right { right:0; width:50%; border-radius:0 10px 10px 0; }
.ib-spine { position:absolute; left:50%; top:0; bottom:0; width:2px; transform:translateX(-1px); background:#000; z-index:500; box-shadow:0 0 18px 6px rgba(0,0,0,.55); pointer-events:none; }

.ib-leaf { position:absolute; left:50%; top:0; width:50%; height:100%; transform-origin:left center; transform-style:preserve-3d; }
.ib-leaf.ib-anim { transition:transform .9s cubic-bezier(.3,.1,.2,1); }
.ib-leaf.ib-turned { transform:rotateY(-180deg); }
.ib-face { position:absolute; inset:0; backface-visibility:hidden; -webkit-backface-visibility:hidden; padding:30px 34px 26px; display:flex; flex-direction:column; background:var(--ib-paper); overflow:hidden; cursor:auto; }
.ib-front { border-radius:0 10px 10px 0; background:linear-gradient(90deg,#101010 0,var(--ib-paper) 7%,var(--ib-paper) 100%); }
.ib-back { transform:rotateY(180deg); border-radius:10px 0 0 10px; background:linear-gradient(270deg,#101010 0,var(--ib-paper2) 7%,var(--ib-paper2) 100%); align-items:center; justify-content:center; }
.ib-cover { background:var(--ib-y); color:var(--ib-k); justify-content:space-between; }

/* Phones: one full-width page per step, turned away around the left edge. */
.ib-narrow .ib-book { aspect-ratio:4/5; min-height:400px; }
.ib-narrow .ib-bed { left:0; right:0; width:100%; border-radius:10px; }
.ib-narrow .ib-leaf { left:0; width:100%; }
.ib-narrow .ib-face { border-radius:10px; padding:26px 22px 22px; }
.ib-narrow .ib-face.ib-solo-visual { background:var(--ib-paper2); align-items:center; justify-content:center; }

.ib-cover-top { font-size:12.5px; font-weight:600; }
.ib-cover-title { font-size:40px; font-weight:800; letter-spacing:-0.035em; line-height:1; color:var(--ib-k); }
.ib-cover-lede { margin-top:14px !important; font-size:14.5px; font-weight:500; line-height:1.45; max-width:30ch; }
.ib-cover-foot { display:flex; justify-content:space-between; gap:12px; font-size:12.5px; font-weight:600; }

.ib-chap { font-size:12px; font-weight:600; display:inline-flex; gap:6px; align-items:center; }
.ib-title { margin:12px 0 10px !important; font-size:25px; font-weight:700; letter-spacing:-0.025em; line-height:1.18; color:#fff; text-wrap:balance; }
.ib-body { font-size:13.5px; color:var(--ib-t2); line-height:1.6; max-width:46ch; }
.ib-cta-row { margin-top:18px; }
.ib-cta { background:var(--ib-y); color:var(--ib-k); border-radius:9px; padding:9px 15px; font-size:13px; font-weight:600; display:inline-block; text-decoration:none; }
.ib-cta:hover { background:#EAB308; }
.ib-cta:focus-visible { outline:2px solid #fff; outline-offset:3px; }
.ib-pgno { margin-top:auto; display:flex; justify-content:space-between; align-items:center; font-size:11.5px; color:var(--ib-t3); font-variant-numeric:tabular-nums; }

.ib-bigvis { width:100%; display:flex; flex-direction:column; align-items:center; gap:14px; }
.ib-headline { font-size:56px; font-weight:800; letter-spacing:-0.04em; line-height:1; font-variant-numeric:tabular-nums; }
.ib-caption { font-size:12px; color:var(--ib-t2); text-align:center; max-width:34ch; }
.ib-end { text-align:center; display:flex; flex-direction:column; align-items:center; gap:8px; }
.ib-end-title { font-size:22px; font-weight:700; color:#fff; }

.ib-tabs { position:absolute; right:-30px; top:34px; display:flex; flex-direction:column; gap:10px; z-index:0; }
.ib-tab { width:30px; padding:14px 0; border-radius:0 8px 8px 0; writing-mode:vertical-rl; font:inherit; font-size:11px; font-weight:600; letter-spacing:.01em; text-align:center; cursor:pointer; border:1px solid #2a2a2a; border-left:0; transition:transform .25s, background .25s, color .25s; }
.ib-tab-attention { background:#1d1414; color:#c27272; }
.ib-tab-good { background:#1d1a0e; color:#b39a3a; }
.ib-tab-attention.ib-on { background:#F87171; color:#0A0A0A; transform:translateX(4px); border-color:#F87171; }
.ib-tab-good.ib-on { background:#FACC15; color:#0A0A0A; transform:translateX(4px); border-color:#FACC15; }
.ib-tab:focus-visible { outline:2px solid #fff; outline-offset:2px; }

.ib-empty { width:min(520px, 100%); background:var(--ib-paper); border-radius:10px; padding:40px 34px; text-align:center; display:flex; flex-direction:column; gap:10px; align-items:center; }
.ib-empty-title { font-size:22px; font-weight:700; color:#fff; letter-spacing:-0.02em; text-wrap:balance; }
.ib-skeleton { background:var(--ib-paper); border-radius:10px; animation:sk-pulse 1.6s ease-in-out infinite; }

@media (prefers-reduced-motion: reduce) {
  .ib-leaf, .ib-leaf.ib-anim, .ib-tab, .ib-skeleton { transition:none; animation:none; }
}
`;
