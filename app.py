from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2 #pip install psycopg2 
import requests
import psycopg2.extras
import logging
from flask import send_from_directory, abort

import os
from flask import Flask, request, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'


DB_HOST = "localhost"
DB_NAME = "schooldb"
DB_USER = "postgres"
DB_PASS = "pass123"




# Function to establish database connection
def get_db_connection():
    return psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)


# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = generate_password_hash('admin123')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        abort(404, description="File not found")

@app.route('/', methods=['GET'])
def admin_login_page():
    return render_template('admin_login.html')

@app.route('/', methods=['POST'])
def admin_login():
    username = request.form['username']
    password = request.form['password']

    if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
        session['admin_logged_in'] = True
        return redirect(url_for('admin_home'))
    else:
        flash('Invalid credentials')
        return redirect(url_for('admin_login_page'))
    
    

@app.route('/logout', methods=['POST'])
def logout():
    # Clear the user session
    session.clear()
    flash('You have been logged out successfully.')
    return redirect(url_for('admin_login_page'))




    


@app.route('/user', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')

        if not username or not email:
            flash('Both username and email are required')
            return render_template('user_login.html')
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            try:
                cursor.execute('SELECT * FROM Users WHERE username = %s AND email = %s', (username, email))
                account = cursor.fetchone()
                
                if account:
                    session['user_id'] = account['user_id']
                    session['username'] = account['username']
                    session['email'] = account['email']
                    session['role'] = account['role']
                    session['full_name'] = account['full_name']

                    return redirect(url_for('user_home'))
                else:
                    flash('Invalid username or email')
                    
            except psycopg2.Error as e:
                flash('Database error: ' + str(e))
                logging.error('Database error occurred: %s', e)
            finally:
                cursor.close()

    return render_template('user_login.html')


@app.route('/enroll', methods=['POST'])
def enroll_student():
    course_id = request.form.get('course_id')
    student_id = request.form.get('student_id')

    if not course_id or not student_id:
        flash('Course ID and Student ID are required')
        return redirect(url_for('admin_home'))

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # Check if the course_id and student_id are valid
            cursor.execute('SELECT * FROM Courses WHERE course_id = %s', (course_id,))
            course = cursor.fetchone()

            cursor.execute('SELECT * FROM Users WHERE user_id = %s', (student_id,))
            student = cursor.fetchone()

            if not course:
                flash('Invalid course ID')
                return redirect(url_for('enrollment_form'))

            if not student:
                flash('Invalid student ID')
                return redirect(url_for('enrollment_form'))

            # Check if the enrollment already exists
            cursor.execute('SELECT * FROM Enrollments WHERE course_id = %s AND student_id = %s', (course_id, student_id))
            existing_enrollment = cursor.fetchone()

            if existing_enrollment:
                flash('Student is already enrolled in this course')
                return redirect(url_for('enrollment_form'))

            # Check if the course is full
            cursor.execute('SELECT COUNT(*) FROM Enrollments WHERE course_id = %s', (course_id,))
            enrollment_count = cursor.fetchone()[0]
            if enrollment_count >= 25:
                flash('Sorry, this course is full')
                return redirect(url_for('enrollment_form'))

            # Create and add the new enrollment record
            cursor.execute('INSERT INTO Enrollments (course_id, student_id, enrolled_at) VALUES (%s, %s, CURRENT_TIMESTAMP)', (course_id, student_id))
            conn.commit()

            flash('Student successfully enrolled')
            return render_template('user_home.html')

    except psycopg2.Error as e:
        flash('Error: ' + str(e))
        logging.error('Database error occurred: %s', e)
        return redirect(url_for('enrollment_form'))

@app.route('/enroll')
def enrollment_form():
    # Render your enrollment form here
    return render_template('enrollment_form.html')
    



@app.route('/admin/home', methods=['GET'])
def admin_home():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # Fetch courses
            cursor.execute('SELECT * FROM Courses')
            courses = cursor.fetchall()

            # Fetch users
            cursor.execute('SELECT * FROM Users')
            users = cursor.fetchall()

    except psycopg2.Error as e:
        flash('Error: ' + str(e))
        logging.error('Database error occurred: %s', e)
        return redirect(url_for('admin_home'))

    # Render the admin home page with fetched data
    return render_template('admin_home.html', courses=courses, users=users)


@app.route('/user/home', methods=['GET'])
def user_home():
    student_id = session.get('user_id')
    
    if not student_id:
        # Handle case where user_id is not found in session (e.g., redirect to login)
        return redirect(url_for('user_login'))
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # Fetch the enrollments for the specific student
            cursor.execute('''
                SELECT enrollments.enrollment_id, enrollments.course_id, Courses.course_name, enrollments.enrolled_at
                FROM enrollments
                JOIN Courses ON enrollments.course_id = Courses.course_id
                WHERE enrollments.student_id = %s
            ''', (student_id,))
            enrollments = cursor.fetchall()

            # Fetch all courses (if needed for other purposes on the user_home page)
            cursor.execute('SELECT * FROM Courses')
            courses = cursor.fetchall()

    except psycopg2.Error as e:
        flash('Error: ' + str(e))
        logging.error('Database error occurred: %s', e)
        return redirect(url_for('user_login'))

    # Render the user home page with fetched data
    return render_template('user_home.html', courses=courses, enrollments=enrollments)

@app.route('/coursespage')
def coursespage():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # Fetch all courses from the database
            cursor.execute("SELECT * FROM Courses")
            courses = cursor.fetchall()
            print("courses")
            print(courses)
            
            cursor.close()
        
        # Render the template with the courses data
        return render_template('courses.html', courses=courses)
    except Exception as e:
        print(f"Error fetching courses: {e}")
        return "Error fetching courses", 500

@app.route('/admin/add-course', methods=['POST'])
def add_course():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    data = request.form
    course_name = data.get('course_name')
    description = data.get('description')
    
    if not course_name:
        flash('Course name is required')
        return redirect(url_for('admin_home'))

    # Open database connection using a context manager
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            # Execute the insert statement
            cursor.execute(
                "INSERT INTO Courses (course_name, description, created_by) VALUES (%s, %s, %s)",
                (course_name, description, session.get('user_id'))
            )
            conn.commit()
            flash('Course inserted successfully!')
        except psycopg2.Error as e:
            conn.rollback()
            flash('Error adding course: ' + str(e))
            logging.error('Database error occurred: %s', e)
        finally:
            cursor.close()

    return redirect(url_for('admin_home'))

@app.route('/teachers')
def teachers():
    try:
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE role = 'teacher'")
            teachers = cursor.fetchall()
            print(teachers)
            cursor.close()
    except Exception as e:
        print(f"Error retrieving teachers: {e}")
        teachers = []  # Fallback to an empty list on error
    
    # Render the teachers template with the retrieved data
    return render_template('teachers.html', teachers=teachers)

@app.route('/admin/add-teacher', methods=['POST'])
def add_User():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))

    data = request.form
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')
    email = data.get('email')
    user_type = data.get('user_type')

    if not username or not password or not full_name or not email or not user_type:
        flash('All fields are required')
        return redirect(url_for('admin_home'))

    hashed_password = generate_password_hash(password)

    # Open database connection using a context manager
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cursor.execute(
                """
                INSERT INTO Users (username, password_hash, role, full_name, email)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (username, hashed_password, user_type, full_name, email)
            )
            conn.commit()
            flash('Teacher added successfully!')
        except psycopg2.Error as e:
            conn.rollback()
            flash('Error adding teacher: ' + str(e))
            logging.error('Database error occurred: %s', e)
        finally:
            cursor.close()

    return redirect(url_for('admin_home'))

@app.route('/admin/delete-course/<int:course_id>', methods=['GET'])
def delete_course(course_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            # Check if the course exists
            cursor.execute('SELECT * FROM Courses WHERE course_id = %s', (course_id,))
            course = cursor.fetchone()
            
            if not course:
                flash('Course not found')
                return redirect(url_for('admin_home'))

            # Delete the course
            cursor.execute('DELETE FROM Courses WHERE course_id = %s', (course_id,))
            conn.commit()
            flash('Course deleted successfully')
        except psycopg2.Error as e:
            conn.rollback()
            flash('Error deleting course: ' + str(e))
            logging.error('Database error occurred: %s', e)
        finally:
            cursor.close()

    return redirect(url_for('admin_home'))

@app.route('/admin/delete-user/<int:user_id>', methods=['GET'])
def delete_user(user_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            # Delete user from Users table
            cursor.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
            conn.commit()
            flash('User deleted successfully')
            print("user deleted successfully")
        except psycopg2.Error as e:
            conn.rollback()
            flash('Error deleting user: ' + str(e))
            print("error in deleting user")
            logging.error('Database error occurred: %s', e)
        finally:
            cursor.close()

    return redirect(url_for('admin_home'))

@app.route('/admin/get_user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
    if user:
        return jsonify(user)
    else:
        return jsonify({'error': 'User not found'}), 404


@app.route('/admin/update-user/<int:user_id>', methods=['GET', 'POST'])
def update_user(user_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        username = request.form.get('username')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        role = request.form.get('role')
        password = request.form.get('password')

        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                # If password is provided, hash it
                if password:
                    hashed_password = generate_password_hash(password)
                    cursor.execute("""
                        UPDATE Users
                        SET username = %s, full_name = %s, email = %s, role = %s, password_hash = %s
                        WHERE user_id = %s
                    """, (username, full_name, email, role, hashed_password, user_id))
                else:
                    cursor.execute("""
                        UPDATE Users
                        SET username = %s, full_name = %s, email = %s, role = %s
                        WHERE user_id = %s
                    """, (username, full_name, email, role, user_id))
                
                conn.commit()
                flash('User updated successfully')
                print("User update successfully")
                return redirect(url_for('admin_home'))
            except psycopg2.Error as e:
                conn.rollback()
                flash('Error updating user: ' + str(e))
                logging.error('Database error occurred: %s', e)
            finally:
                cursor.close()
    
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cursor.execute("SELECT * FROM Users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                flash('User not found')
                return redirect(url_for('admin_home'))
            
            return render_template('update_user.html', user=user)
        except psycopg2.Error as e:
            flash('Error fetching user data: ' + str(e))
            logging.error('Database error occurred: %s', e)
        finally:
            cursor.close()

@app.route('/admin/update-course/<int:course_id>', methods=['GET', 'POST'])
def update_course(course_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        course_name = request.form.get('course_name')
        description = request.form.get('description')

        if not course_name:
            flash('Course name is required')
            return redirect(url_for('update_course', course_id=course_id))

        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE Courses
                    SET course_name = %s, description = %s
                    WHERE course_id = %s
                """, (course_name, description, course_id))
                
                conn.commit()
                flash('Course updated successfully')
                return redirect(url_for('admin_home'))
            except psycopg2.Error as e:
                conn.rollback()
                flash('Error updating course: ' + str(e))
                logging.error('Database error occurred: %s', e)
            finally:
                cursor.close()

    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cursor.execute("SELECT * FROM Courses WHERE course_id = %s", (course_id,))
            course = cursor.fetchone()

            if not course:
                flash('Course not found')
                return redirect(url_for('admin_home'))

            return render_template('update_course.html', course=course)
        except psycopg2.Error as e:
            flash('Error fetching course data: ' + str(e))
            logging.error('Database error occurred: %s', e)
        finally:
            cursor.close()

