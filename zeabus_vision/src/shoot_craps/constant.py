'''
    File name: constant.py
    Author: zeabus2018
    Date created: 05/27/2018
    Python Version: 3.6.1
'''
import math

'''
    REAL SIZE
        SIDE by SIDE = 9x9 
        RADIUS = 1
    DICE_SIZE must be divided by 3 
'''
DICE_SIZE = 60
SIDE_PER_RADIUS = 9
POINT_RADIUS = DICE_SIZE / SIDE_PER_RADIUS
POINT_AREA_LOWER = math.pi * (POINT_RADIUS-1.5)**2
POINT_AREA_UPPER = math.pi * (POINT_RADIUS+1.5)**2
EXPECTED_AREA_RATIO = 0.7

'''
    For windows
'''
# ABS_PATH = 'C:/Users/skconan/Desktop/Workspace/dice/'
# IMG_PATH = ABS_PATH + 'images/'

'''
    For Ubuntu
'''
ABS_PATH = '/home/skconan/catkin_ws/src/src_code/zeabus_vision/src/dice/'
IMG_PATH = ABS_PATH + 'images/'