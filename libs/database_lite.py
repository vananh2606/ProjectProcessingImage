import time
import sqlite3
from sqlite3 import Error, IntegrityError
from datetime import datetime

# from constant import *

def create_db(db_file):
    """ create a database connection to the SQLite database
        specified by db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        pass

    return conn

def create_table(conn,create_table_sql):
    '''
    'CREATE TABLE IF NOT EXISTS table_name(
        column_1 data_type PRIMARY KEY,
   	    column_2 data_type NOT NULL,
	    column_3 data_type DEFAULT 0
    )'
    '''
    c = conn.cursor()
    c.execute(create_table_sql)

def insert(conn,insert_table_sql,values):
    '''
    'INSERT INTO table_name (column1,column2 ,..)
    VALUES (?,?,..)'
    '''
    cur = conn.cursor()
    cur.execute(insert_table_sql,values)
    conn.commit()

def update(conn,update_table_sql,values):
    ''' UPDATE tasks
              SET priority = ? ,
                  begin_date = ? ,
                  end_date = ?
              WHERE id = ?'''
    cur = conn.cursor()
    cur.execute(update_table_sql,values)
    conn.commit()

def select(conn,select_table_sql,key=None):
    ''' 'SELECT * FROM table WHERE id = ?' '''
    cur = conn.cursor()
    if key :
        obj = cur.execute(select_table_sql,key)
    else:
        obj = cur.execute(select_table_sql)
    rows = obj.fetchall()
    return rows

def delete(conn,delete_sql,value=None):
    '''DELETE * FROM mytable WHERE id=?'''
    cur = conn.cursor()
    if value is not None:
        cur.execute(delete_sql,value)
    else:
        cur.execute(delete_sql)
    conn.commit()

def create_databse(database_path, sql_scripts):
    with open(sql_scripts, 'r') as f:
        script = f.read()

        conn = create_db(database_path)
        if conn:
            c = conn.cursor()
            c.executescript(script)
            conn.commit()
            conn.close()

if __name__ == '__main__':
    # tao database
    create_databse("database.db", "resources/database/database.sql")

    import faker
    faker = faker.Faker()
    
    row = (
        faker.name(),
        faker.phone_number(),
        faker.address(),
        faker.hostname(),
        faker.email(),
        faker.city(),
        faker.country(),
        # "Roger Rojas" # Upadte
    )

    # INSERT
    # sql = "INSERT INTO history (camera, model, result, time_check, img_path, code, error_type) VALUES (?, ?, ?, ?, ?, ?, ?)"
    # conn = create_db("database.db")
    # insert(conn, sql, row)

    # UPDATE
    # sql = "UPDATE history SET camera = ?, model = ?, result = ?, time_check = ?, img_path = ?, code = ?, error_type = ? WHERE camera = ?"
    # conn = create_db("database.db")
    # update(conn, sql, row)

    # SELECT
    # sql = "SELECT * FROM history"
    # conn = create_db("database.db")
    # select(conn, sql)

    # DELETE
    # sql = "DELETE FROM history WHERE camera = 'Mr. James Johnson II'"
    # conn = create_db("database.db")
    # delete(conn, sql)
        


