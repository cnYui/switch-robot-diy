from model import RobotSimulation,parameters
import mujoco
from PIL import Image,ImageDraw
from pathlib import Path
R=Path(__file__).resolve().parent
s=RobotSimulation()
r=mujoco.Renderer(s.model,height=720,width=960)
images=[]
for az in [-90,-65,-35,90]:
 c=mujoco.MjvCamera();mujoco.mjv_defaultCamera(c)
 c.lookat[:]=[.05,-.017,.14];c.distance=.30;c.azimuth=az;c.elevation=-18
 r.update_scene(s.data,camera=c);im=Image.fromarray(r.render());ImageDraw.Draw(im).text((20,20),str(az),fill='white');images.append(im)
out=Image.new('RGB',(1920,1440));
for i,im in enumerate(images):out.paste(im,((i%2)*960,(i//2)*720))
out.save(R/'results/view_previews.jpg');r.close();print('rendered')
