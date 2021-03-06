/*
 * dvl_node.cpp
 *
 *  Created on: Dec 22, 2014
 *      Author: mahisorn
 */

#include <ros/ros.h>
#include <hg_ros_serial/serial.h>
#include <geometry_msgs/TwistWithCovarianceStamped.h>
#include <nav_msgs/Odometry.h>
#include <diagnostic_updater/diagnostic_updater.h>
#include <diagnostic_updater/publisher.h>
#include <boost/thread.hpp>

using namespace std;

boost::mutex g_mutex;
bool g_status_updated = false;
long g_status_date = 0;
float g_status_salinity = 0;
float g_status_temperature = 0;
float g_status_depth_of_transducer_face = 0;
float g_status_speed_of_sound = 0;
int g_status_num_error = 0;
int g_status_current_error = 0;
bool g_status_velocity_ok = false;

/*//// For Emergency //////////

ros::Publisher g_pub_dvl_odom;
float surface_depth;

/////////////////////////////*/

float surface_depth;

void checkDVLStatus(diagnostic_updater::DiagnosticStatusWrapper &stat)
{
  boost::lock_guard<boost::mutex> guard(g_mutex);

  if(g_status_updated)
  {
    //printf("TS: %ld %6.3f %6.3f %6.3f %6.3f %d 0x%02x\n", g_status_date, g_status_salinity, g_status_temperature, g_status_depth_of_transducer_face, g_status_speed_of_sound, g_status_num_error, g_status_current_error);
    g_status_updated = false;

    if(g_status_velocity_ok)
    {
      stat.summary(diagnostic_msgs::DiagnosticStatus::OK, "Velocity data is Good");
    }
    else
    {
      stat.summary(diagnostic_msgs::DiagnosticStatus::WARN, "Velocity data is Bad");
    }

    stat.add("Velocity data status", g_status_velocity_ok);
    stat.add("Time (yyMMddhhmmssff)", g_status_date);
    stat.add("Salinity (ppt)", g_status_salinity);
    stat.add("Temperature (C)", g_status_temperature);
    stat.add("Depth of transducer face (m)", g_status_depth_of_transducer_face);
    stat.add("Speed of sound (m/s)", g_status_speed_of_sound);
    stat.add("Total error", g_status_num_error);
    stat.add("Current error", g_status_current_error);
  }
}

