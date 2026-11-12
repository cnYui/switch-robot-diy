"""核对预期故障、步长收敛和接口实测证据，生成图表及可交互测试报告。"""
import csv
import hashlib
import html
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,
                     'figure.facecolor':'white','savefig.facecolor':'white'})
suite=json.loads((OUT/'suite.json').read_text())
cases={x['name']:x for x in suite['cases']}
negative={
 'v01_existing_stl':'INITIAL_PRELOAD',
 'v02_animation_geometry':'FRAME_OR_CRADLE_COLLISION',
 'v05_rigid_power_loss':'NO_RETRACTION_WITHOUT_POWER',
 'v06_power_loss':'NO_RETRACTION_WITHOUT_POWER',
 'v06_weak_servo':'TARGET_NOT_REACHED',
 'v06_stiff_switch':'TARGET_NOT_REACHED',
 'v06_switch_beyond_pad_capacity':'PAD_BOTTOMED_OUT',
 'v06_insufficient_stroke':'TARGET_NOT_REACHED',
 'v06_excessive_stroke':'EXCEEDS_ASSUMED_6N_TEST_LIMIT',
 'v06_large_mount_offset':'FRAME_OR_CRADLE_COLLISION',
 'v06_large_height_offset':'TARGET_NOT_REACHED',
 'v06_narrow_rocker_missed':'TARGET_NOT_REACHED',
 'v06_no_contact_negative_control':'TARGET_NOT_REACHED',
}
checks=[]
for name,result in cases.items():
    expected_fault=negative.get(name)
    matched=expected_fault in result['defects'] if expected_fault else result['mechanical_check_passed']
    checks.append({'case':name,'expected_fault':expected_fault,'matched_expectation':matched,
                   'observed_defects':result['defects']})
assert all(x['matched_expectation']for x in checks),checks
assert all(not x['runtime_warnings'] and not any(x['warnings'])for x in cases.values())
assert len(cases['v06_twenty_cycles']['transitions'])==20
assert len(cases['v06_no_contact_negative_control']['transitions'])==0
assert cases['v06_on_then_hold']['final']['rocker_state']=='ON'
assert cases['v06_off_then_hold']['final']['rocker_state']=='OFF'
assert json.loads((OUT/'interface_tests.json').read_text())['passed']
exact=json.loads((OUT/'exact_cad_intersections.json').read_text())
assert exact['arm_v01']['neutral_rocker_overlap_mm3']>1
assert exact['arm_v02']['maximum_cradle_overlap_mm3']>.001
assert exact['arm_v05']['maximum_cradle_overlap_mm3']<1e-6
assert exact['arm_v06']['neutral_rocker_overlap_mm3']<1e-6
assert exact['arm_v06']['maximum_cradle_overlap_mm3']<1e-6
# 修复后的关键结论也在这里断言，而不是只靠人工阅读。
assert cases['v06_power_loss_with_return_spring']['mechanical_check_passed']
assert cases['v06_harder_switch_4N']['mechanical_check_passed']

nominal=cases['v06_nominal'];fine=cases['v06_dt_6p25e-05']
a=json.loads((OUT/'v06_nominal_trace.json').read_text())
b=json.loads((OUT/'v06_dt_6p25e-05_trace.json').read_text())
ta=np.array([x['time_s']for x in a]);tb=np.array([x['time_s']for x in b])
convergence={}
for field in ['arm_deg','rocker_deg']:
    delta=np.array([x[field]for x in a])-np.interp(ta,tb,[x[field]for x in b])
    convergence[field+'_max_delta']=float(np.max(abs(delta)))
fa=nominal['metrics']['peak_contact_force_n'];fb=fine['metrics']['peak_contact_force_n']
convergence['peak_force_relative_delta']=abs(fa-fb)/fb
convergence['baseline_timestep_s']=.000125
convergence['fine_timestep_s']=.0000625
assert convergence['peak_force_relative_delta']<.10,convergence
assert convergence['arm_deg_max_delta']<.5 and convergence['rocker_deg_max_delta']<.5,convergence
quality={'harness_passed':True,'named_checks':checks,'numerical_warnings':0,
         'convergence':convergence,'negative_control_no_contact_no_flip':True,
         'physical_calibration_performed':False,'real_firmware_binary_executed':False}
