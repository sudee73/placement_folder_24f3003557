from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, User, CompanyProfile, StudentProfile, PlacementDrive, Application
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement.db'
app.config['SECRET_KEY'] = 'abc_pqr_123' # Your sponsor-themed key

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database and Admin user automatically
with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='admin').first():
        admin = User(username='admin', password='adminpassword', role='admin')
        db.session.add(admin)
        db.session.commit()
        print("Admin user created!")


@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            # For Companies: Check if they are approved before letting them in
            if user.role == 'company':
                profile = CompanyProfile.query.filter_by(user_id=user.id).first()
                if profile.status != 'Approved':
                    flash("Your company account is pending Admin approval.")
                    return redirect(url_for('index'))

            login_user(user)
            flash(f"Logged in as {username}")

            # REDIRECTION LOGIC
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'company':
                return redirect(url_for('company_dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student_dashboard'))
        else:
            flash("Invalid username or password.")
            
    return render_template('login.html')

# Placeholder routes so the redirects don't fail
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        flash("Unauthorized!")
        return redirect(url_for('index'))
    
    # Requirement: Students can view approved placement drives
    available_drives = PlacementDrive.query.filter_by(status='Approved').all()
    
    # Requirement: Students can view their application status and history
    my_applications = Application.query.filter_by(student_id=current_user.id).all()
    
    # We pass drive_ids to the template to check if student already applied
    applied_drive_ids = [app.drive_id for app in my_applications]
    
    return render_template('student_dashboard.html', 
                           drives=available_drives, 
                           my_apps=my_applications,
                           applied_ids=applied_drive_ids)

@app.route('/apply/<int:drive_id>', methods=['POST'])
@login_required
def apply_to_drive(drive_id):
    if current_user.role != 'student':
        return redirect(url_for('index'))
    
    # Core Requirement: Prevent multiple applications for the same drive
    existing_app = Application.query.filter_by(student_id=current_user.id, drive_id=drive_id).first()
    
    if existing_app:
        flash("You have already applied for this drive!")
    else:
        new_app = Application(
            student_id=current_user.id,
            drive_id=drive_id,
            status='Applied'
        )
        db.session.add(new_app)
        db.session.commit()
        flash("Application submitted successfully!")
        
    return redirect(url_for('student_dashboard'))

@app.route('/company/dashboard')
@login_required
def company_dashboard():
    if current_user.role != 'company':
        flash("Unauthorized access!")
        return redirect(url_for('index'))
    
    # Get the company profile for the logged-in user
    profile = CompanyProfile.query.filter_by(user_id=current_user.id).first()
    
    # Fetch drives created by this company
    drives = PlacementDrive.query.filter_by(company_id=profile.id).all()
    
    return render_template('company_dashboard.html', profile=profile, drives=drives)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    # Get the search query from the URL (e.g., /admin/dashboard?q=Sudeep)
    search_query = request.args.get('q', '')
    
    if search_query:
        # Filter students by name
        students = StudentProfile.query.filter(StudentProfile.full_name.contains(search_query)).all()
    else:
        students = StudentProfile.query.all()

    stats = {
        'students': User.query.filter_by(role='student').count(),
        'companies': CompanyProfile.query.count(),
        'drives': PlacementDrive.query.count(),
        'applications': Application.query.count()
    }
    pending_companies = CompanyProfile.query.filter_by(status='Pending').all()
    
    return render_template('admin_dashboard.html', stats=stats, pending_companies=pending_companies, students=students)
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register_student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash("Username already taken!")
            return redirect(url_for('register_student'))
        
        new_user = User(username=username, password=password, role='student')
        db.session.add(new_user)
        db.session.commit()
        
        new_profile = StudentProfile(user_id=new_user.id, full_name=full_name)
        db.session.add(new_profile)
        db.session.commit()
        
        flash("Student registered successfully! Please login.")
        return redirect(url_for('index'))
    return render_template('register_student.html')

@app.route('/register_company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        company_name = request.form.get('company_name')
        website = request.form.get('website')
        
        new_user = User(username=username, password=password, role='company')
        db.session.add(new_user)
        db.session.commit()
        
        new_profile = CompanyProfile(user_id=new_user.id, company_name=company_name, website=website, status='Pending')
        db.session.add(new_profile)
        db.session.commit()
        
        flash("Registration submitted! Wait for Admin approval.")
        return redirect(url_for('index'))
    return render_template('register_company.html')

@app.route('/admin/approve_company/<int:id>', methods=['POST'])
@login_required
def approve_company(id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    company = CompanyProfile.query.get(id)
    if company:
        company.status = 'Approved'
        db.session.commit()
        flash(f"{company.company_name} approved!")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_company/<int:id>', methods=['POST'])
@login_required
def reject_company(id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    company = CompanyProfile.query.get(id)
    if company:
        company.status = 'Rejected'
        db.session.commit()
        flash(f"{company.company_name} rejected.")
    return redirect(url_for('admin_dashboard'))

@app.route('/company/create_drive', methods=['GET', 'POST'])
@login_required
def create_drive():
    if current_user.role != 'company':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        profile = CompanyProfile.query.filter_by(user_id=current_user.id).first()
        
        new_drive = PlacementDrive(
            company_id=profile.id,
            job_title=request.form.get('job_title'),
            description=request.form.get('description'),
            eligibility=request.form.get('eligibility'),
            deadline=request.form.get('deadline'),
            status='Pending' # Admin must approve the drive too!
        )
        db.session.add(new_drive)
        db.session.commit()
        flash("Placement Drive created and sent for Admin approval!")
        return redirect(url_for('company_dashboard'))
        
    return render_template('create_drive.html')

if __name__ == '__main__':
    app.run(debug=True)