from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response

from flask_jwt_extended import JWTManager, create_access_token, set_access_cookies, jwt_required, get_jwt_identity, unset_jwt_cookies
from utils.env_p import *
from inventory_handler import Handle_Operations
from datetime import datetime
import os
from itertools import zip_longest



manage_op = Handle_Operations("central.json")
primary_data_db = manage_op.set_db('primary_data')
operation_db = manage_op.set_db('operation')
logs_db = manage_op.set_db("logs")
app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = SECRET_KEY
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = False
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
app.config['JWT_REFRESH_COOKIE_NAME'] = 'refresh_token_cookie'
jwt = JWTManager(app)


@app.route("/login", methods=["GET", "POST"])
def login():
    return render_template('pages/login.html')

@app.route("/validate_user", methods=["POST"])
def validate_user():
    form_values = request.form
    user = manage_op.process_user_validation(primary_data_db, form_values)
    if user is None:
       error = "" 
       return render_template('pages/login.html',  error = error)
    else:
        token = create_access_token({"id": str(user["_id"]), "email": user["email"], "senha" : user["senha"]})
        resp = make_response(redirect("/"))
        set_access_cookies(resp, token)
        return resp        

@app.route('/logout', methods=['POST', 'GET'])
# @jwt_required()
def logout():
    response = make_response(redirect('/login'))
    unset_jwt_cookies(response)
    return response

@app.route('/', methods=["GET", "POST"])
@jwt_required(optional=True)
def index():
    current_user = get_jwt_identity()
    print('user is ', current_user)
    if current_user == None:
        return redirect('/login')
    colec = primary_data_db.list_collection_names()
    sample = manage_op.get_db_by_collection(primary_data_db, 'usuarios')
    
    if request.method == "POST":
        ("Requisiçao recebida")
    return render_template('index.html', item_list = colec, sample = sample, user_name = sample[0]["nome"])

@app.route('/cadastro/<collection_name>', methods=['POST',  'GET'])
# @jwt_required(locations=["cookies"])
def cadastro(collection_name):
    field = manage_op.make_datapack(primary_data_db, collection_name, 1) 
    return render_template('pages/form.html', titulo = "Inicio" , title = collection_name, collection_name = collection_name, field = field)

@app.route('/register', methods=['POST', 'GET'])
def register_user(collection_name = "usuarios"):
    login_check = request.args.get('login_check', default=None, type=bool)
    field = manage_op.make_datapack(primary_data_db, collection_name, 1)
    now = datetime.strftime(datetime.now(), "%Y-%m-%d")
    return render_template('pages/register_user.html', field = field, now = now, login_check = login_check)

@app.route('/send_data/<collection_name>', methods= ['POST'])
# @jwt_required()
def send(collection_name):
    form_values = {key: value for key, value in request.form.items()}
    print("Values to be send are: ", form_values)
    url_args = request.args.to_dict()
    op_type = url_args.get('op_type')
    print("COLLECTION IN SEND IS: ", collection_name)
    if op_type != None:
        redirect_to = "/operation"
        form_values.update({'operacao': url_args.get("op_type")})
        required_db = operation_db
        form_values = manage_op.hand_mandatory_data(required_db, form_values, "operacao", url_args.get("op_type").lower())
    else:
        required_db = primary_data_db
        redirect_to = "/view/" + collection_name
        if collection_name == "usuarios":
            form_values = manage_op.process_user_registration(required_db, form_values)
            if form_values == None:
                return redirect(url_for('register_user', login_check = True))
        form_values = manage_op.hand_mandatory_data(required_db, form_values, collection_name)
        form_values = manage_op.send_treatment(required_db, collection_name, form_values)    
    manage_op.insert_into_db(required_db, collection_name, form_values)
    manage_op.save_log(collection_name)
    if op_type != None:
        manage_op.create_position(form_values)
    return redirect(redirect_to)

@app.route('/view/<collection_name>', methods=['POST', 'GET'])
# @jwt_required()
def view(collection_name):
    sample = manage_op.make_view_by_att(primary_data_db, collection_name, {"status": "enabled"})
    base_dir = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(base_dir, 'static/images_'  + collection_name)
    file = os.listdir(path)
    if collection_name == "produtos":
        category_filter = []
        for db_dict in sample:
            entered = 0
            for icon in file:
                icon = icon.split("-")[1]
                if db_dict['Categoria'].lower() == icon.split('.')[0]:
                    category_filter.append(icon)
                    entered = 1
                    break
            if entered == 0:
                category_filter.append("notfound.jpg")
        zipped = zip_longest(sample, category_filter, fillvalue=None)
        return render_template('pages/view.html', titulo = "Inicio", collection_name = collection_name, zipped = zipped)
    zipped = zip_longest(sample, file, fillvalue= file[0])
    return render_template('pages/view.html', titulo = "Inicio", collection_name = collection_name, zipped = zipped)

@app.route('/operation', methods=['POST',  'GET'])
# @jwt_required(locations=["cookies"])
def operation():
    options = manage_op.return_op()
    op_type = request.args.get("op_type")
    field = manage_op.render_op_form(op_type)
    final_field, combined_lists = list(), list()
    if op_type != None:
        combined_lists = field[1]
        final_field = field[0]
    return render_template('pages/populate.html', options=options, op_type=op_type, field=final_field, combined_lists = combined_lists)

@app.route('/edit_card/<collection_name>/<codigo>', methods=['POST', 'GET'])
# @jwt_required(locations=["cookies"])
def edit_card(collection_name, codigo):
    field = manage_op.make_datapack(primary_data_db, collection_name, 1)
    field = manage_op.edit_preview(primary_data_db, codigo, field, collection_name)
    return render_template('pages/edit_form.html', codigo = codigo, title = collection_name, collection_name = collection_name, field = field)


@app.route('/send/edit/<collection_name>/<codigo>', methods = ["POST", "GET"])
# @jwt_required(locations=["cookies"])
def edit(collection_name, codigo):
    form_values = {key: value for key, value in request.form.items()}
    form_values = manage_op.hand_mandatory_data(primary_data_db, form_values, collection_name,is_new=False)
    form_values = manage_op.send_treatment(primary_data_db, collection_name, form_values)
    primary_data_db[collection_name].update_one({'codigo' : codigo}, {'$set': form_values})
    return redirect('/view/' + collection_name)

@app.route('/disable_card/<collection_name>/<codigo>', methods=['POST', 'GET'])
# @jwt_required(locations=["cookies"])
def disable_card(collection_name, codigo):
    resultado = primary_data_db[collection_name].update_one({"codigo":codigo} ,  {'$set': {"status" : 'disabled'}})
    print(f"Documentos modificados: {resultado.modified_count}")
    return redirect('/view/'+ collection_name)


"""Testing Cookies and something
@app.route('/staging/<operation_type>', methods=['POST', 'GET'])
def edit_staging(operation_type):
    resp = make_response(jsonify({"operation": operation_type}))
    resp.set_cookie("data1", ,max_age=10000)
    return resp


@app.route('/del_cookie/<cookie_name>', methods=['POST', 'GET'])
def clean_cookie(cookie_name):
    req = request.cookies.get(cookie_name)
    print(f"req is: {req}")
    
    deleted = make_response("cookie_deleted")
    deleted.delete_cookie(cookie_name)
    print(f"now requested is: {request.cookies.get(cookie_name).__str__()}")
    return deleted
"""