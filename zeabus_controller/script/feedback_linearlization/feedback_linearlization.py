#!/usr/bin/python2

import rospy, math , tf

import numpy

from coriolis import coriolis_rb , coriolis_a 
from hydrodynamic import hydrodynamic_q , hydrodynamic_i
from gravity_buoyancy import gravitational_buoyancy_force  

from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist

class feedback_linearlization:
	
	def __init__( self ):
		rospy.init_node('feedback_linearlization')
		
		self.position = [0 , 0 , 0 , 0 , 0 , 0]
		self.velocity = [0 , 0 , 0 , 0 , 0 , 0]

		rospy.Subscriber('/auv/state' , Odometry , self.listen_state)
		rospy.Subscriber('/feedback/cmd_vel', Twist , self.listen_cmd_vel)

		self.publish_thruster = rospy.Publisher('/cmd_vel' , Twist , queue_size = 1)

##############################################################################################
# test get param
#		if rospy.has_param('test'):
#			print('have param test')
#		else:
#			print('don\'t have param test')
#		self.test = rospy.get_param("/feedback_linearlization/test" , [4 , 5 ,6])
#		print( self.test )
#		self.mass = rospy.get_param("mass" , 25)
#		print( self.mass )
##############################################################################################

#----------------------------- this part for get value param --------------------------------

		self.mass = rospy.get_param("/feedback_linearlization/mass" , 45 )
		self.i_xx = rospy.get_param("/feedback_linearlization/i_xx" , 1.03 )
		self.i_yy = rospy.get_param("/feedback_linearlization/i_yy" , 0.038 )
		self.i_zz = rospy.get_param("/feedback_linearlization/i_zz" , 0.06)

		self.x_u_dot = rospy.get_param("/feedback_linearlization/x_u_dot" , 3 )
		self.x_w_dot = rospy.get_param("/feedback_linearlization/x_w_dot" , 0.0 )
		self.x_q_dot = rospy.get_param("/feedback_linearlization/x_q_dot" , 0.0)
		
		self.y_u_dot = rospy.get_param("/feedback_linearlization/y_u_dot" , 3 )
		self.y_w_dot = rospy.get_param("/feedback_linearlization/y_w_dot" , 0.0 )
		self.y_q_dot = rospy.get_param("/feedback_linearlization/y_q_dot" , 0.0)
		
		self.z_u_dot = rospy.get_param("/feedback_linearlization/z_u_dot" , 0 )
		self.z_w_dot = rospy.get_param("/feedback_linearlization/z_w_dot" , 3.0 )
		self.z_q_dot = rospy.get_param("/feedback_linearlization/z_q_dot" , 0.0)
		
		self.k_u_dot = rospy.get_param("/feedback_linearlization/k_u_dot" , 0 )
		self.k_w_dot = rospy.get_param("/feedback_linearlization/k_w_dot" , 0.001 )
		self.k_q_dot = rospy.get_param("/feedback_linearlization/k_q_dot" , 0.0)
		
		self.m_u_dot = rospy.get_param("/feedback_linearlization/m_u_dot" , 0.0 )
		self.m_w_dot = rospy.get_param("/feedback_linearlization/m_w_dot" , 0.0 )
		self.m_q_dot = rospy.get_param("/feedback_linearlization/m_q_dot" , 0.001)
		
		self.n_u_dot = rospy.get_param("/feedback_linearlization/n_u_dot" , 0.0 )
		self.n_w_dot = rospy.get_param("/feedback_linearlization/n_w_dot" , 0.0 )
		self.n_q_dot = rospy.get_param("/feedback_linearlization/n_q_dot" , 0.001)
	
		self.x_u = rospy.get_param("/feedback_linearlization/x_u" , 0.3 )
		self.y_u = rospy.get_param("/feedback_linearlization/y_u" , 0.3 )
		self.z_u = rospy.get_param("/feedback_linearlization/z_u" , 0.3 )
		self.k_u = rospy.get_param("/feedback_linearlization/k_u" , 0.001 )
		self.m_u = rospy.get_param("/feedback_linearlization/m_u" , 0.001 )
		self.n_u = rospy.get_param("/feedback_linearlization/n_u" , 0.001 )
	
		self.x_abs_u = rospy.get_param("/feedback_linearlization/x_abs_u" , 85.25 )
		self.y_abs_u = rospy.get_param("/feedback_linearlization/y_abs_u" , 100 )
		self.z_abs_u = rospy.get_param("/feedback_linearlization/z_abs_u" , 173.975 )
		self.k_abs_u = rospy.get_param("/feedback_linearlization/k_abs_u" , 0.399 )
		self.m_abs_u = rospy.get_param("/feedback_linearlization/m_abs_u" , 8.925 )
		self.n_abs_u = rospy.get_param("/feedback_linearlization/n_abs_u" , 23.296 )
		
		self.weight = rospy.get_param("/feedback_linearlization/weight" , 85.25 )
		self.buoyancy = rospy.get_param("/feedback_linearlization/buoyancy" , 100 )
		self.x_cm = rospy.get_param("/feedback_linearlization/x_cm" , 173.975 )
		self.x_cb = rospy.get_param("/feedback_linearlization/x_cb" , 0.399 )
		self.y_cm = rospy.get_param("/feedback_linearlization/y_cm" , 8.925 )
		self.y_cb = rospy.get_param("/feedback_linearlization/y_cb" , 23.296 )
		self.z_cm = rospy.get_param("/feedback_linearlization/z_cm" , 8.925 )
		self.z_cb = rospy.get_param("/feedback_linearlization/z_cb" , 23.296 )

