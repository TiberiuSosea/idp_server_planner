from typing import List, Dict
from flask import Flask, request, render_template, redirect, url_for
import mysql.connector
import json
import os
from flask import Flask, flash, request, redirect, render_template
from werkzeug.utils import secure_filename
import sys
import time

app = Flask(__name__)

config = {
    'user': 'root',
    'password': 'root',
    'host': 'database',
    'port': '3306',
    'database': 'timetable'
}

@app.route('/')
def upload_form():
    return redirect(url_for('computation'))

@app.route('/start_computation', endpoint='computation')
def start_computation_form():
    return render_template('start_computing_plan.html')

@app.route('/start_computation', methods=['POST'])
def start_computation():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    person_name = request.form['name']
    plan_name = request.form['plan_name']
    create_if_not_existent = 'CREATE TABLE IF NOT EXISTS timetable_computed (person_name VARCHAR(20), timetable_name VARCHAR(20), actual_timetable TEXT );'
    cursor.execute(create_if_not_existent)
    cursor.execute("COMMIT")

    get_existing_plan = "SELECT * FROM timetable_computed WHERE person_name = \'" + person_name + "\' AND timetable_name = \'" + plan_name + "\';"
    cursor.execute(get_existing_plan)
    data = cursor.fetchall()

    if request.form['delete'] == 'yes':
        delete_query1 = "DELETE FROM timetable_computed WHERE person_name = \'" + person_name + "\' AND timetable_name = \'" + plan_name + "\';"
        delete_query2 = "DELETE FROM timetable_pending WHERE person_name = \'" + person_name + "\' AND timetable_name = \'" + plan_name + "\';"
        cursor.execute(delete_query1)
        cursor.execute(delete_query2)
        cursor.execute("COMMIT")
        return "DELTED"

    if len(data) != 0:
        res = data[0][2]
        return "COMPUTED ALREADY"

    get_crt_plan = "SELECT * FROM timetable_pending WHERE person_name = \'" +  person_name + "\' AND timetable_name = \'" + plan_name  + "\';"
    cursor.execute(get_crt_plan)
    data = cursor.fetchall()
    f = open("work_file.yml", "w")
    f.write(data[0][2])
    f.close()
    os.system('python planner.py work_file.yml work_result.yml ' + request.form['time'])
    time.sleep(int(request.form['time']) + 5)
    f = open("work_result.yml", 'r')
    res = f.read()
    f.close()

    query = "INSERT INTO timetable_computed (person_name, timetable_name, actual_timetable) VALUES (%s,%s,%s)"
    args = (data[0][0], data[0][1], res)
    cursor.execute(query, args)
    cursor.execute("COMMIT");
    return "DONE"


@app.route('/computed/<my_name>/<plan_name>')
def printAll(my_name, plan_name):
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM timetable_computed WHERE person_name = \'" + my_name + "\' AND timetable_name = \'" + plan_name + "\';")
    results = [var for var in cursor]


    if len(results) != 0:
        return "<pre>" + str(results[0][2]) + "</pre>"
    else:
        cursor.execute("SELECT * FROM timetable_pending WHERE person_name = \'" + my_name + "\' AND timetable_name = \'" + plan_name + "\';")
        results = [var for var in cursor]
        if len(results) != 0:
            return "Not yet computed or not submitted for computation"
        else:
            return "Not even registered"
    cursor.close()
    connection.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)