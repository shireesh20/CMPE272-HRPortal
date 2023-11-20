from flask import Flask, request, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from sqlalchemy.orm import aliased
from sqlalchemy import func, desc, text
from sqlalchemy.exc import SQLAlchemyError
from functools import wraps
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
import os
import pathlib
import random
import string
from datetime import datetime

# Models and database configuration
from models import db, HRUser, Employee, Department, Dept_Emp, Title, Salary, Dept_Manager, HRRequest, ManagerRequest

# Flask application setup
app = Flask(__name__)
# Configuration settings in a separate file
app.config.from_pyfile('config.py')

# Initialize database, login, and bcrypt
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
bcrypt = Bcrypt(app)

# Google OAuth configuration
GOOGLE_CLIENT_ID = app.config['GOOGLE_CLIENT_ID']
client_secrets_file = os.path.join(
    pathlib.Path(__file__).parent, "client_secrets.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri=url_for('callback', _external=True)
)

# User session class


class UserSession(UserMixin):
    def __init__(self, user_id, user_role):
        self.id = user_id
        self.role = user_role

# User authentication and management


@login_manager.user_loader
def load_user(user_id):
    user = HRUser.query.get(int(user_id))
    return UserSession(user.id, user.role) if user else None


@login_manager.unauthorized_handler
def handle_unauthorized_access():
    flash('You must be logged in to view that page.')
    return redirect(url_for('login_view'))


