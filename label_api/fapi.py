import json
import math
import cv2
from fastapi import FastAPI, File
from pydantic import BaseModel
import mysql.connector
import shapely
from magicwand import SelectionWindow
from utils import byte_to_image, filename_gen

database = mysql.connector.connect(
  host="localhost",
  user="root",
  password="root",
  database="mydb"
)
cursorObject = database.cursor()
app = FastAPI()

class Item(BaseModel):
    image_id: str = None
    rectangle: list = []
    selected_point = []
    points: list = []
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

@app.post("/save_img")
async def save_img(file: bytes = File()):
    img = byte_to_image(file)
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
    list_points = item.points

    temp_x, temp_y = 0, 0
    for point in list_points:
        temp_x += point[0]
        temp_y += point[1]
    center = [temp_x/len(list_points), temp_y/len(list_points)]

    rectangle = item.rectangle
    obj = SelectionWindow(img)
    obj._ix, obj._iy = rectangle[0]
    obj._x, obj._y = rectangle[1]

    list_of_points = obj._shift_key(item.selected_point[0], item.selected_point[1])
    current_polygon = shapely.geometry.Polygon(item.points)

    new_points = []
    
    for point in list_of_points:
        line = shapely.geometry.LineString([[center[0], center[1]], [point.x(), point.y()]])
        if line.intersects(current_polygon):
            new_points += [[point.x(), point.y()]]

    current_contours = sort_contours(list_points + new_points, center)
    
    return {'points': current_contours}

@app.post("/remove_selection")
async def remove_selection(item: Item):
    path = f"saved_images/{item.image_id}.jpg"
    img = cv2.imread(path)
    list_points = item.points

    temp_x, temp_y = 0, 0
    for point in list_points:
        temp_x += point[0]
        temp_y += point[1]
    center = [temp_x/len(list_points), temp_y/len(list_points)]

    rectangle = item.rectangle
    obj = SelectionWindow(img)
    obj._ix, obj._iy = rectangle[0]
    obj._x, obj._y = rectangle[1]

    list_of_points = obj._alt_key(item.selected_point[0], item.selected_point[1])
    current_polygon = shapely.geometry.Polygon(item.points)

    new_points = []

    for point in list_of_points:
        line = shapely.geometry.LineString([[center[0], center[1]], [point.x(), point.y()]])
        if not line.intersects(current_polygon):
            new_points += [[point.x(), point.y()]]

    current_contours = sort_contours(list_points + new_points, center)
    
    return {'points': current_contours}

@app.post("/save_poly")
async def save_poly(item: Item):
    path = f"saved_images/{item.image_id}.json"
    points = item.saved_points

    json_obj = json.dumps(points, indent=4)
    with open(path, "w") as f:
        f.write(json_obj)
    f.close()
    
    return {'image_id': item.image_id,
            'points': item.points}

@app.post("/load_poly")
async def load_poly(item: Item):
    sql = "SELECT * FROM image_db WHERE image_id = %s"
    val = (item.image_id, )
    cursorObject.execute(sql, val)
    results = cursorObject.fetchall()
    if len(results) > 0:
        path = f"saved_images/{item.image_id}.json"
        with open(path, "r") as f:
            output = json.load(f)
        f.close()
    
    return output
