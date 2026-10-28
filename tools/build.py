#!/usr/bin/env python3
"""Bygger en statisk version av treknivar.se från WordPress-exporten (content.json)."""
import json, re, os, sys, html, shutil
from urllib.parse import unquote

SRC = sys.argv[1]          # content.json
OUT = sys.argv[2]          # utmapp
ASSETS = sys.argv[3]       # mapp med css/js att kopiera in

data = json.load(open(SRC))
ATT = data['att']
ITEMS = {x['id']: x for x in data['items']}
MEDIA_USED = set()

MEDIA_RE = re.compile(r'https?://media\.treknivar\.se/([^"\'\s)<>]+)')
SITE_RE = re.compile(r'https?://(?:www\.)?treknivar\.se(/[^"\'\s<>]*)?')


def media(url):
    """Mappa en media.treknivar.se-URL till lokal sökväg /media/..."""
    m = MEDIA_RE.match(url)
    if not m:
        return url
    MEDIA_USED.add(m.group(1))
    return '/media/' + m.group(1)


def att_url(aid):
    a = ATT.get(str(aid))
    return media(a['url']) if a else ''


def fix_urls(s):
    s = MEDIA_RE.sub(lambda m: media(m.group(0)), s)
    s = SITE_RE.sub(lambda m: (m.group(1) or '/'), s)
    return s

# ---------------------------------------------------------------- shortcodes
SC_RE = re.compile(r'\[(/?)([a-z_0-9]+)((?:\s+[a-z_0-9]+="[^"]*")*)\s*(/?)\]')
ATTR_RE = re.compile(r'([a-z_0-9]+)="([^"]*)"')
CONTAINERS = {'vc_row', 'vc_column', 'vc_row_inner', 'vc_column_inner', 'vc_column_text',
              'edgtf_elements_holder', 'edgtf_elements_holder_item', 'edgtf_custom_font'}


def parse(text):
    """Parsar shortcodes till ett träd: lista av str eller dict(tag, attrs, children)."""
    root = {'tag': 'root', 'attrs': {}, 'children': []}
    stack = [root]
    pos = 0
    for m in SC_RE.finditer(text):
        if m.start() > pos:
            stack[-1]['children'].append(text[pos:m.start()])
        pos = m.end()
        closing, tag, attrs = m.group(1), m.group(2), m.group(3)
        if closing:
            # stäng närmaste matchande
            for i in range(len(stack) - 1, 0, -1):
                if stack[i]['tag'] == tag:
                    del stack[i:]
                    break
            continue
        node = {'tag': tag, 'attrs': dict(ATTR_RE.findall(attrs)), 'children': []}
        stack[-1]['children'].append(node)
        if tag in CONTAINERS and not m.group(4):
            stack.append(node)
    if pos < len(text):
        stack[-1]['children'].append(text[pos:])
    return root['children']


def col_class(a):
    w = a.get('width', '')
    off = a.get('offset', '')
    m = re.search(r'vc_col-lg-(\d+)', off)
    if m and 'offset' not in m.group(0):
        lg = re.findall(r'vc_col-lg-(\d+)(?!\S*offset)', off)
    lg = [x for x in re.findall(r'vc_col-lg-(\d+)', off)]
    off_lg = re.findall(r'vc_col-lg-offset-(\d+)', off)
    span = None
    if lg:
        span = int(lg[-1])
    elif w:
        n, d = w.split('/')
        span = 12 * int(n) // int(d)
    cls = 'col'
    if span:
        cls += f' span-{span}'
    if off_lg and off_lg[0] != '0':
        cls += f' offset-{off_lg[0]}'
    return cls


def esc(s):
    return html.escape(html.unescape(s or ''), quote=True)


def render(nodes, ctx=None):
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append(n)
        else:
            out.append(render_node(n, ctx or {}))
    return ''.join(out)


def video_embed(url, aspect='169'):
    m = re.search(r'(?:youtu\.be/|v=|shorts/|embed/)([\w-]{6,})', url)
    if m:
        src = f'https://www.youtube-nocookie.com/embed/{m.group(1)}'
    else:
        m = re.search(r'vimeo\.com/(\d+)', url)
        if not m:
            return f'<p><a href="{esc(url)}">{esc(url)}</a></p>'
        src = f'https://player.vimeo.com/video/{m.group(1)}'
    cls = 'video portrait' if aspect == '916' else 'video'
    return (f'<div class="{cls}"><iframe src="{src}" loading="lazy" title="Video" '
            f'allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe></div>')


