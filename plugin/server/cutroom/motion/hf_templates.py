"""Built-in HTML motion-graphics templates (Hyperframes compositions: GSAP timeline registered on window.__timelines).

Every template is resolution-independent: sizes are expressed in `u` = min(w, h) / 1080, so the same template looks
right in 16:9, 9:16 and 1:1. Templates return (html, default_duration_s, transparent).
"""
import html
import json

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,600;9..144,800&'
         'family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=block" rel="stylesheet">')
GSAP = '<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>'

PALETTE = {
    "ink": "#0b0d10", "paper": "#f3efe6", "accent": "#e8b04a", "accent2": "#5fb3a1", "muted": "#9aa3ad",
}


def e(s):
    return html.escape(str(s or ""))


def page(w, h, duration, body, css, js, transparent=False, accent=None):
    u = min(w, h) / 1080
    pal = dict(PALETTE)
    if accent:
        pal["accent"] = accent
    bg = "transparent" if transparent else pal["ink"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width={w}, height={h}" />
{FONTS}{GSAP}
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:{bg}}}
:root{{--u:{u:.5f};--ink:{pal['ink']};--paper:{pal['paper']};--accent:{pal['accent']};--accent2:{pal['accent2']};--muted:{pal['muted']}}}
#root{{position:relative;width:{w}px;height:{h}px;overflow:hidden;font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:var(--paper)}}
.serif{{font-family:Fraunces,Georgia,serif}}
.mono{{font-family:'JetBrains Mono',ui-monospace,monospace}}
{css}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{duration}" data-width="{w}" data-height="{h}">
{body}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const U = {u:.5f}, W = {w}, H = {h}, D = {duration};
const tl = gsap.timeline({{ paused: true }});
{js}
tl.to({{}}, {{ duration: 0.001 }}, D - 0.001);
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body></html>"""


BACKDROP_CSS = """
.bg{position:absolute;inset:0;background:
  radial-gradient(120% 90% at 20% 10%, rgba(232,176,74,.16), transparent 55%),
  radial-gradient(90% 80% at 85% 90%, rgba(95,179,161,.14), transparent 60%),
  linear-gradient(160deg,#0e1116 0%,#07080a 100%)}
.grain{position:absolute;inset:-50%;opacity:.07;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")}
.sweep{position:absolute;top:-20%;bottom:-20%;width:35%;left:-40%;background:linear-gradient(100deg,transparent,rgba(255,240,210,.10),transparent);transform:skewX(-12deg)}
.vignette{position:absolute;inset:0;background:radial-gradient(ellipse at center,transparent 55%,rgba(0,0,0,.55) 100%)}
"""
BACKDROP = '<div class="bg"></div><div class="grain" id="grain"></div><div class="sweep" id="sweep"></div><div class="vignette"></div>'
BACKDROP_JS = """
tl.fromTo('#sweep', {xPercent:0}, {xPercent: 520, duration: D*0.9, ease:'power1.inOut'}, 0.2);
tl.fromTo('#grain', {x:0,y:0}, {x:40*U, y:-30*U, duration:D, ease:'none'}, 0);
"""


def title_card(p, w, h):
    title = p.get("title", "Untitled")
    words = "".join(f'<span class="wmask"><span class="w">{e(wd)}</span></span>' for wd in str(title).split())
    kicker = e(p.get("kicker", ""))
    sub = e(p.get("subtitle", ""))
    portrait = h > w
    css = BACKDROP_CSS + f"""
.wrap{{position:absolute;left:calc(var(--u)*{90 if portrait else 140}px);right:calc(var(--u)*{90 if portrait else 140}px);top:50%;transform:translateY(-50%)}}
.kicker{{font-size:calc(var(--u)*26px);letter-spacing:.32em;text-transform:uppercase;color:var(--accent);font-weight:600;margin-bottom:calc(var(--u)*34px);display:flex;align-items:center;gap:calc(var(--u)*18px)}}
.kicker .tick{{width:calc(var(--u)*56px);height:calc(var(--u)*2px);background:var(--accent);transform-origin:left}}
.title{{font-size:calc(var(--u)*{104 if portrait else 128}px);line-height:1.02;font-weight:600;letter-spacing:-.025em}}
.wmask{{display:inline-block;overflow:hidden;vertical-align:top;padding-bottom:.08em;margin-right:.18em}}
.w{{display:inline-block}}
.rule{{height:calc(var(--u)*2px);background:linear-gradient(90deg,var(--paper),transparent);opacity:.5;margin:calc(var(--u)*44px) 0 calc(var(--u)*30px);transform-origin:left}}
.sub{{font-size:calc(var(--u)*36px);color:var(--muted);font-weight:400;max-width:calc(var(--u)*1300px);line-height:1.35}}
"""
    body = BACKDROP + f"""<div class="wrap" id="wrap">
<div class="kicker" id="kicker"><span class="tick"></span><span>{kicker}</span></div>
<div class="title serif">{words}</div>
<div class="rule" id="rule"></div>
<div class="sub" id="sub">{sub}</div></div>"""
    js = BACKDROP_JS + """
tl.from('#wrap', {scale:1.04, duration:D, ease:'none'}, 0);
tl.from('#kicker .tick', {scaleX:0, duration:.7, ease:'power3.out'}, .15);
tl.from('#kicker span:last-child', {opacity:0, x:-14*U, duration:.6, ease:'power3.out'}, .3);
tl.from('.w', {yPercent:110, rotate:4, duration:1.0, ease:'expo.out', stagger:.08}, .35);
tl.from('#rule', {scaleX:0, duration:1.1, ease:'power3.inOut'}, .9);
tl.from('#sub', {opacity:0, y:18*U, filter:'blur(6px)', duration:.9, ease:'power3.out'}, 1.15);
tl.to('#wrap', {opacity:0, y:-12*U, filter:'blur(4px)', duration:.55, ease:'power2.in'}, D-.6);
"""
    return css, body, js, float(p.get("duration", 4.5)), bool(p.get("transparent", False))


def lower_third(p, w, h):
    portrait = h > w
    css = f"""
.lt{{position:absolute;left:calc(var(--u)*{70 if portrait else 110}px);bottom:{'22%' if portrait else 'calc(var(--u)*120px)'};display:flex;align-items:stretch;gap:calc(var(--u)*22px)}}
.bar{{width:calc(var(--u)*7px);background:var(--accent);border-radius:calc(var(--u)*4px);transform-origin:bottom;box-shadow:0 0 calc(var(--u)*24px) rgba(232,176,74,.6)}}
.card{{position:relative;padding:calc(var(--u)*18px) calc(var(--u)*34px) calc(var(--u)*20px) calc(var(--u)*26px);overflow:hidden}}
.plate{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(8,10,13,.82),rgba(8,10,13,.55));backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.08);border-radius:calc(var(--u)*10px);transform-origin:left}}
.name{{position:relative;font-size:calc(var(--u)*52px);font-weight:700;letter-spacing:-.01em;white-space:nowrap}}
.role{{position:relative;font-size:calc(var(--u)*24px);letter-spacing:.22em;text-transform:uppercase;color:var(--accent);margin-top:calc(var(--u)*8px);font-weight:600;white-space:nowrap}}
"""
    body = f"""<div class="lt" id="lt"><div class="bar" id="bar"></div><div class="card"><div class="plate" id="plate"></div>
