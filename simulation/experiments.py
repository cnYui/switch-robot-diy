"""执行物理测试并输出逐时刻证据，失败判据使用模型真值且不反馈给控制器。"""
from dataclasses import asdict
import json
import math
from pathlib import Path
import time
import numpy as np
from model import RobotSimulation, parameters
from controller import PressController

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
RESULTS.mkdir(exist_ok=True)


def experiment(name, overrides=None, events=None, duration=3.5, initial_state='OFF',
               stop_pwm_at=None, power_off_at=None, record=True, expected=None, callback=None):
    p = parameters(**(overrides or {}))
    sim = RobotSimulation(p, initial_state=initial_state)
    controller = PressController(p)
    events = events if events is not None else [(.4, 'ON'), (1.9, 'OFF')]
    events = sorted(events)
    initial_penetration = max([max(0, -c.dist)*1000 for c in sim.data.contact] + [0])
    initial_contacts = len(sim.data.contact)
    event_index = 0
    pwm_tick = max(1, round(p['pwm_period_s']/p['timestep_s']))
    sample_tick = max(1, round(.005/p['timestep_s']))
    qposes, trace, idle_forces = [], [], []
    for i in range(round(duration/p['timestep_s'])):
        t = sim.time
        while event_index < len(events) and t >= events[event_index][0]-p['timestep_s']/2:
            controller.command(events[event_index][1], t)
            event_index += 1
        if i % pwm_tick == 0:
            pulse = controller.tick(t)
            if stop_pwm_at is None or t < stop_pwm_at:
                sim.pwm(pulse)
        if power_off_at is not None and t >= power_off_at:
            sim.servo_power = False
        sim.step()
        if i % sample_tick == 0:
            sample = sim.sample(controller.phase)
            sample['commanded_state'] = controller.active or 'NONE'
            sample['pwm_us'] = round(p['pwm_center_us']+controller.command_angle*p['pwm_us_per_degree'])
            trace.append(sample)
            if controller.phase == 'IDLE' and t > .25:
                idle_forces.append(sample['contact_n'])
            if record:
                qposes.append(sim.data.qpos.copy())
        if callback:
            callback(sim, controller)
    final = sim.sample(controller.phase)
    stable = abs(abs(final['rocker_deg'])-p['rocker_stable_angle_deg']) < .3
    rest_clearance=sim.resting_clearance_mm()
    # 舵机有死区与回差。回中验收使用声明的角度误差预算，并独立检查两侧实空间隙。
    rest_angle_budget=p['servo_deadband_deg']+p['servo_backlash_deg']/2+.2
    neutral = abs(final['arm_deg']) <= rest_angle_budget and rest_clearance>=.30
    defects = []
    if initial_penetration > .03:
        defects.append('INITIAL_PRELOAD')
    if sim.metrics.forbidden_contact_time_s > .002:
        defects.append('FRAME_OR_CRADLE_COLLISION')
    if expected and final['rocker_state'] != expected:
        defects.append('TARGET_NOT_REACHED')
    if not stable:
        defects.append('ROCKER_NOT_RETAINED')
    if not neutral and power_off_at is None:
        defects.append('ARM_NOT_RETRACTED')
    if max(idle_forces, default=0) > .05:
        defects.append('CONTACT_WHILE_IDLE')
    if sim.metrics.peak_contact_force_n > p['test_contact_force_limit_n']:
        defects.append('EXCEEDS_ASSUMED_6N_TEST_LIMIT')
    if p.get('pad_stiffness_n_per_mm', 0) > 0 and sim.metrics.peak_pad_travel_mm > .95*p['pad_travel_mm']:
        defects.append('PAD_BOTTOMED_OUT')  # 弹性压垫压到底后又变成刚性接触，力上限不再受弹簧保护
    if power_off_at is not None and not neutral:
        defects.append('NO_RETRACTION_WITHOUT_POWER')
    if sim.warning_counts.any() or sim.runtime_warnings:
        defects.append('NUMERICAL_WARNING')
    result = {
        'name': name, 'calibration_status': p['calibration_status'],
        'parameters': p, 'events': events, 'duration_s': duration,
        'initial_state': initial_state, 'final': final,
        'initial_contact_count': initial_contacts, 'initial_penetration_mm': initial_penetration,
        'transitions': sim.transitions, 'metrics': asdict(sim.metrics),
        'warnings': sim.warning_counts.tolist(), 'runtime_warnings':sim.runtime_warnings, 'defects': defects,
        'expected_state': expected, 'mechanical_check_passed': not defects,
        'controller_completed': controller.completed,
        'forbidden_pairs': [list(x) for x in sorted(sim.forbidden_pairs)],
        'idle_peak_force_n': max(idle_forces, default=0),
        'observations': {'rocker_retained':stable, 'arm_retracted':neutral,
                         'servo_power_at_end':sim.servo_power,
                         'rest_clearance_both_rocker_states_mm':rest_clearance,
                         'rest_angle_budget_deg':rest_angle_budget,
                         'minimum_required_rest_clearance_mm':.30},
        'peak_force_note': ('Rigid wedging reaction is not a reliable material stress prediction'
                            if sim.metrics.peak_forbidden_force_n > 50 else 'Uncalibrated rigid-body contact estimate'),
    }
    if record:
        (RESULTS/(name+'.json')).write_text(json.dumps(result, indent=2), encoding='utf8')
        (RESULTS/(name+'_trace.json')).write_text(json.dumps(trace), encoding='utf8')
        np.savez_compressed(RESULTS/(name+'_states.npz'),
                            qpos=np.array(qposes), time_s=np.array([x['time_s'] for x in trace]))
        (RESULTS/(name+'.xml')).write_text(sim.xml, encoding='utf8')
    return result