@app.route('/viewclass/<int:course_id>', methods=['GET', 'POST'])
def view_class(course_id):
    user_id = session.get('user_id')  # Get the user ID from the session

    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            # Fetch enrollment data for the given course
            cursor.execute("""
                SELECT student_id
                FROM Enrollments
                WHERE course_id = %s
            """, (course_id,))
            enrollments = cursor.fetchall()

            if not enrollments:
                return "No enrollments found", 404

            # Prepare to fetch student data
            student_ids = [enrollment['student_id'] for enrollment in enrollments]

            # Fetch student details
            cursor.execute("""
                SELECT user_id, username, role, full_name
                FROM Users
                WHERE user_id = ANY(%s)
            """, (student_ids,))
            students = cursor.fetchall()

            # Prepare enrollment data
            enrollment_data = []
            for student in students:
                enrollment_data.append({
                    'user_id': student['user_id'],
                    'username': student['username'],
                    'role': student['role'],
                    'full_name': student['full_name']
                })

            # Fetch assignments for the course
            cursor.execute("""
                SELECT assignment_name, file_url, assignment_id
                FROM Assignments
                WHERE course_id = %s
            """, (course_id,))
            assignments = cursor.fetchall()

            # Fetch solutions for the current course and logged-in user
            cursor.execute("""
                SELECT a.assignment_name, s.marks
                FROM Solutions s
                JOIN Assignments a ON s.assignment_id = a.assignment_id
                WHERE s.user_id = %s
                AND s.course_id = %s
            """, (user_id, course_id))
            grades = cursor.fetchall()

            # Prepare data for solutions
            solutions = []
            if session.get('role') == 'teacher':
                cursor.execute("""
                    SELECT s.solution_id, s.solution_name, s.file_url, s.user_id, s.created_at, a.assignment_name
                    FROM Solutions s
                    JOIN Assignments a ON s.assignment_id = a.assignment_id
                    WHERE s.course_id = %s
                """, (course_id,))
                solutions = cursor.fetchall()

            # Render the template with both enrollment data, assignments, and grades
            return render_template('view_class.html', enrollment_data=enrollment_data, assignments=assignments, solutions=solutions, grades=grades, course_id=course_id)
        except psycopg2.Error as e:
            flash('Error fetching class data: ' + str(e))
            logging.error('Database error occurred: %s', e)
            return "Error fetching class data", 500
        finally:
            cursor.close()



app.config['UPLOAD_FOLDER'] = r'C:\Users\Laiba Ahmad\Desktop\django\New folder\uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def ensure_upload_folder_exists():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


@app.route('/upload_note/<int:course_id>', methods=['POST'])
def upload_note(course_id):
    ensure_upload_folder_exists()
    
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cursor.execute('SELECT * FROM Courses WHERE course_id = %s', (course_id,))
            course = cursor.fetchone()
            if not course:
                return f"Course with ID {course_id} does not exist.", 400

            teacher_id = session.get('user_id')
            cursor.execute('SELECT * FROM Users WHERE user_id = %s', (teacher_id,))
            teacher = cursor.fetchone()
            if not teacher:
                return f"Teacher with ID {teacher_id} does not exist.", 400

            if 'file' not in request.files:
                return "No file part", 400
            
            file = request.files['file']
            if file.filename == '':
                return "No selected file", 400

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    file.save(file_path)
                except Exception as e:
                    return f"Error saving file: {e}", 500
                 
                try:
                    cursor.execute("""
                        INSERT INTO Course_Notes (course_id, teacher_id, note, file_url)
                        VALUES (%s, %s, %s, %s)
                    """, (course_id, teacher_id, request.form.get('note_title'), filename))
                    conn.commit()
                except psycopg2.Error as e:
                    conn.rollback()
                    return f"Database error: {e}", 500
                
                return redirect(url_for('course_notes', course_id=course_id))
        except psycopg2.Error as e:
            return f"Database error: {e}", 500
        finally:
            cursor.close()

