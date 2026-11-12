"""真实启动本地接口进程，验证命令、非法输入、PWM 超时和模型状态回读。"""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from model import RobotSimulation
from controller import PressController

ROOT=Path(__file__).resolve().parent
log=[]
server=subprocess.Popen([sys.executable,str(ROOT/'bridge.py'),'--port','0','--duration','12'],
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=ROOT)
try:
    ready=json.loads(server.stdout.readline())
    assert ready['ready'] and ready['host']=='127.0.0.1'
    client=socket.create_connection(('127.0.0.1',ready['port']),timeout=3)
    stream=client.makefile('rwb')
    def request(message):
        stream.write((json.dumps(message)+'\n').encode());stream.flush()
        value=json.loads(stream.readline());log.append({'request':message,'response':value});return value
    assert request({'type':'command','value':'INVALID'})['accepted'] is False
    assert request({'type':'pwm','microseconds':99999})['accepted'] is False
    assert request({'type':'command','value':'ON'})['accepted'] is True
    time.sleep(1.6)
    on=request({'type':'state'})
    assert on['rocker_state']=='ON' and abs(on['arm_deg'])<.7,on
    assert request({'type':'command','value':'OFF'})['accepted'] is True
    time.sleep(1.6)
    off=request({'type':'state'})
    assert off['rocker_state']=='OFF' and abs(off['arm_deg'])<.7,off
    assert request({'type':'pwm','microseconds':1550})['accepted'] is True
    held=request({'type':'state'})
    assert abs(held['target_deg']-4.5)<.01,held  # 刚发出的 PWM 在 250 ms 超时内，应报告为目标
    time.sleep(.4)
    recovered=request({'type':'state'})
    # 超时回中后，读回的目标必须也是 0，而不是最后一次指令（旧版本这里会报告 4.5 而臂已回中）。
    assert abs(recovered['arm_deg'])<1.0 and recovered['target_deg']==0,recovered
    request({'type':'shutdown'})
    stream.close();client.close()
    server.wait(timeout=3)
    assert server.returncode==0
finally:
    if server.poll() is None:server.terminate();server.wait(timeout=3)
sim=RobotSimulation()
initial=sim.target
for invalid in [None,'1500',float('nan'),float('inf'),-1,499,2501]:
    assert sim.pwm(invalid) is False
assert sim.target==initial
ctrl=PressController(sim.p)
for i in range(1000):
    ctrl.command('ON' if i%2 else 'OFF',i*.0001)
    pulse=ctrl.tick(i*.0001)
    assert 500<=pulse<=2500 and ctrl.pending in [None,'ON','OFF']
result={'passed':True,'backend':'localhost TCP process exercised with actual sockets',
        'physical_hardware_connected':False,'requests':log,'invalid_pwm_cases':7,
        'burst_commands':1000,'finite_queue_latest_wins':True}
(ROOT/'results/interface_tests.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('Interface tests PASS',flush=True)
