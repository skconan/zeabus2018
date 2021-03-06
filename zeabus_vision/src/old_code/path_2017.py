#!/usr/bin/python2.7
"""
    To use in simulator please assign world varible (line 20) to 'sim' 
    # world = 'sim'
    To use in real world please assign world varible (line 20) to 'real' 
    # world = 'real'
"""
import math
import rospy
import cv2 as cv
import numpy as np
from sensor_msgs.msg import CompressedImage
from zeabus_vision.msg import path
from zeabus_vision.srv import path_srv
from vision_lib import *
img = None
img_res = None
sub_sampling = 1
pub_topic = "/vision/path/"
world = "real"


def mission_callback(msg):
    """
        When call service it will run this 
        Returns:
            a group of process value from this program
    """
    print_result('mission_callback')

    task = msg.task.data

    print('task:', str(task))
    if task == 'path':
        return find_path()


def image_callback(msg):
    """
        Convert data from camera to image
    """
    global img, sub_sampling, img_res
    arr = np.fromstring(msg.data, np.uint8)
    img = cv.resize(cv.imdecode(arr, 1), (0, 0),
                    fx=sub_sampling, fy=sub_sampling)
    size = 500
    r = 1.0*size / img.shape[1]
    dim = (size, int(img.shape[0] * r))
    resized = cv.resize(img, dim, interpolation = cv.INTER_AREA)
    img = resized
    img_res = img.copy()


def message(cx=-1, cy=-1, degrees = 0, appear=False):
    """
        Convert value into a message (from vision_path.msg)
        Returns:
            vision_path (message): a group of value from args
    """
    m = path()
    m.cx = cx
    m.cy = cy
    m.degrees = degrees
    m.appear = appear
    print(m)
    return m


def get_object():
    """
        get mask from picture and remove some noise
        Returns:
            mask (ONLY PATH AREA)
    """
    global img
    hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)

    # sim
    # lower = np.array([0, 120, 0], dtype=np.uint8)
    # upper = np.array([37, 255, 255], dtype=np.uint8)
    # # real world
    # lower = np.array([20, 120, 0], dtype=np.uint8)
    # upper = np.array([62, 255, 255], dtype=np.uint8)

    lower = np.array([3,146,124])
    upper = np.array([28,255,255])
    mask = cv.inRange(hsv, lower, upper)
    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv.GaussianBlur(mask, (5, 5), 0)
    mask = cv.erode(mask, kernel)
    mask = cv.erode(mask, kernel)
    mask = cv.dilate(mask, kernel)
    mask = cv.dilate(mask, kernel)
    return mask


def get_cx(mask):
    """
        Slice 8 part of mask (only top half) and 
        find center of each slice of mask
        Returns:
            int: cx (MAX 8 POINT),
            int: cy (MAX 8 POINT),
            int: average area in range of 0 to 1
    """
    global img
    himg, wimg = img.shape[:2]
    cx = []
    cy = []
    sli = 8
    for i in range(sli):
        begin = ((himg/2)*i/sli)
        end = ((himg/2)*(i+1)/sli)
        ROI = mask[begin:end, ]
        cnt = cv.findContours(ROI, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)[1]
        if len(cnt) >= 1:
            cnt = max(cnt, key=cv.contourArea)
            this_area = cv.contourArea(cnt)
            # sim
            # if this_area > 2000:
            # real world
            if this_area > 200:
                print this_area
                M = cv.moments(cnt)
                ROI_cx = int(M["m10"]/M["m00"])
                ROI_cy = int(M['m01']/M['m00']) + begin
                if ROI_cx >= 0.05 * wimg and ROI_cx <= 0.95 * wimg:
                    cv.circle(img_res, (ROI_cx, ROI_cy), 2, (0, 0, 255), -1)
                    cx.append(ROI_cx)
                    cy.append(ROI_cy)
    cx = cx[::-1]
    cy = cy[::-1]
    return cx, cy


def find_angle(cx, cy):
    """
    Calculate angle from at least 2 point

    Returns:
        float: degrees in range of -90 to 90 
               where left side is positive right side is negative
    """
    global img_res
    deg = []
    for i in range(len(cx)-1):
        rad = math.atan2(cy[i+1]-cy[i], cx[i+1]-cx[i])
        this_deg = math.degrees(rad)
        if len(deg) > 0 and abs(this_deg-deg[-1]) > 5:
            cv.circle(img_res, (cx[i], cy[i]), 2, (0, 255, 0), -1)
            break
        deg.append(this_deg)
    degrees = abs(sum(deg)/len(deg))-90
    return degrees


def find_path():
    """
        find path on the picture draw a point on path
        that this code can detect (MAX 8 point)

        Returns:
            message: (a group of data from vision_path.msg)
            if cannot find path:
                return default value
            else if find a little bit path:
                return float: cx in range of -1 to 1, 
                       float: cy in range of 0 to 1,
                       float: area in range of 0 to 1,
                       bool: appear is true
            else if find a lot of path:
                return float: cx in range of -1 to 1, 
                       float: cy in range of 0 to 1,
                       float: area in range of 0 to 1,
                       float: degrees in range of -90 to 90,
                       bool: appear is true        

        # for this code min cy is 0.0641447368421        
    """
    global img, img_res
    while img is None and not rospy.is_shutdown():
        print('img is none.\nPlease check topic name or check camera is running')

    mask = get_object()
    cx, cy = get_cx(mask)

    if cx == [] and cy == []:
        mode = 1
    elif len(cx) == 1 and len(cy) == 1:
        mode = 2
        cv.circle(img_res, (cx[0], cy[0]), 2, (255, 0, 0), -1)
    elif len(cx) >= 2 and len(cy) >= 2:
        mode = 3
        cv.circle(img_res, (cx[0], cy[0]), 2, (255, 0, 0), -1)

    if mode == 1:
        print_result("MODE 1: CANNOT FIND PATH")
        publish_result(img_res, 'bgr', pub_topic + 'img_res')
        publish_result(mask, 'gray', pub_topic + 'mask')
        return message()
    elif mode == 2:
        print_result("MODE 2: CAN FIND 1 CX AND 1 CY")
        himg, wimg = img.shape[:2]
        return_cx = convert(cx[0],wimg)
        return_cy = convert(cy[0],himg)
        publish_result(img_res, 'bgr', pub_topic + 'img_res')
        publish_result(mask, 'gray', pub_topic + 'mask')
        return message(cx=return_cx, cy=return_cy, appear=True)
    elif mode == 3:
        print_result("MODE 3: CAN FIND DEGREE (2 POINT OR MORE)")
        himg, wimg = img.shape[:2]
        return_cx = 1.0*(cx[0] - (wimg/2))/(1.0*wimg/2)
        return_cy = -1.0*(cy[0] - (himg/2))/(1.0*himg/2)
        return_degrees = find_angle(cx, cy)
        publish_result(img_res, 'bgr', pub_topic + 'img_res')
        publish_result(mask, 'gray', pub_topic + 'mask')
        return message(cx=return_cx, cy=return_cy, degrees=return_degrees, appear=True)


if __name__ == '__main__':
    rospy.init_node('vision_path', anonymous=True)
    print_result("INIT NODE")

    image_topic = get_topic("bottom",world)
    rospy.Subscriber(image_topic, CompressedImage, image_callback)
    print_result("INIT SUBSCRIBER")

    rospy.Service('vision_path', path_srv(),
                  mission_callback)
    print_result("INIT SERVICE")

    rospy.spin()
    print_result("END PROGRAM")