def role_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash("Access denied.")
                return redirect(url_for('logout_view'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# Route definitions


@app.route('/')
def home_view():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login_view():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = HRUser.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(UserSession(user.id, user.role))
            return redirect(user_dashboard_url(user.role))

        flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register_view():
    if request.method == 'POST':
        user_details = extract_user_details(request.form)
        if not HRUser.query.filter_by(username=user_details['username']).first():
            new_user = create_new_user(user_details)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('login_view'))

        flash('Username already exists', 'error')

    return render_template('register.html')


@app.route('/dashboard')
@login_required
@role_required('hr')
def hr_dashboard_view():
    return render_template('dashboard.html', user=current_user)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_view():
    if request.method == 'GET':
        return render_user_profile(current_user.id)

    if request.method == 'POST':
        update_user_profile(current_user.id, request.json)
        return jsonify({'message': 'Profile updated successfully'}), 200


@app.route('/dashboard/manager')
@login_required
@role_required('manager')
def manager_dashboard_view():
    department_info = get_manager_department_info(current_user.id)
    return render_template('dashboard-manager.html', **department_info)

# Helper Functions


def user_dashboard_url(role):
    if role == 'manager':
        return url_for('manager_dashboard_view')
    elif role == 'employee':
        return url_for('employee_dashboard_view')
    return url_for('hr_dashboard_view')


def extract_user_details(form_data):
    return {
        'username': form_data.get('username'),
        # Other fields...
    }


def create_new_user(user_details):
    new_user = HRUser(username=user_details['username'], ...)
    new_user.set_password(user_details['password'])
    return new_user


@login_manager.user_loader
def load_user(user_id):
    # Loading user logic
    pass


@app.route('/manager-profile/<int:manager_id>')
@login_required
def view_manager_profile(manager_id):
    manager_profile = get_manager_profile(current_user.id, manager_id)
    return render_template('manager_profile.html', **manager_profile)


@app.route('/pending-approvals')
@login_required
def view_pending_approvals():
    approvals_count = count_pending_approvals()
    return jsonify({'pendingApprovalsCount': approvals_count})


@app.route('/employee-dashboard')
@login_required
def employee_dashboard():
    dashboard_data = get_employee_dashboard_data(current_user.id)
    return render_template('employee_dashboard.html', **dashboard_data)


@app.route('/sign-out', methods=['GET', 'POST'])
@login_required
def sign_out():
    user_sign_out()
    return redirect(url_for('home'))


@app.route('/employee-record/<int:employee_number>')
@login_required
def employee_record(employee_number):
    employee_data = get_employee_record(employee_number)
    return jsonify(employee_data)


@app.route('/load-employee-history/<int:employee_number>')
@login_required
def load_employee_history(employee_number):
    return render_template('employee_history_view.html', employee_number=employee_number)


@app.route('/list-employees')
@login_required
@hr_role_required
def list_employees():
    employee_list_data = get_employee_list_data(request.args)
    return render_template('employee_list.html', **employee_list_data)

# Helper Functions


def get_employee_list_data(request_args):
    page, per_page = get_pagination_details(request_args)
    sort_details = get_sort_details(request_args)
    only_managers, search_query = get_filter_criteria(request_args)

    employee_query = build_employee_query(
        only_managers, sort_details, search_query)
    paginated_employees = paginate_query(employee_query, page, per_page)

    if is_ajax_request(request):
        return {
            'template': 'partials/_employee_table_body.html',
            'employees': paginated_employees.items,
            'pagination': paginated_employees,
            'only_managers_state': str(only_managers).lower()
        }

    return {
        'employees': paginated_employees.items,
        'pagination': paginated_employees,
        'only_managers_state': str(only_managers).lower()
    }


def get_pagination_details(request_args):
    page = request_args.get('page', 1, type=int)
    per_page = 10
    return page, per_page


def get_sort_details(request_args):
    sort_by = request_args.get('sort_by', 'emp_no')
    sort_direction = request_args.get('direction', 'asc')
    return {'by': sort_by, 'direction': sort_direction}


def get_filter_criteria(request_args):
    only_managers = request_args.get('onlyManagers', 'false') == 'true'
    search_query = request_args.get('search', '')
    return only_managers, search_query


def build_employee_query(only_managers, sort_details, search_query):
    query = create_base_employee_query()
    if only_managers:
        query = filter_for_managers(query)
    query = apply_search_filter(query, search_query)
    query = apply_sorting(query, sort_details)
    return query.distinct(Employee.emp_no)


@app.route('/get_manager_requests/<int:emp_no>')
@login_required
def get_manager_requests(emp_no):
    try:
        # Fetch manager_requests for the specified emp_no
        manager_requests = ManagerRequest.query.filter_by(
            assignee=emp_no, task_status=0).all()
        manager_requests_data = []

        for request in manager_requests:
            manager_requests_data.append({
                'id': request.id,
                'title': request.task_name,
                'description': request.description,
                'task_status': request.task_status,
                'deadline': request.deadline,
                'assignee': request.assignee
            })

        return jsonify(manager_requests_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/manager-employees')
@login_required
def view_manager_employees():
    department_number, manager_number = get_dept_manager_params(request.args)
    employee_search_criteria = get_employee_search_criteria(request.args)
    paginated_employees = fetch_paginated_employees(
        department_number, employee_search_criteria)
    return render_template('manager_employees.html', employees=paginated_employees, dept_no=department_number, mgr_no=manager_number)


@app.route('/employee-details/<int:employee_number>')
@login_required
def employee_details(employee_number):
    employee_info = fetch_employee_information(employee_number)
    if employee_info:
        return jsonify(employee_info)
    return jsonify({'error': 'Employee not found'}), 404

# Helper Functions


def get_dept_manager_params(request_args):
    dept_no = request_args.get('dept_no')
    manager_no = request_args.get('mgr_no')
    return dept_no, manager_no


def get_employee_search_criteria(request_args):
    page = request_args.get('page', 1, type=int)
    per_page = 10
    search_term = request_args.get('search', '')
    return {'page': page, 'per_page': per_page, 'search': search_term}


def fetch_paginated_employees(dept_no, search_criteria):
    query = build_employee_query(dept_no, search_criteria['search'])
    return query.paginate(page=search_criteria['page'], per_page=search_criteria['per_page'], error_out=False)


def build_employee_query(dept_no, search_term):
    query = db.session.query(
        Employee.emp_no,
        Employee.first_name,
        Employee.last_name,
        Employee.gender,
        Employee.birth_date,
        Employee.hire_date
    ).join(Dept_Emp, Employee.emp_no == Dept_Emp.emp_no) \
        .filter(Dept_Emp.dept_no == dept_no, Dept_Emp.to_date > datetime.now())

    if search_term:
        search_condition = db.or_(
            Employee.first_name.ilike(f'%{search_term}%'),
            Employee.last_name.ilike(f'%{search_term}%')
        )
        query = query.filter(search_condition)
    return query


def fetch_employee_information(emp_no):
    latest_title_subquery, latest_salary_subquery = build_latest_title_salary_subqueries(
        emp_no)
    employee_data = db.session.query(
        Employee.emp_no,
        Employee.first_name,
        Employee.last_name,
        Department.dept_name,
        Dept_Emp.dept_no,
        latest_title_subquery.c.title,
        latest_salary_subquery.c.salary
    ).join(Dept_Emp, Employee.emp_no == Dept_Emp.emp_no) \
        .join(Department, Dept_Emp.dept_no == Department.dept_no) \
        .outerjoin(latest_title_subquery, Employee.emp_no == latest_title_subquery.c.emp_no) \
        .outerjoin(latest_salary_subquery, Employee.emp_no == latest_salary_subquery.c.emp_no) \
        .filter(Employee.emp_no == emp_no, latest_title_subquery.c.rnk == 1, latest_salary_subquery.c.rnk == 1) \
        .first()

    if employee_data:
        return {
            'emp_no': employee_data.emp_no,
            'first_name': employee_data.first_name,
            'last_name': employee_data.last_name,
            'dept_name': employee_data.dept_name,
            'dept_no': employee_data.dept_no,
            'title': employee_data.title,
            'salary': employee_data.salary
        }
    return None


def build_latest_title_salary_subqueries(emp_no):
    # Logic to build subqueries for latest title and salary
    pass


@app.route('/manager-employees')
@login_required
def view_manager_employees():
    department_number, manager_number = get_dept_manager_params(request.args)
    employee_search_criteria = get_employee_search_criteria(request.args)
    paginated_employees = fetch_paginated_employees(
        department_number, employee_search_criteria)
    return render_template('manager_employees.html', employees=paginated_employees, dept_no=department_number, mgr_no=manager_number)


@app.route('/employee-details/<int:employee_number>')
@login_required
def employee_details(employee_number):
    employee_info = fetch_employee_information(employee_number)
    if employee_info:
        return jsonify(employee_info)
    return jsonify({'error': 'Employee not found'}), 404

# Helper Functions


def get_dept_manager_params(request_args):
    dept_no = request_args.get('dept_no')
    manager_no = request_args.get('mgr_no')
    return dept_no, manager_no


def get_employee_search_criteria(request_args):
    page = request_args.get('page', 1, type=int)
    per_page = 10
    search_term = request_args.get('search', '')
    return {'page': page, 'per_page': per_page, 'search': search_term}


def fetch_paginated_employees(dept_no, search_criteria):
    query = build_employee_query(dept_no, search_criteria['search'])
    return query.paginate(page=search_criteria['page'], per_page=search_criteria['per_page'], error_out=False)


def build_employee_query(dept_no, search_term):
    query = db.session.query(
        Employee.emp_no,
        Employee.first_name,
        Employee.last_name,
        Employee.gender,
        Employee.birth_date,
        Employee.hire_date
    ).join(Dept_Emp, Employee.emp_no == Dept_Emp.emp_no) \
        .filter(Dept_Emp.dept_no == dept_no, Dept_Emp.to_date > datetime.now())

    if search_term:
        search_condition = db.or_(
            Employee.first_name.ilike(f'%{search_term}%'),
            Employee.last_name.ilike(f'%{search_term}%')
        )
        query = query.filter(search_condition)
    return query


def fetch_employee_information(emp_no):
    latest_title_subquery, latest_salary_subquery = build_latest_title_salary_subqueries(
        emp_no)
    employee_data = db.session.query(
        Employee.emp_no,
        Employee.first_name,
        Employee.last_name,
        Department.dept_name,
        Dept_Emp.dept_no,
        latest_title_subquery.c.title,
        latest_salary_subquery.c.salary
    ).join(Dept_Emp, Employee.emp_no == Dept_Emp.emp_no) \
        .join(Department, Dept_Emp.dept_no == Department.dept_no) \
        .outerjoin(latest_title_subquery, Employee.emp_no == latest_title_subquery.c.emp_no) \
        .outerjoin(latest_salary_subquery, Employee.emp_no == latest_salary_subquery.c.emp_no) \
        .filter(Employee.emp_no == emp_no, latest_title_subquery.c.rnk == 1, latest_salary_subquery.c.rnk == 1) \
        .first()

    if employee_data:
        return {
            'emp_no': employee_data.emp_no,
            'first_name': employee_data.first_name,
            'last_name': employee_data.last_name,
            'dept_name': employee_data.dept_name,
            'dept_no': employee_data.dept_no,
            'title': employee_data.title,
            'salary': employee_data.salary
        }
    return None


def build_latest_title_salary_subqueries(emp_no):
    # Logic to build subqueries for latest title and salary
    pass


@app.route('/employee/update/<int:employee_id>', methods=['POST'])
@login_required
def update_employee_info(employee_id):
    employee_data = request.get_json()
    if update_employee_details(employee_id, employee_data):
        return jsonify({'message': 'Employee successfully updated'}), 200
    return jsonify({'error': 'Employee update failed'}), 500


@app.route('/employee/search')
@login_required
def search_employee():
    search_parameters = get_search_parameters(request.args)
    employee_search_results = paginate_employee_search(search_parameters)
    return jsonify(format_employee_search_results(employee_search_results))


@app.route('/approvals/pending')
@login_required
def view_pending_approvals():
    pending_approvals_data = fetch_pending_approvals()
    return jsonify(pending_approvals_data)

# Helper Functions


def update_employee_details(emp_no, data):
    try:
        employee = Employee.query.get(emp_no)
        if not employee:
            return False

        update_basic_employee_info(employee, data)
        update_employee_department(employee, data.get('dept_no'))
        update_employee_title_and_salary(employee, data)

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        return False


def update_basic_employee_info(employee, data):
    employee.first_name = data.get('first_name', employee.first_name)
    employee.last_name = data.get('last_name', employee.last_name)
    # Update other fields as necessary


def update_employee_department(employee, new_dept_no):
    if new_dept_no:
        current_dept_emp = Dept_Emp.query.filter_by(
            emp_no=employee.emp_no).first()
        if current_dept_emp:
            current_dept_emp.dept_no = new_dept_no
        else:
            db.session.add(
                Dept_Emp(emp_no=employee.emp_no, dept_no=new_dept_no))


def update_employee_title_and_salary(employee, data):
    update_title(employee.emp_no, data)
    update_salary(employee.emp_no, data)


def update_title(emp_no, data):
    new_title, from_date, to_date = data.get(
        'title'), data.get('from_date'), data.get('to_date')
    if new_title and from_date and to_date:
        existing_title = Title.query.filter_by(
            emp_no=emp_no, from_date=from_date, to_date=to_date).first()
        if existing_title:
            existing_title.title = new_title
        else:
            db.session.add(Title(emp_no=emp_no, title=new_title,
                           from_date=from_date, to_date=to_date))


def update_salary(emp_no, data):
    new_salary, from_date, to_date = data.get(
        'new_salary'), data.get('from_date'), data.get('to_date')
    if new_salary and from_date and to_date:
        existing_salary = Salary.query.filter_by(
            emp_no=emp_no, from_date=from_date, to_date=to_date).first()
        if existing_salary:
            existing_salary.salary = new_salary
        else:
            db.session.add(Salary(emp_no=emp_no, salary=new_salary,
                           from_date=from_date, to_date=to_date))


def get_search_parameters(args):
    return {
        'query': args.get('query', ''),
        'page': args.get('page', 1, type=int),
        'per_page': args.get('per_page', 10, type=int)
    }


def paginate_employee_search(params):
    return Employee.query.filter(Employee.first_name.ilike(f'%{params["query"]}%')) \
        .paginate(page=params['page'], per_page=params['per_page'], error_out=False)


def format_employee_search_results(paginated_results):
    return {
        'employees': [employee.to_dict() for employee in paginated_results.items],
        'has_more': paginated_results.has_next
    }


def fetch_pending_approvals():
    return [
        {
            'dept_no': req.dept_no,
            'first_name': req.first_name,
            'last_name': req.last_name,
            'hire_date': req.hire_date.strftime('%Y-%m-%d'),
            'manager_no': req.manager_no,
            'title': req.title,
            'salary': req.salary,
            'req_type': req.req_type
        } for req in HRRequest.query.filter_by(hire_status=0).all()
    ]


@app.route('/employee/approve', methods=['POST'])
def approve_employee_request():
    approval_data = request.get_json()

    hr_request = find_hr_request(approval_data)
    if not hr_request:
        return jsonify({'error': 'HR request not found'}), 404

    try:
        process_hr_request(hr_request, approval_data)
        db.session.commit()
        return jsonify({'message': f'HR request for {hr_request.req_type} processed successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Helper Functions


def find_hr_request(data):
    return HRRequest.query.filter_by(
        first_name=data['first_name'],
        last_name=data['last_name'],
        hire_status=0
    ).first()


def process_hr_request(hr_request, data):
    hr_request.hire_status = 1  # Update hire_status

    if hr_request.req_type == 'newhire':
        create_new_employee(data)
    elif hr_request.req_type == 'terminate':
        terminate_employee(data)
    elif hr_request.req_type == 'promote':
        promote_employee(data)


def create_new_employee(data):
    emp_no = generate_unique_emp_no()
    new_employee = Employee(emp_no=emp_no, ...)  # Fill in details
    db.session.add(new_employee)
    # Add dept_emp and salary records as well


def generate_unique_emp_no():
    while True:
        emp_no = random.randint(600000, 999999)
        if not Employee.query.filter_by(emp_no=emp_no).first():
            return emp_no


def terminate_employee(data):
    employee = find_employee(data)
    if employee:
        delete_dept_emp_and_employee(employee)


def promote_employee(data):
    employee = find_employee(data)
    if employee:
        update_employee_salary_and_title(employee, data)


def find_employee(data):
    return Employee.query.filter_by(
        first_name=data['first_name'],
        last_name=data['last_name']
    ).first()


@app.route('/manager/dashboard')
@login_required
def manager_dashboard():
    return render_template('manager_dashboard.html')


@app.route('/department/employees')
def fetch_department_employees():
    department_number = request.args.get('dept_no')
    if not department_number:
        return jsonify({'error': 'Department number is required'}), 400
    employee_data = get_employees_by_department(department_number)
    return jsonify(employee_data)


@app.route('/task/create', methods=['POST'])
def create_task():
    task_info = request.get_json()
    response, status_code = add_new_task(task_info)
    return jsonify(response), status_code


@app.route('/task/update/<int:task_id>', methods=['POST'])
def update_task(task_id):
    task_status_info = request.get_json()
    response, status_code = modify_task_status(task_id, task_status_info)
    return jsonify(response), status_code


@app.route('/department/list')
@login_required
def list_departments():
    departments = get_all_departments()
    return jsonify(departments)


@app.route('/department/details')
@login_required
def department_details():
    department_info = fetch_department_info()
    return render_department_view(department_info)

# Helper Functions


def get_employees_by_department(dept_no):
    employees = db.session.query(Employee.emp_no, Employee.first_name, Employee.last_name)\
                          .join(Dept_Emp, Dept_Emp.emp_no == Employee.emp_no)\
                          .filter(Dept_Emp.dept_no == dept_no).all()
    return [{'id': emp.emp_no, 'name': f"{emp.first_name} {emp.last_name}"} for emp in employees]


def add_new_task(task_info):
    try:
        # Handle None case in parse_date function
        deadline = parse_date(task_info.get('deadline'))
        new_task = ManagerRequest(task_name=task_info['taskName'], description=task_info['description'],
                                  assignee=task_info['assignee'], deadline=deadline, manager_no=task_info['managerNo'],
                                  task_status=task_info.get('task_status', 0))
        db.session.add(new_task)
        db.session.commit()
        return {'message': 'Task added successfully'}, 200
    except Exception as e:
        return {'error': str(e)}, 500


def modify_task_status(task_id, status_info):
    task = ManagerRequest.query.get(task_id)
    if task:
        task.task_status = status_info.get('status')
        db.session.commit()
        return {'message': 'Task status updated'}, 200
    else:
        return {'error': 'Task not found'}, 404


def get_all_departments():
    return [{'dept_no': dept.dept_no, 'dept_name': dept.dept_name} for dept in Department.query.all()]


def fetch_department_info():
    latest_dept_managers_subquery = db.session.query(Dept_Manager.dept_no, func.max(Dept_Manager.from_date).label('latest_from_date'))\
                                              .group_by(Dept_Manager.dept_no).subquery()
    return db.session.query(Department.dept_no, Department.dept_name, Dept_Manager.emp_no,
                            Employee.first_name, Employee.last_name)\
        .join(latest_dept_managers_subquery, Department.dept_no == latest_dept_managers_subquery.c.dept_no)\
        .join(Dept_Manager, (Dept_Manager.dept_no == latest_dept_managers_subquery.c.dept_no) &
              (Dept_Manager.from_date == latest_dept_managers_subquery.c.latest_from_date))\
        .join(Employee, Dept_Manager.emp_no == Employee.emp_no)\
        .filter(Dept_Manager.to_date > datetime.now()).all()


def render_department_view(departments):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('partials/_departments_table.html', departments=departments)
    return render_template('departments.html', departments=departments)


def parse_date(date_string):
    return datetime.strptime(date_string, '%Y-%m-%d') if date_string else None


def create_unique_department_number(length=3):
    """Generates a unique department number."""
    while True:
        dept_no = 'd' + \
            ''.join(random.choices(
                string.ascii_uppercase + string.digits, k=length))
        if not Department.query.filter_by(dept_no=dept_no).first():
            return dept_no


@app.route('/department/add', methods=['POST'])
@login_required
def add_new_department():
    """Handles the addition of a new department."""
    department_data = request.get_json()
    new_department = prepare_new_department(department_data)
    assign_manager_to_department(
        department_data.get('empNo'), new_department.dept_no)
    flash('New department added successfully.')
    return redirect(url_for('departments'))


@app.route('/department/manager-history/<dept_no>', methods=['GET'])
@login_required
def view_department_manager_history(dept_no):
    """Fetches and displays the history of managers for a specific department."""
    history_data = fetch_manager_history(dept_no)
    return jsonify(history_data)

# Helper Functions


def prepare_new_department(data):
    unique_dept_no = create_unique_department_number()
    new_department = Department(
        dept_no=unique_dept_no, dept_name=data.get('deptName'))
    db.session.add(new_department)
    db.session.commit()
    return new_department


def assign_manager_to_department(manager_emp_no, dept_no):
    new_dept_manager = Dept_Manager(emp_no=manager_emp_no, dept_no=dept_no, from_date=datetime.now(),
                                    to_date=datetime(datetime.now().year + 1, 1, 1))
    db.session.add(new_dept_manager)
    db.session.commit()


def fetch_manager_history(department_no):
    manager_history = db.session.query(Dept_Manager.emp_no, Employee.first_name, Employee.last_name,
                                       Dept_Manager.from_date, Dept_Manager.to_date)\
        .join(Employee, Dept_Manager.emp_no == Employee.emp_no)\
        .filter(Dept_Manager.dept_no == department_no)\
        .order_by(Dept_Manager.from_date).all()
    return [{'emp_no': mh.emp_no, 'name': f"{mh.first_name} {mh.last_name}",
             'from_date': mh.from_date.strftime('%Y-%m-%d'),
             'to_date': mh.to_date.strftime('%Y-%m-%d')} for mh in manager_history]


# Main execution
if __name__ == '__main__':
    app.run()


@login_required
@app.route('/update_department_manager', methods=['POST'])
def update_department_manager():
    data = request.get_json()
    emp_no = data.get('emp_no')
    dept_no = data.get('dept_no')
    from_date = datetime.strptime(data.get('from_date'), '%Y-%m-%d').date()
    to_date = datetime.strptime(data.get('to_date'), '%Y-%m-%d').date()

    # Check for existing dept_manager entry
    existing_dept_manager = Dept_Manager.query.filter_by(dept_no=dept_no, from_date=from_date,
                                                         to_date=to_date).first()

    if existing_dept_manager:
        # Update existing entry
        existing_dept_manager.emp_no = emp_no  # This might be redundant
    else:
        # Create new entry
        new_dept_manager = Dept_Manager(
            emp_no=emp_no, dept_no=dept_no, from_date=from_date, to_date=to_date)
        db.session.add(new_dept_manager)

    # Check for existing dept_emp entry
    existing_dept_emp = Dept_Emp.query.filter_by(dept_no=dept_no, from_date=from_date,
                                                 to_date=to_date).first()

    if existing_dept_emp:
        # Update existing entry
        existing_dept_emp.emp_no = emp_no  # This might be redundant
    else:
        # Create new entry
        new_dept_emp = Dept_Emp(
            emp_no=emp_no, dept_no=dept_no, from_date=from_date, to_date=to_date)
        db.session.add(new_dept_emp)

    # Commit the changes to the database
    try:
        db.session.commit()
        return jsonify({'message': 'Department manager updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Flask route example


def create_unique_department_number(length=3):
    """Generates a unique department number."""
    while True:
        dept_no = 'd' + \
            ''.join(random.choices(
                string.ascii_uppercase + string.digits, k=length))
        if not Department.query.filter_by(dept_no=dept_no).first():
            return dept_no


@app.route('/department/add', methods=['POST'])
@login_required
def add_new_department():
    """Handles the addition of a new department."""
    department_data = request.get_json()
    new_department = prepare_new_department(department_data)
    assign_manager_to_department(
        department_data.get('empNo'), new_department.dept_no)
    flash('New department added successfully.')
    return redirect(url_for('departments'))


@app.route('/department/manager-history/<dept_no>', methods=['GET'])
@login_required
def view_department_manager_history(dept_no):
    """Fetches and displays the history of managers for a specific department."""
    history_data = fetch_manager_history(dept_no)
    return jsonify(history_data)

# Helper Functions


def prepare_new_department(data):
    unique_dept_no = create_unique_department_number()
    new_department = Department(
        dept_no=unique_dept_no, dept_name=data.get('deptName'))
    db.session.add(new_department)
    db.session.commit()
    return new_department


def assign_manager_to_department(manager_emp_no, dept_no):
    new_dept_manager = Dept_Manager(emp_no=manager_emp_no, dept_no=dept_no, from_date=datetime.now(),
                                    to_date=datetime(datetime.now().year + 1, 1, 1))
    db.session.add(new_dept_manager)
    db.session.commit()


def fetch_manager_history(department_no):
    manager_history = db.session.query(Dept_Manager.emp_no, Employee.first_name, Employee.last_name,
                                       Dept_Manager.from_date, Dept_Manager.to_date)\
        .join(Employee, Dept_Manager.emp_no == Employee.emp_no)\
        .filter(Dept_Manager.dept_no == department_no)\
        .order_by(Dept_Manager.from_date).all()
    return [{'emp_no': mh.emp_no, 'name': f"{mh.first_name} {mh.last_name}",
             'from_date': mh.from_date.strftime('%Y-%m-%d'),
             'to_date': mh.to_date.strftime('%Y-%m-%d')} for mh in manager_history]


# Main execution
if __name__ == '__main__':
    app.run()
