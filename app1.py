from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os
import MySQLdb.cursors
import base64
import datetime 
import time
from flask import send_file

app = Flask(__name__)
app.secret_key = 'replace_with_a_strong_secret'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_PORT'] = 1405
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Utkarsh@05'
app.config['MYSQL_DB'] = 'utkarsh'
mysql = MySQL(app)

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'adminpass'  

def format_seconds(seconds):
    if seconds is None:
        seconds = 0
    return str(datetime.timedelta(seconds=int(seconds)))
def fetchall_dict(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def track_user_activity(user_id):
    if user_id:
        cursor = None
        try:
            cursor = mysql.connection.cursor() 

            cursor.execute("UPDATE users SET last_seen = UTC_TIMESTAMP() WHERE id = %s", (user_id,))

            mysql.connection.commit()

        except Exception as e:
            print(f"Error updating last_seen for user {user_id}: {e}")

            try:
                mysql.connection.rollback()
            except Exception:
                pass 

        finally:
            if cursor:
                cursor.close()

@app.before_request
def before_request():
    global session_start_time
    session_start_time = {}
    user_id = session.get('user_id')
    if user_id:
        if user_id not in session_start_time:
            session_start_time[user_id] = time.time()

        track_user_activity(user_id)

@app.route('/init_db')
def init_db():
    return "DB initialization route is disabled. Please ensure your database tables match the provided SQL queries."

@app.route('/')
def index():
    if session.get('loggedin'):
        return redirect(url_for('dashboard'))
    return render_template('landing.html')
@app.route('/profile')
def user_profile():
    if not session.get('loggedin'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT id, name, username, email, mobile, city, owner, gender FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()

    if not user:
        flash('User profile not found.', 'danger')
        session.clear()
        return redirect(url_for('login'))

    return render_template('profile.html', user=user)


@app.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('loggedin'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    name = request.form.get('name')
    email = request.form.get('email')
    mobile = request.form.get('mobile')
    city = request.form.get('city')


    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE users 
        SET name=%s, email=%s, mobile=%s, city=%s 
        WHERE id=%s
    """, (name, email, mobile, city, user_id))

    mysql.connection.commit()
    cursor.close()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('user_profile'))


@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    if not session.get('loggedin'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')


    cursor = mysql.connection.cursor()

    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cursor.close()

    session.clear()
    flash('Your account and all associated data have been permanently deleted.', 'info')
    return redirect(url_for('login'))
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        city = request.form.get('city')
        password = request.form.get('password')
        is_owner = '1' if request.form.get('role') == 'owner' else '0'
        gender = request.form.get('gender') or 'male'

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        existing = cursor.fetchone()
        if existing:
            flash('Username or email already exists', 'danger')
            cursor.close()
            return render_template('register.html')
        hashed = generate_password_hash(password)
        cursor.execute("INSERT INTO users (name, username, email, mobile, city, password, owner, gender) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
               (name, username, email, mobile, city, password, is_owner, gender))
        mysql.connection.commit()
        cursor.close()
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        if user and user['password'] == password:
            session.clear()
            session['loggedin'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_owner'] = user['owner'] == '1'
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    global session_start_time
    session_start_time = {}
    user_id = session.get('user_id')
    remind_later = request.form.get('remind_later')

    last_session_duration = 0
    if user_id and user_id in session_start_time:
        last_session_duration = int(time.time() - session_start_time[user_id])

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE users SET total_time_spent = total_time_spent + %s WHERE id = %s", 
                       (last_session_duration, user_id))
        mysql.connection.commit()
        cursor.close()

        del session_start_time[user_id]

    if user_id:
        cursor = mysql.connection.cursor()
        if remind_later == '1':
            cursor.execute("UPDATE users SET feedback = IFNULL(feedback, 0) + 1 WHERE id = %s", (user_id,))
        else:
            rating = request.form.get('rating')
            comment = request.form.get('comment')
            if rating:
                cursor.execute("INSERT INTO feedback (user_id, rating, comment, room_id) VALUES (%s,%s,%s, NULL)", (user_id, int(rating), comment))
                cursor.execute("UPDATE users SET feedback = 0 WHERE id = %s", (user_id,))

        mysql.connection.commit()
        cursor.close()

    session.clear()
    flash('You are logged out', 'info')
    return redirect(url_for('login'))


@app.route('/')
@app.route('/dashboard')
def dashboard():
    if not session.get('loggedin'):
        return redirect(url_for('login'))

    q_area = request.args.get('area', '')
    q_gender = request.args.get('gender', '')
    q_room_type = request.args.get('room_type', '')
    q_max_people = request.args.get('max_people', '')
    q_min_rent = request.args.get('min_rent', '')
    q_max_rent = request.args.get('max_rent', '')
    sort_by = request.args.get('sort_by', 'created_at_desc')

    pending_requests_count = 0 

    cursor = mysql.connection.cursor() 

    sql = """
        SELECT r.id, r.room_image, r.address, r.description, r.rent, r.room_type, r.num_rooms, 
               r.preferred_gender, r.water_bill_included, r.light_bill_included, u.username AS owner_username, 
               r.max_people,
               IFNULL(SUM(b.num_people_booking), 0) AS occupied_people,
               -- FIX: Add subquery to calculate AVG(rating) for the room
               (SELECT AVG(rating) FROM feedback WHERE room_id = r.id) AS avg_rating 
        FROM rooms r 
        LEFT JOIN users u ON r.owner_id = u.id 
        LEFT JOIN bookings b ON r.id = b.room_id AND b.request_status IN ('verified')
        WHERE 1=1
    """
    params = []
    sql += " AND r.is_hidden = 0"
    if q_area:
        sql += " AND r.address LIKE %s" 
        params.append(f"%{q_area}%")
    if q_gender:
        sql += " AND (r.preferred_gender = %s OR r.preferred_gender = 'Any')"
        params.append(q_gender)
    if q_room_type:
        sql += " AND r.room_type = %s"
        params.append(q_room_type)
    if q_max_people:
        sql += " AND r.max_people >= %s" 
        params.append(q_max_people)
    if q_min_rent:
        sql += " AND r.rent >= %s"
        params.append(q_min_rent)
    if q_max_rent:
        sql += " AND r.rent <= %s"
        params.append(q_max_rent)

    sql += " GROUP BY r.id"    

    if sort_by == 'rent_asc':
        sql += " ORDER BY r.rent ASC"
    elif sort_by == 'rent_desc':
        sql += " ORDER BY r.rent DESC"
    else:
        sql += " ORDER BY r.created_at DESC"

    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall() 

    rooms = []
    for row in rows:
        img_b64 = None
        if row[1]:
            try:
                img_b64 = base64.b64encode(row[1]).decode('utf-8')
            except Exception:
                img_b64 = None

        max_capacity = row[11]
        occupied_people = row[12]
        avg_rating = row[13]

        rooms.append({
            'id': row[0],
            'img_b64': img_b64,
            'address': row[2],
            'description': row[3],
            'rent': str(row[4]),
            'room_type': row[5],
            'num_rooms': row[6],
            'preferred_gender': row[7],
            'water_bill_included': row[8],
            'light_bill_included': row[9],
            'owner_username': row[10],
            'max_people': max_capacity,
            'occupied_people': occupied_people,
            'available_space': max_capacity - occupied_people,
            'avg_rating': avg_rating 
        })

    if session.get('is_owner'):
        cursor.execute("""
            SELECT COUNT(b.id) AS pending_count
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            WHERE r.owner_id = %s AND b.request_status = 'pending'
        """, (session.get('user_id'),))

        result = cursor.fetchone() 
        if result:
            pending_requests_count = result[0]

    cursor.close()    

    show_feedback = False
    cur_dict = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur_dict.execute("SELECT feedback FROM users WHERE id = %s", (session.get('user_id'),))
    u = cur_dict.fetchone()
    cur_dict.close()

    if u and u.get('feedback', 0) and u.get('feedback', 0) >= 5:
        show_feedback = True

    return render_template('dashboard.html', 
                           rooms=rooms, 
                           show_feedback=show_feedback,
                           pending_requests_count=pending_requests_count)


@app.route('/toggle_visibility/<int:room_id>', methods=['POST'])
def toggle_visibility(room_id):
    if not session.get('loggedin') or not session.get('is_owner'):
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    owner_id = session.get('user_id')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT is_hidden FROM rooms WHERE id = %s AND owner_id = %s", (room_id, owner_id))
    room = cursor.fetchone()

    if not room:
        flash('Room not found or access denied.', 'danger')
        cursor.close()
        return redirect(url_for('my_rooms'))

    new_status = 1 if room['is_hidden'] == 0 else 0    
    status_text = "HIDDEN" if new_status == 1 else "VISIBLE"

    cursor.execute("UPDATE rooms SET is_hidden = %s WHERE id = %s", (new_status, room_id))
    mysql.connection.commit()
    cursor.close()

    flash(f'Room listing visibility set to {status_text}.', 'info')
    return redirect(url_for('my_rooms'))

@app.route('/add_room', methods=['GET','POST'])
def add_room():
    if not session.get('loggedin') or not session.get('is_owner'):
        flash('Only owners can add rooms', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        owner_id = session.get('user_id')
        f = request.files.get('room_image')
        img = f.read() if f else None
        address = request.form.get('address')
        description = request.form.get('description')
        room_type = request.form.get('room_type') 
        num_rooms = int(request.form.get('num_rooms') or 1)
        rent = float(request.form.get('rent') or 0)
        light_bill_included = 1 if request.form.get('light_bill_included') else 0
        water_bill_included = 1 if request.form.get('water_bill_included') else 0
        preferred_gender = request.form.get('preferred_gender') or 'Any'
        area = request.form.get('area') or '' 
        max_people = int(request.form.get('max_people') or 1) 

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO rooms (owner_id, room_image, address, description, rent, light_bill_included, water_bill_included, room_type, num_rooms, preferred_gender, area, max_people)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (owner_id, img, address, description, rent, light_bill_included, water_bill_included, room_type, num_rooms, preferred_gender, area, max_people))
        mysql.connection.commit()
        cursor.close()
        flash('Room added successfully!', 'success')
        return redirect(url_for('my_rooms'))
    return render_template('add_room.html')

@app.route('/view_documents/<int:booking_id>')
def view_documents(booking_id):
    if not session.get('loggedin') or not session.get('is_owner'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    owner_id = session.get('user_id')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT d.document_file, d.document_name
        FROM booking_documents d
        JOIN bookings b ON d.booking_id = b.id
        JOIN rooms r ON b.room_id = r.id
        WHERE b.id = %s 
        AND r.owner_id = %s 
        AND b.request_status = 'verified'
    """, (booking_id, owner_id))

    documents = cursor.fetchall()
    cursor.close()

    if not documents:
        flash('No verified documents found for this booking, or access denied.', 'danger')
        return redirect(url_for('owner_requests'))


    doc_html = f"<h2>Documents for Booking #{booking_id}</h2>"
    doc_html += "<p>Click to download or view the document in your browser.</p>"
    doc_html += "<table border='1' cellpadding='10'><tr><th>Name</th><th>Action</th></tr>"


    all_links = []

    for i, doc in enumerate(documents):

        doc_html += f"<tr><td>{doc['document_name']}</td><td><img src='data:image/jpeg;base64,{base64.b64encode(doc['document_file']).decode('utf-8')}' style='max-width: 200px; height: auto;'></td></tr>"


    doc_html += "</table>"


    documents_b64 = []
    for doc in documents:
        documents_b64.append({
            'name': doc['document_name'],
            'b64_data': base64.b64encode(doc['document_file']).decode('utf-8')
        })

    return render_template('document_viewer.html', documents=documents_b64, booking_id=booking_id)

@app.route('/my_rooms')
def my_rooms():
    if not session.get('loggedin') or not session.get('is_owner'):
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    owner_id = session.get('user_id')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT r.id, r.room_image, r.address, r.rent, r.room_type, r.num_rooms, r.max_people, r.is_hidden,
               IFNULL(SUM(b.num_people_booking), 0) AS occupied_people, 
               (SELECT COUNT(id) FROM feedback WHERE room_id = r.id) AS total_feedback,
               (SELECT AVG(rating) FROM feedback WHERE room_id = r.id) AS avg_rating
        FROM rooms r 
        LEFT JOIN bookings b ON r.id = b.room_id AND b.request_status IN ('verified')
        WHERE r.owner_id = %s 
        GROUP BY r.id 
        ORDER BY r.created_at DESC""", (owner_id,))
    rooms = cursor.fetchall()
    cursor.close()

    for room in rooms:
        room['img_b64'] = base64.b64encode(room['room_image']).decode('utf-8') if room['room_image'] else None
        room['avg_rating'] = f"{room['avg_rating']:.1f}" if room['avg_rating'] is not None else 'N/A'

        room['available_space'] = room['max_people'] - room['occupied_people']

    return render_template('my_rooms.html', rooms=rooms)

@app.route('/edit_room/<int:room_id>', methods=['GET','POST'])
def edit_room(room_id):
    if not session.get('loggedin') or not session.get('is_owner'):
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    owner_id = session.get('user_id')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM rooms WHERE id = %s AND owner_id = %s", (room_id, owner_id))
    room = cursor.fetchone()

    if not room:
        flash('Room not found or you do not own it.', 'danger')
        cursor.close()
        return redirect(url_for('my_rooms'))

    if request.method == 'POST':
        f = request.files.get('room_image')
        img = f.read() if f else None 
        address = request.form.get('address')
        description = request.form.get('description')
        room_type = request.form.get('room_type') 
        num_rooms = int(request.form.get('num_rooms') or 1)
        rent = float(request.form.get('rent') or 0)
        light_bill_included = 1 if request.form.get('light_bill_included') else 0
        water_bill_included = 1 if request.form.get('water_bill_included') else 0
        preferred_gender = request.form.get('preferred_gender') or 'Any'
        area = request.form.get('area') or ''
        max_people = int(request.form.get('max_people') or 1)

        sql_update = """UPDATE rooms SET 
            address=%s, description=%s, rent=%s, light_bill_included=%s, water_bill_included=%s, 
            room_type=%s, num_rooms=%s, preferred_gender=%s, area=%s, max_people=%s
            WHERE id=%s AND owner_id=%s
        """
        params_update = [address, description, rent, light_bill_included, water_bill_included, 
                         room_type, num_rooms, preferred_gender, area, max_people, room_id, owner_id]

        if img:
            sql_update = sql_update.replace('SET', 'SET room_image=%s,', 1)
            params_update.insert(0, img)

        cursor.execute(sql_update, tuple(params_update))
        mysql.connection.commit()
        cursor.close()
        flash('Room updated successfully!', 'success')
        return redirect(url_for('my_rooms'))

    room['img_b64'] = base64.b64encode(room['room_image']).decode('utf-8') if room['room_image'] else None
    cursor.close()
    return render_template('edit_room.html', room=room)

@app.route('/delete_room/<int:room_id>', methods=['POST'])
def delete_room(room_id):
    if not session.get('loggedin') or not session.get('is_owner'):
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    owner_id = session.get('user_id')
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM rooms WHERE id = %s AND owner_id = %s", (room_id, owner_id))
    mysql.connection.commit()
    cursor.close()
    flash('Room listing deleted.', 'info')
    return redirect(url_for('my_rooms'))



@app.route('/book_room/<int:room_id>', methods=['POST'])
def book_room(room_id):
    if not session.get('loggedin') or session.get('is_owner'):
        flash('Only registered students can send a booking request.', 'danger')
        return redirect(url_for('room_detail', room_id=room_id))

    user_id = session.get('user_id')
    num_people = int(request.form.get('num_people', 1)) 

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT r.max_people, IFNULL(SUM(b.num_people_booking), 0) AS occupied
        FROM rooms r
        LEFT JOIN bookings b ON r.id = b.room_id AND b.request_status IN ('approved', 'verified')
        WHERE r.id = %s
        GROUP BY r.id
    """, (room_id,))
    room_data = cursor.fetchone()

    if not room_data:
        flash('Room not found or no capacity data.', 'danger')
        cursor.close()
        return redirect(url_for('dashboard'))

    available_space = room_data['max_people'] - room_data['occupied']

    if available_space < num_people:
        flash(f'Cannot request for {num_people} people. Only {available_space} space(s) available.', 'warning')
        cursor.close()
        return redirect(url_for('room_detail', room_id=room_id))

    cursor.execute("SELECT id FROM bookings WHERE user_id = %s AND room_id = %s AND request_status IN ('pending', 'approved')", (user_id, room_id))
    if cursor.fetchone():
        flash('You already have a pending or approved request for this room.', 'info')
        cursor.close()
        return redirect(url_for('room_detail', room_id=room_id))

    cursor.execute("""
        INSERT INTO bookings (room_id, user_id, num_people_booking, request_status)
        VALUES (%s, %s, %s, 'pending')
    """, (room_id, user_id, num_people))

    mysql.connection.commit()
    cursor.close()

    flash(f'Booking request sent to the owner for {num_people} person(s). Awaiting owner approval.', 'success')
    return redirect(url_for('room_detail', room_id=room_id))


@app.route('/room/<int:room_id>')
def room_detail(room_id):
    if not session.get('loggedin'):
        flash('Please log in to view room details.', 'warning')
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT r.*, u.username as owner_username, u.mobile as owner_mobile, u.email as owner_email,
               IFNULL(SUM(b.num_people_booking), 0) AS occupied_people
        FROM rooms r 
        LEFT JOIN users u ON r.owner_id = u.id
        -- FIX: Only count people from 'verified' bookings
        LEFT JOIN bookings b ON r.id = b.room_id AND b.request_status IN ('verified')
        WHERE r.id = %s
        GROUP BY r.id, u.id
    """, (room_id,))   
    room = cursor.fetchone()

    if not room:
        flash('Room not found', 'danger')
        cursor.close()
        return redirect(url_for('dashboard'))

    room['available_space'] = room['max_people'] - room['occupied_people']

    user_booking = None
    if not session.get('is_owner'):
        user_id = session.get('user_id')
    cursor.execute("""
            SELECT id, request_status, num_people_booking 
            FROM bookings
            WHERE user_id = %s AND room_id = %s AND request_status NOT IN ('rejected')
            ORDER BY booked_at DESC LIMIT 1
        """, (user_id, room_id))
    user_booking = cursor.fetchone()
    cursor.execute("""
        SELECT f.rating, f.comment, u.username 
        FROM feedback f 
        JOIN users u ON f.user_id = u.id 
        WHERE f.room_id = %s 
        ORDER BY f.created_at DESC""", (room_id,))
    feedbacks = cursor.fetchall()

    cursor.execute("SELECT AVG(rating) as avg_rating FROM feedback WHERE room_id = %s", (room_id,))
    avg_rating = cursor.fetchone()['avg_rating']
    cursor.close()

    img_b64 = base64.b64encode(room['room_image']).decode('utf-8') if room['room_image'] else None

    room['avg_rating'] = f"{avg_rating:.1f}" if avg_rating is not None else 'N/A'

    return render_template('room_detail.html', 
                           room=room, 
                           img_b64=img_b64, 
                           feedbacks=feedbacks, 
                           user_booking=user_booking)

@app.route('/submit_room_feedback/<int:room_id>', methods=['POST'])
def submit_room_feedback(room_id):
    if not session.get('loggedin'):
        return redirect(url_for('login'))
        
    user_id = session.get('user_id')
    
    try:
        scores = [int(request.form.get(f'q{i}')) for i in range(1, 11)]
    except (TypeError, ValueError):
        flash('Please answer all 10 satisfaction questions.', 'danger')
        return redirect(url_for('room_detail', room_id=room_id))

    comment = request.form.get('comment')
    
    overall_rating = sum(scores) / len(scores)
    
    cursor = mysql.connection.cursor()
    
    cursor.execute("""
        INSERT INTO room_reviews (room_id, user_id, q1_clean, q2_accuracy, q3_amenities, 
        q4_location, q5_value, q6_owner, q7_noise, q8_ventilation, q9_maintenance, q10_overall, comment) 
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
        (room_id, user_id, *scores, comment))
        
    cursor.execute("INSERT INTO feedback (user_id, room_id, rating, comment) VALUES (%s,%s,%s,%s)", 
                   (user_id, room_id, overall_rating, comment))
                   
    mysql.connection.commit()
    cursor.close()
    
    flash(f'Review submitted! Your calculated rating is {overall_rating:.1f}/5', 'success')
    return redirect(url_for('room_detail', room_id=room_id))


