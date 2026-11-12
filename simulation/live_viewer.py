"""打开可实时操作的 MuJoCo 样机；键 1 开、0 关、S 退回、P 自动循环。"""
import queue
import time
import mujoco
import mujoco.viewer
from model import RobotSimulation
from controller import PressController


def main():
    sim=RobotSimulation()
    controller=PressController(sim.p)
    commands=queue.SimpleQueue()
    def key(code):
        if code in [49,48,83,115,80,112]:commands.put(code)
    auto=True;next_auto=.5;auto_state='ON';last_pwm=-1
    start=time.perf_counter()
    with mujoco.viewer.launch_passive(sim.model,sim.data,key_callback=key) as viewer:
        viewer.cam.lookat[:]=[.05,-.017,.14]
        viewer.cam.distance=.27;viewer.cam.azimuth=100;viewer.cam.elevation=-18
        viewer.opt.geomgroup[3]=0
        while viewer.is_running():
            elapsed=time.perf_counter()-start
            while sim.time<elapsed:
                while not commands.empty():
                    code=commands.get()
                    if code in [80,112]:auto=not auto;next_auto=sim.time+.5
                    else:
                        auto=False
                        controller.command({49:'ON',48:'OFF',83:'STOP',115:'STOP'}[code],sim.time)
                if auto and sim.time>=next_auto:
                    controller.command(auto_state,sim.time)
                    auto_state='OFF' if auto_state=='ON' else 'ON'
                    next_auto=sim.time+1.8
                if sim.time-last_pwm>=sim.p['pwm_period_s']-1e-8:
                    sim.pwm(controller.tick(sim.time));last_pwm=sim.time
                sim.step()
            viewer.sync()
            time.sleep(.008)


if __name__=='__main__':main()