def run_suite():
    started = time.perf_counter()
    results = []

    def add(name, **kwargs):
        r = experiment(name, **kwargs)
        results.append(r)
        print(name, 'PASS' if r['mechanical_check_passed'] else ','.join(r['defects']),
              'flips', len(r['transitions']), 'force', round(r['metrics']['peak_contact_force_n'], 3), flush=True)
        return r

    # 旧版本按它们当时的参数（刚性压垫、11.4°、无垫高）复测，作为修复前的对照。
    legacy = {'pad_stiffness_n_per_mm':0, 'press_angle_deg':11.4, 'mount_dz_mm':0.0}
    add('v01_existing_stl', overrides={'arm_revision':'arm_v01', **legacy}, expected='OFF')
    add('v02_animation_geometry', overrides={'arm_revision':'arm_v02', **legacy}, expected='OFF')
    add('v05_rigid_baseline', overrides={'arm_revision':'arm_v05', **legacy}, expected='OFF')
    add('v05_rigid_power_loss', overrides={'arm_revision':'arm_v05', **legacy}, events=[(.4,'ON')],
        power_off_at=.65, duration=2)
    add('v06_nominal', expected='OFF')
    add('v06_on_then_hold', events=[(.4,'ON')], duration=3, expected='ON')
    add('v06_off_then_hold', initial_state='ON', events=[(.4,'OFF')], duration=3, expected='OFF')
    add('v06_repeated_command', events=[(.4,'ON'),(1.8,'ON'),(3.2,'OFF')], duration=4.7, expected='OFF')
    add('v06_fast_reversal', events=[(.4,'ON'),(.48,'OFF'),(.52,'ON'),(.56,'OFF')], duration=3, expected='OFF')
    add('v06_stop_mid_press', events=[(.4,'ON'),(.52,'STOP')], duration=2)
    add('v06_pwm_dropout', events=[(.4,'ON')], stop_pwm_at=.65, duration=2)
    # 没有回位弹簧时，断电后压垫弹簧只能把臂推到刚好脱离接触的位置，臂仍留在翘板行程内。
    add('v06_power_loss', events=[(.4,'ON')], power_off_at=.65, duration=2)
    add('v06_power_loss_with_return_spring', overrides={'return_spring_nm_per_rad':.05},
        events=[(.4,'ON')], power_off_at=.65, duration=2)
    add('v06_weak_servo', overrides={'servo_stall_torque_nm':.025}, events=[(.4,'ON')], duration=2, expected='ON')
    add('v06_stiff_switch', overrides={'rocker_peak_force_n':9.0}, events=[(.4,'ON')], duration=2, expected='ON')
    add('v06_harder_switch_4N', overrides={'rocker_peak_force_n':4.0}, events=[(.4,'ON')], duration=2, expected='ON')
    add('v06_switch_beyond_pad_capacity', overrides={'rocker_peak_force_n':5.0}, events=[(.4,'ON')],
        duration=2, expected='ON')
    add('v06_insufficient_stroke', overrides={'press_angle_deg':6}, events=[(.4,'ON')], duration=2, expected='ON')
    add('v06_excessive_stroke', overrides={'press_angle_deg':22}, events=[(.4,'ON')], duration=2, expected='ON')
    add('v06_large_mount_offset', overrides={'mount_dx_mm':15}, events=[(.4,'ON')], duration=2, expected='ON')
    add('v06_large_height_offset', overrides={'mount_dz_mm':5}, events=[(.4,'ON')], duration=2, expected='ON')
    add('v06_narrow_rocker_missed', overrides={'rocker_width_mm':20}, events=[(.4,'ON')], duration=2, expected='ON')
    add('v06_three_gang_right', overrides={'rocker_width_mm':20,'rocker_center_x_mm':24}, expected='OFF')
    add('v06_twenty_cycles', events=[(.4+i*1.35, 'ON' if i%2==0 else 'OFF') for i in range(20)],
        duration=27.7, expected='OFF')
    for dt in [.00025,.0000625]:
        add('v06_dt_'+str(dt).replace('.','p'), overrides={'timestep_s':dt}, expected='OFF')
    for friction in [.05,.9]:
        add('v06_friction_'+str(friction).replace('.','p'), overrides={'friction_coefficient':friction}, expected='OFF')
    add('v06_no_contact_negative_control',overrides={'disable_contacts':True},
        events=[(.4,'ON')],duration=2,expected='ON')
    add('v06_soft_contact_sensitivity',overrides={'contact_time_constant_s':.002},expected='OFF')
    # 扫描输入范围，用于发现边界；不把人为选取的分布称为实物可靠性。
    def height_sweep(offsets, angles, base, label):
        rows = []
        for off in offsets:
            for angle in angles:
                r = experiment(f'height_{off}_stroke_{angle}',
                               overrides={**base, 'mount_dz_mm':base['mount_dz_mm']+off,'press_angle_deg':angle},
                               events=[(.3,'ON')], duration=1.8, record=False, expected='ON')
                rows.append({'height_offset_mm':off,'press_angle_deg':angle,
                             'pass':r['mechanical_check_passed'], 'defects':r['defects'],
                             'peak_force_n':r['metrics']['peak_contact_force_n'],
                             'saturation_time_s':r['metrics']['saturation_time_s'],
                             'rest_clearance_mm':r['observations']['rest_clearance_both_rocker_states_mm']})
            print(label,'height offset',off,'complete',flush=True)
        return rows
    # 高度偏差相对各自的名义安装高度：V0.6 名义垫高 1.0 mm，旧刚性版本为 0。
    nominal = parameters()
    sweep = height_sweep([-2,-1.5,-1,-.5,0,.5,1,1.5,2], [11.4,13,15,17,19,21,23],
                         {'mount_dz_mm':nominal['mount_dz_mm']}, 'V0.6')
    legacy_sweep = height_sweep([-1,-.5,0,.5,1,1.5,2], [7,8,9,10,11.4,12,13,14,16],
                                {'arm_revision':'arm_v05', **legacy}, 'V0.5 rigid')
    sensitivity = []
    for force in [1,2,3,4,5,6,7,8,9]:
        r = experiment('force_sweep',overrides={'rocker_peak_force_n':force},events=[(.3,'ON')],
                       duration=1.8,record=False,expected='ON')
        sensitivity.append({'parameter':'rocker_peak_force_n','value':force,'pass':r['mechanical_check_passed'],
                            'defects':r['defects'],'peak_torque_nm':r['metrics']['peak_torque_nm']})
    for torque in [.025,.04,.06,.08,.10,.12,.1569,.1765]:
        r=experiment('torque_sweep',overrides={'servo_stall_torque_nm':torque},events=[(.3,'ON')],
                     duration=1.8,record=False,expected='ON')
        sensitivity.append({'parameter':'servo_stall_torque_nm','value':torque,'pass':r['mechanical_check_passed'],
                            'defects':r['defects'],'peak_force_n':r['metrics']['peak_contact_force_n']})
    print('Force/torque sensitivity complete',flush=True)
    rng=np.random.default_rng(20261106)
    randomized=[]
    for i in range(32):
        overrides={'mount_dx_mm':float(rng.uniform(-.8,.8)), 'mount_dy_mm':float(rng.uniform(-.8,.8)),
                   'mount_dz_mm':float(nominal['mount_dz_mm']+rng.uniform(-1,1)),
                   'rocker_peak_force_n':float(rng.uniform(2,3.8)),
                   'servo_stall_torque_nm':float(rng.uniform(.12,.1765)),
                   'friction_coefficient':float(rng.uniform(.25,.65)),
                   'servo_backlash_deg':float(rng.uniform(.3,1.2)),
                   'servo_deadband_deg':float(rng.uniform(.15,.5)),
                   'pad_stiffness_n_per_mm':float(nominal['pad_stiffness_n_per_mm']*rng.uniform(.8,1.2)),
                   'press_angle_deg':float(nominal['press_angle_deg']+rng.uniform(-1.5,1.5))}
        r=experiment('tolerance_'+str(i),overrides=overrides,events=[(.3,'ON')],duration=1.8,
                     record=False,expected='ON')
        randomized.append({'index':i,'parameters':overrides,'pass':r['mechanical_check_passed'],
                           'defects':r['defects'],'peak_force_n':r['metrics']['peak_contact_force_n'],
                           'observations':r['observations'],'final':r['final']})
    output={'mujoco_version':__import__('mujoco').__version__,'calibration_status':'ASSUMED_NOT_MEASURED',
            'cases':results,'height_stroke_sweep':sweep,'legacy_v05_height_stroke_sweep':legacy_sweep,
            'force_torque_sweep':sensitivity,
            'randomized_tolerances':randomized,'random_seed':20261106,
            'wall_time_s':time.perf_counter()-started,
            'physics_model_does_not_cover':['electrical current/voltage/thermal/RF','real firmware binary',
               'plastic flex/strength/fatigue','adhesive or screw retention','unmeasured switch force curve']}
    (RESULTS/'suite.json').write_text(json.dumps(output,indent=2),encoding='utf8')
    print('Suite complete',len(results)+len(sweep)+len(legacy_sweep)+len(sensitivity)+len(randomized),'scenarios',
          round(output['wall_time_s'],1),'s',flush=True)
    return output


if __name__=='__main__':
    run_suite()
