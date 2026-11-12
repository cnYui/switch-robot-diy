"""给 Blender 实际渲染帧添加中文讲解，并编码演示视频与循环预览。"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import json
import math
import subprocess
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parent
FONT='C:/Windows/Fonts/msyh.ttc'
BOLD='C:/Windows/Fonts/msyhbd.ttc'
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)
WHITE=(241,246,249)
MUTED=(164,184,197)
ORANGE=(255,158,68)
TEAL=(94,222,191)
NAVY=(17,28,38)

def state(frame):
    if frame<95:return 3.5
    if frame<99:return 3.5-(frame-95)/4*7
    if frame<143:return -3.5
    if frame<147:return -3.5+(frame-143)/4*7
    return 3.5

def caption(frame):
    if frame<=22:return '01  安装支架','先把安装框固定在面板边缘，开关原有结构保留。'
    if frame<=40:return '02  装入舵机和控制板','托架固定舵机；原装舵盘连接橙色双向按压臂。'
    if frame<=53:return '03  合上控制盒','连接控制线，合上盒盖，再固定螺钉。'
    if frame<=72:return '04  装配完成','左边负责按开关，右边是联网控制盒。'
    if frame<=99:return '05  按下翘起的上端','收到开灯指令后，舵机带动上方压脚向墙面按压。'
    if frame<=116:return '06  机械臂回中','上端保持压下、下端保持翘起；开关不会回平。'
    if frame<=147:return '07  反向按下另一端','收到关灯指令后，机械臂反转，下方压脚按下下端。'
    if frame<=168:return '08  再次收回机械臂','下端保持压下、上端保持翘起，恢复待机间隙。'
    return '09  完整装配与待机','机械臂只在操作时动作；翘板一直保持在两个倾斜状态之一。'

def inset(draw,frame):
    x,y,w,h=805,126,287,165
    draw.rounded_rectangle((x,y,x+w,y+h),radius=14,fill=NAVY,outline=(63,82,96),width=1)
    draw.text((x+16,y+12),'翘板侧视 · 倾角放大',font=font(17,True),fill=WHITE)
    cx,cy=x+w/2,y+91
    angle=math.radians(state(frame)/3.5*12)
    length=155
    dx=math.cos(angle)*length/2;dy=math.sin(angle)*length/2
    draw.line((cx-dx,cy-dy,cx+dx,cy+dy),fill=WHITE,width=10)
    draw.polygon([(cx,cy+9),(cx-12,cy+35),(cx+12,cy+35)],fill=MUTED)
    draw.text((x+28,y+133),'上端',font=font(16),fill=ORANGE)
    draw.text((x+w-65,y+133),'下端',font=font(16),fill=TEAL)
    draw.ellipse((cx-dx-7,cy-dy-7,cx-dx+7,cy-dy+7),fill=ORANGE)
    draw.ellipse((cx+dx-7,cy+dy-7,cx+dx+7,cy+dy+7),fill=TEAL)

def decorate(image,frame,still=False):
    image=ImageEnhance.Brightness(image.convert('RGB')).enhance(1.19)
    d=ImageDraw.Draw(image)
    d.rectangle((0,0,1120,105),fill=NAVY)
    if still:
        title='86 型翘板开关 · 装配后的样子'
        subtitle='橙色机械臂负责按压，蓝色舵机负责转动，右侧控制盒负责联网。'
    else:title,subtitle=caption(frame)
    d.text((30,17),title,font=font(28,True),fill=WHITE)
    d.text((30,61),subtitle,font=font(20),fill=MUTED)
    d.rectangle((0,782,1120,840),fill=NAVY)
    d.text((30,795),'动作与装配示意；未做实物试装、受力验证及联网测试。',font=font(18),fill=MUTED)
    d.rounded_rectangle((862,794,1092,825),radius=10,fill=(39,55,67))
    d.text((875,797),'翘板保持倾斜 · 不回平',font=font(16,True),fill=TEAL)
    if 74<=frame<=168 and not still:inset(d,frame)
    if not still:
        progress=(frame-1)/215
        d.rectangle((0,836,int(1120*progress),839),fill=ORANGE)
    return image

def tag(d,label,box,point,color):
    x,y,w=box;h=39
    d.rounded_rectangle((x,y,x+w,y+h),radius=9,fill=NAVY,outline=color,width=2)
    d.text((x+12,y+8),label,font=font(18,True),fill=WHITE)
    start=(x+w/2,y+h if point[1]>y+h else y)
    d.line((start,point),fill=color,width=2)
    d.ellipse((point[0]-4,point[1]-4,point[0]+4,point[1]+4),fill=color)

still=decorate(Image.open(ROOT/'assembled_raw.png'),60,True)
d=ImageDraw.Draw(still)
tag(d,'安装框',(32,136,112),(185,339),MUTED)
tag(d,'双向按压臂',(305,133,154),(461,360),ORANGE)
tag(d,'舵机与固定绑带',(418,650,192),(573,484),MUTED)
tag(d,'联网控制盒',(826,152,158),(879,405),TEAL)
tag(d,'舵机连接线',(649,121,155),(671,324),MUTED)
still.save(ROOT/'assembled_annotated.png')

out=ROOT/'captioned_frames';out.mkdir(exist_ok=True)
paths=sorted((ROOT/'frames').glob('frame_*.png'))
if len(paths)!=216:raise RuntimeError(f'Expected 216 Blender frames, got {len(paths)}')
for i,path in enumerate(paths,1):
    im=decorate(Image.open(path),i)
    im.save(out/f'frame_{i:04d}.png',compress_level=2)
print('Captioned all 216 frames',flush=True)

ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
subprocess.run([ffmpeg,'-y','-v','error','-framerate','12','-i',str(out/'frame_%04d.png'),'-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(ROOT/'assembly_and_operation.mp4')],check=True)
subprocess.run([ffmpeg,'-y','-v','error','-i',str(ROOT/'assembly_and_operation.mp4'),'-filter_complex','fps=8,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3','-loop','0',str(ROOT/'assembly_and_operation.gif')],check=True)

chosen=[20,60,99,116,147,164]
sheet=Image.new('RGB',(1120,3*454),NAVY)
for j,f in enumerate(chosen):
    im=Image.open(out/f'frame_{f:04d}.png');im.thumbnail((560,420))
    x=(j%2)*560;y=(j//2)*454
    sheet.paste(im,(x,y))
    ImageDraw.Draw(sheet).text((x+15,y+423),f'F{f:03d}  {caption(f)[0]}',font=font(17),fill=WHITE)
sheet.save(ROOT/'animation_contact_sheet.jpg',quality=90)
manifest={'fps':12,'frames':216,'duration_seconds':18,'files':['assembled_annotated.png','assembly_and_operation.mp4','assembly_and_operation.gif','animation_contact_sheet.jpg','switch_robot_assembled_v02.blend'],'rocker_states_deg':[-3.5,3.5],'arm_press_deg':[-11.4,11.4],'note':'Illustrative animation. Remote commands and electrical state are not implemented or verified.'}
(ROOT/'demo_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False),flush=True)
