"""通过定时按压、退回和 PWM 输出驱动模型，不读取仿真的开关位置来作弊。"""
import math


class PressController:
    def __init__(self, parameters):
        self.p = parameters
        self.phase = 'IDLE'
        self.pending = None
        self.active = None
        self.phase_start = 0
        self.command_angle = 0.0
        self.last_tick = 0
        self.accepted = []
        self.completed = []

    def command(self, name, time):
        if name not in ['ON', 'OFF', 'STOP']:
            return False
        self.accepted.append({'time_s': time, 'command': name})
        if name == 'STOP':
            self.pending = None
            self.active = None
            self.phase = 'RETRACT'
            self.phase_start = time
        else:
            self.pending = name  # 有限队列：保留最新请求，避免快速点击积压动作。
        return True

    def tick(self, time):
        dt = max(0, time-self.last_tick)
        self.last_tick = time
        if self.phase == 'IDLE' and self.pending:
            self.active = self.pending
            self.pending = None
            self.phase = 'PRESS'
            self.phase_start = time
        if self.phase == 'PRESS' and time-self.phase_start >= .65:
            self.phase = 'RETRACT'
            self.phase_start = time
        if self.phase == 'RETRACT' and time-self.phase_start >= .50:
            if self.active:
                self.completed.append({'time_s': time, 'command': self.active,
                                       'status': 'MOTION_SEQUENCE_COMPLETE_PHYSICAL_STATE_UNCONFIRMED'})
            self.active = None
            self.phase = 'IDLE'
            self.phase_start = time
        goal = (-1 if self.active == 'ON' else 1) * self.p['press_angle_deg'] if self.phase == 'PRESS' else 0
        step = self.p['command_speed_deg_s']*dt
        self.command_angle += max(-step, min(step, goal-self.command_angle))
        pulse = self.p['pwm_center_us']+self.command_angle*self.p['pwm_us_per_degree']
        return round(max(500, min(2500, pulse)))
