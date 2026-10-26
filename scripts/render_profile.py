"""Render a monochrome profile animation from fetched aggregate GitHub stats."""

from PIL import Image, ImageDraw, ImageFont
import argparse
from datetime import date, timedelta
import json
import math
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stats', type=Path, default=Path('assets/profile-stats.json'))
parser.add_argument('--output-dir', type=Path, default=Path('assets'))
parser.add_argument('--font', type=Path, help='Path to a monospace TrueType font')
args = parser.parse_args()
stats = json.loads(args.stats.read_text())
days = stats['contributions']
if len(days) != 30 or any(type(day['count']) is not int or day['count'] < 0 for day in days):
    raise ValueError('Expected 30 nonnegative daily contribution counts')
start = date.fromisoformat(days[0]['date'])
if [day['date'] for day in days] != [(start + timedelta(days=i)).isoformat() for i in range(30)]:
    raise ValueError('Contribution dates must be 30 consecutive days')
languages = stats['languages']
if any(type(item['bytes']) is not int or item['bytes'] < 0 for item in languages):
    raise ValueError('Language byte sizes must be nonnegative integers')
if stats['language_status'] not in ('complete', 'pending'):
    raise ValueError('Unknown language status')
languages = sorted((item for item in languages if item['bytes']), key=lambda item: (-item['bytes'], item['name']))
language_total = sum(item['bytes'] for item in languages)
display_languages = languages[:5]
if len(languages) > 5:
    display_languages.append({'name': 'Other', 'bytes': sum(item['bytes'] for item in languages[5:])})
