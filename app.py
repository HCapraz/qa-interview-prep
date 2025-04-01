from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os
import json
import random
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.config.from_object('config.Config')

# Initialize database
db = SQLAlchemy(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import models
from models.user import User
from models.question import Question, Category, QuestionAttempt
from models.progress import Progress

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    """Home page route"""
    categories = Category.query.all()
    return render_template('index.html', categories=categories)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        # Add user to database
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login route"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        # Check if user exists and password is correct
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout route"""
    logout_user()
    return redirect(url_for('index'))

@app.route('/quiz')
@login_required
def quiz_categories():
    """Quiz categories selection route"""
    categories = Category.query.all()
    return render_template('quiz_categories.html', categories=categories)

@app.route('/quiz/<category_id>', methods=['GET', 'POST'])
@login_required
def quiz(category_id):
    """Quiz route for a specific category"""
    category = Category.query.get_or_404(category_id)
    
    if request.method == 'POST':
        # Process quiz answers
        question_id = request.form.get('question_id')
        answer = request.form.get('answer')
        
        question = Question.query.get(question_id)
        is_correct = (answer.strip().lower() == question.correct_answer.strip().lower())
        
        # Record attempt
        attempt = QuestionAttempt(
            user_id=current_user.id,
            question_id=question_id,
            is_correct=is_correct,
            user_answer=answer
        )
        db.session.add(attempt)
        
        # Update user progress
        progress = Progress.query.filter_by(
            user_id=current_user.id,
            category_id=category_id
        ).first()
        
        if not progress:
            progress = Progress(
                user_id=current_user.id,
                category_id=category_id,
                questions_attempted=1,
                questions_correct=1 if is_correct else 0
            )
            db.session.add(progress)
        else:
            progress.questions_attempted += 1
            if is_correct:
                progress.questions_correct += 1
        
        db.session.commit()
        
        flash('Correct!' if is_correct else f'Incorrect. The correct answer is: {question.correct_answer}')
        return redirect(url_for('quiz', category_id=category_id))
    
    # Get a random question from the category
    questions = Question.query.filter_by(category_id=category.id).all()
    
    if not questions:
        flash('No questions available for this category.')
        return redirect(url_for('quiz_categories'))
    
    question = random.choice(questions)
    
    return render_template('quiz.html', category=category, question=question)

@app.route('/flashcards')
@login_required
def flashcard_categories():
    """Flashcard categories selection route"""
    categories = Category.query.all()
    return render_template('flashcard_categories.html', categories=categories)

@app.route('/flashcards/<category_id>')
@login_required
def flashcards(category_id):
    """Flashcards route for a specific category"""
    category = Category.query.get_or_404(category_id)
    questions = Question.query.filter_by(category_id=category.id).all()
    
    if not questions:
        flash('No flashcards available for this category.')
        return redirect(url_for('flashcard_categories'))
    
    return render_template('flashcards.html', category=category, questions=questions)

@app.route('/mock-interview')
@login_required
def mock_interview():
    """Mock interview simulation route"""
    categories = Category.query.all()
    questions = []
    
    # Get random questions from each category
    for category in categories:
        category_questions = Question.query.filter_by(category_id=category.id).all()
        if category_questions:
            questions.append(random.choice(category_questions))
    
    if not questions:
        flash('No questions available for mock interview.')
        return redirect(url_for('index'))
    
    return render_template('mock_interview.html', questions=questions)

@app.route('/progress')
@login_required
def progress():
    """User progress tracking route"""
    progress_data = Progress.query.filter_by(user_id=current_user.id).all()
    categories = Category.query.all()
    
    # Prepare data for the progress chart
    chart_data = []
    for category in categories:
        category_progress = next((p for p in progress_data if p.category_id == category.id), None)
        
        if category_progress:
            percentage = (category_progress.questions_correct / category_progress.questions_attempted * 100) if category_progress.questions_attempted > 0 else 0
            chart_data.append({
                'category': category.name,
                'attempted': category_progress.questions_attempted,
                'correct': category_progress.questions_correct,
                'percentage': round(percentage, 2)
            })
        else:
            chart_data.append({
                'category': category.name,
                'attempted': 0,
                'correct': 0,
                'percentage': 0
            })
    
    return render_template('progress.html', chart_data=chart_data)

@app.route('/reference')
def reference():
    """Reference materials route"""
    categories = Category.query.all()
    return render_template('reference.html', categories=categories)

@app.route('/reference/<category_id>')
def reference_category(category_id):
    """Reference materials for a specific category"""
    category = Category.query.get_or_404(category_id)
    
    # Read reference content for the category
    reference_file = os.path.join(app.root_path, 'data', 'references', f'{category.slug}.md')
    
    if os.path.exists(reference_file):
        with open(reference_file, 'r') as f:
            content = f.read()
    else:
        content = "Reference material not available for this category."
    
    return render_template('reference_category.html', category=category, content=content)

# Initialize database and create tables
@app.before_first_request
def create_tables():
    db.create_all()
    
    # Check if categories exist, if not create them
    if Category.query.count() == 0:
        categories = [
            {'name': 'General QA', 'slug': 'general_qa'},
            {'name': 'SDLC & STLC', 'slug': 'sdlc_stlc'},
            {'name': 'Agile & Scrum', 'slug': 'agile_scrum'},
            {'name': 'Java', 'slug': 'java'},
            {'name': 'Selenium', 'slug': 'selenium'},
            {'name': 'TestNG & JUnit', 'slug': 'testing_frameworks'},
            {'name': 'Cucumber & BDD', 'slug': 'cucumber_bdd'},
            {'name': 'Jenkins, Git & Maven', 'slug': 'devops_tools'},
            {'name': 'API Testing', 'slug': 'api_testing'},
            {'name': 'SQL & Databases', 'slug': 'sql_databases'},
            {'name': 'Behavioral Questions', 'slug': 'behavioral'}
        ]
        
        for category_data in categories:
            category = Category(name=category_data['name'], slug=category_data['slug'])
            db.session.add(category)
        
        db.session.commit()

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """404 error handler"""
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    """500 error handler"""
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)