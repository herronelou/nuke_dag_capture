import time
import threading
import nuke

from Qt import QtWidgets, QtOpenGL, QtGui, QtCore
from math import ceil


class DagCapturePanel(QtWidgets.QDialog):
    def __init__(self):
        super(DagCapturePanel, self).__init__()

        # Variables
        self.dag = get_dag()
        if not self.dag:
            raise RuntimeError("Couldn't get DAG widget")

        self.dag_bbox = None
        self.capture_size = None

        # UI
        self.setWindowTitle("DAG Capture options")

        main_layout = QtWidgets.QVBoxLayout()
        form_layout = QtWidgets.QFormLayout()
        form_layout.setFieldGrowthPolicy(form_layout.AllNonFixedFieldsGrow)
        form_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        main_layout.addLayout(form_layout)

        # Options
        # Path
        container = QtWidgets.QWidget()
        path_layout = QtWidgets.QHBoxLayout()
        path_layout.setMargin(0)
        container.setLayout(path_layout)
        self.path = QtWidgets.QLineEdit()
        browse_button = QtWidgets.QPushButton("Browse")
        browse_button.clicked.connect(self.show_file_browser)
        path_layout.addWidget(self.path)
        path_layout.addWidget(browse_button)
        form_layout.addRow("File Path", container)

        # Zoom
        self.zoom_level = QtWidgets.QDoubleSpinBox()
        self.zoom_level.setValue(1.0)
        self.zoom_level.setRange(0.01, 5)
        self.zoom_level.setSingleStep(.5)
        self.zoom_level.valueChanged.connect(self.display_info)
        form_layout.addRow("Zoom Level", self.zoom_level)

        # Margins
        self.margins = QtWidgets.QSpinBox()
        self.margins.setRange(0, 1000)
        self.margins.setValue(20)
        self.margins.setSingleStep(10)
        self.margins.valueChanged.connect(self.display_info)
        form_layout.addRow("Margins", self.margins)

        # Right Crop
        self.ignore_right = QtWidgets.QSpinBox()
        self.ignore_right.setRange(0, 1000)
        self.ignore_right.setValue(200)
        self.ignore_right.setToolTip("The right side of the DAG usually contains a mini version of itself.\n"
                                     "This gets included in the screen capture, so it is required to crop it out. \n"
                                     "If you scaled it down, you can reduce this number to speed up capture slightly.")
        self.ignore_right.valueChanged.connect(self.display_info)
        form_layout.addRow("Crop Right Side", self.ignore_right)

        # Delay
        self.delay = QtWidgets.QDoubleSpinBox()
        self.delay.setValue(.3)
        self.delay.setRange(0.1, 1)
        self.delay.setSuffix("s")
        self.delay.setSingleStep(.1)
        self.delay.valueChanged.connect(self.display_info)
        self.delay.setToolTip("A longer delay ensures the Nuke DAG has fully refreshed between capturing tiles.\n"
                              "It makes the capture slower, but ensures a correct result.\n"
                              "Feel free to adjust based on results you have seen on your machine.\n"
                              "Increase if the capture looks incorrect.")
        form_layout.addRow("Delay Between Captures", self.delay)

        # Capture all nodes or selection
        self.capture = QtWidgets.QComboBox()
        self.capture.addItems(["All Nodes", "Selected Nodes"])
        self.capture.currentIndexChanged.connect(self.inspect_dag)
        form_layout.addRow("Nodes to Capture", self.capture)

        # Deselect Nodes before Capture?
        self.deselect = QtWidgets.QCheckBox("Deselect Nodes before capture")
        self.deselect.setChecked(True)
        form_layout.addWidget(self.deselect)

        # Add Information box
        self.info = QtWidgets.QLabel("Hi")
        info_box = QtWidgets.QFrame()
        info_box.setFrameStyle(info_box.StyledPanel)
        info_box.setLayout(QtWidgets.QVBoxLayout())
        info_box.layout().addWidget(self.info)

        main_layout.addWidget(info_box)
        self.setLayout(main_layout)

        self.inspect_dag()

    def display_info(self):
        zoom = self.zoom_level.value()
        # Check the size of the current widget, excluding the right side (because of minimap)
        capture_width = max(self.dag.width() - self.ignore_right.value(), 1)
        capture_height = self.dag.height()

        # Calculate the number of tiles required to cover all
        min_x, min_y, max_x, max_y = self.dag_bbox
        image_width = (max_x - min_x) * zoom + self.margins.value() * 2
        image_height = (max_y - min_y) * zoom + self.margins.value() * 2

        horizontal_tiles = int(ceil(image_width / float(capture_width)))
        vertical_tiles = int(ceil(image_height / float(capture_height)))
        total_tiles = horizontal_tiles * vertical_tiles
        total_time = total_tiles * self.delay.value()

        info = "Image Size: {width}x{height}\n" \
               "Number of tiles required: {tiles} (Increase DAG size to reduce) \n" \
               "Estimated Capture Duration: {time}s"
        info = info.format(width=int(image_width), height=int(image_height), tiles=total_tiles, time=total_time)
        self.info.setText(info)

    def inspect_dag(self):
        print self.capture.currentIndex()
        nodes = nuke.allNodes() if self.capture.currentIndex() == 0 else nuke.selectedNodes()
        # Calculate the total size of the DAG
        min_x = min([node.xpos() for node in nodes])
        min_y = min([node.ypos() for node in nodes])
        max_x = max([node.xpos() + node.screenWidth() for node in nodes])
        max_y = max([node.ypos() + node.screenHeight() for node in nodes])
        self.dag_bbox = (min_x, min_y, max_x, max_y)

        self.display_info()

    def show_file_browser(self):
        filename, _filter = QtWidgets.QFileDialog.getSaveFileName(parent=self, caption='Select output file',
                                                                  filter="PNG Image (*.png)")
        self.path.setText(filename)


