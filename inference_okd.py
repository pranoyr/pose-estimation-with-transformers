# -*- coding: utf-8 -*-
"""detr_demo.ipynb

Automatically generated by Colaboratory.

Original file is located at
	https://colab.research.google.com/github/facebookresearch/detr/blob/colab/notebooks/detr_demo.ipynb

# Object Detection with DETR - a minimal implementation

In this notebook we show a demo of DETR (Detection Transformer), with slight differences with the baseline model in the paper.

We show how to define the model, load pretrained weights and visualize bounding box and class predictions.

Let's start with some common imports.
"""
#!/usr/bin/env python3

import cv2
import depthai as dai

# Create pipeline
pipeline = dai.Pipeline()

# Define source and output
camRgb = pipeline.create(dai.node.ColorCamera)
xoutVideo = pipeline.create(dai.node.XLinkOut)

xoutVideo.setStreamName("video")

# Properties
camRgb.setBoardSocket(dai.CameraBoardSocket.RGB)
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
camRgb.setVideoSize(1280, 720)

xoutVideo.input.setBlocking(False)
xoutVideo.input.setQueueSize(100)

# Linking
camRgb.video.link(xoutVideo.input)

# # Connect to device and start pipeline
# with dai.Device(pipeline) as device:

#     video = device.getOutputQueue(name="video", maxSize=1, blocking=False)

#     while True:
#         videoIn = video.get()

#         # Get BGR frame from NV12 encoded video frame to show with opencv
#         # Visualizing the frame on slower hosts might have overhead
#         cv2.imshow("video", videoIn.getCvFrame())

#         if cv2.waitKey(1) == ord('q'):
#             break




# Commented out IPython magic to ensure Python compatibility.
from PIL import Image
import cv2
import numpy as np
import requests
import matplotlib.pyplot as plt
# %config InlineBackend.figure_format = 'retina'

import torch
from torch import nn
from torchvision.models import resnet50
import torchvision.transforms as T
import json
import argparse
torch.set_grad_enabled(False);

"""## DETR
Here is a minimal implementation of DETR:
"""

from main import get_args_parser
from models import build_model

parser = argparse.ArgumentParser('DETR training and evaluation script', parents=[get_args_parser()])
args = parser.parse_args()

model, criterion, postprocessors = build_model(args)
model.to("cuda")
model.eval()


checkpoint = torch.load("./snapshots/model.pth")
model.load_state_dict(checkpoint["model"])


writer = cv2.VideoWriter('output.avi', cv2.VideoWriter_fourcc(*'XVID'), 20, (1280, 720))

# colors for visualization
COLORS = [[0.000, 0.447, 0.741], [0.850, 0.325, 0.098], [0.929, 0.694, 0.125],
		  [0.494, 0.184, 0.556], [0.466, 0.674, 0.188], [0.301, 0.745, 0.933]]

"""DETR uses standard ImageNet normalization, and output boxes in relative image coordinates in $[x_{\text{center}}, y_{\text{center}}, w, h]$ format, where $[x_{\text{center}}, y_{\text{center}}]$ is the predicted center of the bounding box, and $w, h$ its width and height. Because the coordinates are relative to the image dimension and lies between $[0, 1]$, we convert predictions to absolute image coordinates and $[x_0, y_0, x_1, y_1]$ format for visualization purposes."""

