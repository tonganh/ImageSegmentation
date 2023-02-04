import mysql.connector

database = mysql.connector.connect(
  host="localhost",
  user="root",
  password="root",
  database="mydb"
)

cursorObject = database.cursor()

# cursorObject.execute("CREATE DATABASE mydb")
 
cursorObject.execute("""CREATE TABLE image_db (
                    image_id VARCHAR(255) NOT NULL PRIMARY KEY,
                    image_path VARCHAR(255) NOT NULL
                    )
                    """)
   
# myresult = cursorObject.fetchall()
   
# for x in myresult:
#     print(x, type(x), x[1])
#     print()
 
# disconnecting from server
database.close()
