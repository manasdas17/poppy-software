import numpy
import scipy.io

import pypot.primitive
from poppytools.behavior.human_like_walking_cpg import WALKING_CPG


class WalkingGaitFromCPGFile(pypot.primitive.LoopPrimitive):
    def __init__(self, robot, walking_cpg_dict=WALKING_CPG, cycle_period=1.0, gain=1.0, compliant_motion=True, refresh_freq=50):
        pypot.primitive.LoopPrimitive.__init__(self, robot, refresh_freq)

        self.walking_cpg_dict = walking_cpg_dict
        self.refresh_freq = refresh_freq
        self.cycle_period = cycle_period
        self.gain = gain
        self.compliant_motion = compliant_motion
        self.cycle_iter = 0
        self.current_period = 0

        for key in self.walking_cpg_dict:
            setattr(self, key, self.walking_cpg_dict[key])

        pop_list = ['n_elem', 'r_ankle_compliance','l_ankle_compliance','r_knee_compliance_flexion','r_knee_compliance_extension','l_knee_compliance_flexion','l_knee_compliance_extension',]
        for var in pop_list:
            self.walking_cpg_dict.pop(var)
        self.generate_loop_motion()


    def setup(self):
        self.robot.l_hip_z.goal_position = 0
        self.robot.l_hip_x.goal_position = 1
        self.robot.r_hip_z.goal_position = 0
        self.robot.r_hip_x.goal_position = -1

        self.robot_configuration()

        self.robot.goto_position(self.cycle_motors_orders[0], self.cycle_period / 2.0, wait=True)


    def update(self):
        self.current_period = 1.0 / numpy.mean(self.recent_update_frequencies)
        self.t_cycle = self.elapsed_time % self.cycle_period
        self.cycle_iter = int((self.n_elem) * self.t_cycle / self.cycle_period)

        if self.compliant_motion:
            # self.manage_knee_compliance()
            self.manage_ankle_compliance()

        self.robot.goto_position(self.cycle_motors_orders[self.cycle_iter],
                                self.current_period)

    def teardwon(self):
        for m in self.robot.motors:
            m.moving_speed = 0

    def generate_loop_motion(self):
        # Creation du dictionnaire de positions moteurs
        self.cycle_motors_orders = [
                                    dict([(k, self.gain*v[i]) for k, v in self.walking_cpg_dict.items()])
                                    for i in range(self.n_elem)
                                    ]

    def robot_configuration(self):
        for m in self.robot.legs:
            m.compliant = False
            m.goal_position = 0
            m.pid = (3, 1, 0)
            m.torque_limit = 100


    def manage_ankle_compliance(self):
        if self.r_ankle_compliance[self.cycle_iter]:
            self.robot.r_ankle_y.compliant = True
        else:
            self.robot.r_ankle_y.compliant = False

        if self.l_ankle_compliance[self.cycle_iter]:
            self.robot.l_ankle_y.compliant = True
        else:
            self.robot.l_ankle_y.compliant = False

    def manage_knee_compliance(self):
        # Right Knee
            # Extension
        if ((self.robot.r_knee_y.present_position < 21)
            and self.r_knee_extend[self.cycle_iter]):
            self.robot.r_knee_y.compliant = True
            # Flexion
        elif ((self.robot.r_knee_y.present_position > 29)
             and (self.robot.r_knee_y.present_position < 70)
             and self.r_knee_flex[self.cycle_iter]):
            self.robot.r_knee_y.compliant = True
        else :
            self.robot.r_knee_y.compliant = False
        # Left Knee
           # Flexion
        if ((self.robot.l_knee_y.present_position < 21) and
            self.l_knee_extend[self.cycle_iter]):
            self.robot.l_knee_y.compliant = True
            # Extension
        elif ((self.robot.l_knee_y.present_position > 29)
            and (self.robot.l_knee_y.present_position < 70)
            and self.l_knee_flex[self.cycle_iter]):
            self.robot.l_knee_y.compliant = True
        else :
            self.robot.l_knee_y.compliant = False



class SimpleInteraction(pypot.primitive.LoopPrimitive):
    def __init__(self, robot, freq = 1):
        pypot.primitive.LoopPrimitive.__init__(self, robot, freq)

    def update(self):
        for m in self.robot.l_arm + self.robot.r_arm:
            m.compliant = False
            m.torque_limit = 30

        self.robot.l_shoulder_y.goal_position = -130
        self.robot.r_shoulder_y.goal_position = -130
        self.robot.l_shoulder_x.goal_position = -0
        self.robot.r_shoulder_x.goal_position = -0
        self.robot.l_elbow_y.goal_position = -15
        self.robot.r_elbow_y.goal_position = -15


