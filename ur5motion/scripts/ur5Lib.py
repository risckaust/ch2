#!/usr/bin/env python
import time
import rospy
import roslib
import numpy as np
import cv2
import actionlib

from std_msgs.msg import *
from control_msgs.msg import *
from trajectory_msgs.msg import *
from sensor_msgs.msg import *
from actionlib_msgs.msg import *
from geometry_msgs.msg import *
from math import *

def setParams():

    rospy.set_param('/ur5/onHusky',True)
    rospy.set_param('/ur5/poseWakeup',[0.0,-np.pi/2.0,0.0,-np.pi/2.0,0.0,0.0])
    rospy.set_param('/ur5/poseReady',[0.0,-0.75*np.pi,0.75*np.pi,-np.pi,-0.50*np.pi,0.0])
    rospy.set_param('/ur5/vMax',100.0) # maximum endpoint velocity in mm/s
    rospy.set_param('/ur5/fbRate',20.0)
    rospy.set_param('/ur5/gazeboOrder',[2,1,0,3,4,5]) # order of joints in gazebo sim
    rospy.set_param('/ur5/jointLengths',[86.900,111.70,425.24,393.94]) # dz, l1, l2, l3 (empirical)
    # rospy.set_param('/ur5/jointLengths',[89.159,109.15,425.00,392.25]) # dz, l1, l2, l3 (internet)

class ur5Class():
    def __init__(self):
        # Pull the joint names from the /joint_states topic
        if rospy.get_param('/ur5/onHusky'):
            GettingNames = True
            while GettingNames == True:
                msg = rospy.wait_for_message('/joint_states',JointState)
                if not msg.name[0] == 'front_left_wheel':
                    self.jointNames = msg.name
                    GettingNames = False
        else:
            self.jointNames = ['shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
               'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint']
        
        self.jointPosition = [0.0]*6
        self.jointVelocity = [0.0]*6
        self.jointTime = rospy.Time()
        self.buttons = [False]*4
        self.vMax = rospy.get_param('/ur5/vMax')
        self.q5offset = 0.0 # wrist rotation offset

        self.pixel_x = 0.0
        self.pixel_y = 0.0
        self.pixel_z = 0.0

        # Subscribe to joint positions and velocities
        self.subJoints = rospy.Subscriber('/joint_states', JointState, self.cbJoints)

	   # Subscribe to vision coordinate differences
        self.subCoord = rospy.Subscriber('/pixelDiff', Twist, self.cbPixel)

        # Create an actionLib client & message variables
        # Prepare to publish goals
        if rospy.get_param('/ur5/onHusky'):
            self.thePrefix = ''
        else:
            self.thePrefix = '/arm_controller'
        self.client = actionlib.SimpleActionClient(self.thePrefix+'/follow_joint_trajectory',
            FollowJointTrajectoryAction)
        self.theGoal = FollowJointTrajectoryGoal()
        self.theGoal.trajectory = JointTrajectory()
        self.theGoal.trajectory.joint_names = self.jointNames

        # Subscribe to pushbuttons
        self.subSwitch1 = rospy.Subscriber('/switch1', Bool, self.cbSwitch1)
        self.subSwitch2 = rospy.Subscriber('/switch2', Bool, self.cbSwitch2)
        self.subSwitch3 = rospy.Subscriber('/switch3', Bool, self.cbSwitch3)
        self.subSwitch4 = rospy.Subscriber('/switch4', Bool, self.cbSwitch4)

    def cbJoints(self,msg):
        if not msg == None:
            if rospy.get_param('/ur5/onHusky'):
                if msg.name[0] == self.jointNames[0]:
                    self.jointPosition = msg.position
                    self.jointVelocity = msg.velocity
                    self.jointTime = msg.header.stamp
            else:
                self.jointPosition = [msg.position[i] for i in rospy.get_param('/ur5/gazeboOrder')]
                self.jointVelocity = [msg.velocity[i] for i in rospy.get_param('/ur5/gazeboOrder')]
                self.jointTime = msg.header.stamp



    def cbPixel(self,msg):
        if not msg == None:
            self.pixel_x = msg.linear.x
            self.pixel_y = msg.linear.y
            self.pixel_z = msg.linear.z


    def getJoints(self): # Alternative to subscribing to joint positions
        Success = False
        while not Success:
            msg = rospy.wait_for_message('/joint_states',JointState)
            if rospy.get_param('/ur5/onHusky'):
                if msg.name[0] == self.jointNames[0]:
                    Success = True
                    Q = msg.position
                    T = msg.header.stamp
            else:
                Success = True
                Q = [msg.position[i] for i in rospy.get_param('/ur5/gazeboOrder')]
                T = msg.header.stamp
        return Q, T

    # Switch callbacks
    def cbSwitch1(self,msg):
        if not msg == None:
            self.buttons[0] = msg.data
    def cbSwitch2(self,msg):
        if not msg == None:
            self.buttons[1] = msg.data
    def cbSwitch3(self,msg):
        if not msg == None:
            self.buttons[2] = msg.data
    def cbSwitch4(self,msg):
        if not msg == None:
            self.buttons[3] = msg.data

    def anyButton(self):
        # Return True if any button is pressed
        if self.buttons[0] or self.buttons[1] or self.buttons[2] or self.buttons[3]:
            return True
        else:
            return False

    # Commanded joint position
    def jointGoto(self,Qtarget,dT):

        retry = True
        while retry:
#            Q = self.jointPosition
#            currentPoint = JointTrajectoryPoint(positions=Q,
#                velocities=[0]*6, time_from_start=rospy.Duration(0.0))
            targetPoint = JointTrajectoryPoint(positions=Qtarget, 
                velocities=[0]*6, time_from_start=rospy.Duration(dT))
