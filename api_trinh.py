import time
import string
import random
import os
import numpy as np
import cv2
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from ade import CLASSES
from segmentation import get_largest_object_polygon, DeepLabModel

import json
import math
import cv2
from fastapi import FastAPI, File, Form, UploadFile
from typing import Union
from pydantic import BaseModel
import mysql.connector
import shapely
from magicwand import SelectionWindow
from new_utils import byte_to_image, filename_gen

database = mysql.connector.connect(
  host="localhost",
  user="root",
  password="root",
  database="mydb"
)
cursorObject = database.cursor()
app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "./temp/"
os.makedirs(TEMP_DIR, exist_ok=True)

MODEL = DeepLabModel(
    "deeplabv3_xception_ade20k_train/frozen_inference_graph.pb"
    # "deeplabv3_mnv2_ade20k_train_2018_12_03/frozen_inference_graph.pb"
)
print("model loaded successfully!")

ORI_CLASS2IDX = {k: i for i, k in enumerate(CLASSES)}

CONSIDER_CLASSES = {
    "building, edifice": 1,
    "house": 1,
    "skyscraper": 1,
    "car, auto, automobile, machine, motorcar": 2,
    "truck, motortruck": 2,
    "airplane, aeroplane, plane": 3
}  # class to our new label indices

IDX2CONSIDER_CLASS = {1: "building", 2: "car+truck", 3: "plane"}

# app = Flask(__name__)
# cors = CORS(app)

class Item(BaseModel):
    image_id: str = None
    rectangle: list = []
    selected_points: list = []
    click_point: list = []

class SavePoly(BaseModel):
    image_id: str = None
    saved_points: dict = None

def distance_between_points(point_1, point_2):
    vector = [point_2[0]-point_1[0], point_2[1]-point_1[1]]
    return math.hypot(vector[0], vector[1])

def sort_contours(contours, center):
    refvec = [0, 1]
    
    def clockwise_sort(point):
        vector = [point[0] - center[0], point[1] - center[1]]
        len_vector = distance_between_points(center, point)
        
        if len_vector == 0:
            return -math.pi, 0

        # Normalize vector: v/||v||
        normalized = [vector[0]/len_vector, vector[1]/len_vector]

        dotprod  = normalized[0] * refvec[0] + normalized[1] * refvec[1] # x1*x2 + y1*y2
        diffprod = refvec[1] * normalized[0] - refvec[0] * normalized[1] # x1*y2 - y1*x2
        angle = math.atan2(diffprod, dotprod) # angle = arctan2(y, x)

        if angle < 0:
            return 2*math.pi + angle, len_vector

        return angle, len_vector

    return sorted(contours, key=clockwise_sort)

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return "".join(random.choice(chars) for _ in range(size))

@app.get('/test')
def test():
    return 1

@app.post("/get_main_object")
async def get_main_object(image_file: UploadFile = File(), 
                          x1: Union[str, float, int] = Form(), 
                          y1: Union[str, float, int] = Form(), 
                          x2: Union[str, float, int] = Form(), 
                          y2: Union[str, float, int] = Form()):
    img = byte_to_image(await image_file.read())
    print("Image:", img)
    x1 = float(x1)
    y1 = float(y1)
    x2 = float(x2)
    y2 = float(y2)

    original_filename = image_file.filename
    original_ext = original_filename.split(".")[-1]

    temp_filename = str(time.time()) + id_generator()
    temp_filepath = f"{TEMP_DIR}/{temp_filename}.{original_ext}"

    cv2.imwrite(temp_filepath, img)

    print(temp_filepath)

    img = Image.open(temp_filepath)
    print("Size: ", img.size)
    img = img.crop((x1, y1, x2, y2))
    resized_im, seg_map = MODEL.run(img)

    filter_seg_map = np.zeros_like(seg_map, dtype=np.int32)
    for label in CONSIDER_CLASSES.keys():
        filter_seg_map[seg_map == ORI_CLASS2IDX[label]] = CONSIDER_CLASSES[label]
    box = get_largest_object_polygon(filter_seg_map, x1, y1, img.width, img.height, IDX2CONSIDER_CLASS)

    if len(box["points"]) > 0:
        img_cv = np.asarray(img)
        img_cv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        img_cv = cv2.polylines(img_cv, [np.array(box["points"])], True, (255, 0, 0), thickness=2)
        cv2.imwrite(f"{TEMP_DIR}/{temp_filename}-box.png", img_cv)

        os.remove(temp_filepath)
    else:
        print("len(points)==0")
    
    # print("Type of box:", type(box))
    return box
    # return {"status": 200}