<div class="name" id="name">{e(p.get('name', ''))}</div><div class="role" id="role">{e(p.get('role', ''))}</div></div></div>"""
    js = """
tl.from('#bar', {scaleY:0, duration:.5, ease:'power3.out'}, .1);
tl.from('#plate', {scaleX:0, duration:.7, ease:'expo.out'}, .25);
tl.from('#name', {x:-30*U, opacity:0, duration:.7, ease:'power3.out'}, .45);
tl.from('#role', {x:-20*U, opacity:0, duration:.7, ease:'power3.out'}, .6);
tl.to('#lt', {x:-40*U, opacity:0, duration:.5, ease:'power2.in'}, D-.6);
"""
    return css, body, js, float(p.get("duration", 4.5)), bool(p.get("transparent", True))


def data_callout(p, w, h):
    portrait = h > w
    value = float(p.get("value", 0))
    decimals = int(p.get("decimals", 0 if value == int(value) else 1))
    bars = p.get("bars") or []
    mx = max([float(b.get("value", 0)) for b in bars] + [1e-9])
    bar_html = "".join(
        f'<div class="row"><div class="bl">{e(b.get("label"))}</div><div class="track"><div class="fill" data-v="{float(b.get("value", 0)) / mx:.4f}"></div></div>'
        f'<div class="bv mono" data-to="{float(b.get("value", 0))}">0</div></div>' for b in bars)
    css = BACKDROP_CSS + f"""
