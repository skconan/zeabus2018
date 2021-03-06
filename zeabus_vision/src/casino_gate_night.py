#!/usr/bin/python2.7
"""
    To use in simulator please assign world varible (line 20) to 'sim' 
    # world = 'sim'
    To use in real world please assign world varible (line 20) to 'real' 
    # world = 'real'
"""
import rospy
import cv2 as cv
import numpy as np
from sensor_msgs.msg import CompressedImage, Image
from zeabus_vision.msg import vision_casino_gate
from zeabus_vision.srv import vision_srv_casino_gate
from cv_bridge import CvBridge, CvBridgeError
from vision_lib import *
import color_text
img = None
img_res = None
sub_sampling = 1
pub_topic = "/vision/casino_gate/"
world = "real"


def mission_callback(msg):
    """
        When call service it will run this 
        Returns:
            a group of process value from this program
    """
    print_result('mission_callback', color_text.CYAN)

    task = msg.task.data

    print('task:', str(task))
    if task == 'casino_gate':
        return find_gate()


def image_callback(msg):
    """
        Convert data from camera to image
    """
    global img, sub_sampling, img_res
    arr = np.fromstring(msg.data, np.uint8)
    img = cv.resize(cv.imdecode(arr, 1), (0, 0),
                    fx=sub_sampling, fy=sub_sampling)
    himg, wimg = img.shape[:2]
    img = cv.resize(img, (int(wimg/3), int(himg/3)))
    img_res = img.copy()


def message(cx1=-1, cx2=-1, area=-1, appear=False, w_h_ratio=0, right_excess=False, left_excess=False):
    """
        Convert value into a message (from vision_qualifying_gate.msg)
        Returns:
            vision_qualifying_gate (message): a group of value from args
    """
    m = vision_casino_gate()
    m.cx1 = cx1
    m.cx2 = cx2
    m.area = area
    m.appear = appear
    m.w_h_ratio = w_h_ratio
    m.left_excess = left_excess
    m.right_excess = right_excess
    print(m)
    return m


def rm_sure_bg(img):
    lower = np.array([0, 0, 0], dtype=np.uint8)
    upper = np.array([255, 100, 100], dtype=np.uint8)
    mask = cv.inRange(img, lower, upper)
    return mask


def get_object():
    """
        get mask from picture and remove some noise
        Returns:
            mask (ONLY GATE AREA)
    """
    global img
    hsv = cv.cvtColor(img,cv.COLOR_BGR2HSV)
    r1 = np.array([0,0,0])
    r2 = np.array([40,255,255])
    r3 = np.array([130,0,0])
    r4 = np.array([180,255,255])
    mr1 = cv.inRange(hsv,r1,r2)
    mr2 = cv.inRange(hsv,r3,r4)
    mr = cv.bitwise_or(mr1,mr2)
    b1 = np.array([0,0,0])
    b2 = np.array([180,255,80])
    mb = cv.inRange(hsv,b1,b2)
    mask = cv.bitwise_or(mb,mr)
    return mask


def get_ROI(mask):
    global img
    himg, wimg = img.shape[:2]
    ROI = []
    contours = cv.findContours(
        mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)[1]
    for cnt in contours:
        if cv.contourArea(cnt) < 100:
            continue
        x, y, w, h = cv.boundingRect(cnt)
        area = (1.0*w*h)/(1.0*wimg*himg)
        w_h_ratio = 1.0*w/h
        top_excess = (y < 0.05*himg)
        bot_excess = ((y+h) > 0.95*himg)
        right_excess = (x+w > 0.95*wimg)
        left_excess = (x < 0.05*wimg)
        window_excess = top_excess or bot_excess or right_excess or left_excess
        #print (w_h_ratio,area,window_excess)
        if area > 0.05 and w_h_ratio <= 3 and w_h_ratio >= 1 and not window_excess:
            ROI.append(cnt)
    return ROI


def find_gate():
    """
        find gate on the picture and draw rectangle cover the gate

        Returns:
            message: (a group of data from vision_qualifying_gate.msg)
            if cannot find gate:
                return default value
            else if find a gate (a little bit noise):
                return float: cx in range of -1 to 1, 
                       int: pos 
                              0 = all part of gate (can calculate cx)
                             -1 = left side of gate
                              1 = right side of gate
                            -99 = not sure (can find only one pole of gate)
                       float: area in range of 0 to 1,
                       bool: appear is true
            else if find a gate (a lot of noise):
                return float: cx in range of -1 to 1, 
                       int: pos is 0
                       float: area in range of 0 to 1,
                       bool: appear is true         
    """
    global img, img_res
    while img is None and not rospy.is_shutdown():
        img_is_none()
    area = -1
    appear = False
    himg, wimg = img.shape[:2]
    mask = get_object()
    publish_result(mask, 'gray', pub_topic+'mask')
    ROI = get_ROI(mask)

    if ROI == []:
        mode = 1
        print_result('NOT FOUND', color_text.RED)
    elif len(ROI) == 1:
        mode = 2
        gate = ROI[0]
        print_result("FOUND A GATE", color_text.GREEN)
    elif len(ROI) > 1:
        mode = 2
        gate = max(ROI, key=cv.contourArea)
        print_result("FOUND BUT HAVE SOME NOISE", color_text.YELLOW)

    if mode == 1:
        publish_result(img, 'bgr', pub_topic + 'result')
        return message()
    elif mode == 2:
        x, y, w, h = cv.boundingRect(gate)
        w_h_ratio = 1.0*w/h
        right_excess = (x+w > 0.95*wimg)
        left_excess = (x < 0.05*wimg)
        cv.rectangle(img, (x, y), (x+w, y+h), (0, 0, 255))
        area = 1.0*w*h/(wimg*himg)
        return_cx1 = x+(w/4)
        return_cx2 = x+(w*3/4)
        return_y = y+(h/2)
        cv.circle(img, (return_cx1, return_y), 3, (0, 0, 0), -1)
        cv.circle(img, (return_cx2, return_y), 3, (0, 0, 0), -1)
        return_cx1 = Aconvert(return_cx1, wimg)
        return_cx2 = Aconvert(return_cx2, wimg)
        publish_result(img, 'bgr', pub_topic + 'result')
        return message(cx1=return_cx1, cx2=return_cx2, area=area, appear=True, w_h_ratio=w_h_ratio)


if __name__ == '__main__':
    rospy.init_node('vision_casino_gate', anonymous=False)
    print_result("INIT NODE",color_text.GREEN)
    # image_topic = "/stereo/right/image_color/compressed"
    image_topic = get_topic("front", world)
    rospy.Subscriber(image_topic, CompressedImage, image_callback)
    print_result("INIT SUBSCRIBER",color_text.GREEN)
    rospy.Service('vision_casino_gate',
                  vision_srv_casino_gate(), mission_callback)
    print_result("INIT SERVICE",color_text.GREEN)
    rospy.spin()
    print_result("END PROGRAM",color_text.YELLOW_HL+color_text.RED)