#            thePoints = [currentPoint, targetPoint]
            thePoints = [targetPoint]

            self.theGoal.trajectory.points = thePoints

            self.theGoal.trajectory.header.stamp = rospy.Time.now()

            self.client.send_goal(self.theGoal)
            
            assessing = True
            while assessing:
                status = self.client.get_state()
                if status > 0:
                    assessing = False

            if status == 5:
                print "***REJECTED***"
                print "Retrying after 5 seconds..."
                time.sleep(5.0)
            else:
                retry = False

        return status

        #self.client.wait_for_result()

    # commanded wrist location
    def xyzGoto(self,x,y,z,velocity):
        # returns flag for successful execution

        flag, q1, q2, q3 = self.wristIK(x,y,z)
        print "Q_forward: ", q1, q2, q3
        if not flag:
            return flag # = False
        else:
            Q = self.jointPosition
            xNow, yNow, zNow = self.wristFK(Q[0],Q[1],Q[2])
            print "zNow: ", zNow
            distance = sqrt( (x - xNow)**2 + (y - yNow)**2 + (z - zNow)**2)
            if velocity > self.vMax:
                print "Reducing requested velocity: ", velocity, " to vMax: ", self.vMax
                velocity = self.vMax
            dT = distance/velocity
            q4, q5 = self.cobraHead(q1,q2,q3)
            Qtarget = [q1, q2, q3, q4, q5, 0.0]
            status = self.jointGoto(Qtarget,dT)
            if not status == 5:
                flag = True
            else:
                flag = False
            return flag

    # commanded shift in wrist location using wrist coordinates
    def xyzShift(self,delx,dely,delz,velocity):
        Q = self.jointPosition
        q5o = self.q5offset
        x,y,z = self.wristFK(Q[0],Q[1],Q[2])
        xNew = x + delx*cos(q5o) - dely*sin(q5o)
        yNew = y + delx*sin(q5o) + dely*cos(q5o)
        zNew = z

        flag = self.xyzGoto(xNew,yNew,zNew,velocity)
        return flag


    def cancel(self):
        self.client.cancel_all_goals()
        time.sleep(1.0)
        # self.client.cancel_goal()
#        Q = self.jointPosition
#        Q, _ = self.getJoints()
#        self.client.cancel_goal()
#        self.jointGoto(Q,0.25)
#        self.client.wait_for_result()

    def cobraHead(self,q1,q2,q3):
        # returns q4 & q5 for cobraHead orientation
        q4 = np.pi-q2-q3
        q5 = -0.50*np.pi-q1
        if q4 > 0:
            q4 = q4 - 2.0*np.pi
        q5 = q5 + self.q5offset
        return q4, q5

    def wristFK(self,q1,q2ur5,q3ur5):
        # returns x,y,z of wrist (mm)
        links = rospy.get_param('/ur5/jointLengths')
        dz = links[0]
        l1 = links[1]
        l2 = links[2]
        l3 = links[3]

        #%%%%%%%%%%%%%%%% From matlab code %%%%%%%%%%%%%%%% 
        q2 = -np.pi/2.0-q2ur5
        q3 = -(q3ur5 + q2ur5)

        z = dz + l2*cos(q2) + l3*sin(q3)
        v = l3*cos(q3)-l2*sin(q2);

        y = -l1*cos(-q1)-v*sin(q1)
        x = -l1*sin(-q1)-v*cos(q1)
        #%%%%%%%%%%%%%%%% From matlab code %%%%%%%%%%%%%%%% 

        return x,y,z

    def wristIK(self,x,y,z):
        # returns flag, q1, q2, q3 for desired wrist x,y,z (mm)
        # if unreachable: returns False + current q1, q2, q3

        links = rospy.get_param('/ur5/jointLengths')
        dz = links[0]
        l1 = links[1]
        l2 = links[2]
        l3 = links[3]
        reach = l2 + l3

        flag = False
        if x > -25.0:
            print "IK error: x-axis"
        elif sqrt(x**2 + y**2 + (z-dz)**2) > 0.95*reach:
            print "IK error: Reach"
        elif z < dz:
            print "IK error: z-axis"
        elif sqrt(x**2+y**2) < l1*1.05:
            print "IK error: cylinder"
        else:
            flag = True

        if not flag: # return False with current joint angles
            Q = self.jointPosition
            return flag, Q[0], Q[1], Q[2] 
        else:
            links = rospy.get_param('/ur5/jointLengths')
            dz = links[0]
            l1 = links[1]
            l2 = links[2]
            l3 = links[3]

            #%%%%%%%%%%%%%%%% From matlab code %%%%%%%%%%%%%%%% 
            # compute q1

            theta_a = atan2(y,x)
            if y < 0:
                theta_a = 2.0*np.pi + theta_a

            w = sqrt(x**2 + y**2)
            theta_b = acos(l1/w)
            q1 = 2.0*np.pi - theta_a - theta_b
            q1 = -(q1 - np.pi/2)

            # compute q2 & q3

            zred = z - dz

            v = sqrt(x**2+y**2)*sin(theta_b)

            ratio = (l2**2 + l3**2 - (v**2+zred**2))/(2.0*l2*l3)
            d23 = asin(ratio) # q2 - q3

            gamma = atan(zred/v)
            temp = l3*sin(np.pi/2 - d23)/sqrt(v**2+zred**2)
            q2 = asin(temp);
            q2 = q2 + gamma - np.pi/2;

            q3 = q2 - d23;
            #%%%%%%%%%%%%%%%% From matlab code %%%%%%%%%%%%%%%% 
            
            q2ur5 = -np.pi/2.0 - q2
            q3ur5 = -q3 - q2ur5

            return flag, q1, q2ur5, q3ur5

