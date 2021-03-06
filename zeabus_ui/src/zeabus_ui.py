#!/usr/bin/env python
'''
    File name: zeabus_ui.py
    Author: zeabus2018
    Date created: 2018/04/26
    Python Version: 2.7
'''
import rospy
import rosnode
import rospkg
import os
import sys
from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import csv
import os
import pyautogui
import time


class NodeHandle(QtGui.QWidget):
    def __init__(self):
        super(NodeHandle, self).__init__()
        self.nodes = []
        self.status = []

    def get_node_status(self):
        size = len(self.nodes)
        self.status = [True] * size

        for i in range(size):
            try:
                self.status[i] = rosnode.rosnode_ping(
                    self.nodes[i], max_count=1)
            except Exception:
                self.status[i] = False

    def get_node(self):
        tmp = rosnode.get_node_names()
        # tmp = self.nodes
        tmp = set(tmp)
        tmp = list(tmp)
        self.nodes = sorted(tmp)
        size = len(self.nodes)
        return self.nodes

    def kill_node(self, name):
        try:
            rosnode.kill_nodes([str(name)])
            return True
        except:
            return False


class NodeListWidget(QListWidget):
    def __init__(self):
        super(NodeListWidget, self).__init__()
        self.itemClicked.connect(self.Clicked)
        self.nh = NodeHandle()
        self.fetch_node2list()

    def Clicked(self, item):
        msg = QMessageBox()
        node_name = item.text()
        msg.setWindowTitle("Kill Node: ")
        msg.setText("Do u want to kill node: " + node_name)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        retval = msg.exec_()

        if retval == 1024:
            res = self.nh.kill_node(node_name)
            print("Result: ", res)
        else:
            print('Cancel kill node')

        self.fetch_node2list()

    def fetch_node2list(self):
        self.clear()
        for i in range(10):
            nodes = self.nh.get_node()
        if nodes is not None:
            for n in nodes:
                self.addItem(n)

    def refresh_on_click(self):
        self.fetch_node2list()


class CommandWidget(QWidget):
    def __init__(self, NodeListWidget):
        super(CommandWidget, self).__init__()
        self.node_list_widget = NodeListWidget
        self.path = rospkg.RosPack().get_path('zeabus_ui')
        self.aliases = []
        self.command = []
        self.button = []
        self.button_status = []
        self.get_command()
        self.display()

    def key(self, event):
        print "pressed", repr(event.char)

    def get_command(self):
        with open(self.path + '/src/command.csv', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                self.aliases.append(str(row[0]))
                self.command.append(str(row[1]))

    def display(self):
        glayout = QGridLayout()
        row = 0
        for alias in self.aliases:
            self.button.append(QPushButton(alias))
            self.button[row].setFixedWidth(200)
            self.button[row].setFixedHeight(50)
            self.button[row].setCheckable(True)
            self.button[row].toggle()
            self.button_status.append(False)
            self.button[row].clicked.connect(self.command_sending)
            glayout.addWidget(self.button[row], row, 0)
            row += 1

        self.setLayout(glayout)

    def command_sending(self):
        length = len(self.button)
        for i in range(length):
            print(self.button_status[i])
            if self.button[i].isChecked() == self.button_status[i]:
                print(str(self.button[i].text()) + ' is pressed')
                self.button_status[i] = not self.button_status[i]

                pyautogui.hotkey('alt', 'tab')
                pyautogui.keyDown('F2')
                pyautogui.keyUp('F2')
                pyautogui.typewrite(self.command[i])
                pyautogui.keyDown('return')
                pyautogui.keyUp('return')
                pyautogui.hotkey('alt', 'tab')
                # wait new node(s)
                time.sleep(1)
                self.node_list_widget.fetch_node2list()


def main():
    app = QApplication(sys.argv)

    screen_resolution = app.desktop().screenGeometry()
    width, height = screen_resolution.width(), screen_resolution.height()
    app_width, app_height = int(width / 2), int(height / 2)

    window = QWidget()
    window.setWindowTitle("ZEABUS UI")
    window.setGeometry(app_width, app_height, app_width, app_height)

    # List of Nodes
    listWidget = NodeListWidget()
    btn = QPushButton('refresh')
    btn.clicked.connect(listWidget.refresh_on_click)

    # Command button
    btnCommand = CommandWidget(listWidget)

    # Grid layout
    glayout = QGridLayout()
    glayout.addWidget(btn, 0, 0)
    glayout.addWidget(btnCommand, 1, 1)
    glayout.addWidget(listWidget, 1, 0)

    window.setLayout(glayout)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    rospy.init_node('zeabus_handle_node', anonymous=True)
    main()
