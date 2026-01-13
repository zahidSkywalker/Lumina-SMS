from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from wtforms import StringField, IntegerField, FloatField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, NumberRange, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-change-in-production'
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
    # Relationship: One User has many Students
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
    # Foreign Key: Links this student to a User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

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
        # Check if user exists
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
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
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
    else:
        avg_gpa = 0
        top_student = None

    return render_template('dashboard.html', total=total_students, avg=avg_gpa, top=top_student)

@app.route('/students')
@login_required
def student_list():
    # CRITICAL: Only show students belonging to the logged-in user
    students = Student.query.filter_by(user_id=current_user.id).all()
    return render_template('students.html', students=students)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_student():
    form = StudentForm()
    if form.validate_on_submit():
        # Assign the current user's ID to the student
        new_student = Student(
            name=form.name.data,
            roll_no=form.roll_no.data,
            email=form.email.data,
            course=form.course.data,
            gpa=form.gpa.data,
            user_id=current_user.id # Link to logged in user
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
    # CRITICAL: Check if the logged in user owns this student
    if student.author != current_user:
        flash('You are not authorized to delete this record.', 'danger')
        return redirect(url_for('student_list'))
        
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted.', 'info')
    return redirect(url_for('student_list'))

# Initialize DB
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
