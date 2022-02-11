from __future__ import print_function
import os
import time
import yaml
import rospy
import rospkg
import actionlib

from virtual_instron.hardware_interface import DataLogger
import virtual_instron.utils as utils
from geometry_msgs.msg import Twist, Vector3

class RunTest:
    def __init__(self, filename, robot, action_server, params={}):
        if not self.validate_params(params):
            print("Invalid parameter set. Skipping test")
            return

        self._as = action_server
        self.params = params
        self.poll_rate = params.get('poll_rate', 500)

        self.test_params = params.get('test')
        self.preload_params = params.get('preload')

        self.robot = robot
        self.jogpub = rospy.Publisher('twist_controller/command', Twist, queue_size=10)
        self.logger = self.create_logger(filename)


    def create_logger(self,filename):
        filepath_config = os.path.join(rospkg.RosPack().get_path('virtual_instron'), 'config')
        log_config_file = os.path.join(filepath_config,'data_to_save.yaml')
        with open(log_config_file, 'r') as f:
            log_config = yaml.safe_load(f)
        
        logger = DataLogger(filename,log_config)
        return logger


    def validate_params(self, params):
        if not isinstance(params, dict):
            print("Params must be a dict")
            return False

        keys = params.keys()      
        if ('test' not in keys) or ('preload' not in keys):
            print("KeyError: You must pass both testing and preload parameters")
            return False

        keys_to_test = ['test','preload']
        for key_test in keys_to_test:
            test_keys = params[key_test].keys()

            if ('motion' not in test_keys) or ('stop_conditions' not in test_keys):
                print("KeyError: test/preload must have all aspects defined")
                return False
        
        return True
   

    def get_condition_functions(self, stop_conditions, condition_values):

        idx_map = {'x':0, 'y':1, 'z':2, 'w':3}

        def get_position(idx):
            print(self.robot.position_curr[idx])
            return self.robot.position_curr[idx]

        def get_orientation(idx):
            return self.robot.orientation_curr[idx]

        def get_force(idx):
            return abs(self.robot.force_curr[idx])
        
        def get_torque(idx):
            return abs(self.robot.torque_curr[idx])

        def get_time():
            print(rospy.get_rostime().to_sec() - self.start_time)
            return rospy.get_rostime().to_sec() - self.start_time

        function_list = []
        for condition, val in zip(stop_conditions, condition_values):
                       
            if 'position' in condition:
                idx = condition.split('position_')[1]
                pos_init = float(self.robot.position_curr[idx_map[idx]])
                fun = lambda : get_position(idx_map[idx]) - pos_init
            elif 'orientation' in condition:
                idx = condition.split('orientation_')[1]
                ori_init = float(self.robot.orientation_curr[idx_map[idx]])
                fun = lambda : get_orientation(idx_map[idx]) - ori_init
            elif 'force' in condition:
                idx = condition.split('force_')[1]
                fun = lambda : get_force(idx_map[idx])
            elif 'torque' in condition:
                idx = condition.split('torque_')[1]
                fun = lambda : get_torque(idx_map[idx])
            elif 'time' in condition:
                fun = lambda : get_time()
            else:
                fun = lambda : True

            if 'max' in condition:
                function_list.append(lambda : fun() > val)
            elif 'min' in condition:
                function_list.append(lambda : fun() < val )
            else:
                function_list.append(lambda : fun())

        return function_list



    def run_sequence(self, config):
        
        stop_conditions = [[],[]]
        for key in config['stop_conditions']:
            stop_conditions[0].append(key)
            stop_conditions[1].append(config['stop_conditions'][key])

        self.start_time = rospy.get_rostime().to_sec()
        condition_funs = self.get_condition_functions(stop_conditions[0], stop_conditions[1])


        run_flag = True
        preload_stop = False
        r = rospy.Rate(self.poll_rate)

        self._set_jog(config['motion']['linear'], config['motion']['angular'])
        i=0
        while not preload_stop:
            # check that preempt has not been requested by the client
            if self._as.is_preempt_requested() or rospy.is_shutdown():
                rospy.loginfo('%s: Preempted' % self._action_name)
                self._as.set_preempted()
                return False             
            i+=1   
            r.sleep()
            checks = []
            for condition in condition_funs:
                checks.append(condition())

            print(checks)
            preload_stop=utils.check_any(checks)
            
        self._set_jog([0,0,0], [0,0,0])
        return True



    def run(self):
        # Switch controller to jog control:
        self.robot.set_controller('twist_controller')
        time.sleep(0.5)

        inp = raw_input('Start Preload? Press [ENTER] ')
        
        self.logger.start()
        success = self.run_sequence(self.preload_params)
        self.logger.pause()

        if not success:
            print("Sequence Failed")
            self.shutdown()
            return False

        inp = raw_input('Start Test? Press [ENTER] ')
        self.logger.resume() 
        success = self.run_sequence(self.test_params)

        if not success:
            self.shutdown()
            return False

        self.logger.stop()
        return True  

    
    
    def _set_jog(self, linear, angular):
        twist = self.robot.get_twist(linear,angular)
        self.jogpub.publish(twist)


    def shutdown(self):
        self._set_jog([0,0,0], [0,0,0])
        self.logger.shutdown()