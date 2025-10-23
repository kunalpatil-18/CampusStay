from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from flask_mysqldb import MySQL
import base64

app = Flask(__name__)
app.secret_key = 'utkarsh_secret_key'

# -------------------- Database Configuration --------------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Kunal@2006'
app.config['MYSQL_DB'] = 'semproject'

mysql = MySQL(app)

# -------------------- Test DB --------------------
@app.route('/test-db')
def test_db():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT DATABASE();")
        db_name = cur.fetchone()
        cur.close()
        return f"Connected to database: {db_name[0]}"
    except Exception as e:
        return f"Database connection failed: {str(e)}"

# -------------------- Login --------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM user WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()

        if user:
            if password == user[5]:
                # ✅ Save login info in session
                session['username'] = user[2]  # or use user[1] depending on your table order
                session['is_owner'] = bool(user[6])

                # Redirect based on role
                if user[6] == 1:
                    return redirect(url_for('DashboardOwner'))
                else:
                    return redirect(url_for('DashboardStudent'))
            else:
                flash('Invalid password.', 'danger')
        else:
            flash('User not found.', 'danger')

    return render_template('login.html')


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        mobile = request.form['mobile']
        city = request.form['city']
        is_owner = 1 if 'isOwner' in request.form else 0
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO user (name, username, email, mobile, city, owner, password)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, username, email, mobile, city, is_owner, password))
        mysql.connection.commit()
        cur.close()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')



# -------------------- Add Room --------------------
@app.route('/add_room', methods=['GET', 'POST'])
def add_room():
    if request.method == 'POST':
        file = request.files.get('room_image')
        address = request.form.get('address')
        city = request.form.get('city')
        description = request.form.get('description')
        rent = request.form.get('rent')
        room_type = request.form.get('room_type')
        num_rooms = request.form.get('num_rooms')
        light_bill = 1 if 'light_bill' in request.form else 0
        water_bill = 1 if 'water_bill' in request.form else 0

        encoded_image = None
        mime_type = None

        if file and file.filename != '':
            mime_type = file.content_type
            encoded_image = base64.b64encode(file.read()).decode('utf-8')

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO rooms (room_image, mime_type, address, city, description, rent, room_type, num_rooms, light_bill, water_bill)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (encoded_image, mime_type, address, city, description, rent, room_type, num_rooms, light_bill, water_bill))

        mysql.connection.commit()
        cur.close()

        flash('Room added successfully!', 'success')
        return redirect(url_for('DashboardOwner'))

    return render_template('AddRoomForm.html')

# -------------------- Owner Dashboard --------------------
@app.route('/OwnerDashboard')
def DashboardOwner():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, room_image, mime_type, address, description, rent, room_type, num_rooms, city
        FROM rooms
    """)
    rooms = cur.fetchall()
    cur.close()

    rooms_data = []
    for room in rooms:
        rooms_data.append({
            'id': room[0],
            'image': room[1],
            'mime_type': room[2],
            'address': room[3],
            'description': room[4],
            'rent': room[5],
            'room_type': room[6],
            'num_rooms': room[7],
            'city': room[8]
        })

    # ✅ Debug print
    if rooms_data:
        print("ROOM IMAGE SAMPLE:", rooms_data[0]['mime_type'])
        if rooms_data[0]['image']:
            print("IMAGE DATA START:", rooms_data[0]['image'][:60])

    return render_template('DashboardOwner.html', rooms=rooms_data)

# -------------------- Student Dashboard --------------------
@app.route('/StudentDashboard')
def DashboardStudent():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, room_image, mime_type, address, description, rent, room_type, num_rooms, city
        FROM rooms
    """)
    rooms = cur.fetchall()
    cur.close()

    rooms_data = []
    for room in rooms:
        rooms_data.append({
            'id': room[0],
            'image': room[1],
            'mime_type': room[2],
            'address': room[3],
            'description': room[4],
            'rent': room[5],
            'room_type': room[6],
            'num_rooms': room[7],
            'city': room[8]
        })

    return render_template('DashboardStudent.html', rooms=rooms_data)


# -------------------- Filter --------------------
@app.route('/filter_rooms', methods=['GET'])
def filter_rooms():
    # Get filter inputs
    min_rent = request.args.get('min_rent', type=float)
    max_rent = request.args.get('max_rent', type=float)
    city = request.args.get('city')
    light_bill = request.args.get('light_bill')
    water_bill = request.args.get('water_bill')

    # Detect which dashboard triggered the filter (owner or student)
    dashboard_type = request.args.get('dashboard', 'owner')  # default to owner

    # Base query
    query = """
        SELECT id, room_image, mime_type, address, city, description, rent, room_type, num_rooms
        FROM rooms
        WHERE 1=1
    """
    params = []

    # Apply filters dynamically
    if min_rent:
        query += " AND rent >= %s"
        params.append(min_rent)
    if max_rent:
        query += " AND rent <= %s"
        params.append(max_rent)
    if city:
        query += " AND city LIKE %s"
        params.append(f"%{city}%")
    if light_bill:
        query += " AND light_bill = 1"
    if water_bill:
        query += " AND water_bill = 1"

    # Fetch filtered results
    cur = mysql.connection.cursor()
    cur.execute(query, tuple(params))
    rooms = cur.fetchall()
    cur.close()

    rooms_data = []
    for room in rooms:
        rooms_data.append({
            'id': room[0],
            'image': room[1],
            'mime_type': room[2],
            'address': room[3],
            'city': room[4],
            'description': room[5],
            'rent': room[6],
            'room_type': room[7],
            'num_rooms': room[8]
        })

    # Render correct dashboard template
    if dashboard_type == 'student':
        return render_template('DashboardStudent.html', rooms=rooms_data)
    else:
        return render_template('DashboardOwner.html', rooms=rooms_data)
    

# -------------------- Profile Page --------------------
@app.route('/profile')
def profile():
    # ✅ 1. Check if user is logged in
    if 'username' not in session:
        flash("Please log in to view your profile.", "warning")
        return redirect(url_for('login'))

    username = session['username']

    # ✅ 2. Fetch user info from DB
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT name, username, email, mobile, city, owner
        FROM user WHERE username = %s
    """, (username,))
    user = cur.fetchone()
    cur.close()

    if not user:
        flash("User not found!", "danger")
        session.clear()
        return redirect(url_for('login'))

    # ✅ 3. Prepare data for template
    user_data = {
        'name': user[0],
        'username': user[1],
        'email': user[2],
        'mobile': user[3],
        'city': user[4],
        'is_owner': bool(user[5]),
        'role': "Owner" if user[5] == 1 else "Student",
        'joined': "2025"
    }

    # (Optional extras)
    if user_data['is_owner']:
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM rooms WHERE city = %s", (user[4],))
        user_data['total_rooms'] = cur.fetchone()[0]
        user_data['rating'] = "4.9★"
        cur.close()
    else:
        user_data['bookings'] = 2
        user_data['favorites'] = 5
        user_data['reviews'] = 1

    # ✅ 4. Render page
    return render_template('profile.html', user=user_data)


# -------------------- My Listings & Browse --------------------
@app.route('/my_listings')
def my_listings():
    if 'username' not in session:
        return redirect(url_for('login'))
    return "<h2>My Listings Page (Owner)</h2>"

@app.route('/view_rooms')
def view_rooms():
    if 'username' not in session:
        return redirect(url_for('login'))
    return "<h2>Browse Rooms Page (Student)</h2>"


# -------------------- Logout --------------------
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))




   



# -------------------- Run App --------------------
if __name__ == '__main__':
    app.run(debug=True)
