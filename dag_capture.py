import time
import threading
import nuke

from Qt import QtWidgets, QtOpenGL, QtGui
from math import ceil


def get_dag():
    stack = QtWidgets.QApplication.topLevelWidgets()
    while stack:
        widget = stack.pop()
        if widget.objectName() == 'DAG.1':
            for c in widget.children():
                if isinstance(c, QtOpenGL.QGLWidget):
                    return c
        stack.extend(c for c in widget.children() if c.isWidgetType())


def grab_dag(dag, path):
    dag.updateGL()  # This does some funky back and forth but function grabs the wrong thing without it
    pix = dag.grabFrameBuffer()
    pix.save(path)


class DagCapture(threading.Thread):
    def __init__(self, path, margins=20, ignore_right=200):
        self.path = path
        threading.Thread.__init__(self)
        self.margins = margins
        self.ignore_right = ignore_right

    def run(self):
        # Store the current dag size and zoom
        original_zoom = nuke.zoom()
        original_center = nuke.center()
        # Calculate the total size of the DAG
        min_x = min([node.xpos() for node in nuke.allNodes()]) - self.margins
        min_y = min([node.ypos() for node in nuke.allNodes()]) - self.margins
        max_x = max([node.xpos() + node.screenWidth() for node in nuke.allNodes()]) + self.margins
        max_y = max([node.ypos() + node.screenHeight() for node in nuke.allNodes()]) + self.margins

        # Get the Dag Widget
        dag = get_dag()
        if not dag:
            raise RuntimeError("Couldn't get DAG widget")

        # Check the size of the current widget, excluding the right side (because of minimap)
        capture_width = dag.width() - self.ignore_right
        capture_height = dag.height()

        # Calculate the number of tiles required to coveral all
        image_width = max_x - min_x
        image_height = max_y - min_y
        horizontal_tiles = int(ceil(image_width / float(capture_width)))
        vertical_tiles = int(ceil(image_height / float(capture_height)))
        # Create a pixmap to store the results
        pixmap = QtGui.QPixmap(image_width, image_height)
        painter = QtGui.QPainter(pixmap)
        painter.setCompositionMode(painter.CompositionMode_SourceOver)
        # Move the dag so that the top left corner is in the top left corner, screenshot, paste in the pixmap, repeat
        for xtile in range(horizontal_tiles):
            left = min_x + capture_width * xtile
            for ytile in range(vertical_tiles):
                top = min_y + capture_height * ytile
                nuke.executeInMainThread(nuke.zoom, (1, (left + (capture_width + self.ignore_right) / 2, top + capture_height / 2)))
                time.sleep(.5)
                nuke.executeInMainThread(grab_dag, (dag, self.path))
                time.sleep(.5)
                screengrab = QtGui.QImage(self.path)
                painter.drawImage(capture_width * xtile, capture_height * ytile, screengrab)
        painter.end()
        pixmap.save(self.path)
        nuke.executeInMainThread(nuke.zoom, (original_zoom, original_center))
        print "Capture Complete"


t = DagCapture("C:\\Users\\erwan\\Downloads\\test.png")
t.start()
