from __future__ import print_function
import time
import rospy
import actionlib

from geometry_msgs.msg import Wrench, WrenchStamped
from controller_manager_msgs.srv import LoadController, UnloadController, SwitchController
#from controller_manager.msg import ControllerState
from geometry_msgs.msg import Twist, Vector3

controller_list = ['scaled_pos_joint_traj_controller', 'pose_based_cartesian_traj_controller', 'twist_controller']

class RobotController:
    def __init__(self, robot_name=""):
         # Subscribe to the wrench topic
        rospy.Subscriber('/wrench', WrenchStamped, self.update_wrench)

        self.controller_list = controller_list

        self.load_controller_name = robot_name+'/controller_manager/load_controller'
        self.unload_controller_name = robot_name+'/controller_manager/unload_controller'
        self.switch_controller_name = robot_name+'/controller_manager/switch_controller'

        self.force_curr = None
        self.torque_curr = None
    

    def load_controller(self, controller):
        rospy.wait_for_service(self.load_controller_name)
        try:
            fun = rospy.ServiceProxy(self.load_controller_name, LoadController)
            resp1 = fun(controller)
            return resp1.ok
        except rospy.ServiceException as e:
            print("Service call failed: %s"%e)


    def unload_controller(self, controller):
        rospy.wait_for_service(self.unload_controller_name)
        try:
            fun = rospy.ServiceProxy(self.unload_controller_name, UnloadController)
            resp1 = fun(controller)
            return resp1.ok
        except rospy.ServiceException as e:
            print("Service call failed: %s"%e)
        

    def switch_controller(self, start_controllers, stop_controllers, strictness=1, start_asap=False, timeout=0):
        rospy.wait_for_service(self.switch_controller_name)
        try:
            fun = rospy.ServiceProxy(self.switch_controller_name, SwitchController)
            resp1 = fun(start_controllers=start_controllers,
                             stop_controllers=stop_controllers,
                             strictness=strictness,
                             start_asap=start_asap,
                             timeout=timeout)
            return resp1.ok
        except rospy.ServiceException as e:
            print("Service call failed: %s"%e)
        

    def set_controller(self,controller):

        controllers_to_unload = []

        for ctrl in self.controller_list:
            if controller != ctrl:
                controllers_to_unload.append(ctrl)
                
        self.load_controller(controller)
        self.switch_controller([controller],controllers_to_unload)
        
        #for ctrl in controllers_to_unload:
        #    self.unload_controller(ctrl)


    def update_wrench(self,data):
        '''
        Update the internal value of the wrench.

        Parameters
        ----------
        data : geometry_msgs/Wrench
            Wrench message
        '''
        wrench = data.wrench
        self.force_curr = [wrench.force.x, wrench.force.y, wrench.force.z]
        self.torque_curr = [wrench.torque.x, wrench.torque.y, wrench.torque.z]


    def get_twist(self, linear, angular):
        linear_out = Vector3()
        linear_out.x=linear[0]
        linear_out.y=linear[1]
        linear_out.z=linear[2]

        angular_out = Vector3()
        angular_out.x=angular[0]
        angular_out.y=angular[1]
        angular_out.z=angular[2]

        twist_out = Twist()
        twist_out.linear=linear_out
        twist_out.angular=angular_out

        return twist_out