@app.route('/course_notes/<int:course_id>')
def course_notes(course_id):
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cursor.execute("""
                SELECT * FROM Course_Notes
                WHERE course_id = %s
            """, (course_id,))
            
            notes = cursor.fetchall()
            
            return render_template('view_class.html', course_notes=notes)
        except psycopg2.Error as e:
            flash(f"Database error: {e}")
            return "An error occurred while fetching course notes.", 500
        finally:
            cursor.close()

@app.route('/share_notes/<int:course_id>', methods=['GET'])
def share_notes(course_id):
    return render_template('share_notes.html', course_id=course_id)

@app.route('/add_assignment', methods=['POST'])
def add_assignment():
    if session.get('role') != 'teacher':
        flash("You are not authorized to add assignments.")
        return redirect(url_for('user_home'))

    course_id = request.form.get('course_id')
    assignment_name = request.form.get('assignment_name')

    if 'file' not in request.files:
        flash("No file part")
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash("No selected file")
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(file_path)
        except Exception as e:
            flash(f"Error saving file: {e}")
            return redirect(request.url)

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                print(f"Attempting to insert assignment with name: {assignment_name}, file: {filename}, course_id: {course_id}")
                cursor.execute("""
                    INSERT INTO assignments (assignment_name, file_url, course_id)
                    VALUES (%s, %s, %s)
                """, (assignment_name, filename, course_id))
                conn.commit()
                cursor.close()
                print("Assignment inserted successfully")
        except Exception as e:
            flash(f"Error saving assignment to database: {e}")
            return redirect(request.url)

        flash("Assignment added successfully!")
        return redirect(url_for('view_class', course_id=course_id))  # Redirect to view class page
    else:
        flash("Invalid file type")
        return redirect(request.url)
    
