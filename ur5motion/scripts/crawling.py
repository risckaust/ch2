#!/usr/bin/env python
import time
#import roslib 
import rospy
import numpy as np
import cv2

from control_msgs.msg import *
from trajectory_msgs.msg import *
from sensor_msgs.msg import *
from math import *

import ur5Lib
ur5Lib.setParams()

# dummy = rospy.wait_for_message('/joint_states',JointState)

def main():

    rospy.init_node('alpha', anonymous=True)

    sm = ur5Lib.ur5Class()
    rate = rospy.Rate(rospy.get_param('/ur5/fbRate'))

    time.sleep(1.0)

    cv2.namedWindow('keystrokes go here...')

    print "wakeup..."
    Q = rospy.get_param('/ur5/poseWakeup')
    sm.jointGoto(Q,15.0)
    time.sleep(15.0)

    print "get ready..."
    Q = rospy.get_param('/ur5/poseReady')
    sm.jointGoto(Q,15.0)
    time.sleep(15.0)

    print "crawl forward..."
    x,y,z = sm.wristFK(Q[0],Q[1],Q[2])
    x = x - 100
    
    flag, t1, t2, t3 = sm.wristIK(x,y,z)
    target = Q
    target[0] = t1
    target[1] = t2
    target[2] = t3
    target[3], target[4] = sm.cobraHead(t1,t2,t3)
    
    print x, y, z

    sm.jointGoto(target,5.0)
    time.sleep(5.0)

    Moving = True

    kc = 0
    while not rospy.is_shutdown():
        js = sm.jointPosition[0]
        t1, t2, t3 = sm.jointPosition[0], sm.jointPosition[1], sm.jointPosition[2]
        x, y, z = sm.wristFK(t1, t2, t3)
        if Moving:
            print x,y,z

        x = x - 10
        flag, t1, t2, t3 = sm.wristIK(x,y,z)
        t4, t5 = sm.cobraHead(t1, t2, t3)
        target = [t1, t2, t3, t4, t5, 0.0]
        if Moving:
            sm.jointGoto(target, 5.0)

        c = cv2.waitKey(1)
        if c != -1:
            if Moving:
                print "STOPPING!!!"
                sm.halt(0.2)
                Moving = False
            else:
                print "STARTING!!!"
                sm.jointGoto(target,5.0)
                Moving = True

        kc = kc+1
        rate.sleep()
                
if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass

