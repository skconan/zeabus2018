#!/usr/bin/python2.7
import cv2 as cv
import rospy
import numpy as np
#from remove_noise import *
from sensor_msgs.msg import CompressedImage , Image
from qualification_gate.msg import qulification_gate
from qualification_gate.srv import srv_qualification_gate
from cv_bridge import CvBridge , CvBridgeError
from qualify import *
img = None
img_res = None
sub_sampling = 1
    

def mission_callback(msg):
    print_result('mission_callback')

    req = msg.req.data
    task = msg.task.data

    print('task:', str(task), 'request:', str(req))
    if task == 'gate':
        return find_gate()
    

def image_callback(msg):
    global img, sub_sampling, img_res
    arr = np.fromstring(msg.data, np.uint8)
    img = cv.resize(cv.imdecode(arr, 1), (0, 0),
                     fx=sub_sampling, fy=sub_sampling)
    img_res = img.copy()

def find_gate () :
    global img,img_res
    appear = False
    pos = 99
    cx = -1
    area = 0
    top_excess = False
    bot_excess = False
    left_excess = False
    right_excess = False
    while img is None and not rospy.is_shutdown() :
        print('img is none.\nPlease check topic name or check camera is running')
        break
    # img = frame.copy()
    # cv.imshow('img',img)
    himg , wimg = img.shape[:2]
    print himg
    print wimg
    # img_res = process_gate(img_res)
    # hsv = cv.cvtColor(img_res,cv.COLOR_BGR2HSV)
    # l = np.array([8,111,109])
    # h = np.array([19,216,247])
    # mask = cv.inRange(hsv,l,h)
    mask = process_gate(img_res)
    contours = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)[1]
    c = 0
    ROI = []
    ROI_area = []
    for cnt in contours:
        cnt_area = cv.contourArea(cnt)
        if cnt_area > 500 :
            c += 1
            appear = True
            rect = cv.minAreaRect(cnt)
            box = cv.boxPoints(rect)
            box = np.int0(box)
            hbox = (abs(box[0, 0] - box[1, 0])**2 + abs(box[0, 1] - box[1, 1])**2)**0.5
            wbox = (abs(box[1, 0] - box[2, 0])**2 + abs(box[1, 1] - box[2, 1])**2)**0.5
            for i in box:
                if(i[0] < 0.05*wimg):
                    left_excess = True
                if(i[0] > 0.95*wimg):
                    right_excess = True
                if(i[1] < 0.05*himg):
                    top_excess = True
                if(i[1] > 0.95*himg):
                    bot_excess = True
            img = cv.drawContours(img, [box], 0, (0,0,255), 2)
            ROI.append(cnt)
            ROI_area.append([hbox,wbox])
    # print "appear = " + str(appear)
    # print len(ROI)
    if len(ROI) == 2:
        pos = 0
        M = cv.moments(ROI[0])
        cx_0 = int(M["m10"] / M["m00"])
        M = cv.moments(ROI[1])
        cx_1 = int(M["m10"] / M["m00"])
        cx = int((cx_0+cx_1)/2)
        # print "pos = " + str(pos)
        # print "cx = " + str(cx)
        img = cv.line(img,(cx,0),(cx,himg),(255,0,0),5)
    if len(ROI) == 1:
        # print ROI_area[0]
        # print "----"
        area = ROI_area[0][0]*ROI_area[0][1]/(himg*wimg)
        if left_excess is False and right_excess is True:
            pos = -1
            # print "-1 = left"
        elif left_excess is True and right_excess is False:
            pos = 1
            # print "1 = right"
        elif area > 0.1:
            pos = 0
            M = cv.moments(ROI[0])
            cx = int(M["m10"] / M["m00"])
            # print "pos = " + str(pos)
            # print "cx = " + str(cx)
            img = cv.line(img,(cx,0),(cx,himg),(255,0,0),5)
        else:
            pos = -99
        # print area
    # cv.imshow('img',img)
    publish_result(img,'bgr','/imgbhhkmyug')
    publish_result(mask,'gray','/imgbug')
    # cv.imshow('m',mask)
    # cv.waitKey(1000)
    # cv.destroyAllWindows()
    return message(cx,pos,area,appear)


def main():
    rospy.init_node('vision_gate', anonymous=True)
    image_topic = "/syrena/front_cam/image_raw/compressed"
    # image_topic = "/top/center/image_raw/compressed"
    res_topic = "/top/center/res/compressed"
    rospy.Subscriber(image_topic, CompressedImage, image_callback)
    #abc = rospy.Publisher(res_topic, CompressedImage, queue_size=10)
    print "fuck"
    rospy.Service('vision_gate', srv_qualification_gate (), mission_callback)
    print "fuck"
    rospy.spin()



if __name__ == '__main__':
    main()