def get_dag():
    stack = QtWidgets.QApplication.topLevelWidgets()
    while stack:
        widget = stack.pop()
        if widget.objectName() == 'DAG.1':
            for c in widget.children():
                if isinstance(c, QtOpenGL.QGLWidget):
                    return c
        stack.extend(c for c in widget.children() if c.isWidgetType())


def grab_dag(dag, painter, xpos, ypos):
    dag.updateGL()  # This does some funky back and forth but function grabs the wrong thing without it
    pix = dag.grabFrameBuffer()
    painter.drawImage(xpos, ypos, pix)


class DagCapture(threading.Thread):
    def __init__(self, path, margins=20, ignore_right=200):
        super(DagCapture, self).__init__()
        self.path = path
        self.margins = margins
        self.ignore_right = ignore_right
        self.delay = 0.2

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

        # Calculate the number of tiles required to cover all
        image_width = max_x - min_x
        image_height = max_y - min_y
        horizontal_tiles = int(ceil(image_width / float(capture_width)))
        vertical_tiles = int(ceil(image_height / float(capture_height)))
        # Create a pixmap to store the results
        pixmap = QtGui.QPixmap(image_width, image_height)
        painter = QtGui.QPainter(pixmap)
        painter.setCompositionMode(painter.CompositionMode_SourceOver)
        # Move the dag so that the top left corner is in the top left corner, screenshot, paste in the pixmap, repeat
        for tile_x in range(horizontal_tiles):
            center_x = (min_x + capture_width * tile_x) + (capture_width + self.ignore_right) / 2
            for tile_y in range(vertical_tiles):
                center_y = (min_y + capture_height * tile_y) + capture_height / 2
                nuke.executeInMainThread(nuke.zoom, (1, (center_x, center_y)))
                time.sleep(self.delay)
                nuke.executeInMainThread(grab_dag, (dag, painter, capture_width * tile_x, capture_height * tile_y))
        time.sleep(self.delay)
        painter.end()
        pixmap.save(self.path)
        nuke.executeInMainThread(nuke.zoom, (original_zoom, original_center))
        print "Capture Complete"


if __name__ == '__main__':
    p = DagCapturePanel()
    p.show()
    # t = DagCapture("C:\\Users\\herro\\Downloads\\test.png")
    # t.start()
