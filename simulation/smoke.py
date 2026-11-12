from model import RobotSimulation, parameters
import math,json
for arm in ['arm_v01','arm_v02','arm_v05']:
 sim=RobotSimulation(parameters(arm_revision=arm))
 initial=[(sim.model.geom(c.geom1).name,sim.model.geom(c.geom2).name,round(c.dist*1000,4)) for c in sim.data.contact]
 trace=[]
 n=int(3/sim.p['timestep_s'])
 for step in range(n):
  t=sim.time
  deg=-11.4 if .4<=t<1.2 else (11.4 if 1.8<=t<2.6 else 0)
  if step%80==0:sim.pwm(1500+deg*sim.p['pwm_us_per_degree'])
  sim.step()
  if step%800==0:trace.append(sim.sample())
 print(arm,'initial',initial,'end',sim.sample(),'transitions',sim.transitions,'metrics',sim.metrics,'warnings',sim.warning_counts.tolist(),flush=True)
 print('trace',json.dumps(trace),flush=True)