OUT = args.output_dir
OUT.mkdir(parents=True, exist_ok=True)
font_paths = [args.font, Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')]
FONT = next((str(path) for path in font_paths if path and path.is_file()), None)
if FONT is None:
    raise RuntimeError('Install fonts-dejavu-core or pass --font /path/to/monospace.ttf')
def font(size): return ImageFont.truetype(FONT, size)
bg, panel, ink, muted, border = '#000000', '#161b22', '#e6e6e6', '#9299a1', '#515a64'
language_height = max(150, 80 + 30 * len(display_languages))
language_bottom = 650 + language_height
base = Image.new('RGB', (900, language_bottom + 35), bg)
d = ImageDraw.Draw(base)
def text(x,y,s,size=16,color=ink): d.text((x,y),s,font=font(size),fill=color)
def box(y,h): d.rectangle((30,y,870,y+h),fill=panel,outline=border,width=1)
text(30,22,'$ ls ~/projects',24)
box(85,185)
text(55,106,'FEATURED PROJECT',13,muted)
text(55,136,'Total-Sense',24)
text(55,178,'Check the sketchy link before you click.',17)
text(55,210,'One-click reputation checks using your VirusTotal API key.',14)
text(55,241,'JavaScript / HTML / CSS / VirusTotal API',14,muted)
text(30,294,'$ activity',23)
box(345,225)
text(55,354,f"{days[0]['date']} / {days[-1]['date']} UTC",12,muted)
text(55,376,f"{sum(day['count'] for day in days)} contributions / updated {stats['updated_at'][:10]}",12,muted)
values=[day['count'] for day in days]
ceiling=max(4,math.ceil(max(values)/4)*4)
for tick in range(5):
    y=530-tick*30
    for x in range(70,831,8): d.line((x,y,x+2,y),fill='#303840')
    text(40,y-6,str(ceiling*tick//4),10,muted)
pts=[(70+i*26,530-v/ceiling*120) for i,v in enumerate(values)]
d.line(pts,fill='#b9c0c7',width=2)
for x,y in pts: d.rectangle((x-2,y-2,x+2,y+2),fill=ink)
text(65,545,days[0]['date'][5:],12,muted)
text(425,545,'DAY',12,muted)
text(790,545,days[-1]['date'][5:],12,muted)
text(30,596,'$ languages',23)
box(650,language_height)
text(55,660,'PUBLIC NON-FORK REPOS / SHARE OF LANGUAGE BYTES',12,muted)
if stats['language_status']=='pending':
    text(55,700,'Language totals pending the first GitHub Actions refresh.',15)
elif not language_total:
    text(55,700,'No language bytes reported for public non-fork repositories.',14)
else:
    for i,item in enumerate(display_languages):
        percent=item['bytes']/language_total*100
        filled=round(percent/5)
        name=item['name'] if len(item['name'])<=18 else item['name'][:17]+'~'
        bar='#'*filled+'-'*(20-filled)
        text(55,690+30*i,f"{name:18} [{bar}] {percent:5.1f}%",17)

# One continuous route visits each panel border and returns along the gutter.
vertices=[(30,85),(870,85),(870,270),(14,270),(14,345),(870,345),(870,570),(14,570),(14,650),(870,650),(870,language_bottom),(14,language_bottom),(14,85),(30,85)]
segments=[]
total=0
for a,b in zip(vertices,vertices[1:]):
    length=math.dist(a,b)
    segments.append((total,length,a,b))
    total+=length
def point(distance):
    distance%=total
    for start,length,a,b in segments:
        if distance<=start+length:
            t=(distance-start)/length
            return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
    return vertices[0]
apple_distances=[400,1150,2050,2900,3850,4700,5500]
def apple(draw,x,y):
    # Small square-pixel apple, including a stem and leaf.
    x,y=round(x),round(y)
    draw.rectangle((x-6,y-3,x+6,y+5),fill=ink)
    draw.rectangle((x-4,y-5,x+4,y+7),fill=ink)
    draw.rectangle((x,y-10,x+2,y-6),fill=muted)
    draw.rectangle((x+3,y-10,x+6,y-8),fill=muted)
route=[]
for _,length,a,b in segments:
    steps=max(1,round(length/16))
    for step in range(steps):
        t=step/steps
        route.append((round(a[0]+(b[0]-a[0])*t),round(a[1]+(b[1]-a[1])*t)))
apple_steps=[min(range(len(route)),key=lambda i:math.dist(route[i],point(a))) for a in apple_distances]
frames=[]
palette=base.quantize(colors=48)
# A still version lets visitors read the same stats without motion.
base.save(OUT/'profile.png')
for frame in range(len(route)):
    im=base.copy(); draw=ImageDraw.Draw(im)
    eaten=sum(a<=frame for a in apple_steps)
    for a in apple_steps:
        if a>frame: apple(draw,*route[a])
    body_length=9+eaten*2
    for n in range(body_length,0,-1):
        x,y=route[(frame-n)%len(route)]
        # Nearly touching equal blocks evoke the classic grid-based game.
        draw.rectangle((x-7,y-7,x+7,y+7),fill='#c8c8c8')
        draw.rectangle((x-5,y-5,x+5,y+5),outline='#a5a5a5')
    x,y=route[frame]
    nx,ny=route[(frame+1)%len(route)]
    # Blunt square head, no tongue or decorative taper.
    dx=1 if nx>x else -1 if nx<x else 0
    dy=1 if ny>y else -1 if ny<y else 0
    px,py=-dy,dx
    def local(forward,side):
        return (round(x+dx*forward+px*side),round(y+dy*forward+py*side))
    draw.rectangle((x-8,y-8,x+8,y+8),fill='#ededed')
    for side in (-4,4):
        ex,ey=local(4,side)
        draw.rectangle((ex-1,ey-1,ex+1,ey+1),fill=bg)
    frames.append(im.quantize(palette=palette,dither=Image.Dither.NONE))
gif_path=OUT/'profile.gif'
temporary=OUT/'profile.tmp.gif'
frames[0].save(temporary,save_all=True,append_images=frames[1:],duration=90,loop=0,optimize=True,disposal=1)
temporary.replace(gif_path)
summary=[
    '# Profile stats', '',
    'Total-Sense: one-click website reputation checks using your own VirusTotal API key.',
    'Stack: JavaScript / HTML / CSS / VirusTotal API.', '',
    f"Updated: {stats['updated_at']} (UTC). Source: {stats['source']}.", '',
    '## Activity', '',
    'Counts reflect the contribution calendar visible on GitHub, including anonymized private counts only when GitHub makes them visible.', '',
    '| Date (UTC) | Contributions |', '| --- | ---: |',
    *[f"| {day['date']} | {day['count']} |" for day in days], '',
    '## Languages', '', stats['language_scope']+'.', '',
]
if stats['language_status']=='pending':
    summary.append('Language totals are pending the first successful GitHub Actions API refresh.')
elif not language_total:
    summary.append('GitHub reports no language bytes for the selected public repositories.')
else:
    summary.extend(['| Language | Share of bytes |','| --- | ---: |'])
    for item in languages:
        name=item['name'].replace('|',r'\|').replace('\n',' ')
        summary.append(f"| {name} | {item['bytes']/language_total*100:.1f}% |")
(OUT/'profile-summary.md').write_text('\n'.join(summary)+'\n')
print(f"Rendered {len(frames)} frames; GIF {gif_path.stat().st_size:,} bytes")