.wrap{{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);display:flex;flex-direction:{'column' if portrait else 'row'};align-items:{'flex-start' if portrait else 'center'};justify-content:center;gap:calc(var(--u)*{70 if portrait else 120}px);padding:0 calc(var(--u)*{90 if portrait else 150}px)}}
.left{{flex:{'0' if portrait else '1.1'}}}
.eyebrow{{font-size:calc(var(--u)*24px);letter-spacing:.3em;text-transform:uppercase;color:var(--accent2);font-weight:600}}
.big{{font-size:calc(var(--u)*{190 if portrait else 220}px);font-weight:800;line-height:1;letter-spacing:-.04em;margin:calc(var(--u)*20px) 0;background:linear-gradient(180deg,#fff, #d9cfbd);-webkit-background-clip:text;color:transparent}}
.label{{font-size:calc(var(--u)*36px);color:var(--muted);max-width:calc(var(--u)*760px);line-height:1.35}}
.right{{flex:1;width:100%;display:flex;flex-direction:column;gap:calc(var(--u)*26px)}}
.row{{display:grid;grid-template-columns:calc(var(--u)*230px) 1fr calc(var(--u)*150px);align-items:center;gap:calc(var(--u)*20px)}}
.bl{{font-size:calc(var(--u)*26px);color:var(--paper);opacity:.85;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.track{{height:calc(var(--u)*22px);background:rgba(255,255,255,.07);border-radius:99px;overflow:hidden}}
.fill{{height:100%;width:100%;border-radius:99px;background:linear-gradient(90deg,var(--accent2),var(--accent));transform-origin:left;transform:scaleX(0)}}
.bv{{font-size:calc(var(--u)*28px);text-align:right;color:var(--paper)}}
"""
    body = BACKDROP + f"""<div class="wrap"><div class="left" id="left"><div class="eyebrow">{e(p.get('title', ''))}</div>
<div class="big"><span>{e(p.get('prefix', ''))}</span><span id="num">0</span><span>{e(p.get('suffix', ''))}</span></div>
<div class="label">{e(p.get('label', ''))}</div></div>
<div class="right" id="right">{bar_html}</div></div>"""
    js = BACKDROP_JS + f"""
const fmt = (v, d) => Number(v).toLocaleString('en-US', {{minimumFractionDigits:d, maximumFractionDigits:d}});
const counter = {{v:0}};
tl.from('#left', {{opacity:0, y:30*U, duration:.8, ease:'power3.out'}}, .1);
tl.to(counter, {{v:{value}, duration:1.8, ease:'expo.out', onUpdate:()=>{{document.getElementById('num').textContent = fmt(counter.v, {decimals});}}}}, .3);
document.querySelectorAll('.row').forEach((r, i) => {{
  const f = r.querySelector('.fill'), bv = r.querySelector('.bv'), o = {{v:0}}, to = parseFloat(bv.dataset.to);
  const dec = to === Math.round(to) ? 0 : 1;
  tl.from(r, {{opacity:0, x:30*U, duration:.6, ease:'power3.out'}}, .6 + i*.12);
  tl.to(f, {{scaleX: parseFloat(f.dataset.v), duration:1.3, ease:'expo.out'}}, .75 + i*.12);
  tl.to(o, {{v: to, duration:1.3, ease:'expo.out', onUpdate:()=>{{ bv.textContent = fmt(o.v, dec); }}}}, .75 + i*.12);
}});
tl.to('.wrap', {{opacity:0, duration:.5, ease:'power2.in'}}, D-.55);
"""
    return css, body, js, float(p.get("duration", 5.5)), bool(p.get("transparent", False))


def kinetic_quote(p, w, h):
    portrait = h > w
    quote = str(p.get("quote", ""))
    emph = {x.lower().strip(".,;:!?\"'") for x in (p.get("emphasis") or [])}
    words = []
    for wd in quote.split():
        cls = "kw em" if wd.lower().strip(".,;:!?\"'") in emph else "kw"
        words.append(f'<span class="{cls}">{e(wd)}</span>')
    n = max(1, len(words))
    css = BACKDROP_CSS + f"""
.wrap{{position:absolute;left:calc(var(--u)*{90 if portrait else 170}px);right:calc(var(--u)*{90 if portrait else 170}px);top:50%;transform:translateY(-50%)}}
.mark{{font-size:calc(var(--u)*220px);line-height:.6;color:var(--accent);opacity:.9;height:calc(var(--u)*110px)}}
.q{{font-size:calc(var(--u)*{70 if portrait else 78}px);line-height:1.22;font-weight:300;letter-spacing:-.01em}}
.kw{{display:inline-block;margin-right:.24em}}
.em{{font-weight:800;font-style:italic;color:var(--accent)}}
.who{{margin-top:calc(var(--u)*44px);font-size:calc(var(--u)*28px);letter-spacing:.24em;text-transform:uppercase;color:var(--muted)}}
"""
    body = BACKDROP + f"""<div class="wrap" id="wrap"><div class="mark serif" id="mark">&ldquo;</div>
<div class="q serif">{''.join(words)}</div><div class="who" id="who">{('— ' + e(p.get('author'))) if p.get('author') else ''}</div></div>"""
    js = BACKDROP_JS + f"""
const per = Math.min(.22, (D - 2.0) / {n});
gsap.set('.kw', {{opacity:.12, y: 0.25*{70 if portrait else 78}*U, filter:'blur(4px)'}});
tl.from('#mark', {{opacity:0, y:-20*U, duration:.6, ease:'power3.out'}}, .05);
tl.to('.kw', {{opacity:1, y:0, filter:'blur(0px)', duration:.5, ease:'power3.out', stagger: per}}, .3);
tl.fromTo('.em', {{scale:1.25}}, {{scale:1, duration:.6, ease:'back.out(3)', stagger: per, immediateRender:false}}, .3 + per*0.5);
tl.from('#who', {{opacity:0, x:-20*U, duration:.6, ease:'power3.out'}}, .4 + per*{n});
tl.to('#wrap', {{opacity:0, y:-10*U, duration:.5, ease:'power2.in'}}, D-.55);
"""
    return css, body, js, float(p.get("duration", max(4.5, 1.8 + 0.3 * n))), bool(p.get("transparent", False))


TEMPLATES = {"title_card": title_card, "lower_third": lower_third, "data_callout": data_callout, "kinetic_quote": kinetic_quote}


def build(template, params, w, h, duration=None):
    """-> (html, duration, transparent)"""
    if template not in TEMPLATES:
        raise ValueError(f"unknown hyperframes template {template!r}; have {sorted(TEMPLATES)}")
    params = dict(params or {})
    if duration:
        params["duration"] = duration
    css, body, js, dur, transparent = TEMPLATES[template](params, w, h)
    return page(w, h, dur, body, css, js, transparent, params.get("accent")), dur, transparent


def wrap_custom(source, w, h, duration):
    """Accept a full Hyperframes document, or a fragment (markup + <script> using `tl`) and wrap it in the page shell."""
    s = source.strip()
    if "<html" in s.lower():
        return s
    body, js = s, ""
    if "<script>" in s:
        body, _, rest = s.partition("<script>")
        js = rest.rsplit("</script>", 1)[0]
    return page(w, h, duration, BACKDROP + body, BACKDROP_CSS, BACKDROP_JS + js)


if __name__ == "__main__":
    print(json.dumps(sorted(TEMPLATES)))
