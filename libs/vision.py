import cv2
import numpy as np
import random
import os
import time
from collections import namedtuple, deque

import ultralytics
from ultralytics import YOLO
from ultralytics.utils import ops
import torch
import yaml

from PIL import Image

class DNNRESULT:
    def __init__(self, class_index=0, box=None, 
                 mask=None, conf=None, rect=None, imgsz=None) -> None:
        '''
        @class_index: class index of object
        @box: bounding box (x1, y1, x2, y2) of object
        @mask: polygon around object (segmention key point)
        @conf: confidence
        @rect: minAreaRect of mask
        @imgsz: tuple size (width, height) of image 
        '''
        self._class_index = class_index
        self._box = box
        self._mask = mask
        self._conf = conf
        self._rect = rect
        self._imgsz = imgsz
    
    @property
    def class_index(self):
        return self._class_index

    @property
    def box(self):
        return self._box

    @property
    def mask(self):
        return self._mask

    @property
    def conf(self):
        return self._conf
    
    @property
    def rect(self):
        return self._rect
    
    @property
    def imgsz(self):
        return self._imgsz
    
    @property
    def boxStr(self):
        '''
        return bndbox coordinates as yolo format
        '''
        im_w, im_h = self.imgsz
        x1, y1, x2, y2 = self.box

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        w = x2 - x1
        h = y2 - y1

        cx /= im_w
        cy /= im_h
        w /= im_w
        h /= im_h

        line = f"{self.class_index} {round(cx, 5)} {round(cy, 5)} {round(w, 5)} {round(h, 5)}"
        return line
    
    @property
    def maskStr(self):
        '''
        return polygon coordinates as yolo format
        '''
        if self.mask is None:
            return ""
        
        im_w, im_h = self.imgsz
        line = f"{self.class_index}"

        for pos in self.mask:
            x, y = pos

            x /= im_w
            y /= im_h

            line += f" {round(x, 5)} {round(y, 5)}"
        return line

def plot_text(text, img:np.ndarray, org:tuple=None, color:tuple=None, line_thickness=5):
    """
    Helper function for drawing single min area rect on image
    Parameters:
        text : string
        img (np.ndarray): input image
    """
    color = color or (255, 255, 255)
    org = org or (10, 10)
    tl = line_thickness or round(0.002 * (img.shape[0] + img.shape[1]) / 2) + 1  # line/font thickness
    tf = max(tl -1, 1)
    
    cv2.putText(img, text, org, 0, tl / 3, color, tf, cv2.LINE_AA)
    return img
    pass

def plot_one_min_rect(rect, img:np.ndarray, color:tuple=None, line_thickness=5):
    """
    Helper function for drawing single min area rect on image
    Parameters:
        rect :result of cv2.minAreaRect
        img (np.ndarray): input image
    """
    color = color or (255, 255, 255)
    tl = line_thickness or round(0.002 * (img.shape[0] + img.shape[1]) / 2) + 1  # line/font thickness
    box = cv2.boxPoints(rect).astype(np.uint64)
    cv2.drawContours(img, [box], 0, color, tl)
    return img
    pass

