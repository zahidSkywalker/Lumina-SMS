from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from wtforms import StringField, IntegerField, FloatField, PasswordField, SubmitField, DateField
from wtforms.validators import DataRequired, Email, NumberRange, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-change-in-production'

# --- FIX FOR VERCEL DATA SAVING & POST REQUESTS ---
# This line ensures the database is in the writable /tmp folder for Vercel
import os

# Check if DATABASE_URL is set (Vercel Environment Variable)
if os.environ.get('DATABASE_URL'):
    # Supabase sometimes uses 'postgres://' but python needs 'postgresql://'
    db_url = os.environ.get('DATABASE_URL')
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    # Fallback to local SQLite if not on Vercel
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db' 

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Database Models ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    students = db.relationship('Student', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    roll_no = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    course = db.Column(db.String(50), nullable=False)
    gpa = db.Column(db.Float, nullable=False)
    
    # --- NEW FIELDS FOR COACHING & FEES ---
    start_date = db.Column(db.Date, nullable=False, default=datetime.today)
    fee_amount = db.Column(db.Float, nullable=False, default=0.0)
    last_payment_date = db.Column(db.Date, nullable=True) # When did they last pay?
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    @property
    def next_due_date(self):
        # If never paid, due date is start_date
        if not self.last_payment_date:
            return self.start_date + timedelta(days=30)
        # Otherwise, due date is last payment + 30 days
        return self.last_payment_date + timedelta(days=30)

    @property
    def is_overdue(self):
        return datetime.now().date() > self.next_due_date

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Forms ---

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class StudentForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired()])
    roll_no = StringField('Roll Number', validators=[DataRequired()])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    course = StringField('Course/Major', validators=[DataRequired()])
    gpa = FloatField('GPA (0.0 - 4.0)', validators=[DataRequired(), NumberRange(min=0.0, max=4.0)])
    
    # --- NEW FORM FIELDS ---
    start_date = DateField('Teaching Start Date', validators=[DataRequired()], format='%Y-%m-%d')
    fee_amount = FloatField('Monthly Fee ($)', validators=[DataRequired()])
    last_payment_date = DateField('Last Payment Date', validators=[DataRequired()], format='%Y-%m-%d')
    
    submit = SubmitField('Save Student')

# --- Routes ---

@app.route('/')
@app.route('/home')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('home_landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already taken!', 'danger')
            return redirect(url_for('register'))
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Account created! You can now login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    total_students = Student.query.filter_by(user_id=current_user.id).count()
    if total_students > 0:
        avg_gpa = db.session.query(db.func.avg(Student.gpa)).filter_by(user_id=current_user.id).scalar()
        top_student = Student.query.filter_by(user_id=current_user.id).order_by(Student.gpa.desc()).first()
        # Calculate Dues count
        overdue_count = Student.query.filter_by(user_id=current_user.id).all()
        overdue_count = sum(1 for s in overdue_count if s.is_overdue)
    else:
        avg_gpa = 0
        top_student = None
        overdue_count = 0

    return render_template('dashboard.html', total=total_students, avg=avg_gpa, top=top_student, overdue=overdue_count)

@app.route('/students')
@login_required
def student_list():
    students = Student.query.filter_by(user_id=current_user.id).all()
    return render_template('students.html', students=students)

@app.route('/reminders')
@login_required
def reminders():
    # Filter students who are overdue
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    overdue_students = [s for s in all_students if s.is_overdue]
    return render_template('reminders.html', students=overdue_students)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_student():
    form = StudentForm()
    if form.validate_on_submit():
        new_student = Student(
            name=form.name.data,
            roll_no=form.roll_no.data,
            email=form.email.data,
            course=form.course.data,
            gpa=form.gpa.data,
            start_date=form.start_date.data,
            fee_amount=form.fee_amount.data,
            last_payment_date=form.last_payment_date.data,
            user_id=current_user.id
        )
        db.session.add(new_student)
        db.session.commit()
        flash('Student added successfully!', 'success')
        return redirect(url_for('student_list'))
    return render_template('create.html', form=form)

@app.route('/delete/<int:id>')
@login_required
def delete_student(id):
    student = Student.query.get_or_404(id)
    if student.author != current_user:
        flash('You are not authorized to delete this record.', 'danger')
        return redirect(url_for('student_list'))
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted.', 'info')
    return redirect(url_for('student_list'))

# --- CRITICAL: HANDLE DB RESET FOR VERCEL DEPLOYMENT ---
# Only needed if schema changes and using /tmp
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
