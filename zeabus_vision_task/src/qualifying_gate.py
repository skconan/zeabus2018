#!/usr/bin/python2.7
import rospy
import cv2 as cv
import numpy as np
from sensor_msgs.msg import CompressedImage, Image
from zeabus_vision_task.msg import vision_qualifying_gate
from zeabus_vision_task.srv import vision_srv_qualifying_gate
from cv_bridge import CvBridge, CvBridgeError
from vision_lib import *
img = None
img_res = None
sub_sampling = 1
pub_topic = "/vision/qualifying_gate/"


def mission_callback(msg):
    """
        When call service it will run this 
        Returns:
            a group of process value from this program
    """
    print_result('mission_callback')

    task = msg.task.data

    print('task:', str(task))
    if task == 'gate':
        return find_gate()


def image_callback(msg):
    """
        Convert data from camera to image
    """
    global img, sub_sampling, img_res
    arr = np.fromstring(msg.data, np.uint8)
    img = cv.resize(cv.imdecode(arr, 1), (0, 0),
                    fx=sub_sampling, fy=sub_sampling)
    img_res = img.copy()


def message(cx=-1, pos=-1, area=-1, appear=False):
    m = vision_qualifying_gate()
    m.cx = cx
    m.pos = pos
    m.area = area
    m.appear = appear
    print(m)
    return m


def get_object():
    """
        get mask from picture and remove some noise
        Returns:
            mask (ONLY GATE AREA)
    """
    global img
    hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)

    # real world
    lower = np.array([0, 0, 0], dtype=np.uint8)
    upper = np.array([180, 180, 68], dtype=np.uint8)

    # lower,upper = get_color('yellow','morning','path')
    mask = cv.inRange(hsv, lower, upper)
    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv.GaussianBlur(mask, (5, 5), 0)
    mask = cv.erode(mask, kernel)
    mask = cv.erode(mask, kernel)
    mask = cv.dilate(mask, kernel)
    mask = cv.dilate(mask, kernel)
    return mask


def get_roi(mask):
    global img, img_res
    top_excess = False
    bot_excess = False
    left_excess = False
    right_excess = False
    himg, wimg = img.shape[:2]
    ROI = []
    contours = cv.findContours(
        mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)[1]

    for cnt in contours:
        cnt_area = cv.contourArea(cnt)
        if cnt_area > 5000:
            appear = True
            x, y, w, h = cv.boundingRect(cnt)
            if(x < 0.05*wimg):
                left_excess = True
            if((x+w) > 0.95*wimg):
                right_excess = True
            if(y < 0.05*himg):
                top_excess = True
            if((y+h) > 0.95*himg):
                bot_excess = True
            img = cv.rectangle(img_res, (x, y), (x+w, y+h), (0, 0, 255), 2)
            ROI.append(cnt)
    return ROI, left_excess, right_excess, top_excess, bot_excess


def find_gate():
    global img, img_res
    while img is None and not rospy.is_shutdown():
        print('img is none.\nPlease check topic name or check camera is running')

    mask = get_object()
    ROI, left_excess, right_excess, top_excess, bot_excess = get_roi(mask)

    if len(ROI) == 0:
        mode = 1
    if len(ROI) == 1:
        mode = 2
    if len(ROI) >= 2:
        mode = 3

    if mode == 1:
        print_result("MODE 1: CANNOT FIND GATE")
        publish_result(img_res, 'bgr', pub_topic + 'img')
        publish_result(mask, 'gray', pub_topic + 'mask')
        return message()
    elif mode == 2:
        himg, wimg = img.shape[:2]
        x, y, w, h = cv.boundingRect(ROI[0])
        area = (1.0*h*w)/(himg*wimg)
        if left_excess is False and right_excess is True:
            print_result("MODE 2(-1): CAN FIND LEFT GATE")
            publish_result(img_res, 'bgr', pub_topic + 'img')
            publish_result(mask, 'gray', pub_topic + 'mask')
            return message(pos=-1, area=area, appear=True)
        elif left_excess is True and right_excess is False:
            print_result("MODE 2(1): CAN FIND RIGHT GATE")
            publish_result(img_res, 'bgr', pub_topic + 'img')
            publish_result(mask, 'gray', pub_topic + 'mask')
            return message(pos=1, area=area, appear=True)
        elif left_excess is True and right_excess is True:
            print_result(
                "MODE 2(0): CAN FIND ALL GATE(GATE IS BIGGER THAN FRAME")
            cx = wimg/2
            cv.line(img_res, (cx, 0), (cx, himg), (255, 0, 0), 5)
            publish_result(img_res, 'bgr', pub_topic + 'img')
            publish_result(mask, 'gray', pub_topic + 'mask')
            return message(cx=cx, pos=0, area=area, appear=True)
        elif h < 4*w:
            print_result("MODE 2(0): CAN FIND ALL GATE")
            cx = (2*x+w)/2
            cv.line(img_res, (cx, 0), (cx, himg), (255, 0, 0), 5)
            publish_result(img_res, 'bgr', pub_topic + 'img')
            publish_result(mask, 'gray', pub_topic + 'mask')
            return message(cx=cx, pos=0, area=area, appear=True)
        else:
            print_result(
                "MODE 2(-99): CAN FIND PART OF GATE BUT NOT SURE WHICH PART")
            publish_result(img_res, 'bgr', pub_topic + 'img')
            publish_result(mask, 'gray', pub_topic + 'mask')
            return message(pos=-99, area=area, appear=True)

    if mode == 3:
        cx_horizontal = []
        cx_vertical = []
        for cnt in ROI:
            x, y, w, h = cv.boundingRect(cnt)
            M = cv.moments(cnt)
            cx = int(M["m10"]/M["m00"])
            if h > 4 * w:
                cx_horizontal.append(cx)
            else:
                cx_vertical.append(cx)
        if len(cx_horizontal) == 2 or len(cx_horizontal) == 1:  # found or found(on water)
            print_result("MODE 3(1): CAN FIND HORIZONTAL OF GATE")
            cx = sum(cx_horizontal)/len(cx_horizontal)
        elif len(cx_vertical) == 2:
            print_result("MODE 3(2): CAN FIND VERTICAL OF GATE")
            cx = sum(cx_vertical)/2
        else:
            print_result("MODE 3(3): CAN FIND GATE BUT MAYBE A LOT OF NOISE")
            cx = (sum(cx_vertical)+(sum(cx_horizontal)*3)) / \
                (len(cx_vertical)+len(cx_horizontal)+3)
        cv.line(img_res, (cx, 0), (cx, himg), (255, 0, 0), 5)
        publish_result(img_res, 'bgr', pub_topic + 'img')
        publish_result(mask, 'gray', pub_topic + 'mask')
        return message(cx=cx, pos=0, area=-1, appear=True)


if __name__ == '__main__':
    rospy.init_node('vision_qualifying_gate', anonymous=True)
    image_topic = "/top/center/image_raw/compressed"
    rospy.Subscriber(image_topic, CompressedImage, image_callback)
    print "init_pub_sub"
    rospy.Service('vision_qualifying_gate',
                  vision_srv_qualifying_gate(), mission_callback)
    print "init_ser"
    rospy.spin()