@app.post("/save_img")
async def save_img(file: UploadFile = File()):
    img = byte_to_image(await file.read())
    filename = filename_gen()
    path = f'saved_images/{filename}.jpg'
    sql = "INSERT INTO image_db (image_id, image_path) VALUES (%s, %s)"
    val = (filename, path)
    cursorObject.execute(sql, val)
    database.commit()
    cv2.imwrite(path, img)
    return {'image_id': filename}

@app.post("/add_selection")
async def add_selection(item: Item):
    path = f"saved_images/{item.image_id}.jpg"
    img = cv2.imread(path)
    list_points = item.selected_points

    if len(list_points) > 0:
        temp_x, temp_y = 0, 0
        for point in list_points:
            temp_x += point[0]
            temp_y += point[1]
        center = [temp_x/len(list_points), temp_y/len(list_points)]

        rectangle = item.rectangle
        obj = SelectionWindow(img)
        obj._ix, obj._iy = rectangle[0]
        obj._x, obj._y = rectangle[1]

        list_of_points = obj._shift_key(item.click_point[0], item.click_point[1])
        current_polygon = shapely.geometry.Polygon(item.selected_points)

        new_points = []
        
        for point in list_of_points:
            line = shapely.geometry.LineString([[center[0], center[1]], [point.x(), point.y()]])
            if line.intersects(current_polygon):
                new_points += [[point.x(), point.y()]]

        current_contours = sort_contours(list_points + new_points, center)

        return {'points': current_contours}
    else:
        return {'Error': "Please provide selected_points!"}
    

@app.post("/remove_selection")
async def remove_selection(item: Item):
    path = f"saved_images/{item.image_id}.jpg"
    img = cv2.imread(path)
    list_points = item.selected_points

    if len(list_points) > 0:
        temp_x, temp_y = 0, 0
        for point in list_points:
            # print(f'point: {point[0]}')
            temp_x += point[0]
            temp_y += point[1]
        center = [temp_x/len(list_points), temp_y/len(list_points)]

        rectangle = item.rectangle
        obj = SelectionWindow(img)
        obj._ix, obj._iy = rectangle[0]
        obj._x, obj._y = rectangle[1]

        list_of_points = obj._alt_key(item.click_point[0], item.click_point[1])
        current_polygon = shapely.geometry.Polygon(item.selected_points)

        new_points = []

        for point in list_of_points:
            line = shapely.geometry.LineString([[center[0], center[1]], [point.x(), point.y()]])
            if not line.intersects(current_polygon):
                new_points += [[point.x(), point.y()]]

        current_contours = sort_contours(list_points + new_points, center)
        
        return {'points': current_contours}
    else:
        return {'Error': "Please provide selected_points!"}

@app.post("/save_poly")
async def save_poly(item: SavePoly):
    path = f"saved_images/{item.image_id}.json"
    saved_points = item.saved_points

    json_obj = json.dumps(saved_points, indent=4)
    with open(path, "w") as f:
        f.write(json_obj)
    f.close()
    
    return {'image_id': item.image_id,
            'points': saved_points}

@app.post("/load_poly")
async def load_poly(image_id: str):
    sql = "SELECT * FROM image_db WHERE image_id = %s"
    val = (image_id, )
    cursorObject.execute(sql, val)
    results = cursorObject.fetchall()
    if len(results) > 0:
        path = f"saved_images/{image_id}.json"
        with open(path, "r") as f:
            output = json.load(f)
        f.close()
    
    return output