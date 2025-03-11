from flask import Flask, render_template, request, redirect, session, flash,url_for
from email.mime.multipart import MIMEMultipart
from datetime import datetime,timedelta
from email.mime.text import MIMEText
import mysql.connector
import secrets
import smtplib
import os

app = Flask(__name__)
def get_secret_key():
    return 'your_secret_key'

app = Flask(__name__)
app.secret_key = get_secret_key()


USE_DEPLOYED_DB = os.getenv("USE_DEPLOYED_DB", "false").lower() == "true"

if USE_DEPLOYED_DB:
    db = mysql.connector.connect(
        host=os.getenv("DEPLOYED_DB_HOST"),
        user=os.getenv("DEPLOYED_DB_USER"),
        password=os.getenv("DEPLOYED_DB_PASS"),
        database=os.getenv("DEPLOYED_DB_NAME")
    )
else:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="videomeet"
    )

cursor = db.cursor()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['username']
        email = request.form['email']
        password = request.form['password']

        sql = "SELECT * FROM users WHERE email = %s"
        val = (email,)
        cursor.execute(sql, val)
        user = cursor.fetchone()

        if user:
            flash('User already exists. Please Login.', 'danger')
        else:
            sql = "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)"
            val = (name, email, password)
            cursor.execute(sql, val)
            db.commit()
            flash('Signup Successful!', 'success')

    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        sql = "SELECT * FROM users WHERE email = %s AND password = %s"
        val = (email, password)
        cursor.execute(sql, val)
        user = cursor.fetchone()

        if user:
            session['user'] = email
            session['user_name'] = user[1]  
            flash('Login Successful!', 'success')
            return redirect('/dashboard')
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        email = session['user']
        sql = "SELECT name, email FROM users WHERE email = %s"
        val = (email,)
        cursor.execute(sql, val)
        user = cursor.fetchone()
        user_info = {'name': user[0], 'email': user[1]}

    
        sql = "SELECT meeting_id, meeting_name, meeting_date, meeting_time, meeting_duration, meeting_description FROM meetings WHERE email = %s"
        cursor.execute(sql, (email,))
        meetings = cursor.fetchall()

        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        meeting_list = []
        for meeting in meetings:
            meeting_dict = {
                'meeting_id': meeting[0],
                'meeting_name': meeting[1],
                'meeting_date': meeting[2],
                'meeting_time': meeting[3],
                'meeting_duration': meeting[4],
                'meeting_description': meeting[5],
                'can_start': current_time >= f"{meeting[2]} {meeting[3]}"
            }
            meeting_list.append(meeting_dict)

        return render_template('dashboard.html', logged_in=True, user=user_info, meetings=meeting_list)
    else:
        return render_template('dashboard.html', logged_in=False)

@app.route('/create_meeting', methods=['GET', 'POST'])
def create_meeting():
    if 'user' not in session:
        return redirect('/login')

    if request.method == 'POST':    
        meeting_name = request.form['meeting_name']
        meeting_date = request.form['meeting_date']
        meeting_time = request.form['meeting_time']
        meeting_time_period = request.form['meeting_time_period']
        meeting_duration = request.form['meeting_duration']
        meeting_description = request.form['meeting_description']
        meeting_id = secrets.token_hex(8) 
        email = session['user']  

        meeting_time = datetime.strptime(meeting_time, '%H:%M')
        if meeting_time_period == 'PM' and meeting_time.hour != 12:
            meeting_time = meeting_time.replace(hour=meeting_time.hour + 12)
        elif meeting_time_period == 'AM' and meeting_time.hour == 12:
            meeting_time = meeting_time.replace(hour=0)
        meeting_time = meeting_time.strftime('%H:%M:%S')

        sql = "INSERT INTO meetings (meeting_id, meeting_name, meeting_date, meeting_time, meeting_duration, meeting_description, email) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        val = (meeting_id, meeting_name, meeting_date, meeting_time, meeting_duration, meeting_description, email)
        cursor.execute(sql, val)
        db.commit()

        flash('Meeting created successfully!', 'success')
        return redirect('/dashboard')

    email = session['user']
    sql = "SELECT name, email FROM users WHERE email = %s"
    val = (email,)
    cursor.execute(sql, val)
    user = cursor.fetchone()
    user_info = {'name': user[0], 'email': user[1]}

    return render_template('create_meeting.html', logged_in=True, user=user_info)

@app.route('/start_meeting/<meeting_id>')
def start_meeting(meeting_id):
    meeting_link = url_for('meeting_room', meeting_id=meeting_id, _external=True)
    flash(f'Meeting started! Share this link: {meeting_link}', 'success')
    return redirect(url_for('meeting_room', meeting_id=meeting_id))

@app.route('/meeting_room/<meeting_id>')
def meeting_room(meeting_id):
    return render_template('meeting_room.html', meeting_id=meeting_id)

@app.route('/delete_meeting/<meeting_id>', methods=['DELETE'])
def delete_meeting(meeting_id):
    if 'user' in session:
        sql = "DELETE FROM meetings WHERE meeting_id = %s"
        val = (meeting_id,)
        cursor.execute(sql, val)
        db.commit()
        return '', 204
    else:
        return '', 401

@app.route('/join_meeting', methods=['GET', 'POST'])
def join_meeting():
    if request.method == 'POST':
        meeting_id_or_link = request.form['meeting_id']
        if 'meeting_room' in meeting_id_or_link:
            meeting_id = meeting_id_or_link.split('/')[-1]
        else:
            meeting_id = meeting_id_or_link

        return redirect(url_for('meeting_room', meeting_id=meeting_id))
    
    return render_template('join_meeting.html')    

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if request.method == 'POST':
        email = request.form['email']
        sql = "SELECT * FROM users WHERE email = %s"
        val = (email,)
        cursor.execute(sql, val)
        user = cursor.fetchone()

        if user:
            token = secrets.token_hex(16)
            expiration = datetime.now() + timedelta(hours=1)
            sql = "INSERT INTO password_resets (email, token, expiration) VALUES (%s, %s, %s)"
            val = (email, token, expiration)
            cursor.execute(sql, val)
            db.commit()

            reset_url = url_for('reset_password', token=token, _external=True)
            print(f"Sending reset email to {email} with URL: {reset_url}")  # Debugging statement
            send_reset_email(email, reset_url)
            flash('A password reset link has been sent to your email.', 'info')
        else:
            flash('Email not found.', 'danger')

    return render_template('reset_password_req.html')
def send_reset_email(email, reset_url):
    sender_email = "20211460@sbsstc.ac.in"
    sender_password = "jjud bxmd kckq bwyd"
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email
    msg['Subject'] = "Password Reset Request"
    body = f"Please click the link to reset your password: {reset_url}"
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)
    text = msg.as_string()
    server.sendmail(sender_email, email, text)
    server.quit()

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    sql = "SELECT * FROM password_resets WHERE token = %s"
    val = (token,)
    cursor.execute(sql, val)
    reset_request = cursor.fetchone()

    if reset_request and reset_request[2] > datetime.now():
        if request.method == 'POST':
            new_password = request.form['password']
            email = reset_request[0]
            sql = "UPDATE users SET password = %s WHERE email = %s"
            val = (new_password, email)
            cursor.execute(sql, val)
            db.commit()

            sql = "DELETE FROM password_resets WHERE token = %s"
            val = (token,)
            cursor.execute(sql, val)
            db.commit()

            flash('Your password has been reset successfully.', 'success')
            return redirect('/login')
    else:
        flash('The password reset link is invalid or has expired.', 'danger')

    return render_template('reset_password.html')



if __name__ == '__main__':
    app.run(debug=True)