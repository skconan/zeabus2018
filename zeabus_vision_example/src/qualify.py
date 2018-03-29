# #!/usr/bin/python2.7
import cv2 as cv
import rospy
import numpy as np
#from remove_noise import *
from sensor_msgs.msg import CompressedImage , Image
from qualification_gate.msg import *
from qualification_gate.srv import *
from cv_bridge import CvBridge , CvBridgeError
from qualify_gate import *
from find_marker import *
sub_sampling = 1

def prepocessing (image):
    b,g,r = cv.split(image)
    b.fill(250)
    image =cv.merge((b,g,r))
    blur = cv.medianBlur(image,5)
    return blur

def print_result (msg) :
    print ('<----------') + str(msg) + ('---------->')
    

def get_object(image) :
    hsv = cv.cvtColor(image,cv.COLOR_BGR2HSV)
    # lower_orange = np.array([130,0,0])
    # upper_orange = np.array([158,255,255])
    lower_orange = np.array([123,0,0])
    upper_orange = np.array([180,255,255])
    obj = cv.inRange(hsv,lower_orange,upper_orange)
    return obj

# # def get_bg(image) :
# #     lower_bg = np.array([24,0,250])
# #     upper_bg = np.array([125,255,255])
# #     hsv = cv.cvtColor(image,cv.COLOR_BGR2HSV)
# #     bg = cv.inRange(hsv,lower_bg,upper_bg)
# #     return bg

def remove_noise (mask) :
    kernel = get_kernel('rect',(5,9))
    erode = cv.erode(mask,kernel)

    kernel = get_kernel('rect',(5,15))
    dilate = cv.dilate(erode,kernel)

    kernel = get_kernel('rect',(2,19))
    erode = cv.erode(dilate,kernel)

    return erode

def get_kernel(shape = 'rect',ksize =(5,5)) :
    if shape == 'rect' :
        return cv.getStructuringElement(cv.MORPH_RECT,ksize)

def process_gate(frame) :
    mask_change_color = prepocessing(frame)
    obj = get_object(mask_change_color)
    # bg = get_bg(mask_change_color)
    #mask = obj - bg
    remove = remove_noise(obj)
    return remove

def publish_result(img, type, topicName):
    if img is None:
        img = np.zeros((200, 200))
        type = "gray"
    bridge = CvBridge()
    pub = rospy.Publisher(
        str(topicName), Image, queue_size=10)
    if type == 'gray':
        msg = bridge.cv2_to_imgmsg(img, "mono8")
    elif type == 'bgr':
        msg = bridge.cv2_to_imgmsg(img, "bgr8")
    pub.publish(msg)


def message(x=0, pos=0, area=0, appear=False):
    global c_img
    print(x,pos,area,appear)
    m = qulification_gate()
    m.cx = x
    m.pos = pos
    m.area = area
    m.appear = appear
    print(m)
    return m

def message_marker(cx_left = 0 , cx_right = 0 , area = 0 , appear = False) :
    global c_img
    print(cx_left,cx_right,area,appear)
    m = qualification_marker()
    m.cx_left = cx_left
    m.cx_right = cx_right
    m.area = area
    m.appear = appear
    print(m)
    return m


def img_callback(msg):
    global img

    arr = np.fromstring( msg.data, np.uint8)
    img = cv.resize(cv.imdecode(arr, 1), (640, 512))

def img_bot_callback(msg):
    global img_bot, height_bot, width_bot
    arr = np.fromstring( msg.data, np.uint8)
    img_bot = cv.resize(cv.imdecode(arr, 1), (640, 512))
    height_bot, width_bot,_ = img_bot.shape


