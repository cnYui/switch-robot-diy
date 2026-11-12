"""在本机提供 JSON/PWM 仿真接口，供控制程序联调；不会访问或驱动真实硬件。"""
import argparse
import json
import selectors
import socket
import time
from model import RobotSimulation
from controller import PressController


def serve(port=8711, duration=None):
    sim=RobotSimulation()
    controller=PressController(sim.p)
    selector=selectors.DefaultSelector()
    listener=socket.socket()
    listener.bind(('127.0.0.1',port))
    listener.listen()
    listener.setblocking(False)
    selector.register(listener,selectors.EVENT_READ)
    buffers={}
    direct=False
    running=True
    start=time.perf_counter()
    last_pwm=-1
    print(json.dumps({'ready':True,'host':'127.0.0.1','port':listener.getsockname()[1],
                      'mode':'SIMULATION_ONLY_NO_PHYSICAL_HARDWARE'}),flush=True)

    def process(message):
        nonlocal direct,running
        typ=message.get('type')
        if typ=='command':
            accepted=controller.command(message.get('value'),sim.time)
            if accepted:direct=False
            return {'accepted':accepted,'physical_state_confirmed':False}
        if typ=='pwm':
            accepted=sim.pwm(message.get('microseconds'))
            if accepted:direct=True
            return {'accepted':accepted}
        if typ=='state':
            return {'mode':'SIMULATION_ONLY',**sim.sample(controller.phase),
                    'feedback_source':'MuJoCo model, not a real sensor'}
        if typ=='power':
            if type(message.get('enabled')) is not bool:return {'accepted':False}
            sim.servo_power=message['enabled']
            return {'accepted':True}
        if typ=='shutdown':
            running=False
            return {'accepted':True}
        return {'accepted':False,'error':'unsupported message'}

    try:
        while running and (duration is None or time.perf_counter()-start<duration):
            for key,_ in selector.select(timeout=0):
                if key.fileobj is listener:
                    client,_=listener.accept();client.setblocking(False)
                    buffers[client]=b'';selector.register(client,selectors.EVENT_READ)
                else:
                    client=key.fileobj
                    data=client.recv(4096)
                    if not data:
                        selector.unregister(client);buffers.pop(client,None);client.close();continue
                    buffers[client]+=data
                    if len(buffers[client])>8192:
                        selector.unregister(client);buffers.pop(client,None);client.close();continue
                    while b'\n' in buffers[client]:
                        line,buffers[client]=buffers[client].split(b'\n',1)
                        try:
                            request=json.loads(line)
                            response=process(request) if isinstance(request,dict) else {'accepted':False}
                        except (ValueError,TypeError):response={'accepted':False,'error':'invalid JSON/value'}
                        client.sendall((json.dumps(response,allow_nan=False)+'\n').encode())
            elapsed=time.perf_counter()-start
            # 小批量追上真实时间，远程请求可在循环之间处理。
            steps=0
            while sim.time<elapsed and steps<2000:
                if not direct and sim.time-last_pwm>=sim.p['pwm_period_s']-1e-8:
                    sim.pwm(controller.tick(sim.time));last_pwm=sim.time
                sim.step()
                steps+=1
            time.sleep(.001)
    finally:
        for client in list(buffers):client.close()
        listener.close();selector.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8711)
    parser.add_argument('--duration',type=float)
    args=parser.parse_args()
    serve(args.port,args.duration)
