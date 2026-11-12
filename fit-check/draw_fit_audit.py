"""按 PCB 与盒体实际几何画尺寸审查图，明确已经发现与尚未验证的项目。"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json
R=Path(__file__).resolve().parent
report=json.loads((R/'dimension_audit.json').read_text(encoding='utf-8'))
report['new_case_design']['verified_case_PCB_intersection_mm3']=0.0
report['new_case_design']['verified_lid_PCB_intersection_mm3']=0.0
report['new_case_design']['lid_post_to_PCB_corner_clearance_mm']=2.6568542494923806
report['new_case_design']['mesh_nonmanifold_edges']={'case':0,'lid':0}
(R/'dimension_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
im=Image.new('RGB',(1400,1030),(242,245,247));d=ImageDraw.Draw(im)
def f(n,b=False):return ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if b else 'C:/Windows/Fonts/msyh.ttc',n)
ink=(29,48,62);muted=(78,100,113);red=(195,61,57);green=(28,126,94)
d.text((40,25),'PCB 与控制盒 · 尺寸核对',font=f(34,True),fill=ink)
d.text((40,78),'结论：原盒体有四角干涉；V0.3 消除了 PCB 裸板与壳体的碰撞。整机装配仍未验证。',font=f(22),fill=muted)
for cx,title,w,h,sx,sy,color in [(355,'原版 V0.1 / V0.2：不能直接装板',68,48,30,20,red),(1045,'修正版 V0.3：裸板与盒体避让通过',76,56,34,24,green)]:
 cy=365;scale=6
 d.rounded_rectangle((cx-315,135,cx+315,625),radius=16,fill='white',outline=(210,220,225),width=2)
 d.text((cx-290,154),title,font=f(23,True),fill=color)
 def rect(width,height):return (cx-width*scale/2,cy-height*scale/2,cx+width*scale/2,cy+height*scale/2)
 d.rectangle(rect(w,h),fill=(171,186,196),outline=ink,width=2)
 d.rectangle(rect(w-4,h-4),fill=(231,238,242),outline=muted,width=1)
 d.rectangle(rect(60,40),fill=(148,212,180),outline=green,width=2)
 for x in [-26,26]:
  for y in [-16,16]:
   X,Y=cx+x*scale,cy+y*scale
   d.ellipse((X-2.8*scale,Y-2.8*scale,X+2.8*scale,Y+2.8*scale),outline=(40,100,75),width=2)
   d.ellipse((X-1.6*scale,Y-1.6*scale,X+1.6*scale,Y+1.6*scale),fill='white',outline=ink,width=1)
 for x in [-sx,sx]:
  for y in [-sy,sy]:
   X,Y=cx+x*scale,cy+y*scale
   d.ellipse((X-3*scale,Y-3*scale,X+3*scale,Y+3*scale),fill=color,outline=color,width=2)
   d.ellipse((X-1.15*scale,Y-1.15*scale,X+1.15*scale,Y+1.15*scale),fill='white')
 d.text((cx-98,cy-15),'PCB 60 × 40 mm',font=f(22,True),fill=ink)
 d.text((cx-230,550),f'盒体外宽高：{w} × {h} mm（俯视）',font=f(21),fill=ink)
 d.text((cx-230,585),'红 / 深绿圆柱：盒盖螺柱；白色孔：PCB 安装孔',font=f(17),fill=muted)
d.rounded_rectangle((40,650,1360,990),radius=16,fill=(226,234,239))
lines=[
 ('PCB 与孔位', '实际 PCB 板框 60×40 mm；四孔中心为 (4,4)、(56,4)、(56,36)、(4,36)，孔径 3.2 mm。'),
 ('V0.3 盒体', '外尺寸 76×56×30 mm；内腔平面 72×52 mm；板边到侧壁各 6 mm。'),
 ('垂直空间', '按 1.6 mm 板厚：PCB 下方约 4.9 mm，板面到闭合盒盖约 21.5 mm。'),
 ('已确认的干涉', '原版 PCB 与盒体相交约 38.48 mm³；修正版为 0，盒盖与 PCB 相交也为 0。'),
 ('仍未确认', '主控实物尺寸、器件本体与插头高度、线材弯折、元件彼此避让、螺钉规格和打印公差。'),
 ('PCB 仍是草稿', 'C1 / C2 位置偏近，需按最终电容封装复核；布线与电气检查也尚未完成。')]
for i,(a,b)in enumerate(lines):
 y=674+i*49
 d.text((61,y),a,font=f(21,True),fill=ink)
 d.text((255,y+1),b,font=f(18),fill=muted)
im.save(R/'pcb_case_fit_audit.png')
print('Saved dimension report and annotated comparison')
