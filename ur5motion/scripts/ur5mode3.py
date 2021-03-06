#!/usr/bin/env python
import time
import rospy
import roslib 
import numpy as np
import cv2
import actionlib
import math

from std_msgs.msg import *
from control_msgs.msg import *
from trajectory_msgs.msg import *
from sensor_msgs.msg import *
from actionlib_msgs.msg import *
from math import *

import ur5libmode
ur5libmode.setParams()

# dummy = rospy.wait_for_message('/joint_states',JointState)

#State publisher [Ready pos=1, Crawling = --, Aligned = --, BackPlane = 2, MovedToTool = 5, .... = 6, ]
ur_mode_pub = rospy.Publisher('/mode_u_main', Int32, queue_size=10)

def main():

    ####### Initializations

    rospy.init_node('alpha', anonymous=True)

    sm = ur5libmode.ur5Class()

    print "Waiting for actionLib server..."
    sm.client.wait_for_server()
    print "Connected to server."
    sm.client.cancel_all_goals()

    rate = rospy.Rate(rospy.get_param('/ur5/fbRate'))

    #######


    if rospy.get_param('/ur5/onHusky'):
	dwellTime   	       = 15.0
	velocity  	       = 9.0
	velCmd      	       = 7.0
	degShift   	       = 0.5
	xBackBlane             = 200.0

	xValveToTools	       = 0.0
	yValveToTools	       = 450.0
	zValveToTools	       = 50.0
	nWayPoints	       = 4

	xToolsToValve          = 0.0
	yToolsToValve          = -350.0


	xTOvalve	      = -20.0
	yTOvalve	      = 0.0
	zTOvalve	      = 0.0


	time.sleep(1.0)
	state_topic           = 0
    

    # Initialize logical variables
    Crawling 	     	= True
    Ready 	        = True
    MoveToValve         = True
    BackPlane	        = True
    MoveTOTools         = True
    

    while not rospy.is_shutdown():
###################################################
#####  Mode 1: Get ready, aligned and backplane ###
##################################################
	if sm.ur_mode==0:
	   time.sleep(0.1)
	   print "I am in sleeping mode, ur_mode is 0"
	   

	elif Ready and sm.ur_mode==1:
		print "sm.ur_mode=1, Get ready..."
		state_topic = 1 
		sm.jointGoto(rospy.get_param('/ur5/poseReady'),dwellTime)
		time.sleep(dwellTime)
		sm.client.wait_for_result()
		if Crawling: # CRAWL MODE
		    Aligned = False
		    x,y,z = sm.wristFK(sm.jointPosition[0],sm.jointPosition[1],sm.jointPosition[2])
		    print "Current: ", x, y, z
		    Arrived = False
		    while not Arrived:
		        flag = sm.xyzShift(-1.0, 0.0, 0.0, velCmd)
		        time.sleep(0.2)
		        sm.client.wait_for_result()
		        if sm.anyButton():
		            print "STOPPING!!!"
		            Arrived = True
		            Crawling = False
		        else:
		            xNow,yNow,zNow = sm.wristFK(sm.jointPosition[0],sm.jointPosition[1],sm.jointPosition[2])
		            print "x/y/z: ", xNow, yNow, zNow
		elif not Aligned: # ALIGN MODE
		    Aligned = False
		    while not Aligned:
		        greenSide = (sm.buttons[0] or sm.buttons[1])
		        blueSide = (sm.buttons[2] or sm.buttons[3])
		        dq = degShift/180.0*np.pi # degShift  degree shift per second
		        Q = sm.jointPosition
		        print Q[4]
		        if (greenSide and blueSide):
		            Aligned = True
		            Crawling = False
		            sm.q5offset = Q[4] - rospy.get_param('/ur5/poseReady')[4]
		            print "Aligned! dQ = ", sm.q5offset

			    xTouch,yTouch,zTouch = sm.wristFK(sm.jointPosition[0],sm.jointPosition[1],sm.jointPosition[2])
		        elif (greenSide or blueSide):
			    print "One side pushbutton pressed"
		            flag = sm.xyzShift(15.0, 0.0, 0.0, velCmd) # If key pressed, come back
		            sm.client.wait_for_result()

		            if greenSide: # Assumes green side on right when facing panel
		                sm.q5offset = sm.q5offset + dq
		            else: # blueSide
		                sm.q5offset = sm.q5offset - dq

			    Crawling = True # Move forward again
		            Aligned = True
		        else:
		            print "No buttons pressed?"
		            flag = sm.xyzShift(10.0, 0.0, 0.0, velCmd)
		            sm.client.wait_for_result()
		            
		elif Aligned and not BackPlane and sm.ur_mode==2:  #Aligned; Switch to search mode
		    print "ARM: Moving back: [x,y,z] = [200,0,0]"
		    flag = sm.xyzShift(200.0, 0.0, 0.0, velCmd)

		    sm.client.wait_for_result()
		    flag = sm.xyzShift(0.0, 0.0, 150.0, velCmd)
		    sm.client.wait_for_result()
    		    state_topic = 2
		    Ready=False