TESTIMONIALS = [
    ('“Djärvt polyfont projekt. Drottningholmsteaterns andra uruppförande i sommar liknar ingenting annat. Det är ett praktfullt audiovisuellt myller som möter publiken.”', 'SvD', 'recension'),
    ('"Reine Jönssons musik bygger på klara mönster och är melodiskt infallsrikt på ett mycket tilltalande sätt och detta simultanberättande är ett fräscht och ambitiöst grepp, som regissören Patrik Sörling liksom alla medverkande- utmärkta sångare och musiker över lag – har gjort ett imponerande arbete för att ro i hamn."', 'Aftonbladet', 'recension'),
    ('"Strändernas svall är operahistoria"', 'SvD', 'recension'),
]


def render_node(n, ctx):
    t, a, ch = n['tag'], n['attrs'], n['children']
    if t in ('vc_row', 'vc_row_inner'):
        cls = 'row'
        if a.get('row_content_width') == 'grid':
            cls += ' grid'
        if a.get('content_text_aligment') == 'center':
            cls += ' center'
        if a.get('content_placement') == 'middle':
            cls += ' middle'
        style = ''
        m = re.search(r'padding-top:\s*(\d+)px', a.get('css', ''))
        if m:
            style += f'--pt:{min(int(m.group(1)), 160)}px;'
        m = re.search(r'padding-bottom:\s*(\d+)px', a.get('css', ''))
        if m:
            style += f'--pb:{min(int(m.group(1)), 160)}px;'
        bg = ''
        if a.get('parallax_background_image'):
            bg = f'<div class="parallax" style="background-image:url({att_url(a["parallax_background_image"])})"></div>'
            cls += ' has-parallax'
        inner = render(ch, ctx)
        if not re.sub(r'<[^>]+>|\s|&nbsp;', '', inner) and '<img' not in inner and '<iframe' not in inner and 'class="sep' not in inner:
            return ''
        st = f' style="{style}"' if style else ''
        return f'<div class="{cls}"{st}>{bg}<div class="row-inner">{inner}</div></div>\n'
    if t in ('vc_column', 'vc_column_inner'):
        inner = render(ch, ctx)
        if a.get('video_bg') == 'yes' and a.get('video_bg_url'):
            return f'<div class="{col_class(a)} video-bg">{video_embed(a["video_bg_url"])}<div class="video-bg-content">{inner}</div></div>'
        return f'<div class="{col_class(a)}">{inner}</div>'
    if t == 'vc_column_text':
        return f'<div class="text">{render(ch, ctx)}</div>'
    if t == 'edgtf_elements_holder':
        cols = 'two' if a.get('number_of_columns') == 'two-columns' else 'one'
        return f'<div class="holder {cols}">{render(ch, ctx)}</div>'
    if t == 'edgtf_elements_holder_item':
        return f'<div class="holder-item">{render(ch, ctx)}</div>'
    if t in ('vc_single_image', 'edgtf_single_image'):
        u = att_url(a.get('image'))
        if not u:
            return ''
        return f'<figure class="single-image"><img src="{u}" alt="" loading="lazy"></figure>'
    if t == 'vc_custom_heading':
        fc = dict(p.split(':', 1) for p in a.get('font_container', '').split('|') if ':' in p)
        tag = fc.get('tag', 'h2')
        color = unquote(fc.get('color', ''))
        st = f' style="color:{color}"' if color else ''
        if fc.get('text_align'):
            st = st[:-1] + f';text-align:{fc["text_align"]}"' if st else f' style="text-align:{fc["text_align"]}"'
        txt = esc(a.get('text'))
        link = unquote(a.get('link', '')).replace('url:', '', 1).split('|')[0]
        if link:
            txt = f'<a href="{esc(fix_urls(link))}">{txt}</a>'
        return f'<{tag} class="custom-heading"{st}>{txt}</{tag}>'
    if t == 'edgtf_video_button':
        img = att_url(a.get('video_image'))
        return (f'<a class="video-button" href="{esc(a.get("video_link"))}" target="_blank" rel="noopener" data-video="{esc(a.get("video_link"))}">'
                f'<img src="{img}" alt="Spela trailer" loading="lazy"><span class="play" aria-hidden="true"></span></a>')
    if t == 'edgtf_separator':
        th = a.get('thickness', '').replace('px', '')
        st = f' style="border-top-width:{th}px"' if th else ''
        return f'<hr class="sep"{st}>'
    if t == 'vc_empty_space':
        h = a.get('height', '32px')
        return f'<div class="space" style="height:{esc(h)}"></div>'
    if t == 'edgtf_custom_font':
        title = esc(a.get('title'))
        link = a.get('link')
        if link:
            title = f'<a href="{esc(fix_urls(link))}" target="{esc(a.get("target", "_self"))}">{title}</a>'
        fam = a.get('font_family', '')
        cls = 'custom-font'
        style = ''
        if a.get('hollow_effect') == 'yes':
            cls += ' hollow'
        if 'Roboto Mono' in fam:
            cls += ' mono'
        elif a.get('font_size'):
            px = lambda k: int(re.sub(r'\D', '', a.get(k, '')) or 0)
            big = px('font_size_1366') or px('font_size')
            small = px('font_size_680') or max(40, big // 3)
            cls += ' sized'
            style = f' style="font-size:clamp({small}px,{big / 13.66:.1f}vw,{big}px)"'
        else:
            cls += ' large'
        if a.get('style') == 'inline-block':
            cls += ' inline'
        tag = a.get('title_tag') or 'div'
        return f'<{tag} class="{cls}"{style}>{title}</{tag}>' + render(ch, ctx)
    if t == 'edgtf_button':
        return f'<p class="btn-wrap {a.get("horizontal_alignment", "")}"><a class="btn" href="{esc(fix_urls(a.get("link", "#")))}">{esc(a.get("text"))}</a></p>'
    if t == 'edgtf_icon_with_text':
        icon = att_url(a['custom_icon']) if a.get('custom_icon') else ''
        title = esc(a.get('title'))
        link = a.get('link', '')
        if a.get('type') == 'icon-left-from-title':
            if '456' in title or 'Resume' in title:
                return ''  # platshållare från temat
            if link and link != '#':
                title = f'<a href="{esc(link)}">{title}</a>'
            return f'<p class="info-line">{title}</p>'
        body = f'<img class="iwt-icon" src="{icon}" alt="" loading="lazy">' if icon else ''
        body += f'<h4 class="iwt-title">{title}</h4><p class="iwt-text">{esc(a.get("text"))}</p>'
        if link:
            body = f'<a href="{esc(link)}" target="_blank" rel="noopener">{body}</a>'
        return f'<div class="icon-with-text">{body}</div>'
    if t == 'rev_slider':
        return '<!--SLIDER-->'
    if t == 'edgtf_section_title':
        tag = a.get('title_tag') or 'h2'
        cls = 'section-title hollow' if a.get('enable_hollow_effect') == 'yes' else 'section-title'
        return f'<{tag} class="{cls}">{esc(a.get("title"))}</{tag}>'
    if t == 'edgtf_numbered_text_with_content':
        img = att_url(a.get('image'))
        side = a.get('media_orientation', 'left')
        return (f'<div class="numbered {side}"><div class="numbered-media"><img src="{img}" alt="" loading="lazy"></div>'
                f'<div class="numbered-content"><span class="number">{esc(a.get("number"))}</span>'
                f'<h3>{esc(a.get("title"))}</h3><p>{esc(a.get("text"))}</p>'
                f'<a class="btn" href="{esc(fix_urls(a.get("button_link", "#")))}">{esc(a.get("button_text", "Läs mer"))}</a></div></div>')
    if t == 'edgtf_testimonials':
        slides = ''.join(f'<blockquote class="testimonial"><p>{esc(q)}</p><footer>{esc(au)} / {esc(p)}</footer></blockquote>'
                         for q, au, p in TESTIMONIALS)
        return f'<div class="testimonials" data-slider><span class="quote-mark" aria-hidden="true">“</span>{slides}<div class="dots"></div></div>'
    if t == 'edgtf_team':
        img = att_url(a.get('team_image'))
        name = esc(a.get('team_name'))
        if a.get('team_link'):
            name = f'<a href="{esc(a["team_link"])}" target="_blank" rel="noopener">{name}</a>'
        soc = []
        for i in range(1, 6):
            if a.get(f'team_social_{i}_link'):
                soc.append(f'<a href="{esc(a[f"team_social_{i}_link"])}" target="_blank" rel="noopener">{esc(a.get(f"team_social_link_{i}_text") or "länk")}</a>')
        typ = 'on-image' if a.get('type') == 'info-on-image' else 'below-image'
        return (f'<div class="team {typ}"><div class="team-img"><img src="{img}" alt="{esc(a.get("team_name"))}" loading="lazy"></div>'
                f'<div class="team-info"><h3 class="team-name">{name}</h3><p class="team-position">{esc(a.get("team_position"))}</p>'
                + (f'<p class="team-social">{" ".join(soc)}</p>' if soc else '') + '</div></div>')
    if t == 'vc_video':
        return video_embed(a.get('link', ''), a.get('el_aspect', '169'))
    if t == 'edgtf_portfolio_list':
        return ''  # temats demoportfolio, tas bort
    # okänd shortcode: rendera barnen
    return render(ch, ctx)


# ---------------------------------------------------------------- Gutenberg / HTML-städning

def clean_html(s):
    # presto-player self-hosted video
    s = re.sub(r'<!-- wp:presto-player/self-hosted \{[^}]*"src":"([^"]+)"[^}]*\} /-->',
               lambda m: f'<video controls preload="metadata" src="{m.group(1)}"></video>', s)
    s = re.sub(r'<!--\s*/?wp:[^>]*?-->', '', s)
    s = re.sub(r'<!--\s*wp:masvideos[^>]*-->', '', s)
    # oembed youtube
    s = re.sub(r'<div class="wp-block-embed__wrapper">\s*(https?://\S+)\s*</div>', lambda m: video_embed(m.group(1)), s)
    s = fix_urls(s)
    # ta bort tomma stycken och &nbsp;-stycken i följd
    s = re.sub(r'<p>\s*</p>', '', s)
    s = re.sub(r'(?:<p>(?:&nbsp;|\s)*</p>\s*){2,}', '<p>&nbsp;</p>', s)
    s = re.sub(r'(<p>(?:&nbsp;|\s)*</p>\s*)+$', '', s.strip())
    s = re.sub(r'<p>\s*(<figure)', r'\1', s)
    s = re.sub(r'(</figure>)\s*</p>', r'\1', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s


def autop(s):
    """Enkel wpautop för klassiskt innehåll utan <p>."""
    if '<p' in s or '<figure' in s:
        return s
    parts = [p.strip() for p in re.split(r'\n\s*\n', s) if p.strip()]
    return '\n'.join(p if re.match(r'<(div|h\d|blockquote|ul|ol|figure|img)', p) and not p.startswith('<img') else f'<p>{p}</p>' for p in parts)


def convert(content):
    tree = parse(content)
    out = render(tree)
    out = clean_html(out)
    out = re.sub(r'<div class="text">\s*<h3[^>]*>filmography\.</h3>\s*</div>', '', out)
    if '[vc_row' not in content:
        out = autop(out)
    else:
        out = re.sub(r'<div class="text">(.*?)</div>', lambda m: '<div class="text">' + autop(m.group(1).strip()) + '</div>', out, flags=re.S)
    return out


# ---------------------------------------------------------------- sidmall
NAV = [('Hem', '/'), ('Om operan', '/om/'), ('Medverkande', '/medverkande/'), ('Team', '/om-oss/'),
       ('Press', '/press/'), ('Kontakt', '/kontakt/')]
SITE_TITLE = 'Tre knivar från Wei'
SITE_DESC = 'Nyskriven kammaropera av Reine Jönsson och Patrik Sörling'


MONTHS = ['januari', 'februari', 'mars', 'april', 'maj', 'juni', 'juli', 'augusti', 'september', 'oktober', 'november', 'december']


def sv_date(d):
    y, m, day = d[:10].split('-')
    return f'{int(day)} {MONTHS[int(m) - 1]} {y}'


def page(path, title, body, body_class='', desc=SITE_DESC, og_image=''):
    nav = ''.join(f'<li><a href="{u}"{" aria-current=\"page\"" if u == path else ""}><span>{n}</span></a></li>' for n, u in NAV)
    full_title = SITE_TITLE if path == '/' else f'{title} – {SITE_TITLE}'
    og = f'<meta property="og:image" content="https://www.treknivar.se{og_image}">' if og_image else ''
    return f'''<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
{og}
<link rel="canonical" href="https://www.treknivar.se{path}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@300;400;600;700&family=Roboto+Mono:wght@300;400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
<link rel="icon" href="/media/2022/08/3daggers-logo-150x150.png" type="image/png">
</head>
<body class="{body_class}">
<header class="site-header">
  <a class="logo" href="/" aria-label="Tre knivar från Wei – startsida">
    <img class="logo-desktop" src="/media/2022/08/3daggers-logo.png" alt="" width="75" height="75">
    <img class="logo-mobile" src="/media/2022/10/logo-tre150px.png" alt="" width="75" height="75">
  </a>
  <nav id="main-nav" class="main-nav" aria-label="Huvudmeny"><ul>{nav}</ul></nav>
  <button class="side-toggle" aria-expanded="false" aria-controls="side-menu"><span class="side-label">Huvudmeny</span><span class="burger" aria-hidden="true"><i></i><i></i></span></button>
</header>
<aside id="side-menu" class="side-menu" aria-hidden="true">
  <button class="side-close" aria-label="Stäng meny">×</button>
  <nav class="side-nav" aria-label="Meny"><ul>{nav}</ul></nav>
  <a href="https://film.treknivar.se" target="_blank" rel="noopener"><img src="/media/2022/07/tre-affisch512px.png" alt="Se filmen" loading="lazy"></a>
  <a href="https://youtube.com/@treknivarfranwei" target="_blank" rel="noopener"><img src="/media/2021/08/silver-1024x684.jpg" alt="YouTube-kanalen" loading="lazy"></a>
  <p>Nyskriven opera som nyårskalender med premiär 1 december 2022.</p>
  <p class="social"><a href="https://www.facebook.com/patrikspavilion/" target="_blank" rel="noopener">fb.</a> <a href="https://www.instagram.com/treknivar/" target="_blank" rel="noopener">ig.</a></p>
</aside>
<div class="side-overlay"></div>
<main>
{body}
</main>
<footer class="site-footer">
  <div class="footer-top">
    <div class="footer-col"><h5>om oss.</h5><p><a href="/om-oss/">Reine Jönsson</a></p><p><a href="https://pavilion.se" target="_blank" rel="noopener">Patrik Sörling</a></p></div>
    <div class="footer-col"><h5>tre knivar från wei.</h5><p>Fritt efter en pjäs av Harry Martinson</p><p class="social"><a href="https://www.facebook.com/patrikspavilion/" target="_blank" rel="noopener">fb.</a> <a href="https://www.instagram.com/treknivar/" target="_blank" rel="noopener">ig.</a></p></div>
    <div class="footer-col"><h5>nyheter.</h5><p>Vid intresse:</p><p>info(at)treknivar.se</p></div>
    <div class="footer-col"></div>
  </div>
  <div class="footer-bottom">
    <a href="/"><img src="/media/2022/08/3daggers-logo-150x150.png" alt="Tre knivar från Wei" width="150" height="150" loading="lazy"></a>
    <p>Made by <a href="https://pavilion.se" target="_blank" rel="noopener">Pavilion</a></p>
  </div>
</footer>
<script src="/assets/main.js" defer></script>
</body>
</html>
'''


def path_of(link):
    p = re.sub(r'https?://(?:www\.)?treknivar\.se', '', link)
    return p if p.endswith('/') else p + '/'


def write(path, htmltext):
    d = os.path.join(OUT, path.strip('/'))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'index.html'), 'w') as f:
        f.write(htmltext)