int main(int argc, char **argv)
{
  ros::init(argc, argv, "dvl");
  ros::NodeHandle nh("~");

  hg_ros_serial::Serial serial;
  std::string device;
  int baudrate;
  std::string frame_id;

  nh.param<std::string>("device", device,"/dev/usb2serial/ftdi_FT03OMNT_03");

  nh.param<int>("baudrate", baudrate, 115200);

  nh.param<std::string>("frame_id", frame_id,"dvl_link");
  
  nh.param<float>("surface_depth", surface_depth, 4.7);


  if(!serial.openPort(device, baudrate))
  {
    ROS_FATAL("Cannot open port %s", device.c_str());
    return -1;
  }

  ROS_INFO("Open DVL on: %s", device.c_str());
  ROS_INFO("    baudrate: %d", baudrate);
  ROS_INFO("    frame_id: %s", frame_id.c_str());

  //stop device
  serial.writeString("===");
  serial.readLine();
  serial.readLine();
  serial.readLine();
  serial.readLine();

  //load default
  serial.writeString("CR1\n");
  serial.readLine();
  serial.readLine();

  //enable single-ping bottom tracking
  serial.writeString("BP1\n");

  //set maximum bottom search depth (dm)
  int maximum_bottom_search_depth;
  nh.param<int>("maximum_bottom_search_depth", maximum_bottom_search_depth, 100);
  stringstream ss;
  ss << "BX" << maximum_bottom_search_depth << "\n";
  serial.writeString(ss.str());

  //Set Heading Alignment to 0 degrees
  int heading_alignment;
  serial.writeString("EA-09000\n");

  //Set manual transducer depth in case depth sensor fails (dm)
  //serial.writeString("ED0\n");

  //Set Salinity saltwater(35) freshwater (0)
  int salinity;
  nh.param<int>("salinity", salinity, 0);
  ss.clear();
  ss << "ES" << salinity << "\n";
  serial.writeString(ss.str());
  serial.writeString("EX11111\n"); // Coordinate transformation

  /*
   Set Time between Ensembles to zero (ExplorerDVL will ping as fast as possible)
   Format  hh:mm:ss.ff
   Range   hh = 00 to 23 hours
           mm = 00 to 59 minutes
           ss = 00 to 59 seconds
           ff = 00 to 99 hundredths of seconds
   Default 00:00:00.00
  */
  std::string time_between_ensembles;
  nh.param<std::string>("time_between_ensembles", time_between_ensembles, "00:00:00.00");
  serial.writeString("TE" + time_between_ensembles + "\n");

  /*Set Time between Pings to zero (ExplorerDVL will ping as fast as possible)
   Purpose Sets the minimum time between pings.
   Format  mm:ss.ff
   Range   mm = 00 to 59 minutes
           ss = 00 to 59 seconds
           ff = 00 to 99 hundredths of seconds
   Default 00:00.05
   */
  std::string time_between_pings;
  nh.param<std::string>("time_between_pings", time_between_pings, "00:00.00");
  serial.writeString("TP" + time_between_pings + "\n");

  //Select output format (PD6, a ASCII text output format)
  serial.writeString("PD6\n");

  //Keep parameter
  serial.writeString("CK\n");

  //start
  serial.writeString("CS\n");

  ros::Publisher pub_twist = ros::NodeHandle().advertise<geometry_msgs::TwistWithCovarianceStamped>("dvl/data", 10);
  geometry_msgs::TwistWithCovarianceStamped dvl;

  /*//////////////////////////  For Emergency ////////////////////////////////////////////////

  g_pub_dvl_odom = ros::NodeHandle().advertise<nav_msgs::Odometry>("/dvl/odom", 10);
  nav_msgs::Odometry odom;
  float last_zdepth = 0;
  odom.header.frame_id = "odom";
  odom.child_frame_id = "base_link";


  //////////////////////////////////////////////////////////////////////////////////////////*/

  double velocity_stdev;
  nh.param<double>("velocity_stdev", velocity_stdev , 0.018); //1.8 cm/s @ 3 m/s for Phased Array type
  bool publish_invalid_data;
  nh.param<bool>("publish_invalid_data", publish_invalid_data , false);

  dvl.twist.covariance[0] = velocity_stdev * velocity_stdev;
  dvl.twist.covariance[7] = velocity_stdev * velocity_stdev;
  dvl.twist.covariance[13] = velocity_stdev * velocity_stdev;

  dvl.header.frame_id = frame_id;

  // The Updater class advertises to /diagnostics, and has a
  // ~diagnostic_period parameter that says how often the diagnostics
  // should be published.
  diagnostic_updater::Updater updater;
  updater.setHardwareIDf("Teledyne DVL @ %s", device.c_str());
  updater.add("DVL status updater", checkDVLStatus);
  updater.force_update();

  while(ros::ok())
  {
    try
    {
      // We can call updater.update whenever is convenient. It will take care
      // of rate-limiting the updates.
      updater.update();

      std::string line = serial.readLine();

      if(line.find(":SA") != std::string::npos)
      {
        /*
         SYSTEM ATTITUDE DATA
         :SA,±PP.PP,±RR.RR,HH.HH <CR><LF>

         where:
         PP.PP = Pitch in degrees
         RR.RR = Roll in degrees
         HHH.HH = Heading in degrees
         */

        float pitch, roll, yaw;

        sscanf(line.c_str(),":SA,%f,%f,%f", &pitch, &roll, &yaw);

        //printf("SA: p:%6.3f r:%6.3f y:%6.3f\n", pitch, roll, yaw);
      }
      else
      if(line.find(":TS") != std::string::npos)
      {
        /*
         TIMING AND SCALING DATA
         :TS,YYMMDDHHmmsshh,SS.S,+TT.T,DDDD.D,CCCC.C,BBB <CR><LF>

         where:
         YYMMDDHHmmsshh = Year, month, day, hour, minute, second, hundredths of seconds
         SS.S = Salinity in parts per thousand (ppt)
         TT.TT = Temperature in C
         DDDD.D = Depth of transducer face in meters
         CCCC.C = Speed of sound in meters per second
         BBB = Built-in Test (BIT) result code where the first B on the left is the number of BIT errors (MSB) and the last 2 BB (LSB) are the
         actual BIT error as describe below.

         Error Code
         Description
         0x01 Transmitter Shutdown
         0x02 Transmitter Overcurrent
         0x03 Transmitter Undercurrent
         0x04 Transmitter Undervoltage

         0x10 FIFO interrupt misse}d
         0x11 FIFO ISR re-entry

         0x21 Sensor start failure
         0x22 Temperature sensor failure
         0x23 Pressure sensor failure
         0x24 Tilt sensor failure
         0x27 Bad Comms with sensor
         0x28 Bad Comms with sensor
         0x60 Sensor Cal Data checksum failure

         0x30 Stuck UART
         0x31 QUART Transmit timeout
         0x32 QUART IRQ Stuck
         0x33 QUART Buffer stuck
         0x34 QUART IRQ Active
         0x35 QUART cannot clear interrupt

         0x50 RTC low battery
         0x51 RTC time not set

         0xFF Power failure

         If there is more than one BIT error, then it will take several ensembles to output all the BIT errors. For example, if there are 3 BIT
         errors detected, then the output will be BBB = 3xx on ensemble n, BBB = 3yy on ensemble n+1, and BBB = 3zz on ensemble n+2,
         where xx, yy, and zz are the three different error messages detected.
         */

        boost::lock_guard<boost::mutex> guard(g_mutex);
        sscanf(line.c_str(),":TS,%ld,%f,%f,%f,%f,%d",
               &g_status_date,
               &g_status_salinity,
               &g_status_temperature,
               &g_status_depth_of_transducer_face,
               &g_status_speed_of_sound,
               &g_status_num_error);

        g_status_current_error = g_status_num_error & 0xff;
        g_status_num_error = g_status_num_error >> 8;

        g_status_updated = true;


        //printf("TS: %ld %6.3f %6.3f %6.3f %6.3f %d 0x%02x\n", date, salinity, temperature, depth_of_transducer_face, speed_of_sound, num_error, current_error);


      }
      else
      if (line.find(":BI") != std::string::npos)
      {
        /*
         BOTTOM-TRACK, INSTRUMENT-REFERENCED VELOCITY DATA
         :BI,±XXXXX,±YYYYY,±ZZZZZ,±EEEEE,S <CR><LF>
         where:
         ±XXXXX = X-axis velocity data in mm/s (+ = Bm1 Bm2 xdcr movement relative to bottom)
         ±YYYYY = Y-axis velocity data in mm/s (+ = Bm4 Bm3 xdcr movement relative to bottom)
         ±ZZZZZ = Z-axis velocity data in mm/s (+ = transducer movement away from bottom)
         ±EEEEE = Error velocity data in mm/s
         S = Status of velocity data (A = good, V = bad)
         */
#if 0
        int vx, vy, vz, v_error;
        char status;
        sscanf(line.c_str(), ":BI,%d,%d,%d,%d,%c", &vx, &vy, &vz, &v_error, &status);
        //printf("BI: vx %6.3f vy %6.3f vz %6.3f v_error %6.3f OK:%d\n", vx*0.001, vy*0.001, vz*0.001, v_error*0.001, status == 'A');

        dvl.header.stamp = ros::Time::now();

        if(status != 'A')
        {
          g_status_velocity_ok = false;
	  ROS_WARN("DVL : BAD DATA!");
          //invalid data
          if(!publish_invalid_data)
          {
            //ROS_WARN_THROTTLE(2.0, "Invalid BOTTOM-TRACK velocity data");
            continue;
          }
          //else
          //{
            //dvl.twist.twist.linear.x = 0;
            //dvl.twist.twist.linear.y = 0;
            //dvl.twist.twist.linear.z = 0;
          //}
        }
        else
        {
          g_status_velocity_ok = true;
	  ROS_INFO("DVL : GOOD DATA!");
          //ROS_INFO("%d %d %d", vx, vy, vz);

          //float xx, xy, yx, yy;
          //xx = vx*cos(M_PI_4);
          //xy = vx*sin(M_PI_4);
          //yx = vx*cos(M_PI_4);
          //yy = vx*sin(M_PI_4);

          //ROS_INFO("xx:%6.3f xy:%6.3f yx:%6.3f yy:%6.3f", xx, xy, yx, yy);


          dvl.twist.twist.linear.x = -vx * 0.001;
          dvl.twist.twist.linear.y = -vy * 0.001;
          dvl.twist.twist.linear.z = vz * 0.001;

          //double velocity_covariance = v_error * 0.001 * v_error * 0.001;
          //dvl.twist.covariance[0] = velocity_covariance
          //dvl.twist.covariance[7] = velocity_covariance
          //dvl.twist.covariance[14] = velocity_covariance
        }




        if(pub_twist.getNumSubscribers() != 0)
          pub_twist.publish(dvl);
#endif
      }
      else
      if (line.find(":BS") != std::string::npos)
      {
        /*
         BOTTOM-TRACK, SHIP-REFERENCED VELOCITY DATA
         :BS,±TTTTT,±LLLLL,±NNNNN,S <CR><LF>
         where:
         ±TTTTT = Transverse vel. data in mm/s (+ = Port Stbd ship movement relative to bottom)
         ±LLLLL = Longitudinal vel. data in mm/s (+ = Aft Fwd ship movement relative to bottom)
         ±NNNNN = Normal velocity data in mm/s (+ = ship movement away from bottom)
         S = Status of velocity data (A = good, V = bad)
         */
        //printf("BS:\n");
        int vx, vy, vz, v_error;
		char status;
		sscanf(line.c_str(), ":BS,%d,%d,%d,%c", &vy, &vx, &vz, &status);
		//printf("BS: vx %6.3f vy %6.3f vz %6.3f OK:%d\n", vx*0.001, vy*0.001, vz*0.001, status == 'A');

		dvl.header.stamp = ros::Time::now();

		if (status != 'A') {
			g_status_velocity_ok = false;
			ROS_INFO("DVL : BAD DATA");
			//invalid data
			if (!publish_invalid_data) {
				//ROS_WARN_THROTTLE(2.0, "Invalid BOTTOM-TRACK velocity data");
				continue;
			} else {
				//dvl.twist.twist.linear.x = 0;
				//dvl.twist.twist.linear.y = 0;
				//dvl.twist.twist.linear.z = 0;
			}
		} else {
			g_status_velocity_ok = true;
			ROS_INFO("DVL : GOOD DATA");
			dvl.twist.twist.linear.x = vx * 0.001;
			dvl.twist.twist.linear.y = -vy * 0.001;
			dvl.twist.twist.linear.z = vz * 0.001;
		}

		if (pub_twist.getNumSubscribers() != 0)
			pub_twist.publish(dvl);


      }
      else
      if (line.find(":BE") != std::string::npos)
      {
        /*
         BOTTOM-TRACK, EARTH-REFERENCED VELOCITY DATA
         :BE,±EEEEE,±NNNNN,±UUUUU,S <CR><LF>
         where:
         ±EEEEE = East (u-axis) velocity data in mm/s (+ = ADCP movement to east)
         ±NNNNN = North (v-axis) velocity data in mm/s (+ = ADCP movement to north)
         ±UUUUU = Upward (w-axis) velocity data in mm/s (+ = ADCP movement to surface)
         S = Status of velocity data (A = good, V = bad)
         */
        //printf("BS:\n");


      }
      else
      if (line.find(":BD") != std::string::npos)
      {
        /*
         BOTTOM-TRACK, EARTH-REFERENCED DISTANCE DATA
         :BD,±EEEEEEEE.EE,±NNNNNNNN.NN,±UUUUUUUU.UU,DDDD.DD,TTT.TT <CR><LF>
         where:
         +EEEEEEEE.EE = East (u-axis) distance data in meters
         +NNNNNNNN.NN = North (v-axis) distance data in meters
         +UUUUUUUU.UU = Upward (w-axis) distance data in meters
         DDDD.DD = Range to bottom in meters
         TTT.TT = Time since last good-velocity estimate in seconds
         */

/*//////////////////////////////  For Emergency ///////////////////////////////////////////
        odom.header.stamp = ros::Time::now();
		float ua, uv, uw, RtB, ta;
		sscanf(line.c_str(), ":BD,%f,%f,%f,%f,%f", &ua, &uv, &uw, &RtB, &ta);
		//ROS_INFO(":BD,%f,%f,%f,%f,%f", ua, uv, uw, RtB, ta);
                float zdepth = -(surface_depth - RtB);
	if(g_status_velocity_ok)
        {
		odom.pose.pose.position.z = zdepth;
		last_zdepth = zdepth;
        }
        else
        {
             if (!publish_invalid_data) {
				//ROS_WARN_THROTTLE(2.0, "Invalid BOTTOM-TRACK velocity data");
				continue;
			} 
 	     else {

			}
        }

	if (g_pub_dvl_odom.getNumSubscribers() != 0)
                     g_pub_dvl_odom.publish(odom);

/////////////////////////////////////////////////////////////////////////////////////////*/
		
        //printf("BD:\n");
      }
      else
      {
        //unknown line, just print it out as warning message
        ROS_WARN_STREAM("Echo/respond/unknown line: " << line);
      }
    }
    catch (exception& e)
    {
      std::cout << e.what() << endl;
    }

    ros::spinOnce();
}

  //stop stream
  serial.writeString("===");
  serial.readLine();
  serial.readLine();
  serial.readLine();
  serial.readLine();
}

