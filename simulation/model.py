"""生成具有真实 CAD 碰撞形状、双稳态开关及限矩舵机的 MuJoCo 数字样机。"""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'


def parameters(**overrides):
    p = json.loads((ROOT / 'parameters.json').read_text(encoding='utf8'))
    p.update(overrides)
    return p


def nums(values):
    return ' '.join(f'{x:.10g}' for x in values)


def make_xml(p):
    root = ET.Element('mujoco', model='86 rocker robot physical prototype')
    ET.SubElement(root, 'compiler', angle='radian', meshdir=str(ASSETS),
                  autolimits='true', inertiafromgeom='false', fusestatic='false')
    option = ET.SubElement(root, 'option', timestep=str(p['timestep_s']),
                           integrator='implicitfast', solver=p.get('solver','PGS'),
                           iterations=str(p.get('solver_iterations',200)),
                           tolerance='1e-10', cone=p.get('cone','pyramidal'), impratio='10', gravity='0 0 -9.81')
    ET.SubElement(option, 'flag', filterparent='disable', energy='enable',
                  contact='disable' if p.get('disable_contacts') else 'enable')
    ET.SubElement(root, 'size', memory='64M')
    ET.SubElement(root, 'statistic', center='.05 -.02 .14', extent='.24')
    vis = ET.SubElement(root, 'visual')
    ET.SubElement(vis, 'global', offwidth='1280', offheight='960')
    ET.SubElement(vis, 'quality', shadowsize='2048')
    ET.SubElement(vis, 'headlight', ambient='.45 .45 .45', diffuse='.7 .7 .7')
    ET.SubElement(vis, 'map', znear='.005', zfar='10')
    default = ET.SubElement(root, 'default')
    ET.SubElement(default, 'geom', solref=f"{p['contact_time_constant_s']} 1",
                  solimp='.95 .99 .0001', margin='0',
                  friction=f"{p['friction_coefficient']} .001 .0001", condim='3')
    assets = ET.SubElement(root, 'asset')
    ET.SubElement(assets, 'texture', name='sky', type='skybox', builtin='gradient',
                  rgb1='.18 .24 .30', rgb2='.38 .44 .49', width='512', height='512')
    for name in ['frame', 'cradle', 'servo_body', 'servo_shaft', 'rocker_original',
                 p['arm_revision'], 'case_v03', 'lid_v03_closed']:
        kwargs = {}
        if name == 'rocker_original':
            kwargs['scale'] = nums([p['rocker_width_mm'] / 60, p['rocker_height_mm'] / 64, 1])
        ET.SubElement(assets, 'mesh', name=name, file=name + '.obj', **kwargs)
    collision = {}
    for name in ['frame', 'cradle', p['arm_revision']]:
        info = json.loads((ASSETS / (name + '_collision.json')).read_text())
        collision[name] = info
        for i, file in enumerate(info['hulls']):
            ET.SubElement(assets, 'mesh', name=f'{name}_col_{i}', file=file)

    world = ET.SubElement(root, 'worldbody')
    ET.SubElement(world, 'light', pos='-.12 -.2 .38', dir='.3 .8 -1', directional='true')
    ET.SubElement(world, 'light', pos='.22 -.03 .30', dir='-.2 .4 -1', diffuse='.4 .4 .4')
    ET.SubElement(world, 'geom', name='wall', type='box', pos='.04 .006 .14',
                  size='.23 .004 .18', rgba='.23 .29 .34 1', contype='0', conaffinity='0')
    cad = ET.SubElement(world, 'body', name='cad_origin', pos='0 0 .14',
                        quat='.7071067811865476 .7071067811865476 0 0')

    def visual(parent, name, mesh, color, **kwargs):
        return ET.SubElement(parent, 'geom', name=name, type='mesh', mesh=mesh,
                             rgba=color, group='1', contype='0', conaffinity='0', **kwargs)

    def collide(parent, name, mesh):
        return ET.SubElement(parent, 'geom', name=name, type='mesh', mesh=mesh,
                             rgba='.5 .5 .5 0', group='3', contype='1', conaffinity='1')

    # 原来的实心参考面板没有给翘板留孔。这里用开孔外框描述实际开关环境。
    half_x, half_y = p['rocker_width_mm'] / 2000 + .001, p['rocker_height_mm'] / 2000 + .001
    center_x = p['rocker_center_x_mm'] / 1000
    for name, pos, size in [
        ('plate_left', ((-.043 + center_x-half_x) / 2, 0, .0025),
         ((center_x-half_x + .043) / 2, .043, .0025)),
        ('plate_right', ((center_x+half_x + .043) / 2, 0, .0025),
         ((.043-center_x-half_x) / 2, .043, .0025)),
        ('plate_top', (center_x, (half_y+.043)/2, .0025), (half_x, (.043-half_y)/2, .0025)),
        ('plate_bottom', (center_x, -(half_y+.043)/2, .0025), (half_x, (.043-half_y)/2, .0025)),
    ]:
        if min(size) > 0:
            ET.SubElement(cad, 'geom', name=name, type='box', pos=nums(pos), size=nums(size),
                          rgba='.56 .63 .67 1')
    visual(cad, 'frame_visual', 'frame', '.80 .84 .85 1')
    for i in range(len(collision['frame']['hulls'])):
        collide(cad, f'frame_collision_{i}', f'frame_col_{i}')

    mount = ET.SubElement(cad, 'body', name='robot_mount',
                          pos=nums([p['mount_dx_mm']/1000, p['mount_dy_mm']/1000, p['mount_dz_mm']/1000]),
                          euler=nums([0, 0, math.radians(p['arm_yaw_deg'])]))
    visual(mount, 'cradle_visual', 'cradle', '.80 .84 .85 1')
    for i in range(len(collision['cradle']['hulls'])):
        collide(mount, f'cradle_collision_{i}', f'cradle_col_{i}')
    visual(mount, 'servo_visual', 'servo_body', '.06 .22 .43 1')
    visual(mount, 'shaft_visual', 'servo_shaft', '.65 .52 .25 1')
    ET.SubElement(mount, 'geom', name='servo_collision', type='box', pos='.044 -.0055 .025',
                  size='.013 .0115 .0061', rgba='0 0 0 0', group='3')
    arm = ET.SubElement(mount, 'body', name='press_arm', pos='.024 0 .025')
    # 回位弹簧：断电时由它把按压臂拉回中立位置（0 = 不装弹簧，旧行为）。
    ET.SubElement(arm, 'joint', name='servo_axis', type='hinge', axis='1 0 0',
                  range='-.70 .70', armature=str(p['servo_reflected_inertia_kg_m2']),
                  damping='.00015', frictionloss=str(p['servo_joint_friction_nm']),
                  stiffness=str(p.get('return_spring_nm_per_rad', 0)), springref='0')
    a = collision[p['arm_revision']]
    inertia = np.array(a['inertia_kg_m2'])
    ET.SubElement(arm, 'inertial', pos=nums(a['center_of_mass_m']), mass=str(a['mass_kg']),
                  fullinertia=nums([inertia[0,0], inertia[1,1], inertia[2,2],
                                    inertia[0,1], inertia[0,2], inertia[1,2]]))
    visual(arm, 'arm_visual', p['arm_revision'], '.97 .40 .08 1')
    # 弹簧压脚：两个压垫（碰撞体 2、4）装在带弹簧的滑块上，过行程由弹簧吸收，
    # 压力被限制在 刚度×行程 以内，而不是由舵机堵转力矩决定。刚度为 0 时保持刚性旧行为。
    compliant = p.get('pad_stiffness_n_per_mm', 0) > 0
    pad_hulls = {2: 'neg', 4: 'pos'} if compliant else {}
    for i in range(len(a['hulls'])):
        if i not in pad_hulls:
            collide(arm, f'arm_collision_{i}', f"{p['arm_revision']}_col_{i}")
    if compliant:
        contact = ET.SubElement(root, 'contact')
        for i, tag in pad_hulls.items():
            lines = (ASSETS / a['hulls'][i]).read_text().splitlines()
            verts = np.array([[float(x) for x in l.split()[1:4]] for l in lines if l.startswith('v ')])
            pad = ET.SubElement(arm, 'body', name=f'pad_{tag}')
            ET.SubElement(pad, 'joint', name=f'pad_slide_{tag}', type='slide', axis='0 0 1',
                          range=nums([0, p['pad_travel_mm'] / 1000]),
                          stiffness=str(p['pad_stiffness_n_per_mm'] * 1000), springref='0',
                          damping=str(p['pad_damping_n_s_per_m']), solreflimit='.002 1')
            ET.SubElement(pad, 'inertial', pos=nums(verts.mean(axis=0)), mass=str(p['pad_mass_kg']),
                          diaginertia='2e-9 2e-9 2e-9')
            collide(pad, f'arm_collision_{i}', f"{p['arm_revision']}_col_{i}")
            ET.SubElement(contact, 'exclude', body1='press_arm', body2=f'pad_{tag}')
    for side in (-1, 1):
        ET.SubElement(arm, 'site', name=f'press_tip_{side}', pos=nums([0, side*.024, -.013]),
                      size='.0008', rgba='.9 .2 .1 1')

    q0 = math.radians(p['rocker_stable_angle_deg'])
    rocker = ET.SubElement(cad, 'body', name='rocker', pos=nums([center_x, 0, .007]))
    ET.SubElement(rocker, 'joint', name='rocker_axis', type='hinge', axis='1 0 0',
                  range=nums([-q0*1.12, q0*1.12]), damping=str(p['rocker_damping_nm_s_rad']),
                  frictionloss=str(p['rocker_friction_nm']), solreflimit='.0025 1')
    w, h, t, mass = p['rocker_width_mm']/1000, p['rocker_height_mm']/1000, .004, p['rocker_mass_kg']
    ET.SubElement(rocker, 'inertial', pos='0 0 0', mass=str(mass),
                  diaginertia=nums([mass*(h*h+t*t)/12, mass*(w*w+t*t)/12, mass*(h*h+w*w)/12]))
    visual(rocker, 'rocker_visual', 'rocker_original', '.88 .91 .89 1')
    collide(rocker, 'rocker_collision', 'rocker_original')
    ET.SubElement(rocker, 'site', name='rocker_center', size='.001', rgba='.2 .4 .9 1')

    # 完整板和壳体作为同一数字样机中的静态装配。动力学不等于电路仿真。
    visual(cad, 'case_visual', 'case_v03', '.66 .73 .76 .55')
    visual(cad, 'lid_visual', 'lid_v03_closed', '.71 .78 .80 .10')
    pcb_file = ASSETS / 'pcb_materials.json'
    if pcb_file.exists():
        for i, part in enumerate(json.loads(pcb_file.read_text())):
            ET.SubElement(assets, 'mesh', name=f'pcb_mesh_{i}', file=part['file'])
            visual(cad, f'pcb_visual_{i}', f'pcb_mesh_{i}', nums(part['rgba']))
    actuator = ET.SubElement(root, 'actuator')
    stall = p['servo_stall_torque_nm']
    ET.SubElement(actuator, 'motor', name='servo_motor', joint='servo_axis',
                  ctrlrange=nums([-stall, stall]), forcerange=nums([-stall, stall]))
    sensors = ET.SubElement(root, 'sensor')
    for joint in ['servo_axis', 'rocker_axis']:
        ET.SubElement(sensors, 'jointpos', name=joint+'_position', joint=joint)
        ET.SubElement(sensors, 'jointvel', name=joint+'_velocity', joint=joint)
    ET.SubElement(sensors, 'actuatorfrc', name='servo_torque', actuator='servo_motor')
    return ET.tostring(root, encoding='unicode')