(OUT/'validation.json').write_text(json.dumps(quality,indent=2),encoding='utf8')

fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True)
for field,label,color in [('arm_deg','按压臂','#ce6b20'),('rocker_deg','翘板','#1486bf')]:
    axes[0].plot(ta,[x[field]for x in a],label=label,color=color,lw=2)
axes[0].set_ylabel('角度 / °');axes[0].legend(loc='upper right')
axes[1].plot(ta,[x['contact_n']for x in a],color='#248762',lw=1.5)
axes[1].axhline(6,color='#b34b40',ls='--',label='人为设定的 6 N 测试限值')
axes[1].set_ylabel('接触力 / N');axes[1].legend(loc='upper right')
axes[2].plot(ta,[x['servo_torque_nm']for x in a],color='#5e589c',lw=1.5)
axes[2].set_ylabel('输出力矩 / N·m');axes[2].set_xlabel('仿真时间 / s')
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('V0.6：开 → 退回保持 → 关 → 退回保持\nMuJoCo 接触求解；参数未实测校准',fontsize=14)
fig.tight_layout();fig.savefig(OUT/'nominal_curves.png',dpi=160);plt.close(fig)

def heat_map(rows,filename,title,ylabel):
    heights=sorted(set(x['height_offset_mm']for x in rows))
    angles=sorted(set(x['press_angle_deg']for x in rows))
    values=np.array([[next(x for x in rows if x['height_offset_mm']==h and x['press_angle_deg']==ang)['pass']for ang in angles]for h in heights],float)
    fig,ax=plt.subplots(figsize=(10,5.8));ax.imshow(values,cmap=matplotlib.colors.ListedColormap(['#efd3ca','#c4dfcd']),aspect='auto',vmin=0,vmax=1)
    for i,h in enumerate(heights):
        for j,ang in enumerate(angles):
            item=next(x for x in rows if x['height_offset_mm']==h and x['press_angle_deg']==ang)
            if item['pass']:text=f"通过\n{item['peak_force_n']:.1f} N"
            elif 'ARM_NOT_RETRACTED' in item['defects']:text='退不回'
            elif 'EXCEEDS_ASSUMED_6N_TEST_LIMIT' in item['defects'] or 'PAD_BOTTOMED_OUT' in item['defects']:text=f"力过大\n{item['peak_force_n']:.1f} N"
            else:text='未翻转'
            ax.text(j,i,text,ha='center',va='center',fontsize=10)
    ax.set_xticks(range(len(angles)),[str(x)for x in angles]);ax.set_yticks(range(len(heights)),[str(x)for x in heights])
    ax.set_xlabel('按压命令角度 / °');ax.set_ylabel(ylabel)
    ax.set_title(title,pad=15)
    fig.tight_layout();fig.savefig(OUT/filename,dpi=170);plt.close(fig)
heat_map(suite['height_stroke_sweep'],'height_stroke_map.png',
         'V0.6：安装高度与行程的联合扫描（弹性压垫 + 1.0 mm 垫高）\n只对本次假设的 3 N 开关及舵机参数成立；通过不代表实物已验证',
         '安装高度相对名义值的偏差 / mm（正值离开关更远）')
heat_map(suite['legacy_v05_height_stroke_sweep'],'legacy_v05_height_stroke_map.png',
         '修复前 V0.5（刚性压垫）：同样的扫描\n通过区域窄，且高度偏低 1 mm 时全部退不回',
         '安装高度偏差 / mm（正值离开关更远）')

with (OUT/'case_summary.csv').open('w',encoding='utf-8-sig',newline='')as f:
    w=csv.writer(f);w.writerow(['case','expected_failure','observed_defects','target_reached','flips','peak_force_N','rest_clearance_mm','warnings'])
    for name,r in cases.items():w.writerow([name,negative.get(name,''),'|'.join(r['defects']),
          r['expected_state'] is None or r['final']['rocker_state']==r['expected_state'],len(r['transitions']),
          r['metrics']['peak_contact_force_n'],r['observations']['rest_clearance_both_rocker_states_mm'],len(r['runtime_warnings'])])