def excerpt_of(htmltext, n=180):
    t = re.sub(r'<[^>]+>', ' ', htmltext)
    t = re.sub(r'\s+', ' ', html.unescape(t)).strip()
    return (t[:n].rsplit(' ', 1)[0] + ' …') if len(t) > n else t


# ---------------------------------------------------------------- bygg
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)

SLIDER = '''<div class="hero-slider" data-slider>
  <figure><img src="/media/2022/08/tre-poster-olika-1024x688.jpg" alt=""></figure>
  <figure><img src="/media/2022/10/samiwindow_1.18.1-1024x576.jpg" alt=""></figure>
  <figure><img src="/media/2022/10/18still_2.9.1-1024x576.jpg" alt=""></figure>
  <div class="dots"></div>
</div>'''

posts = sorted([x for x in data['items'] if x['type'] == 'post'], key=lambda x: x['date'], reverse=True)

for x in data['items']:
    if x['type'] not in ('page', 'post') or x['title'] == 'Blogg':
        continue
    path = path_of(x['link'])
    body_html = convert(x['content'])
    body_html = body_html.replace('<!--SLIDER-->', '')
    for u in re.findall(r'src="(/media/[^"]+)"', body_html):
        pass
    thumb = att_url(x['thumb']) if x['thumb'] else ''
    is_vc = '[vc_row' in x['content']
    if path == '/':
        body = body_html
        cls = 'home'
    elif x['type'] == 'post':
        i = posts.index(x)
        nxt = posts[i + 1] if i + 1 < len(posts) else None
        hero = f'<figure class="post-hero"><img src="{thumb}" alt=""></figure>' if thumb else ''
        nav_next = f'<p class="next-post"><a href="{path_of(nxt["link"])}">Nästa artikel <span></span></a></p>' if nxt else ''
        body = (f'<article class="post container narrow">{hero}<p class="meta">{sv_date(x["date"])}</p>'
                f'<h1 class="post-title">{esc(x["title"])}</h1>'
                f'<div class="entry">{body_html}</div>{nav_next}</article>')
        cls = 'single-post'
    else:
        no_title = path in ('/medverkande/', '/om-patrik/')
        title_html = '' if no_title else f'<header class="page-head"><h1 class="page-title">{esc(x["title"])}</h1></header>'
        if is_vc:
            body = f'<div class="page-vc">{title_html}{body_html}</div>'
        else:
            body = f'<article class="container">{title_html}<div class="entry">{body_html}</div></article>'
        cls = 'page page-' + (path.strip('/') or 'home')
    desc = excerpt_of(body_html, 155) or SITE_DESC
    first_img = re.search(r'src="(/media/[^"]+)"', body_html)
    write(path, page(path, x['title'], body, cls, desc if path != '/' else SITE_DESC, thumb or (first_img.group(1) if first_img else '')))

