import sys
import os

sys.path.append("src/control_camera/")
from cameras.MVSImport.LoadAndSave import save_feature
from cameras.hik import HIK
from cameras.soda import SODA
from cameras.webcam import Webcam


def get_camera_devices(type: str):
    if type == "HIK":
        return HIK.get_devices()
    elif type == "SODA":
        return SODA.get_devices()
    elif type == "Webcam":
        return Webcam.get_devices()
