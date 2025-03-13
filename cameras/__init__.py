import sys
import os

sys.path.append("src/control_camera/")
from cameras.MVSImport.LoadAndSave import save_feature
from cameras.hik import HIK
from cameras.soda import SODA
from cameras.webcam import Webcam


def get_camera_devices():
    return HIK.get_devices()
