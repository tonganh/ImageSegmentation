import math
import os
import json
import time
import threading
import os

from queue import Empty, Queue
import cv2
from flask import Flask, request
import requests
from magicwand import SelectionWindow
from utils import byte_to_image, filename_gen
import mysql.connector
import shapely


app = Flask(__name__)
requestQueue = Queue()
CHECK_INTERVAL = 1
BATCH_SIZE = 10
BATCH_TIMEOUT = 2
database = mysql.connector.connect(
  host="localhost",
  user="root",
  password="",
  database="mydb"
)
cursorObject = database.cursor()


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


def request_handler():
    while True:
        batch = []
        while not (
                len(batch) > BATCH_SIZE or
                (len(batch) > 0 and time.time() - batch[0]['time'] > BATCH_TIMEOUT)
        ):
            try:
                batch.append(requestQueue.get(timeout=CHECK_INTERVAL))
            except Empty:
                continue
        for req in batch:
            if req['method'] == 'save_img':
                filename = filename_gen()
                path = f'saved_images/{filename}.jpg'
                sql = "INSERT INTO image_db (image_id, image_path) VALUES (%s, %s)"
                val = (filename, path)
                cursorObject.execute(sql, val)
                database.commit()
                cv2.imwrite(path, req['image'])
                out = {'image_id': filename, "status": 0}
                req['output'] = out

            elif req['method'] == 'draw_rectangle':
                path = f"saved_images/{req['image_id']}.jpg"
                img = cv2.imread(path)
                img_en = cv2.imencode(f".{os.path.splitext(os.path.basename(path))[1]}", img)
                file = {'image': (f"{req['image_id']}.jpg", img_en[1])}
                form_data = {'x1': req['points']['x1'],
                            'y1': req['points']['y1'],
                            'x2': req['points']['x2'],
                            'y2': req['points']['y2'],}
                data = requests.post(
                        'http://202.191.58.201/get_main_object',
                        files=file, 
                        data=form_data
                        )
                api_points = json.loads(data.content.decode("utf-8"))["points"]
                new_api_points = []
                for point in api_points:
                    new_api_points += [[req['points']['x1'] + point[0], req['points']['y1'] + point[1]]]
                api_points = new_api_points
                out = {'points': new_api_points, "status": 0}
                req['output'] = out

            elif req['method'] == 'add_selection':
                path = f"saved_images/{req['image_id']}.jpg"
                img = cv2.imread(path)
                list_points = req['points']

                temp_x, temp_y = 0, 0
                for point in list_points:
                    temp_x += point[0]
                    temp_y += point[1]
                center = [temp_x/len(list_points), temp_y/len(list_points)]

                rectangle = req['rectangle']
                obj = SelectionWindow(img)
                obj._ix, obj._iy = rectangle[0]
                obj._x, obj._y = rectangle[1]

                list_of_points = obj._shift_key(req['selected_point'][0], req['selected_point'][1])
                current_polygon = shapely.geometry.Polygon(req['points'])

                new_points = []
                
                for point in list_of_points:
                    line = shapely.geometry.LineString([[center[0], center[1]], [point.x(), point.y()]])
                    if line.intersects(current_polygon):
                        new_points += [[point.x(), point.y()]]
            
                current_contours = sort_contours(list_points + new_points, center)
                out = {'points': current_contours, "status": 0}
                req['output'] = out

            elif req['method'] == 'remove_selection':
                path = f"saved_images/{req['image_id']}.jpg"
                img = cv2.imread(path)

                rectangle = req['rectangle']
                obj = SelectionWindow(img)
                obj._ix, obj._iy = rectangle[0]
                obj._x, obj._y = rectangle[1]

                new_points = []
                
                list_of_points = obj._alt_key(req['selected_point'][0], req['selected_point'][1])
                for point in list_of_points:
                    new_points += [[point.x(), point.y()]]

                out = {'points': new_points, "status": 0}
                req['output'] = out

            elif req['method'] == 'save_poly':
                path = f"saved_images/{req['image_id']}.json"
                points = {"points": req['points']}

                json_obj = json.dumps(points, indent=4)
                with open(path, "w") as f:
                    f.write(json_obj)
                f.close()

                out = {'points': points, "status": 0}
                req['output'] = out
                
            elif req['method'] == 'load_poly':
                sql = "SELECT * FROM image_db WHERE image_id = %s"
                val = (req['image_id'], )
                cursorObject.execute(sql, val)
                results = cursorObject.fetchall()
                if len(results) > 0:
                    path = f"saved_images/{req['image_id']}.json"
                    with open(path, "r") as f:
                        out = json.load(f)
                    f.close()
                    out['status'] = 0
                    req['output'] = out