with (OUT/'parameter_sweep.csv').open('w',encoding='utf-8-sig',newline='')as f:
    w=csv.writer(f);w.writerow(['height_offset_mm','press_angle_deg','pass','peak_force_N','defects'])
    for x in suite['height_stroke_sweep']:w.writerow([x['height_offset_mm'],x['press_angle_deg'],x['pass'],x['peak_force_n'],'|'.join(x['defects'])])

random_pass=sum(x['pass']for x in suite['randomized_tolerances'])
total=(len(cases)+len(suite['height_stroke_sweep'])+len(suite['legacy_v05_height_stroke_sweep'])
       +len(suite['force_torque_sweep'])+len(suite['randomized_tolerances']))


def passing_band(rows,angle):
    """某一固定按压角下，能通过的最长连续安装高度偏差区间（mm）。"""
    offsets=sorted(x['height_offset_mm']for x in rows if x['press_angle_deg']==angle)
    best,current=None,None
    for off in offsets:
        ok=next(x for x in rows if x['height_offset_mm']==off and x['press_angle_deg']==angle)['pass']
        if ok:
            current=(current[0] if current else off,off)
            if best is None or current[1]-current[0]>best[1]-best[0]:best=current
        else:current=None
    return best
band_new=passing_band(suite['height_stroke_sweep'],17)
# 修复前选各自最好的固定按压角来比较，避免拿一个对它不利的角度当对照。
band_old,old_angle=None,None
for angle in sorted(set(x['press_angle_deg']for x in suite['legacy_v05_height_stroke_sweep'])):
    band=passing_band(suite['legacy_v05_height_stroke_sweep'],angle)
    if band and (band_old is None or band[1]-band[0]>band_old[1]-band_old[0]):band_old,old_angle=band,angle
assert band_new and band_old and band_new[1]-band_new[0]>band_old[1]-band_old[0],(band_new,band_old)
assert band_new[0]<=-1 and band_new[1]>=1,band_new  # 名义垫高 ±1 mm 必须落在通过区间内
summary={'simulation_scenarios':total,'named_functional_cases':len(cases),
         'expected_failures_detected':len(negative),'routine_cases_passed':len(cases)-len(negative),
         'consecutive_operations_passed':20,'randomized_parameter_cases_passed':random_pass,
         'randomized_parameter_cases':len(suite['randomized_tolerances']),
         'nominal_peak_contact_force_n':fa,
         'nominal_rest_clearance_mm':nominal['observations']['rest_clearance_both_rocker_states_mm'],
         'calibration_status':'ASSUMED_NOT_MEASURED',
         'do_not_interpret_as_reliability_probability':True}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')