##############################################################################################	

# ( m , i_xx , i_yy , i_zz ) argument of coriolis_rb
		self.c_rb = coriolis_rb( self.mass	, self.i_xx	, self.i_yy	, self.i_zz	)

# ( a_1 , a_2 , a_3 , b_1 , b_2 , b_3 ) argument for input constant
		self.c_a = coriolis_a( 	[	self.x_u_dot , self.x_w_dot , self.x_q_dot]		
							, 	[	self.y_u_dot , self.y_w_dot , self.y_q_dot]			
							, 	[	self.z_u_dot , self.z_w_dot , self.z_q_dot]
							, 	[	self.k_u_dot , self.k_w_dot , self.k_q_dot]		
							, 	[	self.m_u_dot , self.m_w_dot , self.m_q_dot]	
							, 	[	self.n_u_dot , self.n_w_dot , self.n_q_dot] )

# ( x , y , z , k , m , n)
		self.d_i = hydrodynamic_i(	self.x_u,	self.y_u,	self.z_u,	
									self.k_u,	self.m_u,	self.n_u)
# ( x , y , z , k , m , n)
		self.d_q = hydrodynamic_q( 	self.x_abs_u,	self.y_abs_u,	self.z_abs_u,	
									self.k_abs_u,	self.m_abs_u,	self.n_abs_u)

# (w , b , x_cm , x_cb , y_cm , y_cb , z_cm , z_cb):
		self.g_n = gravitational_buoyancy_force( 	self.weight , self.buoyancy , 
													self.x_cm 	, self.x_cb		,
													self.y_cm	, self.y_cb		,
													self.z_cm	, self.z_cb		)

		rospy.spin()

	def listen_state( self , message ):
		euler_angular = tf.transformations.euler_from_quaternion(
							( message.pose.pose.orientation.x , message.pose.pose.orientation.y,
							  message.pose.pose.orientation.z , message.pose.pose.orientation.w)
																)
		self.position[0] = message.pose.pose.position.x
		self.position[1] = message.pose.pose.position.y
		self.position[2] = message.pose.pose.position.z
		self.position[3] = euler_angular[0]
		self.position[4] = euler_angular[1]
		self.position[5] = euler_angular[2]

		self.velocity[0] = message.twist.twist.linear.x
		self.velocity[1] = message.twist.twist.linear.y
		self.velocity[2] = message.twist.twist.linear.z
		self.velocity[3] = message.twist.twist.linear.x
		self.velocity[4] = message.twist.twist.linear.y
		self.velocity[5] = message.twist.twist.linear.z

	def listen_cmd_vel( self , message):		
		self.thruster= numpy.asmatrix( [
										[ self.velocity[0] ],
										[ self.velocity[1] ],
										[ self.velocity[2] ],
										[ self.velocity[3] ],
										[ self.velocity[4] ],
										[ self.velocity[5] ],
										])

		self.output = self.thruster - ( self.c_rb.input_value( self.velocity[0]
												,self.velocity[1]
												,self.velocity[2])
						+ self.c_a.input_value(  self.velocity[0]
												,self.velocity[1]
												,self.velocity[2]
												,self.velocity[3]
												,self.velocity[4]
												,self.velocity[5])) * self.thruster - (
								self.d_i.constant_matrix +
								self.d_q.input_value( 	self.velocity[0] ,
														self.velocity[1] ,
														self.velocity[2] ,
														self.velocity[3] ,
														self.velocity[4] ,
														self.velocity[5])
							) * self.thruster - self.g_n.input_value( 
								self.position[3] , self.position[4] , self.position[5])

		self.publish_thruster.publish( self.convert_output() )
	
	def convert_output( self ):
		data_twist = Twist()	
		data_twist.linear.x = self.output[0 , 0]	
		data_twist.linear.y = self.output[1 , 0]	
		data_twist.linear.z = self.output[2 , 0]	
		data_twist.angular.x = self.output[3 , 0]	
		data_twist.angular.y = self.output[4 , 0]	
		data_twist.angular.z = self.output[5 , 0]
		
		return data_twist	

if __name__=='__main__':
	
	filter_control = feedback_linearlization()
