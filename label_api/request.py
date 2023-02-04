import cv2
import requests
import os
import json
import sys

# url = sys.argv[1]
# image_path = "saved_images/test.jpg"

# """Upload image"""
# with open(image_path, 'rb') as img:
#     name_img= os.path.basename(image_path)
#     files= {'image': (name_img, img, 'formdata', {'Expires': '0'}),
#             'x1': "0",
#             'y1': "0",
#             'x2': "300",
#             'y2': "400"}
#     res = requests.post(url, data=files)
#     print(res.text)

# """Load image"""
# files= {'imageID': '1',
#         'method': 'load'}

# """Save image"""
# files= {'imageID': '1',
#         'method': 'save',
#         'points': [[(0, 0), (0, 1), (1, 0)],
#                     [(0, 0), (0, 1), (-1, 0)]
#                     ]}

# """Add points"""
# files= {'image': '1',
#         'method': 'add',
#         'points': json.dumps([
#                     [[0, 0], [0, 1], [1, 0]],
#                     [[0, 0], [0, 1], [-1, 0]]
#                             ])
#         }

# res = requests.post(url, files=files)
# print(json.loads(res.text)['text'])

# img = cv2.imread("saved_images/test.jpg")
# img_en = cv2.imencode(".jpg", img)
# print("Output:", img_en)

# url = 'http://202.191.58.201/get_main_object'
# file = {'image': ("test.jpg", img_en[1])}
# form_data = {'x1': 0, 'y1': 0, 'x2': 300, 'y2': 400}
# data = requests.post(url, files=file, data=form_data)
# print(json.loads(data.content.decode("utf-8"))["points"])

##### * save_img #####
# path = "saved_images/test.jpg"
# img = cv2.imread(path)
# img_en = cv2.imencode(os.path.splitext(os.path.basename(path))[1], img)

# url = 'http://127.0.0.1:5000/labelingTool'
# file = {'image': img_en[1]}
# res = requests.post(url, files=file)
# print(res.text)

##### * draw_rectangle #####
# url = 'http://127.0.0.1:5000/draw_rectangle'
# form_data = {
#     'image_id': 'lxkl230129_200055',
#     'x1': 100,
#     'y1': 100,
#     'x2': 200,
#     'y2': 200}
# res = requests.post(url, data=form_data)
# print(res.text)

##### * add_selection #####
url = 'http://127.0.0.1:5000/add_selection'
f = open('points.json')
points = json.load(f)['car']
print(points)

form_data = {
    'image_id': 'lxkl230129_200055',
    'rectangle': json.dumps([[100,100], [400,400]]),
    'selected_point': json.dumps([150, 250]),
    'points': json.dumps(points)}
res = requests.post(url, data=form_data)
print(res.text)

##### * remove_selection #####
# url = 'http://127.0.0.1:5000/remove_selection'
# f = open('points.json')
# points = json.load(f)['car']
# # print(points)

# form_data = {
#     'image_id': 'lxkl230129_200055',
#     'method': 'remove_selection',
#     'rectangle': json.dumps([[100,100], [400,400]]),
#     'selected_point': json.dumps([100, 200]),
#     'points': json.dumps(points)}
# res = requests.post(url, data=form_data)
# print(res.text)

##### * save_poly #####
# url = 'http://127.0.0.1:5000/save_poly'
# f = open('points.json')
# points = json.load(f)
# # print(points)

# form_data = {
#     'image_id': 'lxkl230129_200055',
#     'points': json.dumps(points)}
# res = requests.post(url, data=form_data)
# print(res.text)

##### * load_poly #####
# url = 'http://127.0.0.1:5000/load_poly'

# form_data = {
#     'image_id': 'lxkl230129_200055',
#     'method': 'load_poly'
#     }
# res = requests.post(url, data=form_data)
# print(res.text)