###################################################
##########  Mode : align with valve     ##########
###################################################
	           
	elif  sm.ur_mode==7:
		flag = sm.xyzShift(0.5*sm.pixel_x, 0.5*sm.pixel_y, 0.5*sm.pixel_z, 0.5*velCmd)
		sm.client.wait_for_result()
		xValve,yValve,zValve= sm.wristFK(sm.jointPosition[0],sm.jointPosition[1],sm.jointPosition[2])
		print "xValve/yValve/zValve: ", xValve,yValve,zValve
		state_topic = 7


###################################################
############## Mode 7: Approach the valve      ####
###################################################


	elif  sm.ur_mode==8:
		flag = sm.xyzGoto(xValve-120.0,yValve,zValve, velocity)
		sm.client.wait_for_result()
		#TODO something form the gripper/vision to detect the valve size
        state_topic = 9




###################################################
############## Mode 7:           punching      ####
###################################################


	elif  sm.ur_mode==10:
		Q = sm.jointPosition
		Q[5]=Q[5]+15*np.pi/180
		Qtarget=[Q[0],Q[1],Q[2],Q[3],Q[4],Q[5]]
		sm.jointGoto(Qtarget,5.0)
		sm.client.wait_for_result()
		state_topic = 11






###################################################
##############  Mode 8  BackBlane    ###########
###################################################  
	elif BackPlane and  sm.ur_mode==12:
		flag = sm.xyzShift(xBackBlane,0,0, velocity)
		sm.client.wait_for_result()
	    	state_topic = 13
	    	BackPlane = False
	    	
###################################################
##############  Mode 8  Back to tools   ###########
###################################################  	    	
	    	
	    	
	elif MoveTOTools and  sm.ur_mode==14:
		flag = sm.xyzShiftWayPoints(0,450,50,nWayPoints, velocity)
		sm.client.wait_for_result()
		state_topic = 15
		MoveTOTools = False
	  
###################################################
########  Mode 9  Align with the first tool   #####
###################################################  
	elif  sm.ur_mode==16:
		flag = sm.xyzShift(0.5*sm.pixel_x, 0.5*sm.pixel_y, 0.5*sm.pixel_z, 0.5*velCmd)
		sm.client.wait_for_result()
		state_topic = 16
		
###################################################
####  Mode10 get colser to the tool   by 2 mm at a time 
###################################################  
	elif  sm.ur_mode==17:
		flag = sm.xyzShift(2.0, 0.5*sm.pixel_y, 0.5*sm.pixel_z, 0.5*velCmd)
		sm.client.wait_for_result()
		state_topic = 18
		BackPlane = True
		
		
###################################################
########## Mode: Move back to the back blane  #####
###################################################  
	elif  BackPlane and sm.ur_mode==19:
		flag = sm.xyzShift(xBackBlane,0.0, 0.0, velCmd)
		sm.client.wait_for_result()
		state_topic = 20
		BackPlane = False
		MoveToValve  = True 					
		
		
###################################################
#######  Mode 10 back to valve with the tool   ####
###################################################
	elif MoveToValve and sm.ur_mode==21:
		flag = sm.xyzGoto(xValve,yValve,zValve, velocity)
		sm.client.wait_for_result()
		state_topic = 22
		MoveToValve = False
		
		
	
	
	
	
	
	
	
###################################################
#######          Mode 11 ROTAT with the tool   ####
###################################################
	elif  sm.ur_mode==23:
		Q = sm.jointPosition
		Q[5]=Q[5]+15*np.pi/180
		Qtarget=[Q[0],Q[1],Q[2],Q[3],Q[4],Q[5]]
		sm.jointGoto(self,Qtarget,5.0)
		sm.client.wait_for_result()
		state_topic = 24





	

	ur_mode_pub.publish(state_topic)








		


if __name__ == '__main__':
    try:
        main()
	
    except rospy.ROSInterruptException:
        pass

