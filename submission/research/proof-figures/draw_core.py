"""Compare spatial supports of two independently checked local refutations."""
import json
import math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

HERE=Path(__file__).resolve().parent
views=[]
for radius in (14,19):
    q=HERE/"local-native"/f"r{radius}-cover"
    source=HERE/f"geometric-core-r{radius}.json"
    if not source.is_file():
        assert "s VERIFIED" in (q/"trim.log").read_text()
        source=q/"geometric-core.json"
    views.append(json.loads(source.read_text()))
page=Image.new("RGB",(1470,845),"#f6f5ef")
draw=ImageDraw.Draw(page)
mac_font=Path("/System/Library/Fonts/Supplemental/Arial.ttf").is_file()
def text(p,v,sz,bold=False,ink="#243a42"):
    name=("Arial Bold.ttf" if bold else "Arial.ttf") if mac_font else (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    draw.text(p,v,font=ImageFont.truetype("/System/Library/Fonts/Supplemental/"+name if mac_font else name,sz),fill=ink)
def xy(p):
    x,y=p
    return math.sqrt(3)*(x+y/2),1.5*y
def color(t):
    points=[(0,(239,218,177)),(0.5,(226,138,86)),(1,(163,58,51))]
    lo,hi=points[:2] if t<=0.5 else points[1:]
    k=(t-lo[0])/(hi[0]-lo[0])
    return tuple(round(a+(b-a)*k) for a,b in zip(lo[1],hi[1]))
def polygon(c,r):
    x,y=c
    return [(x+r*math.cos(math.radians(30+60*j)),y+r*math.sin(math.radians(30+60*j))) for j in range(6)]
text((50,32),"Where the fifth-ring obstruction appears",43,True)
text((52,100),"Dark blue marks the central 20-hex. Each colored cell supports a surround constraint used in a refutation.",23)
sets=[{(x,y) for x,y,v in d["by_site"]}|set(map(tuple,d["central"])) for d in views]
coordinates=[xy(q) for q in sets[0]|sets[1]]
x0=min(p[0] for p in coordinates)-1.5;x1=max(p[0] for p in coordinates)+1.5
y0=min(p[1] for p in coordinates)-1.5;y1=max(p[1] for p in coordinates)+1.5
scale=min(647/(x1-x0),430/(y1-y0))
maximum=max(v for d in views for x,y,v in d["by_site"])
for index,(radius,d) in enumerate(zip((14,19),views)):
    xx=58+index*725
    text((xx,175),f"Within {radius} steps of the outline",28,True)
    cells={(x,y):color(math.log(v)/math.log(maximum)) for x,y,v in d["by_site"]}
    for p in map(tuple,d["central"]):cells[p]="#264957"
    cx=xx+(650-scale*(x1-x0))/2
    cy=242+(430-scale*(y1-y0))/2
    for p,hue in cells.items():
        x,y=xy(p);center=(cx+(x-x0)*scale,cy+(y1-y)*scale)
        draw.polygon(polygon(center,scale),fill=hue,outline="#eee9dc")
    text((xx,696),f'{d["implications"]:,} retained implications across {len(d["by_site"]):,} sites',21)
text((52,765),"Number of retained implications at each site",20)
for i in range(140):draw.rectangle((480+i,769,480+i,788),fill=color(i/139))
text((642,764),f"1 to {maximum:,}",19)
text((845,765),"Identical implications can occur at several sites.",19)
out=HERE/"local-obstruction.png"
page.save(out);print(out)