def plot_one_box(box:np.ndarray = None, img:np.ndarray = None, color=None, mask:np.ndarray = None,
                label:str = None, line_thickness:int = 5):
        """
        Helper function for drawing single bounding box on image
        Parameters:
            x (np.ndarray): bounding box coordinates in format [x1, y1, x2, y2]
            img (no.ndarray): input image
            color (Tuple[int, int, int], *optional*, None): color in BGR format for drawing box, if not specified will be selected randomly
            mask (np.ndarray, *optional*, None): instance segmentation mask polygon in format [N, 2], where N - number of points in contour, if not provided, only box will be drawn
            label (str, *optonal*, None): box label string, if not provided will not be provided as drowing result
            line_thickness (int, *optional*, 5): thickness for box drawing lines
        """

        if box is None:
            return img
        
        # Plots one bounding box on image img
        tl = line_thickness or round(0.002 * (img.shape[0] + img.shape[1]) / 2) + 1  # line/font thickness
        fs = tl / 2.5
        if color is None:
            color = [random.randint(0, 255) for _ in range(3)]
        
        c1, c2 = (int(box[0]), int(box[1])), (int(box[2]), int(box[3]))
        cv2.rectangle(img, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)
        if label:
            tf = max(tl - 1, 1)  # font thickness
            t_size = cv2.getTextSize(label, 0, fontScale=fs, thickness=tf)[0]

            if c1[1] > t_size[1] + 3:
                c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3
                org = (c1[0], c1[1] -2)
            else:
                c2 = c1[0] + t_size[0], c1[1] + t_size[1] + 3
                org = (c1[0], c1[1] + t_size[1] + 2)

            cv2.rectangle(img, c1, c2, color, -1, cv2.LINE_AA)  # filled
            text_color = (0, 0, 255 - color[2])
            cv2.putText(img, label, org, 0, fs, text_color, thickness=tf, lineType=cv2.LINE_AA)
        if mask is not None:
            image_with_mask = img.copy()
            cv2.fillPoly(image_with_mask, pts=[mask], color=color)
            img = cv2.addWeighted(img, 0.5, image_with_mask, 0.5, 1)
        return img

def plot_results(results, img:np.ndarray, label_map=None, colors=None, lw=5):
        """
        Helper function for drawing bounding boxes on image
        Parameters:
            results: list DNNRESULT("class_index", "box", "mask", "conf")
            source_image (np.ndarray): input image for drawing
            label_map; (Dict[int, str]): label_id to class name mapping
        Returns:

        """
        result:DNNRESULT = None
        for result in results:
            box = result.box
            mask = result.mask
            rect = result.rect
            cls_index = result.class_index
            conf = result.conf

            h, w = img.shape[:2]

            if label_map is not None:
                label = f'{label_map[cls_index]}, {conf:.2f}'
            else:
                label = f"{conf:.2f}"

            if colors is not None:
                color = colors[cls_index]
            else:
                random.seed(42)
                color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

            img = plot_one_box(box, img, 
                                mask=mask, 
                                label=label, 
                                color=color, line_thickness=lw)
            
            color = (0, 255, 255)
            # if mask is not None:
            #     plot_one_min_rect(rect, img, 
            #                     color=color, 
            #                     line_thickness=1)
        return img

def load_labels(label_path:str):
    label_map = {}
    try:
        if label_path.endswith('.yaml'):
            with open(label_path, 'r', encoding="utf-8") as file:
                data = yaml.safe_load(file)
                label_map = data['names']

        elif label_path.endswith('.txt'):
            with open(label_path, 'r', encoding="utf-8") as file:
                lines = file.readlines()
                label_map = {}
                for i, line in enumerate(lines):
                    line = line.strip("\r\n").split(" ")
                    if len(line) > 1:
                        if line[0].isdigit():
                            label_map[int(line[0])] = " ".join(line[1:])
                        else:
                            label_map[i] = " ".join(line)    
                    else:
                        label_map[i] = " ".join(line)
    except:
        pass
    
    return label_map
    

