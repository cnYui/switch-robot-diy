"""用 MuJoCo 原生渲染器回放求解轨迹，叠加真实记录的力、角度和测试结论。"""
import json
import math
from pathlib import Path
import imageio.v2 as imageio
import mujoco
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'
FONT=Path('C:/Windows/Fonts/msyh.ttc')
def font(size):return ImageFont.truetype(str(FONT),size)
F18,F20,F24,F28=font(18),font(20),font(24),font(28)
BG=(19,27,35);PANEL=(26,36,45);INK=(229,236,239);MUTED=(157,178,191)
AMBER=(255,167,68);BLUE=(94,192,255);RED=(255,119,112);GREEN=(115,223,167)
PHASE={'IDLE':'待机','PRESS':'按压','RETRACT':'退回'}


def chart_base(trace,duration):
    im=Image.new('RGB',(1280,328),BG);d=ImageDraw.Draw(im)
    angle_max=max(14,max(abs(x['arm_deg']) for x in trace)*1.15)
    force_max=max(7,max(x['contact_n'] for x in trace)*1.15)
    regions=[(55,64,560,205,angle_max,'角度 / °'),(705,64,525,205,force_max,'按压接触力 / N')]
    d.text((36,12),'按压臂角度',font=F20,fill=AMBER);d.text((193,12),'翘板角度',font=F20,fill=BLUE)
    d.text((690,12),'MuJoCo 计算值，未实测校准',font=F20,fill=MUTED)
    for i,(x,y,w,h,maximum,label) in enumerate(regions):
        d.text((x-20,y-30),label,font=F18,fill=MUTED)
        for j in range(5):
            yy=y+j*h/4;d.line((x,yy,x+w,yy),fill=(51,63,74))
            value=maximum*(1-j/4) if i else maximum*(1-j/2)
            d.text((x-45,yy-10),f'{value:.0f}',font=F18,fill=MUTED)
        for j in range(5):
            xx=x+w*j/4;d.line((xx,y,xx,y+h),fill=(38,50,60))
            d.text((xx-12,y+h+9),f'{duration*j/4:.1f}',font=F18,fill=MUTED)
        d.text((x+w-15,y+h+9),'s',font=F18,fill=MUTED)
    def angle_point(t,v):
        x,y,w,h,maximum,_=regions[0]
        return x+w*t/duration,y+h/2-h*v/(2*maximum)
    def force_point(t,v):
        x,y,w,h,maximum,_=regions[1]
        return x+w*t/duration,y+h-h*v/maximum
    for field,color in [('arm_deg',AMBER),('rocker_deg',BLUE)]:
        d.line([angle_point(x['time_s'],x[field]) for x in trace],fill=color,width=3)
    d.line([force_point(x['time_s'],x['contact_n'])for x in trace],fill=GREEN,width=3)
    fy=force_point(0,6)[1]
    d.line((705,fy,1230,fy),fill=RED,width=1)
    d.text((1020,fy-24),'6 N 测试限值',font=F18,fill=RED)
    d.text((34,305),'原始轨迹以 200 Hz 保存；画面按求解结果回放。',font=F18,fill=MUTED)
    return im,regions


def draw_frame(r,trace,states,index,renderer,side_renderer,camera,side_camera,base,regions,title,note):
    data=r['data'];model=r['model'];data.qpos[:]=states[index]
    data.qvel[:]=0;mujoco.mj_forward(model,data)
    renderer.update_scene(data,camera=camera)
    image=Image.new('RGB',(1280,896),BG)
    image.paste(Image.fromarray(renderer.render()),(0,56))
    opt=mujoco.MjvOption();mujoco.mjv_defaultOption(opt)
    opt.geomgroup[3]=0
    opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT]=True
    side_renderer.update_scene(data,camera=side_camera,scene_option=opt)
    image.paste(Image.fromarray(side_renderer.render()),(800,56))
    d=ImageDraw.Draw(image)
    d.text((20,12),title,font=F28,fill=INK)
    d.text((1065,18),'参数未实测校准',font=F18,fill=AMBER)
    d.rounded_rectangle((14,70,350,105),radius=5,fill=BG)
    d.text((24,76),'打印件、PCB 与外壳同一场景',font=F18,fill=INK)
    d.rectangle((808,62,1258,91),fill=BG)
    d.text((817,65),'侧视：接触点 / 翘板两个稳定位置',font=F18,fill=INK)
    d.rectangle((800,356,1280,568),fill=PANEL)
    sample=trace[index]
    state='开 ON' if sample['rocker_state']=='ON' else '关 OFF'
    d.text((820,366),f"状态 {state}   t={sample['time_s']:.2f} s",font=F24,fill=GREEN if state.startswith('开') else BLUE)
    d.text((820,406),f"臂角 {sample['arm_deg']:+.1f}°   翘板 {sample['rocker_deg']:+.2f}°",font=F20,fill=INK)
    d.text((820,439),f"接触力 {sample['contact_n']:.2f} N   力矩 {sample['servo_torque_nm']:+.3f} N·m",font=F20,fill=INK)
    d.text((820,472),f"{PHASE.get(sample['phase'],sample['phase'])}   支架接触：{'有' if sample['forbidden_n']>.05 else '无'}",font=F20,fill=INK)
    d.text((820,513),note,font=F18,fill=AMBER)
    graph=base.copy();gd=ImageDraw.Draw(graph)
    for x,y,w,h,maximum,label in regions:
        xx=x+w*sample['time_s']/r['result']['duration_s']
        gd.line((xx,y,xx,y+h),fill=INK,width=2)
    image.paste(graph,(0,568))
    return image


