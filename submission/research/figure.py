from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from heesch_verify import verify_witness
from heesch_verify.patch import required_set
D=Path(__file__).resolve().parent;src=verify_witness((D/'parent-19.heesch').read_text());v=verify_witness((D.parent/'best.heesch').read_text());S=v.submission.cells;grid=v.submission.grid
W,H=1260,990;im=Image.new('RGB',(W,H),'#f9f9f6');g=ImageDraw.Draw(im);colors=['#234659','#407c91','#90beb6','#e7c48b'];ink='#283a40';red='#bf474d'
def font(n,b=False):
 for a in (["/System/Library/Fonts/Supplemental/Arial Bold.ttf","DejaVuSans-Bold.ttf"] if b else ["/System/Library/Fonts/Supplemental/Arial.ttf","DejaVuSans.ttf"]):
  try:return ImageFont.truetype(a,n)
  except OSError:pass
 return ImageFont.load_default()
def render(tiles,gaps,box):
 occupied={p for lev,cells in tiles for p in cells}|set(gaps);left=min(x for x,y in occupied);right=max(x for x,y in occupied);top=max(y for x,y in occupied);bottom=min(y for x,y in occupied); x0,y0,w,h=box;scale=min(w/(right-left+1),h/(top-bottom+1));x0+=(w-scale*(right-left+1))/2;y0+=(h-scale*(top-bottom+1))/2
 def loc(x,y):return round(x0+(x-left)*scale),round(y0+(top-y)*scale)
 for level,cells in tiles:
  for x,y in cells:
   u,q=loc(x,y);u1,q1=loc(x+1,y-1);g.rectangle((u,q,u1-1,q1-1),fill=colors[level]);
  for x,y in cells:
   u,q=loc(x,y);u1,q1=loc(x+1,y-1);
   for dd,edge in [((-1,0),(u,q,u,q1)),((1,0),(u1,q,u1,q1)),((0,1),(u,q,u1,q)),((0,-1),(u,q1,u1,q1))]:
    if (x+dd[0],y+dd[1]) not in cells:g.line(edge,fill=ink,width=1)
 for x,y in gaps:
  u,q=loc(x,y);u1,q1=loc(x+1,y-1);g.rectangle((u+1,q+1,u1-1,q1-1),fill=red)
g.text((32,18),'A 20-square tile with exact Heesch number 2',font=font(36,True),fill=ink);g.text((33,66),'A 19-square seed led to a different outline. Its best partial third ring leaves five required squares open.',font=font(20),fill=ink)
left=330;g.line((left,117,left,900),fill='#cad2cf',width=1);g.text((40,125),'Original outline',font=font(22,True),fill=ink);g.text((40,156),'Kaplan record 40 · 19 squares',font=font(16),fill=ink);render([(1,frozenset(src.submission.cells))],[],(42,207,248,225));g.text((40,496),'Synthesized outline',font=font(22,True),fill=ink);g.text((40,526),'20 squares · 7 by 8',font=font(16),fill=ink);render([(0,frozenset(S))],[],(42,574,248,254));inner=v.hc_corona.patch_cells;outer=set().union(*(t.apply_all(S) for l,t in v.submission.defect.tiles));gaps=required_set(inner,v.contact)-outer;render([(l,t.apply_all(S)) for l,t in v.submission.patches[0]]+[(3,t.apply_all(S)) for l,t in v.submission.defect.tiles],gaps,(362,126,860,727));desc=['Center','First · 4 tiles','Second · 11 tiles','Third · 27 partial tiles','5 missing sites'];x=45
for label,col in zip(desc,colors+[red]):
 g.rectangle((x,923,x+15,938),fill=col,outline=ink);g.text((x+23,920),label,font=font(18),fill=ink);x+=36+g.textlength(label,font=font(18))
g.text((45,957),'166 of 171 required sites covered · no additional pocket cells · scalar 508/171',fill=ink,font=font(17));im.save(D/'square20.png')
