#include <ros/ros.h>
#include <iostream>
#include <stdio.h>
#include <fstream>
#include "geometry_msgs/Twist.h"
#include "std_msgs/int16.h"

using namespace std;
using namespace cv;


class ModeSelect
{
public:
	//Global variables
	int16 modeNo, mode_Husky, mode_UR, mode_Viz; //Subscribed modes
	std_msgs::int16 M_h, M_u, M_v, M_g; //Published modes (Default vals)
	
	//Constructor
	ModeSelect(){
		//Initialize all mode vars
		mode_Husky = 0; mode_UR = 0; mode_Viz = 0; mode_Grip = 0;
		M_h = 0; M_u = 0; M_v = 0; M_g = 0;
	};
	
	//Husky current mode callback
	void mode_Husky_Cb(const std_msgs::int16& mode_Hcur){
		mode_Husky = mode_Hcur;
		//cout << "Mode Husky: " << mode_Husky << endl;
	}
	//UR5 current mode callback
	void mode_UR_Cb(const std_msgs::int16& mode_URcur){
		mode_UR = mode_URcur;
		//cout << "Mode UR: " << mode_UR << endl;
	}
	//Vision current mode callback
	void mode_Viz_Cb(const std_msgs::int16& mode_Viscur){
		mode_Viz = mode_Viscur;
		//cout << "Mode Vision: " << mode_Viz << endl;
	}
	//Gripper current mode callback
	void mode_Grip_Cb(const std_msgs::int16& mode_Gripcur){
		mode_Grip = mode_Gripcur;
		//cout << "Mode Grip: " << mode_Grip << endl;
	}
	
	//Main mode selection function
	int modeSwitch(int mode_Husky, int mode_UR, int mode_Vision, int mode_Grip){
		//Until Husky-Rover mode, State is on Husky; deactivate the rest
		if (mode_Husky < 2){
			M_u = 0; M_v = 0; M_g = 0;
		}
		
		//In Husky-Rover mode, activate the cascade detection
		//for CAM_1 (side camera) for "whole tool"
		if (mode_Husky == 2){
			M_u = 0; M_v = 1; M_g = 0;
		}
		
		//Until Husky-Align mode finishes, deactivate the rest
		if ( (mode_Husky > 2) && (mode_Husky <= 9) ){
			M_u = 0; M_v = 0; M_g = 0;
		}
		
		//After Husky aligned, get UR to ready pose
		if ( mode_Husky == 10 ){
			if ( mode_UR == 0 ) {
				M_u = 1; M_v = 0; M_g = 0;
			}
			elseif ( mode_UR == 2 ) {
				//(Internally switched). Means UR aligned to the panel and came back,
				//and elevated to find tools ROI
				M_u = 3; M_v = 2; M_g = 0;
			}
			elseif ( (mode_UR == 3) && (mode_Viz == 3) ) {
				//mode_Viz Internally switched: means 6 tool tips are detected
				M_u = 4; M_v = 0; M_g = 0;
			}
			elseif ( mode_UR == 4) {
				//UR is on valve location, run valve detection and align with the valve
				M_u = 5; M_v = 3; M_g = 1;
			}
			elseif ( mode_UR == 4) {
				//UR is on valve location, run valve detection and align with the valve
				M_u = 5; M_v = 3; M_g = 1;
			}
			
			ros::Duration(0.1).sleep(); // sleep for half a second
			return modeNo;
		}
	
	
private:
	
};
