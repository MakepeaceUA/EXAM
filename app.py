import os, time, datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.config.update(
    SQLALCHEMY_DATABASE_URI='sqlite:///tasks.db',
    UPLOAD_FOLDER='static/uploads'
)
db = SQLAlchemy(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    comment = db.Column(db.Text)
    hashtag = db.Column(db.String(255))
    priority = db.Column(db.Integer, default=1)
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False)
    attachment = db.Column(db.String(255))
    parent_id = db.Column(db.Integer, db.ForeignKey('task.id'))
    subtasks = db.relationship('Task', backref=db.backref('parent', remote_side=[id]), cascade="all, delete-orphan")

def handle_file(file):
    if file and '.' in file.filename:
        name = f"{int(time.time())}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], name))
        return name
    return None

def clean_tags(tags_str):
    tags = [t.strip().lower() for t in tags_str.replace(',', ' ').split() if t.strip()]
    return ", ".join(t if t.startswith('#') else '#'+t for t in sorted(set(tags)))

@app.route('/')
def index():
    search = request.args.get('search', '').strip().lower()
    period = request.args.get('filter')
    today = datetime.date.today()
    
    q = Task.query
    
    if period == 'today': 
        q = q.filter_by(due_date=today)
    elif period == 'week': 
        q = q.filter(Task.due_date <= today + datetime.timedelta(days=7))
    elif period == 'month': 
        q = q.filter(Task.due_date <= today + datetime.timedelta(days=30))
    elif period == 'year':
        q = q.filter(Task.due_date >= datetime.date(today.year, 1, 1), 
                     Task.due_date <= datetime.date(today.year, 12, 31))
    
    tasks = q.order_by(Task.due_date.asc().nullslast(), Task.priority.desc()).all()

    if search:
        tasks = [t for t in tasks if search in t.title.lower() or (t.hashtag and search in t.hashtag.lower())]
    else:
        tasks = [t for t in tasks if t.parent_id is None]

    return render_template('index.html', tasks=tasks, current_filter=period, search_query=request.args.get('search'))

@app.route('/add_task', methods=['POST'])
def add_task():
    date_val = request.form.get('due_date')
    new_task = Task(
        title=request.form['title'],
        description=request.form.get('description'),
        hashtag=clean_tags(request.form.get('hashtag', '')),
        priority=request.form.get('priority', 1),
        due_date=datetime.date.fromisoformat(date_val) if date_val else None,
        attachment=handle_file(request.files.get('file'))
    )
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/create')
def create_page(): return render_template('create_task.html')

@app.route('/task/<int:task_id>')
def task_detail(task_id):
    return render_template('task_detail.html', task=Task.query.get_or_404(task_id))

@app.route('/add_subtask/<int:parent_id>', methods=['POST'])
def add_subtask(parent_id):
    db.session.add(Task(title=request.form['title'], parent_id=parent_id))
    db.session.commit()
    return redirect(url_for('task_detail', task_id=parent_id))

@app.route('/edit/<int:task_id>')
def edit_task(task_id):
    return render_template('edit_task.html', task=Task.query.get_or_404(task_id))

@app.route('/update/<int:task_id>', methods=['POST'])
def update_task(task_id):
    t = Task.query.get_or_404(task_id)
    t.title = request.form['title']
    t.description = request.form.get('description')
    t.comment = request.form.get('comment')
    t.hashtag = clean_tags(request.form.get('hashtag', ''))
    t.priority = request.form.get('priority')
    
    date_val = request.form.get('due_date')
    t.due_date = datetime.date.fromisoformat(date_val) if date_val else None
    
    new_file = handle_file(request.files.get('file'))
    if new_file:
        t.attachment = new_file

    db.session.commit()
    return redirect(url_for('task_detail', task_id=t.id))

@app.route('/toggle_complete/<int:task_id>')
def toggle_complete(task_id):
    t = Task.query.get_or_404(task_id)
    t.completed = not t.completed
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    t = Task.query.get_or_404(task_id)
    p_id = t.parent_id
    if t.attachment:
        try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], t.attachment))
        except: pass
    db.session.delete(t)
    db.session.commit()
    return redirect(url_for('task_detail', task_id=p_id) if p_id else url_for('index'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)