# standard PyTorch mean-std input image normalization
transform = T.Compose([
	T.Resize(800, max_size = 1333),
	# T.Resize((240,352)),
	T.ToTensor(),
	T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# for output bounding box post-processing
def box_cxcywh_to_xyxy(x):
	x_c, y_c, w, h = x.unbind(1)
	b = [(x_c - 0.5 * w), (y_c - 0.5 * h),
		 (x_c + 0.5 * w), (y_c + 0.5 * h)]
	return torch.stack(b, dim=1)

def rescale_bboxes(out_bbox, size):
	img_w, img_h = size
	b = box_cxcywh_to_xyxy(out_bbox)
	b = b * torch.tensor([img_w, img_h, img_w, img_h], dtype=torch.float32)
	return b

"""Let's put everything together in a `detect` function:"""

def detect(im, model, transform):
	# mean-std normalize the input image (batch-size: 1)
	img = transform(im).unsqueeze(0)

	# demo model only support by default images with aspect ratio between 0.5 and 2
	# if you want to use images with an aspect ratio outside this range
	# rescale your image so that the maximum size is at most 1333 for best results
	assert img.shape[-2] <= 1600 and img.shape[-1] <= 1600, 'demo model only supports images up to 1600 pixels on each side'

	# propagate through the model
	outputs = model(img.cuda())
	print(outputs['pred_keypoints'].shape)

	# keep only predictions with 0.7+ confidence
	predictions = outputs['pred_logits'].softmax(-1)[0, :, :-1]
	keep = predictions.max(-1).values > 0.5
	keypoints = outputs['pred_keypoints'][0, keep]
	print(keypoints.shape)


	C_pred = keypoints[:, :2] # shape (N, 2)
	Z_pred = keypoints[:, 2:36] # shape (N, 34)
	V_pred = keypoints[:, 36:] 	# shape (N, 17)

	V_pred = torch.repeat_interleave(V_pred, 2, dim=1)
	C_pred_expand = torch.repeat_interleave(C_pred.unsqueeze(1), 17, dim=1).view(-1,34)
	A_pred = C_pred_expand + Z_pred # torch.size([num_persons, 34])
	A_pred[V_pred < 0.5] = -1
	#A_pred = A_pred[torch.repeat_interleave(V_pred, 2, dim=1) > 0].view(-1,34)

	

	# rescale bounding boxes to absolute image coordinates
	w, h = im.size
	A_pred =  A_pred  *  torch.tensor([w, h] * 17, dtype = torch.float32, device="cuda")
	keypoints_scaled = A_pred.view(-1, 17, 2)
	print(keypoints_scaled.shape)
	

	# print(predictions.shape)
	# print(predictions[keep])
	# print(keypoints.shape)

	return  predictions[keep] , keypoints_scaled.type(torch.int32)

"""## Using DETR
To try DETRdemo model on your own image just change the URL below.
"""

# url = 'http://images.cocodataset.org/val2017/000000039769.jpg'

def plot_results(img, scores, keypoints):
	# plt.figure(figsize=(16,10))
	# plt.imshow(pil_img)
	# ax = plt.gca()
	img_draw = np.array(img)
	# img_draw = img.copy()
	

	for s, keypoints, c in zip(scores, keypoints.tolist(), COLORS * 100):
		# ax.add_patch(plt.Rectangle((xmin, ymin), xmax - xmin, ymax - ymin,
		# 						   fill=False, color=c, linewidth=3))
		cls_ = s.argmax()
		# text = f'{CLASSES[cl]}: {p[cl]:0.2f}'
		text = "person"
		print(text)

		for joint in keypoints:
			if joint[0] >= 0 and joint[1] >= 0:
				cv2.circle(img_draw, (joint[0], joint[1]), 2, (255,0,0), -1)
		# # draw neck
		x, y  = (keypoints[5][0] + keypoints[6][0]) / 2, (keypoints[5][1] + keypoints[6][1]) / 2
		cv2.circle(img_draw, (int(x), int(y)), 2, (0,255,0), -1)

		# ax.text(xmin, ymin, text, fontsize=15,
	# 	# 		bbox=dict(facecolor='yellow', alpha=0.5))
	# plt.axis('off')
	# plt.show()
	img_draw = cv2.resize(img_draw, (1920, 1280))
	cv2.imshow("draw", cv2.cvtColor(img_draw, cv2.COLOR_RGB2BGR))
	writer.write(cv2.resize(cv2.cvtColor(img_draw, cv2.COLOR_RGB2BGR), (1280, 720)))
	cv2.waitKey(1)




# cam = cv2.VideoCapture(0)
# cam = cv2.VideoCapture("rtsp://admin:l2dtech123@192.168.2.33:554/cam/realmonitor?channel=1&subtype=0")

# Connect to device and start pipeline
with dai.Device(pipeline) as device:

	video = device.getOutputQueue(name="video", maxSize=500, blocking=False)

	while True:
		videoIn = video.get()
		# cv2.imshow("video", videoIn.getCvFrame())
		# cv2.waitKey(1)

		# Get BGR frame from NV12 encoded video frame to show with opencv
		# Visualizing the frame on slower hosts might have overhead
		im = videoIn.getCvFrame()
		print(im.shape)

		im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
		im = Image.fromarray(im)

		scores, keypoints = detect(im, model, transform)
		plot_results(im.copy(), scores, keypoints)

		"""Let's now visualize the model predictions"""