@dataclass
class Metrics:
    peak_contact_force_n: float = 0
    peak_forbidden_force_n: float = 0
    peak_penetration_mm: float = 0
    peak_torque_nm: float = 0
    saturation_time_s: float = 0
    forbidden_contact_time_s: float = 0
    peak_pad_travel_mm: float = 0


class RobotSimulation:
    def __init__(self, p=None, initial_state='OFF'):
        self.p = parameters() if p is None else p
        self.runtime_warnings = {}
        def warn(message):
            self.runtime_warnings[message] = self.runtime_warnings.get(message, 0) + 1
        mujoco.set_mju_user_warning(warn)
        self.xml = make_xml(self.p)
        self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.data = mujoco.MjData(self.model)
        self.sq = self.model.jnt_qposadr[self.model.joint('servo_axis').id]
        self.sv = self.model.jnt_dofadr[self.model.joint('servo_axis').id]
        self.rq = self.model.jnt_qposadr[self.model.joint('rocker_axis').id]
        self.rv = self.model.jnt_dofadr[self.model.joint('rocker_axis').id]
        self.q0 = math.radians(self.p['rocker_stable_angle_deg'])
        self.data.qpos[self.rq] = self.q0 if initial_state == 'OFF' else -self.q0
        self.data.qpos[self.sq] = 0
        self.metrics = Metrics()
        self.target = 0
        self.last_pwm_time = -1
        self.servo_power = True
        self.state = initial_state
        self.transitions = []
        self.current_contact_n = 0
        self.current_forbidden_n = 0
        self.warning_counts = np.zeros(len(self.data.warning), dtype=int)
        self.forbidden_pairs = set()
        self.pad_qpos = [self.model.jnt_qposadr[self.model.joint(n).id]
                         for n in ('pad_slide_neg', 'pad_slide_pos')
                         if mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, n) >= 0]
        mujoco.mj_forward(self.model, self.data)

    @property
    def time(self):
        return float(self.data.time)

    def pwm(self, pulse_us):
        if not isinstance(pulse_us, (int, float)) or not math.isfinite(pulse_us) or not 500 <= pulse_us <= 2500:
            return False
        angle = (pulse_us-self.p['pwm_center_us']) / self.p['pwm_us_per_degree']
        self.target = math.radians(max(-35, min(35, angle)))
        self.last_pwm_time = self.time
        return True

    @property
    def effective_target(self):
        """舵机实际跟随的目标：PWM 超时后回中。状态读回必须报告这个值，而不是最后一次的指令。"""
        return self.target if self.time-self.last_pwm_time <= self.p['signal_timeout_s'] else 0

    def step(self):
        p, d = self.p, self.data
        target = self.effective_target
        q, v = float(d.qpos[self.sq]), float(d.qvel[self.sv])
        error = target-q
        dead = math.radians(p['servo_deadband_deg']+p['servo_backlash_deg']/2)
        error = math.copysign(max(0, abs(error)-dead), error)
        voltage = np.clip(p['servo_error_gain_per_rad']*error-p['servo_velocity_gain_s_per_rad']*v, -1, 1)
        # 直流电机的反电势使力矩随转速降低，不能用无限刚度的位置约束代替舵机。
        torque = p['servo_stall_torque_nm'] * (voltage-v/p['servo_no_load_speed_rad_s']) if self.servo_power else 0
        torque = float(np.clip(torque, -p['servo_stall_torque_nm'], p['servo_stall_torque_nm']))
        d.ctrl[0] = torque
        rocker_q = float(d.qpos[self.rq])
        peak = p['rocker_peak_force_n']*p['rocker_force_reference_lever_m']
        k = peak*3*math.sqrt(3)/(2*self.q0)
        d.qfrc_applied[:] = 0
        d.qfrc_applied[self.rv] = k*rocker_q*(1-(rocker_q/self.q0)**2)
        mujoco.mj_step(self.model, d)
        self.metrics.peak_torque_nm = max(self.metrics.peak_torque_nm, abs(torque))
        if abs(torque) >= .98*p['servo_stall_torque_nm']:
            self.metrics.saturation_time_s += p['timestep_s']
        contact_force, forbidden = 0.0, 0.0
        for contact_index, contact in enumerate(d.contact):
            g1 = self.model.geom(contact.geom1).name
            g2 = self.model.geom(contact.geom2).name
            if not (g1.startswith('arm_collision') or g2.startswith('arm_collision')):
                continue
            f = np.zeros(6)
            mujoco.mj_contactForce(self.model, d, contact_index, f)
            force = float(np.linalg.norm(f[:3]))
            self.metrics.peak_penetration_mm = max(self.metrics.peak_penetration_mm, max(0, -contact.dist)*1000)
            if 'rocker_collision' in (g1, g2):
                contact_force += force
            else:
                forbidden += force
                if force > .05:
                    self.forbidden_pairs.add(tuple(sorted([g1, g2])))
        self.current_contact_n = contact_force
        self.current_forbidden_n = forbidden
        for adr in self.pad_qpos:
            self.metrics.peak_pad_travel_mm = max(self.metrics.peak_pad_travel_mm, float(d.qpos[adr])*1000)
        self.metrics.peak_contact_force_n = max(self.metrics.peak_contact_force_n, contact_force)
        self.metrics.peak_forbidden_force_n = max(self.metrics.peak_forbidden_force_n, forbidden)
        if forbidden > .05:
            self.metrics.forbidden_contact_time_s += p['timestep_s']
        if d.qpos[self.rq] < -.6*self.q0:
            state = 'ON'
        elif d.qpos[self.rq] > .6*self.q0:
            state = 'OFF'
        else:
            state = self.state
        if state != self.state:
            self.state = state
            self.transitions.append({'time_s': self.time, 'state': state})
        if not np.isfinite(d.qpos).all() or not np.isfinite(d.qvel).all():
            raise RuntimeError('Non-finite physics state')
        for i, warning in enumerate(d.warning):
            self.warning_counts[i] = max(self.warning_counts[i], warning.number)

    def sample(self, command='IDLE'):
        return {'time_s': self.time, 'phase': command, 'rocker_state': self.state,
                'arm_deg': math.degrees(self.data.qpos[self.sq]),
                'rocker_deg': math.degrees(self.data.qpos[self.rq]),
                'target_deg': math.degrees(self.effective_target),
                'servo_torque_nm': float(self.data.actuator_force[0]),
                'contact_n': self.current_contact_n, 'forbidden_n': self.current_forbidden_n}

    def resting_clearance_mm(self):
        """固定最终臂位置，检查翘板两种稳态都能留出空隙，不改变仿真轨迹。"""
        check=mujoco.MjData(self.model)
        check.qpos[:]=self.data.qpos
        rocker_geom=self.model.geom('rocker_collision').id
        arm_geoms=[i for i in range(self.model.ngeom)
                   if self.model.geom(i).name.startswith('arm_collision_')]
        closest=.02
        for angle in [-self.q0,self.q0]:
            check.qpos[self.rq]=angle
            mujoco.mj_kinematics(self.model,check)
            for geom in arm_geoms:
                closest=min(closest,mujoco.mj_geomDistance(self.model,check,geom,rocker_geom,.02,None))
        return float(closest*1000)