def render_clip(name,title,note,writer,speed=.5,capture=False):
    result=json.loads((OUT/(name+'.json')).read_text())
    trace=json.loads((OUT/(name+'_trace.json')).read_text())
    history=np.load(OUT/(name+'_states.npz'))
    states,times=history['qpos'],history['time_s']
    model=mujoco.MjModel.from_xml_path(str(OUT/(name+'.xml')))
    data=mujoco.MjData(model)
    renderer=mujoco.Renderer(model,height=512,width=800)
    side=mujoco.Renderer(model,height=300,width=480)
    camera=mujoco.MjvCamera();mujoco.mjv_defaultCamera(camera)
    camera.lookat[:]=[.05,-.017,.14];camera.distance=.25;camera.azimuth=100;camera.elevation=-15
    camera2=mujoco.MjvCamera();mujoco.mjv_defaultCamera(camera2)
    camera2.lookat[:]=[.024,-.014,.14];camera2.distance=.10;camera2.azimuth=0;camera2.elevation=0
    camera2.orthographic=1
    base,regions=chart_base(trace,result['duration_s'])
    bundle={'model':model,'data':data,'result':result}
    try:
        total=math.ceil(result['duration_s']/speed*24)
        for frame in range(total):
            t=min(result['duration_s']-.005,frame/24*speed)
            index=int(np.clip(np.searchsorted(times,t),0,len(times)-1))
            im=draw_frame(bundle,trace,states,index,renderer,side,camera,camera2,base,regions,title,note)
            writer.append_data(np.array(im))
            captures={round(.70/speed*24):'_press.png',round(1.7/speed*24):'_rest.png'}
            if capture and frame in captures:
                im.save(OUT/(name+captures[frame]))
        print('Rendered',name,total,'frames',flush=True)
    finally:
        renderer.close();side.close()


def main():
    path=OUT/'mujoco_full_test.mp4'
    with imageio.get_writer(path,fps=24,codec='libx264',quality=7,
                             pixelformat='yuv420p',macro_block_size=16) as writer:
        clips=[
            ('v01_existing_stl','旧 STL：中立位置存在预压','几何干涉已由原网格交集复核'),
            ('v02_animation_geometry','动画版：抬高后仍有边缘干涉','刚体模型在约 5° 附近受阻'),
            ('v05_rigid_baseline','修复前 V0.5：刚性压垫','可用按压角窗口窄，高度偏低 1 mm 即退不回'),
            ('v06_nominal','修复后 V0.6：弹性压垫，按压、翻转、退回','退回后，翘板保持当前状态'),
            ('v06_harder_switch_4N','V0.6：翻转阻力 4 N 的更硬开关','仍在压垫能力内，压垫未压到底'),
            ('v06_switch_beyond_pad_capacity','边界：翻转阻力 5 N','压垫压到底，超出本设计的弹簧能力'),
            ('v06_weak_servo','故障测试：舵机力矩不足','0.025 N·m，目标状态未达到'),
            ('v06_excessive_stroke','故障测试：按压行程过大','超过人为设定的 6 N 测试限值'),
            ('v06_power_loss','故障测试：动作过程中断电','无回位弹簧：臂停在压垫刚脱离处，未回中'),
            ('v06_power_loss_with_return_spring','断电 + 回位弹簧 0.05 N·m/rad','臂回中；该弹簧尚未进入 CAD'),
        ]
        for name,title,note in clips:
            render_clip(name,title,note,writer,speed=.6,capture=name=='v06_nominal')
    print('Video saved',path,path.stat().st_size,flush=True)


if __name__=='__main__':main()