class YoloInference():
    def __init__(self, model, label) -> None:
        self.model = YoloInference.load_model(model)
        self.label_map = load_labels(label)
        np.random.seed(0)
        self.color_map = np.random.uniform(0, 255, size=(len(self.label_map), 3))
    
    def load_model(model_path):
        start_time = time.perf_counter()
        try:
            model = YOLO(model_path)
            model.predict(np.zeros((640, 640, 3), dtype=np.uint8))
            end_time = time.perf_counter()
            msg = f"- Loading the network took {end_time-start_time:.2f} seconds."
            print(msg)
        except Exception as ex:
            print(str(ex))
            model = None
        return model 

    def detect(self, mat, conf=0.25, imgsz=640, approxy_contour=False, epsilon=0.001):
        result = self.model.predict(mat, conf=conf, imgsz=imgsz)[0]
        
        boxes = result.boxes
        masks = result.masks
        
        n_points = n_bndBox = n_class_index = n_conf = []

        if masks is not None:
            n_points = masks.xy

        if len(boxes):
            n_bndBox = boxes.xyxy.cpu().numpy().astype(np.uint64)
            n_class_index = list(map(int, boxes.cls))
            n_conf = list(map(float, boxes.conf))

        results = []
        for i in range(len(n_bndBox)):
            mask = n_points[i].astype(np.uint64) if masks is not None else None
            # 
            if approxy_contour and mask is not None:
                length = epsilon*cv2.arcLength(mask, True)
                mask = cv2.approxPolyDP(mask, length, True)
            # 
            rect = cv2.minAreaRect(mask) if mask is not None else None

            im_size = mat.shape[:2][::-1]

            results.append(DNNRESULT(
                class_index=n_class_index[i],
                box=n_bndBox[i],
                mask=mask,
                conf=n_conf[i],
                rect=rect,
                imgsz=im_size
            ))

        results = sorted(results, key=lambda x: x.conf, reverse=True)
        # 6 set on jig
        # if len(results) > 6:
        #     results = results[:6]
        return results
    
    def detect_multi(self, mats, conf=0.25, imgsz=640, 
                     approxy_contour=False, epsilon=0.001):
        t0 = time.time()
        results = self.model.predict(mats, conf=conf, imgsz=imgsz)
        dt = time.time() - t0
        
        _results = []
        for i, result in enumerate(results):
            boxes = result.boxes
            masks = result.masks
            
            n_points = n_bndBox = n_class_index = n_conf = []

            if masks is not None:
                n_points = masks.xy

            if len(boxes):
                n_bndBox = boxes.xyxy.cpu().numpy().astype(np.uint64)
                n_class_index = list(map(int, boxes.cls))
                n_conf = list(map(float, boxes.conf))

            _preds = []
            for i in range(len(n_bndBox)):
                mask = n_points[i].astype(np.uint64) if masks is not None else None
                # 
                if approxy_contour and mask is not None:
                    length = epsilon*cv2.arcLength(mask, True)
                    mask = cv2.approxPolyDP(mask, length, True)
                # 
                rect = cv2.minAreaRect(mask) if mask is not None else None

                im_size = mats[i].shape[:2][::-1]

                _preds.append(DNNRESULT(
                    class_index=n_class_index[i],
                    box=n_bndBox[i],
                    mask=mask,
                    conf=n_conf[i],
                    rect=rect,
                    imgsz=im_size
                ))
            
            _results.append(_preds)

        return _results

    def classify(self, mat, conf=0.2, imgsz=640):
        result = self.model.predict(mat, conf=conf, imgsz=imgsz)[0]
        probs = result.probs
        return DNNRESULT(
            class_index=probs.top1,
            conf=float(probs.top1conf)
        )
    

if __name__ == "__main__":
    # Khởi tạo model
    yolo = YoloInference(
        model="resources/models_ai/yolov8n-seg.pt",  # Sử dụng model detection (không có hậu tố -seg)
        label="resources/models_ai/labels.yaml"
    )

    # Mở video
    cap = cv2.VideoCapture(0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Thực hiện phát hiện
        results = yolo.detect(frame, conf=0.25, imgsz=640, approxy_contour=False, epsilon=0.001)
        
        # Vẽ kết quả
        output_frame = plot_results(results, frame, yolo.label_map, yolo.color_map)
        
        # Hiển thị FPS
        fps_text = f"Frame: {frame_count}"
        plot_text(fps_text, output_frame, org=(10, 30), color=(0, 255, 0))
        
        # Hiển thị (tùy chọn)
        cv2.imshow('YOLO Detection', output_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
        frame_count += 1
    
    cap.release()
    cv2.destroyAllWindows()
