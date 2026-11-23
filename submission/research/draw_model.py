"""Rasterize the verified porous model with every enclosed cell visible."""
from pathlib import Path
from PIL import Image, ImageDraw,ImageFont
from heesch_verify import verify_witness
from heesch_verify.shape import holes_of

D=Path(__file__).resolve().parent
v=verify_witness((D/'model-four.heesch').read_text());grid=v.submission.grid;shape=v.submission.cells
allposes=v.submission.patches[1];occupied={p for level,xf in allposes for p in xf.apply_all(shape)};holes=holes_of(occupied,grid);xmin=min(x for x,y in occupied);xmax=max(x for x,y in occupied);ymax=max(y for x,y in occupied);ymin=min(y for x,y in occupied);scale=min(17,1000//(1+xmax-xmin),710//(1+ymax-ymin));W=max(780,70+(1+xmax-xmin)*scale);H=205+(1+ymax-ymin)*scale
im=Image.new('RGB',(W,H),'#fafaf7');draw=ImageDraw.Draw(im)
def font(size,bold=False):
    for name in (["/System/Library/Fonts/Supplemental/Arial Bold.ttf","DejaVuSans-Bold.ttf"] if bold else ["/System/Library/Fonts/Supplemental/Arial.ttf","DejaVuSans.ttf"]):
        try:return ImageFont.truetype(name,size)
        except OSError:pass
    return ImageFont.load_default()
colors=['#263d4d','#386985','#67a6a0','#a9ccac','#edc184'];line='#3a4650'
draw.text((30,16),'Four coronas around a 38-square tile',font=font(31,True),fill=line);draw.text((31,57),'The first three coronas are solid. The fourth encloses 36 empty cells.',font=font(18),fill=line)
origin=((W-(1+xmax-xmin)*scale)//2,98);at=lambda x,y:(origin[0]+(x-xmin)*scale,origin[1]+(ymax-y)*scale)
for l,xf in allposes:
    tiles=xf.apply_all(shape)
    for x,y in tiles:
        u,q=at(x,y); draw.rectangle((u,q,u+scale-1,q+scale-1),fill=colors[l]);
    for x,y in tiles:
        u,q=at(x,y)
        for off,edge in [((-1,0),(u,q,u,q+scale)),((1,0),(u+scale,q,u+scale,q+scale)),((0,1),(u,q,u+scale,q)),((0,-1),(u,q+scale,u+scale,q+scale))]:
            if(x+off[0],y+off[1])not in tiles:draw.line(edge,fill=line,width=1)
for x,y in holes:
    u,q=at(x,y);draw.rectangle((u+1,q+1,u+scale-1,q+scale-1),fill='#be4f4f')
legend=[('Center',colors[0]),('1st · 5',colors[1]),('2nd · 10',colors[2]),('3rd · 21',colors[3]),('4th · 31',colors[4]),('Enclosed cells','#be4f4f')];total=sum(29+draw.textlength(label,font=font(16)) for label,col in legend);x=(W-total)/2
for label,col in legend:
    draw.rectangle((x,H-69,x+13,H-56),fill=col,outline=line);draw.text((x+18,H-73),label,font=font(16),fill=line);x+=29+draw.textlength(label,font=font(16))
draw.text((30,H-35),'Certificate of placement · 68 distinct tile copies, including the center',font=font(16),fill=line);im.save(D/'porous-fourth.png')
