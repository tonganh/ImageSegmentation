import cv2
import requests
import os
import json
import sys

img = cv2.imread("saved_images/ocvk230131_192027.jpg")
img_en = cv2.imencode(".jpg", img)
print("Output:", img_en)

url = 'http://localhost:5000/get_main_object'
# file = {'image': ("savedocvk230131_192027.jpg", img_en[1])}
form_data = {'x1': 0, 'y1': 0, 'x2': 300, 'y2': 400}
data = requests.post(url, files=img, data=form_data)
print(json.loads(data.content.decode("utf-8")))