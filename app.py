import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'iitm_mad1_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin, student, company

class StudentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    full_name = db.Column(db.String(100))
    cgpa = db.Column(db.Float)
    branch = db.Column(db.String(50))

class CompanyProfile(db.Column):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    company_name = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Pending') # Pending, Approved

class PlacementDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_profile.id'))
    job_role = db.Column(db.String(100))
    salary = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Pending')

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    drive_id = db.Column(db.Integer, db.ForeignKey('placement_drive.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/')
def index():
    """Professional Landing Page"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_user_to_dashboard(current_user)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.password == password: # In production, use password hashing!
            login_user(user)
            return redirect_user_to_dashboard(user)
        else:
            flash("Invalid credentials. Please try again.")
            
    return render_template('login.html')

def redirect_user_to_dashboard(user):
    if user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif user.role == 'company':
        return redirect(url_for('company_dashboard'))
    return redirect(url_for('student_dashboard'))

# --- DASHBOARDS ---

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    # SEARCH LOGIC
    search_query = request.args.get('q', '')
    if search_query:
        students = StudentProfile.query.filter(StudentProfile.full_name.contains(search_query)).all()
    else:
        students = StudentProfile.query.all()

    stats = {
        'students': User.query.filter_by(role='student').count(),
        'companies': CompanyProfile.query.count(),
        'drives': PlacementDrive.query.count()
    }
    pending_companies = CompanyProfile.query.filter_by(status='Pending').all()
    return render_template('admin_dashboard.html', stats=stats, pending_companies=pending_companies, students=students)

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    drives = PlacementDrive.query.filter_by(status='Approved').all()
    return render_template('student_dashboard.html', profile=profile, drives=drives)

@app.route('/company/dashboard')
@login_required
def company_dashboard():
    profile = CompanyProfile.query.filter_by(user_id=current_user.id).first()
    my_drives = PlacementDrive.query.filter_by(company_id=profile.id).all()
    return render_template('company_dashboard.html', profile=profile, drives=my_drives)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- DATABASE INITIALIZATION ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create a default Admin if one doesn't exist
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='password123', role='admin')
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: admin / password123")
            
    app.run(debug=True)