@app.route('/add_solution', methods=['POST'])
def add_solution():
    if 'user_id' not in session:
        flash("You need to be logged in to add a solution.")
        print("You need to be logged in to add a solution.")
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    course_id = request.form.get('course_id')
    assignment_id = request.form.get('assignment_id')
    solution_name = request.form.get('solution_name')

    # Validate and convert course_id and assignment_id to integers
    try:
        course_id = int(course_id) if course_id else None
        assignment_id = int(assignment_id) if assignment_id else None
    except ValueError:
        flash("Invalid course or assignment ID.")
        print("Invalid course or assignment ID.")
        return redirect(request.url)

    if not course_id or not assignment_id:
        flash("Course ID and Assignment ID are required.")
        print("Course ID and Assignment ID are required.")
        print("Course_id is ")
        print(course_id)
        print("Assignment_id is ")
        print(assignment_id)


        return redirect(request.url)

    if 'file' not in request.files:
        flash("No file part")
        print("No file part")
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash("No selected file")
        print("No selected file")

        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO solutions (solution_name, file_url, user_id, course_id, assignment_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (solution_name, filename, user_id, course_id, assignment_id))
                conn.commit()
                cursor.close()
        except Exception as e:
            flash(f"Error saving solution: {e}")
            print(f"Error saving solution: {e}")
            return redirect(request.url)

        flash("Solution added successfully!")
        print("Solution added successfully!")

        return redirect(url_for('view_class', course_id=course_id))
    else:
        flash("Invalid file type")
        print("Invalid file type")
        return redirect(request.url)
    
@app.route('/all_submissions/<int:course_id>/<int:assignment_id>')
def view_all_submissions(course_id, assignment_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        flash("You need to be logged in as a teacher to view submissions.")
        return redirect(url_for('user_login'))

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.solution_id, s.solution_name, s.file_url, s.user_id, s.created_at, a.assignment_name
                FROM solutions s
                JOIN assignments a ON s.assignment_id = a.assignment_id
                WHERE s.assignment_id = %s
            """, (assignment_id,))
            solutions = cursor.fetchall()
            print(solutions)
            cursor.close()
    except Exception as e:
        flash(f"Error retrieving submissions: {e}")
        return redirect(url_for('view_class', course_id=course_id))

    return render_template('allsubmissions.html', solutions=solutions, course_id=course_id)

@app.route('/mark_assignment', methods=['POST'])
def mark_assignment():
    solution_id = request.form.get('solution_id')
    marks = request.form.get('marks')

    if not solution_id or not marks:
        flash('Missing solution ID or marks.')
        print('Missing solution ID or marks.')
        return redirect(url_for('user_home'))  # Adjust URL as needed

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Example query to update marks
            cursor.execute("""
                UPDATE solutions
                SET marks = %s
                WHERE solution_id = %s
            """, (marks, solution_id))
            conn.commit()
            cursor.close()

        flash('Marks updated successfully.')
        print('Marks updated successfully.')
    except Exception as e:
        flash(f"Error updating marks: {e}")
        print(f"Error updating marks: {e}")

    return redirect(url_for('user_home'))

@app.route('/students')
def students():
    """Fetches all students from the database and renders them on a template."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()  # Fetch rows as dictionaries
            cursor.execute("SELECT * FROM Users WHERE role = 'student'")
            students = cursor.fetchall()
            cursor.close()
            print(students)
        return render_template('students.html', students=students)
    
    except psycopg2.Error as e:
        flash(f"Error fetching students: {e}")
        return render_template('class.html', students=[])
    
if __name__ == '_main_':
    app.run(debug=True)