rows=''.join(f"<tr><td>{html.escape(name)}</td><td>{'预期故障' if name in negative else '正常功能'}</td><td class='{('fault' if name in negative else 'ok')}'>{html.escape(', '.join(r['defects']) or '通过')}</td><td>{len(r['transitions'])}</td><td>{r['metrics']['peak_contact_force_n']:.2f}</td><td>{r['observations']['rest_clearance_both_rocker_states_mm']:.2f}</td></tr>"for name,r in cases.items())
report='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>开关机器人 · MuJoCo 测试</title>
<style>body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;color:#24313b;background:#f1f3f4;margin:0}main{max-width:1120px;margin:auto;padding:32px 24px 64px}h1{font-size:30px}h2{font-size:22px;margin-top:42px}video,img{width:100%;height:auto;background:#17212a}p{max-width:980px}.note{border-left:4px solid #c7832b;padding:12px 20px;background:#fff7e7}table{border-collapse:collapse;width:100%;font-size:13px;background:white}td,th{padding:10px;border-bottom:1px solid #d8e0e5;text-align:left}.ok{color:#277749}.fault{color:#a55638}a{color:#256983}canvas{width:100%;background:#fff;border:1px solid #ccd5dc}input[type=range]{width:100%}.scroll{overflow:auto}select{font:inherit;padding:8px}pre{white-space:pre-wrap;background:white;padding:16px}</style>
<main><h1>开关机器人 · MuJoCo 接触测试</h1><p>本次完成 TOTAL 个仿真场景：COUNT_CASES 个具名功能/故障用例、COUNT_SWEEP 组 V0.6 安装高度与行程扫描、COUNT_LEGACY 组修复前刚性压垫的对照扫描、COUNT_FT 组力矩/阻力扫描、COUNT_TOL 组组合参数扰动。仿真版本 MuJoCo VERSION。</p>
<p class="note">参数未实测校准。测试覆盖机械运动、刚体碰撞与虚拟 PWM 控制链路。ESP32 真固件、电源电流、Wi-Fi/蓝牙、打印件强度、粘贴与螺丝可靠性尚未验证。6 N 是本次人为设定的测试限值，不是实测开关或打印件的承载极限。</p>
<video controls preload="metadata" poster="v06_nominal_rest.png" src="mujoco_full_test.mp4"></video>
<p>视频回放 MuJoCo 求解轨迹，按 0.6 倍速度显示。侧视图用于观察翘板翻转与接触。</p>
<h2>发现与修改</h2><p>旧 STL 的中立位置与翘板有约 0.216 mm 穿入，原网格布尔交集约 2.677 mm³。动画版抬高按压头后，中立干涉消失，但约 5° 附近的垫座仍与支架有细小交集。刚体模型在此受阻；这种楔紧的巨大反力不能用于预测真实塑料强度。</p>
<p>V0.5 把垫座宽度从 7 mm 改为 5 mm，原始网格交集扫描中不再有同一干涉，但它仍是刚性压垫：按压命令角度的可用范围只有约 3.4°，安装高度偏低 1 mm 时中立空隙不足，臂退不回，断电后臂会停在按压位置。</p>
<p>V0.6 做了四处修改：① 以通过交集检查的 V0.5 几何为正式按压臂；② 指杆下端抬高到 17.5 mm，下面粘 4×7×5.5 mm 的弹性压垫（泡棉或 TPU；本仿真假设刚度 2 N/mm、有效行程 2.5 mm），过行程由压垫吸收；③ 支架整体垫高 1.0 mm（每个安装脚下叠两片 M3 平垫圈），中立空隙约 CLEARANCE mm；④ 名义按压角改为 17°。同类扫描里，修复前即使选最好的固定按压角（OLD_ANGLE°），可通过的安装高度偏差范围也只有 BAND_OLD mm；V0.6 在名义 17° 下为 BAND_NEW mm。</p>
<p>V0.6 完成 20 次连续开关，模型按压峰值约 FORCE N。COUNT_TOL 组扰动（含 ±1 mm 安装高度、±1.5° 按压角、±20% 压垫刚度）有 RANDOM 组通过；这些人为分布不能转换成实物可靠性概率。代价是：压垫最大弹簧力约 5 N，翻转阻力峰值达到 4.5 N 以上的开关会把压垫压到底（见 v06_switch_beyond_pad_capacity）。没有回位弹簧时，断电后压垫只能把臂推到刚脱离接触的位置；加 0.05 N·m/rad 的回位弹簧后臂回中，但该弹簧尚未进入 CAD，真实舵机的反向转动阻力也没有测量。</p>
<img src="nominal_curves.png" alt="实际求解曲线"><h2>安装与行程边界</h2><img src="height_stroke_map.png" alt="V0.6 安装高度与行程参数扫描">
<p>图中的数值仅适用于所设定的舵机、质量、摩擦、压垫刚度和 3 N 翻转阻力。实际安装后需要测量高度并校准行程。</p>
<img src="legacy_v05_height_stroke_map.png" alt="修复前的同类扫描">
<h2>检查逐时刻记录</h2><label>用例 <select id="case"></select></label><input id="time" type="range" min="0" max="1000" value="0"><div id="readout"></div><canvas id="curve" width="1080" height="260"></canvas>
<h2>功能及故障用例</h2><div class="scroll"><table><thead><tr><th>用例</th><th>用途</th><th>观察结果</th><th>翻转次数</th><th>峰值力/N</th><th>两稳态空隙/mm</th></tr></thead><tbody>ROWS</tbody></table></div>
<h2>PCB 与壳体</h2><p>已把正式 PCB、元件库模型和 V0.3 壳体放入同一场景。未剪元件引脚有顶到盒底的顶点；按板底以下保留 1.5 mm 引脚的假设修剪后，顶点包含检查未发现板件进入壳体或盒盖。此检查不是完整三角面相交或制造公差证明。元件库高度有近似，外接主控、插头和线材弯曲空间仍需核对。</p>
<h2>文件与实时操作</h2><p><a href="../V06_press_arm.stl">V0.6 按压臂 STL</a> · <a href="case_summary.csv">用例 CSV</a> · <a href="parameter_sweep.csv">参数扫描 CSV</a> · <a href="validation.json">验证证据</a> · <a href="suite.json">完整结果 JSON</a> · <a href="pcb_case_check.json">壳体检查记录</a></p>
<p>在 simulation 目录双击“打开实时仿真.cmd”。键 1 开、0 关、S 退回、P 切换自动循环；鼠标可旋转缩放模型。实时窗口调用完整的 Python 驱动与双稳态阻力模型。单独打开 XML 只会载入几何、关节和执行器定义。</p>
<p>本机 JSON/PWM 接口的进程与套接字已实际联调，测试包括非法输入、ON/OFF 请求、PWM 输入及超时回中。该接口当前仅驱动仿真；真实舵机是否超时回中，取决于之后实现的真板固件与舵机本身。</p>
<p><a href="https://mujoco.readthedocs.io/en/stable/modeling.html">MuJoCo 官方建模文档</a> · <a href="https://towerpro.com.tw/product/sg90-7/">TowerPro SG90 参考规格</a> · <a href="https://docs.m5stack.com/en/accessory/SG90_Servo">M5Stack 同名舵机的不同规格</a></p>
<script>const traces=TRACES;const select=document.getElementById('case'),slider=document.getElementById('time'),cv=document.getElementById('curve'),ctx=cv.getContext('2d');for(const name of Object.keys(traces)){const op=document.createElement('option');op.textContent=name;op.value=name;select.append(op)}select.value='v06_nominal';function update(){const a=traces[select.value],i=Math.round((a.length-1)*Number(slider.value)/1000),p=a[i];document.getElementById('readout').textContent=`t=${p.time_s.toFixed(3)}s | ${p.phase} | ${p.rocker_state} | 臂 ${p.arm_deg.toFixed(2)}° | 翘板 ${p.rocker_deg.toFixed(2)}° | 接触 ${p.contact_n.toFixed(2)} N`;ctx.clearRect(0,0,cv.width,cv.height);ctx.strokeStyle='#d9e0e4';for(let k=0;k<5;k++){ctx.beginPath();ctx.moveTo(30,30+k*45);ctx.lineTo(1050,30+k*45);ctx.stroke()}for(const [key,color,scale,center]of [['arm_deg','#ca7429',7,130],['rocker_deg','#2489bf',7,130],['contact_n','#2d8e61',14,230]]){ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=2;a.forEach((v,j)=>{const x=30+j/(a.length-1)*1020,y=center-v[key]*scale;j?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke()}const x=30+i/(a.length-1)*1020;ctx.strokeStyle='#333';ctx.beginPath();ctx.moveTo(x,20);ctx.lineTo(x,240);ctx.stroke()}select.onchange=update;slider.oninput=update;update();</script></main></html>'''
traces={name:json.loads((OUT/(name+'_trace.json')).read_text())for name in cases}
for key,value in [('TOTAL',str(total)),('VERSION',suite['mujoco_version']),('FORCE',f'{fa:.2f}'),
                  ('COUNT_CASES',str(len(cases))),('COUNT_SWEEP',str(len(suite['height_stroke_sweep']))),
                  ('COUNT_LEGACY',str(len(suite['legacy_v05_height_stroke_sweep']))),
                  ('COUNT_FT',str(len(suite['force_torque_sweep']))),('COUNT_TOL',str(len(suite['randomized_tolerances']))),
                  ('BAND_NEW',f'{band_new[0]:+g} ~ {band_new[1]:+g}'),('BAND_OLD',f'{band_old[0]:+g} ~ {band_old[1]:+g}'),
                  ('OLD_ANGLE',f'{old_angle:g}'),
                  ('CLEARANCE',f"{summary['nominal_rest_clearance_mm']:.2f}"),('RANDOM',str(random_pass)),
                  ('ROWS',rows),('TRACES',json.dumps(traces,ensure_ascii=False).replace('</','<\\/'))]:report=report.replace(key,value)
(OUT/'index.html').write_text(report,encoding='utf8')
print(json.dumps({'summary':summary,'convergence':convergence,'harness_passed':True}),flush=True)