# bloggsida
cards = ''
for x in posts:
    thumb = att_url(x['thumb']) if x['thumb'] else ''
    cards += (f'<article class="card"><a href="{path_of(x["link"])}">'
              + (f'<img src="{thumb}" alt="" loading="lazy">' if thumb else '')
              + f'<p class="meta">{sv_date(x["date"])}</p><h2>{esc(x["title"])}</h2>'
              f'<p>{esc(excerpt_of(convert(x["content"])))}</p></a></article>')
write('/blogg/', page('/blogg/', 'Blogg', f'<div class="container"><header class="page-head"><h1 class="page-title">Blogg</h1></header><div class="cards">{cards}</div></div>', 'page'))

# 404
with open(os.path.join(OUT, '404.html'), 'w') as f:
    f.write(page('/404/', 'Sidan finns inte', '<div class="container narrow"><header class="page-head"><h1 class="page-title">404</h1></header><p>Sidan du letar efter finns inte. <a href="/">Till startsidan</a>.</p></div>', 'page'))

# statiska filer
shutil.copytree(ASSETS, os.path.join(OUT, 'assets'))
with open(os.path.join(OUT, 'CNAME'), 'w') as f:
    f.write('www.treknivar.se\n')
open(os.path.join(OUT, '.nojekyll'), 'w').close()

# slider-bilder räknas som använda
for p in ['2022/08/3daggers-logo.png','2022/08/3daggers-logo-150x150.png','2022/10/logo-tre150px.png','2022/07/tre-affisch512px.png','2021/08/silver-1024x684.jpg']:
    MEDIA_USED.add(p)
with open(os.path.join(OUT, '..', 'media-list.txt'), 'w') as f:
    f.write('\n'.join(sorted(MEDIA_USED)) + '\n')
print('Sidor byggda. Bilder som används:', len(MEDIA_USED))

# extra filer (README, tools, ev. media) kopieras in om en fjärde mapp anges
if len(sys.argv) > 4:
    for name in os.listdir(sys.argv[4]):
        s = os.path.join(sys.argv[4], name); d = os.path.join(OUT, name)
        (shutil.copytree if os.path.isdir(s) else shutil.copy)(s, d)
