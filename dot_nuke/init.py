import os.path

import nuke

if (nuke.env["NukeVersionMajor"]) >= 13:  # Nuke 12 is python 2, not 3
    userfolder = os.path.expanduser("~")
    path = os.path.join(userfolder, "Documents/nuke_screenshot")
    nuke.pluginAddPath(path)