@app.route('/owner_requests')
def owner_requests():

    owner_id = session.get('user_id')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT b.id, r.address, r.room_type, r.max_people, b.num_people_booking, b.request_status,
               u.username AS requester_username, u.email AS requester_email, u.mobile AS requester_mobile,
               (SELECT COUNT(d.id) FROM booking_documents d WHERE d.booking_id = b.id) AS uploaded_docs_count
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        JOIN users u ON b.user_id = u.id
        WHERE r.owner_id = %s
        ORDER BY b.booked_at DESC
    """, (owner_id,))
    requests = cursor.fetchall()
    cursor.close()

    return render_template('owner_requests.html', requests=requests)

@app.route('/respond_request/<int:booking_id>/<string:action>', methods=['POST'])
def respond_request(booking_id, action):
    if not session.get('loggedin') or not session.get('is_owner'):
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    if action not in ['approve', 'reject']:
        flash('Invalid action.', 'danger')
        return redirect(url_for('owner_requests'))

    new_status = 'approved' if action == 'approve' else 'rejected'
    owner_id = session.get('user_id')

    cursor = mysql.connection.cursor()

    cursor.execute("""
        UPDATE bookings b
        JOIN rooms r ON b.room_id = r.id
        SET b.request_status = %s, b.owner_response_at = NOW()
        WHERE b.id = %s AND r.owner_id = %s AND b.request_status = 'pending'
    """, (new_status, booking_id, owner_id))

    mysql.connection.commit()

    if cursor.rowcount > 0:
        flash(f'Request {new_status} successfully.', 'success')
    else:
        flash('Request not found, already processed, or access denied.', 'danger')

    cursor.close()
    return redirect(url_for('owner_requests'))



@app.route('/verify_booking/<int:booking_id>', methods=['GET', 'POST'])
def verify_booking(booking_id):
    if not session.get('loggedin') or session.get('is_owner'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    user_id = session.get('user_id')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT b.id, b.room_id, r.address, b.request_status, b.num_people_booking
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        WHERE b.id = %s AND b.user_id = %s AND b.request_status = 'approved'
    """, (booking_id, user_id))
    booking = cursor.fetchone()

    if not booking:
        flash('Booking not found or not yet approved by the owner.', 'danger')
        cursor.close()
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        required_docs = booking['num_people_booking']
        uploaded_count = 0

        for i in range(1, required_docs + 1):
            file_key = f'doc_{i}'
            name_key = f'name_{i}'

            f = request.files.get(file_key)
            user_name = request.form.get(name_key)

            if f and f.filename and user_name:
                cursor.execute("""
                    INSERT INTO booking_documents (booking_id, user_id_fk, document_name, document_file)
                    VALUES (%s, %s, %s, %s)
                """, (booking_id, user_id, f'{user_name} (Aadhaar)', f.read()))
                uploaded_count += 1

        if uploaded_count == required_docs:
            cursor.execute("""
                UPDATE bookings
                SET request_status = 'verified'
                WHERE id = %s
            """, (booking_id,))

            mysql.connection.commit()
            flash(f'Verification successful! {uploaded_count} documents uploaded. Your booking is confirmed.', 'success')
            cursor.close()
            return redirect(url_for('room_detail', room_id=booking['room_id']))
        else:
            flash(f'Error: You must upload {required_docs} documents (one per person). Only {uploaded_count} found.', 'danger')
            cursor.close()
            return redirect(url_for('verify_booking', booking_id=booking_id))

    cursor.close()
    return render_template('verify_booking.html', booking=booking)


