#!/usr/bin/env python
import time
import rospy
import numpy as np
import cv2

from control_msgs.msg import *
from trajectory_msgs.msg import *
from sensor_msgs.msg import *
from actionlib_msgs.msg import *
from math import *

def setParams():

    rospy.set_param('/ur5/onHusky',False)

    rospy.set_param('/ur5/jointNames',['shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
               'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint'])
    # rospy.set_param('/ur5/jointLengths',[89.159,109.15,425.00,392.25]) # dz, l1, l2, l3 (internet)

    rospy.set_param('/ur5/jointLengths',[86.900,111.70,425.24,393.94]) # dz, l1, l2, l3 (empirical)

    rospy.set_param('/ur5/poseWakeup',[0.0,-np.pi/2.0,0.0,-np.pi/2.0,0.0,0.0])
    rospy.set_param('/ur5/poseReady',[0.0,-0.75*np.pi,0.75*np.pi,-np.pi,-0.50*np.pi,0.0])

    rospy.set_param('/ur5/gazeboOrder',[2,1,0,3,4,5])
    rospy.set_param('/ur5/fbRate',20.0)

class ur5Class():
    def __init__(self):
        self.jointNames =  rospy.get_param('/ur5/jointNames')
        self.jointPosition = [0.0]*6
        self.jointVelocity = [0.0]*6
        self.subJoints = rospy.Subscriber('/joint_states', JointState, self.cbJoints)
        if rospy.get_param('/ur5/onHusky'):
            self.thePrefix = ''
        else:
            self.thePrefix = '/arm_controller'
        self.commander =  rospy.Publisher(self.thePrefix+'/follow_joint_trajectory/goal',
            FollowJointTrajectoryActionGoal, queue_size=10)
        self.goalCancel = rospy.Publisher(self.thePrefix+'/follow_joint_trajectory/cancel',
            GoalID, queue_size=10)

    def cbJoints(self,msg):

        if not msg == None:
            if rospy.get_param('/ur5/onHusky'):
                if msg.name[0] == 'shoulder_pan_joint':
                    self.jointPosition = msg.position
                    self.jointVelocity = msg.velocity
            else:
                self.jointPosition = [msg.position[i] for i in rospy.get_param('/ur5/gazeboOrder')]
                self.jointVelocity = [msg.velocity[i] for i in rospy.get_param('/ur5/gazeboOrder')]

    def jointGoto(self,Qtarget,dT):

        setp = FollowJointTrajectoryActionGoal()

        Qcurrent = self.jointPosition
        currentPoint = JointTrajectoryPoint(positions=Qcurrent,
            velocities=[0]*6, time_from_start=rospy.Duration(0.0))
        targetPoint = JointTrajectoryPoint(positions=Qtarget, 
            velocities=[0]*6, time_from_start=rospy.Duration(dT))
        thePoints = [currentPoint, targetPoint]

        thePoints = targetPoint


        if not rospy.get_param('/ur5/onHusky'):
            setp.header.stamp = rospy.Time.now()
            setp.goal.trajectory.header.stamp = rospy.Time.now()

        setp.goal.trajectory.joint_names = rospy.get_param('/ur5/jointNames')
        setp.goal.trajectory.points = thePoints

        self.commander.publish(setp)

    def halt(self):
        setp = GoalID()
        theStatus = rospy.wait_for_message(self.thePrefix+"/follow_joint_trajectory/status", GoalStatusArray)
        length = len(theStatus.status_list)
        if length > 0:
            theID = theStatus.status_list[length-1].goal_id.id
            setp.id = theID
            self.goalCancel.publish(setp)
        self.clear()

    def clear(self):
        setp = GoalID()
        print "waiting for ", self.thePrefix+"/follow_joint_trajectory/status"
        theStatus = rospy.wait_for_message(self.thePrefix+"/follow_joint_trajectory/status", GoalStatusArray)
        length = len(theStatus.status_list)
        print length
        if length > 0:
            for i in range(0,length):
                theID = theStatus.status_list[i].goal_id.id
                setp.id = theID
                self.goalCancel.publish(setp)

    def cobraHead(self,t1,t2,t3):
        # returns t4 & t5 for cobraHead orientation
        t4 = np.pi-t2-t3
        t5 = -0.50*np.pi-t1
        if t4 > 0:
            t4 = t4 - 2.0*np.pi
        return t4, t5

    def wristFK(self,t1,t2ur5,t3ur5):
        # returns x,y,z of wrist (mm)
        links = rospy.get_param('/ur5/jointLengths')
        dz = links[0]
        l1 = links[1]
        l2 = links[2]
        l3 = links[3]

        #%%%%%%%%%%%%%%%% From matlab code %%%%%%%%%%%%%%%% 
        t2 = -np.pi/2.0-t2ur5
        t3 = -(t3ur5 + t2ur5)

        z = dz + l2*cos(t2) + l3*sin(t3)
        v = l3*cos(t3)-l2*sin(t2);

        y = -l1*cos(-t1)-v*sin(t1)
        x = -l1*sin(-t1)-v*cos(t1)
        #%%%%%%%%%%%%%%%% From matlab code %%%%%%%%%%%%%%%% 

        return x,y,z

    def wristIK(self,x,y,z):
        # returns flag, t1, t2, t3 for desired wrist x,y,z (mm)

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
            # compute t1

            theta_a = atan2(y,x)
            if y < 0:
                theta_a = 2.0*np.pi + theta_a

            w = sqrt(x**2 + y**2)
            theta_b = acos(l1/w)
            t1 = 2.0*np.pi - theta_a - theta_b
            t1 = -(t1 - np.pi/2)

            # compute t2 & t3

            zred = z - dz

            v = sqrt(x**2+y**2)*sin(theta_b)

            ratio = (l2**2 + l3**2 - (v**2+zred**2))/(2.0*l2*l3)
            d23 = asin(ratio) # t2 - t3

            gamma = atan(zred/v)
            temp = l3*sin(np.pi/2 - d23)/sqrt(v**2+zred**2)
            t2 = asin(temp);
            t2 = t2 + gamma - np.pi/2;

            t3 = t2 - d23;
            #%%%%%%%%%%%%%%%% From matlab code %%%%%%%%%%%%%%%% 
            
            t2ur5 = -np.pi/2.0 - t2
            t3ur5 = -t3 - t2ur5

            return flag, t1, t2ur5, t3ur5
        