threading.Thread(target=request_handler).start()


@app.route('/isAlive', methods=['GET'])
def is_alive():
    return {'response': "Alive"}

        
@app.route('/save_img', methods=['POST'])
def save_img():
    file = request.files['image']
    img = byte_to_image(file)
    data = {'image': img, 
            'method': 'save_img',
            'time': time.time() 
            }
    # * put request to Queue
    requestQueue.put(data)
        
    count = 10
    while 'output' not in data and count > 0:
        time.sleep(CHECK_INTERVAL)
        count -= 1

    if 'output' in data and data['output']['status'] == 0:
        return {'image_id': data['output']['image_id']}
    else:
        return {'status': 'Not Successful'}


@app.route('/draw_rectangle', methods=['POST'])
def draw_rectangle():
    image_id = request.form['image_id']
    points = {'x1': int(request.form['x1']), 
            'y1': int(request.form['y1']), 
            'x2': int(request.form['x2']), 
            'y2': int(request.form['y2'])}
    data = {'image_id': image_id,
            'method': 'draw_rectangle',
            'points': points,
            'time': time.time() 
            }
    # * put request to Queue
    requestQueue.put(data)
        
    count = 10
    while 'output' not in data and count > 0:
        time.sleep(CHECK_INTERVAL)
        count -= 1

    if 'output' in data and data['output']['status'] == 0:
        return {'points': data['output']['points']}
    else:
        return {'status': 'Not Successful'}


@app.route('/add_selection', methods=['POST'])
def add_selection():
    image_id = request.form['image_id']
    rectangle = json.loads(request.form['rectangle'])
    selected_point = json.loads(request.form['selected_point'])
    points = json.loads(request.form['points'])
    data = {'image_id': image_id,
            'method': 'add_selection',
            'rectangle': rectangle,
            'selected_point': selected_point,
            'points': points,
            'time': time.time()
            }

    # * put request to Queue
    requestQueue.put(data)
        
    count = 10
    while 'output' not in data and count > 0:
        time.sleep(CHECK_INTERVAL)
        count -= 1

    if 'output' in data and data['output']['status'] == 0:
        return {'points': data['output']['points']}
    else:
        return {'status': 'Not Successful'}


@app.route('/remove_selection', methods=['POST'])
def remove_selection():
    image_id = request.form['image_id']
    rectangle = json.loads(request.form['rectangle'])
    selected_point = json.loads(request.form['selected_point'])
    points = json.loads(request.form['points'])
    data = {'image_id': image_id,
            'method': 'remove_selection',
            'rectangle': rectangle,
            'selected_point': selected_point,
            'points': points,
            'time': time.time()
            }

    # * put request to Queue
    requestQueue.put(data)
        
    count = 10
    while 'output' not in data and count > 0:
        time.sleep(CHECK_INTERVAL)
        count -= 1

    if 'output' in data and data['output']['status'] == 0:
        return {'points': data['output']['points']}
    else:
        return {'status': 'Not Successful'}


@app.route('/save_poly', methods=['POST'])
def save_poly():
    image_id = request.form['image_id']
    points = json.loads(request.form['points'])
    data = {'image_id': image_id,
            'method': 'save_poly',
            'points': points,
            'time': time.time()
            }

    # * put request to Queue
    requestQueue.put(data)
        
    count = 10
    while 'output' not in data and count > 0:
        time.sleep(CHECK_INTERVAL)
        count -= 1

    if 'output' in data and data['output']['status'] == 0:
        return {'status': 'Saved Successfully'}
    else:
        return {'status': 'Not Successful'}


@app.route('/load_poly', methods=['POST'])
def load_poly():
    image_id = request.form['image_id']
    data = {'image_id': image_id,
            'method': 'load_poly',
            'time': time.time()
            }

    # * put request to Queue
    requestQueue.put(data)
        
    count = 10
    while 'output' not in data and count > 0:
        time.sleep(CHECK_INTERVAL)
        count -= 1

    if 'output' in data and data['output']['status'] == 0:
        return data['output']
    else:
        return {'status': 'Not Successful'}


if __name__ == "__main__":
    app.run(debug=True, port=5000, host='0.0.0.0', threaded=True)