@app.route('/admin', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        uname = request.form.get('username')
        pwd = request.form.get('password')
        if uname == ADMIN_USERNAME and pwd == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT id, name, username, email, mobile, city, owner, gender, created_at FROM users")
    users = cur.fetchall()

    cur.execute("SELECT f.*, u.username, r.address FROM feedback f LEFT JOIN users u ON f.user_id = u.id LEFT JOIN rooms r ON f.room_id = r.id ORDER BY f.created_at DESC")
    feedbacks = cur.fetchall()

    cur.execute("SELECT COUNT(*) AS total_users, SUM(CASE WHEN owner = '1' THEN 1 ELSE 0 END) AS total_owners, SUM(CASE WHEN owner = '0' THEN 1 ELSE 0 END) AS total_students FROM users")
    user_agg = cur.fetchone()

    cur.execute("SELECT COUNT(*) AS total_rooms, AVG(rent) AS avg_rent, AVG(num_rooms) AS avg_num_rooms FROM rooms")
    room_agg = cur.fetchone()

    cur.execute("SELECT AVG(rating) as avg_rating, COUNT(*) as total_feedback FROM feedback WHERE room_id IS NULL")
    app_feedback_agg = cur.fetchone()

    cur.execute("SELECT SUM(total_time_spent) AS total_seconds FROM users")
    time_agg = cur.fetchone()

    total_users = user_agg['total_users']

    total_seconds_spent = time_agg['total_seconds'] if time_agg and time_agg['total_seconds'] else 0

    if total_users > 0:
        avg_seconds_spent = total_seconds_spent / total_users
    else:
        avg_seconds_spent = 0

    cur.close()

    summary = {
        'total_users': user_agg['total_users'],
        'total_owners': user_agg['total_owners'],
        'total_students': user_agg['total_students'],
        'total_rooms': room_agg['total_rooms'],
        'avg_rent': f"{room_agg['avg_rent']:.2f}" if room_agg['avg_rent'] else 'N/A',
        'avg_app_rating': f"{app_feedback_agg['avg_rating']:.1f}" if app_feedback_agg['avg_rating'] else 'N/A',
        'total_seconds_spent': total_seconds_spent,
        'total_time_spent_formatted': format_seconds(total_seconds_spent),
        'avg_time_spent_formatted': format_seconds(avg_seconds_spent),
    }

    return render_template('admin_dashboard.html', users=users, feedbacks=feedbacks, summary=summary)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,)) 
    mysql.connection.commit()
    cur.close()
    flash('User deleted', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/<int:user_id>')
def admin_user_detail(user_id):
    if not session.get('admin_logged_in'):
        flash('Admin access required.', 'danger')
        return redirect(url_for('admin_login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, name, username, email, mobile, city, owner, gender, created_at, last_seen, total_time_spent FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.execute("""
        SELECT id, name, username, email, mobile, city, owner, gender, created_at, last_seen, total_time_spent 
        FROM users 
        WHERE id = %s
    """, (user_id,))
    user = cur.fetchone()

    cur.close()
    total_time_formatted = format_seconds(user['total_time_spent'])
    time_diff = None
    if time_diff:
        last_activity_ago = format_seconds(time_diff.total_seconds())
    else:
        last_activity_ago = "N/A"
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_dashboard'))

    status = "Offline"
    time_diff = None

    if user['last_seen']:
        now = datetime.datetime.now()

        last_seen_dt = user['last_seen']

        if isinstance(last_seen_dt, datetime.datetime):
            time_diff = now - last_seen_dt

            if time_diff.total_seconds() > 120: 
                status = "Online"
            else:
                status = "Inactive"             

    return render_template('admin_user_detail.html', 
                           user=user, 
                           status=status, 
                           total_time_formatted=total_time_formatted,
                           last_activity_ago=last_activity_ago)     

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)

    flash('Admin logged out successfully.', 'info')
    return redirect(url_for('admin_login'))
if __name__ == '__main__':
    app.run(debug=True)