class WalkingGaitFromMat(pypot.primitive.LoopPrimitive):
    def __init__(self, robot, filename, cycle_period=1.0, gain=1.0, compliant_motion=True, sync='', refresh_freq=50):
        pypot.primitive.LoopPrimitive.__init__(self, robot, refresh_freq)

        self.move = scipy.io.loadmat(filename, squeeze_me=True)

        self.refresh_freq = refresh_freq
        self.cycle_period = cycle_period
        self.gain = gain
        self.compliant_motion = compliant_motion
        self.sync = sync

        self.arrange_data()

        self.robot_configuration()

        self.cycle_iter = 0
        self.prim_iter = 0
        self.size_period = round(self.cycle_period * self.refresh_freq)

    def update(self):
        if self.compliant_motion:
            # self.knee_compliance_rule()
            self.ankle_compliance_rule()

        self.robot.goto_position(self.cycle_motors_orders[self.cycle_iter],
                                1.0/self.refresh_freq)

        self.robot.l_hip_z.goal_position = 0
        self.robot.l_hip_x.goal_position = 1
        self.robot.r_hip_z.goal_position = 0
        self.robot.r_hip_x.goal_position = -1

        if self.prim_iter < self.size_period:
            self.prim_iter += 1
        else:
            self.prim_iter = 0
            if self.sync:
                self.robot.data_recording.sync_data()
        #Conversion matlab/python (premier element = 1 vs 0)
        self.cycle_iter = int(self.prim_iter * (self.n_elem-1) / self.size_period)

    def generate_loop_motion(self):
        # Creation du dictionnaire de positions moteurs
        self.cycle_motors_orders = [dict([(k, self.gain*v[i]) for k, v in self.move.items()])
                                    for i in range(self.n_elem)]

    def change_gain(self,value):
        self.gain = value
        self.generate_loop_motion()

    def robot_configuration(self):
        for m in self.robot.legs:
            m.compliant = False
            m.goal_position = 0
            m.pid = (3, 1, 0)
            m.torque_limit = 100


        for m in self.robot.torso:
            m.compliant = False
            m.goal_position = 0
            m.pid = (2, 0, 0)
            m.torque_limit = 30

    def ankle_compliance_rule(self):

        if self.r_ankle_compliance[self.cycle_iter]:

            self.robot.r_ankle_y.compliant = True
        else:
            self.robot.r_ankle_y.compliant = False

        if self.l_ankle_compliance[self.cycle_iter]:

            self.robot.l_ankle_y.compliant = True
        else:
            self.robot.l_ankle_y.compliant = False

    def knee_compliance_rule(self):

        # Right Knee
            # Extension
        if ((self.robot.r_knee_y.present_position < 21)
            and self.r_knee_extend[self.cycle_iter]):

            self.robot.r_knee_y.compliant = True

            # Flexion
        elif ((self.robot.r_knee_y.present_position > 29)
             and (self.robot.r_knee_y.present_position < 70)
             and self.r_knee_flex[self.cycle_iter]):

            self.robot.r_knee_y.compliant = True

        else :
            self.robot.r_knee_y.compliant = False

        # Left Knee
           # Flexion
        if ((self.robot.l_knee_y.present_position < 21) and
            self.l_knee_extend[self.cycle_iter]):

            self.robot.l_knee_y.compliant = True

            # Extension
        elif ((self.robot.l_knee_y.present_position > 29)
            and (self.robot.l_knee_y.present_position < 70)
            and self.l_knee_flex[self.cycle_iter]):

            self.robot.l_knee_y.compliant = True

        else :
            self.robot.l_knee_y.compliant = False

    def arrange_data(self):

        self.n_elem = self.move['n_elem']

        self.r_knee_extend = self.move['r_knee_compliance_extension']
        self.l_knee_extend = self.move['l_knee_compliance_extension']
        self.r_knee_flex = self.move['r_knee_compliance_flexion']
        self.l_knee_flex = self.move['l_knee_compliance_flexion']
        self.r_ankle_compliance = self.move['r_ankle_compliance']
        self.l_ankle_compliance = self.move['l_ankle_compliance']

        for m in ['__version__', '__globals__', '__header__',
                    'dt', 'n_elem', 'r_knee_compliance_extension', 'l_knee_compliance_extension',
                    'r_knee_compliance_flexion', 'l_knee_compliance_flexion',
                    'r_ankle_compliance', 'l_ankle_compliance']:
            self.move.pop(m)

        self.generate_loop_motion()
