from flask import Flask, jsonify
from flask import render_template, request, redirect, url_for, flash, session
import csv
import mysql.connector
from io import StringIO
from functools import wraps
import jwt
from flask_mail import Mail, Message
import json
import numpy as np
from sklearn.linear_model import LinearRegression
app = Flask(__name__)
app.debug = True

# Configuration de la Base de Données MYSQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'produits'
app.config['MYSQL_CURSORCLASS'] = 'crs'

# Clé secrète pour signer et vérifier le jeton
SECRET_KEY = 'your-secret-key'

# Fonction de vérification du jeton
def verify_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:
            # Vérifiez si le jeton est valide et décodez-le
            decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            # Si le jeton est valide, appeler la fonction avec les arguments
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
    return decorated_function

def generate_token(user_id):
    payload = {'user_id': user_id}
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

#configuration envoi mail
app.config['DEBUG'] = True
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'coucousiddiq@gmail.com'
app.config['MAIL_PASSWORD'] = 'ufugdqwruagezwmx'
app.config['MAIL_DEFAULT_SENDER'] = ('customer service', 'api@test.com')

mail = Mail(app)

# Fonction pour récupérer les clients ayant déjà acheté un produit
def get_clients_ayant_achete():
    # Connexion à la base de données
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})
    query = """ SELECT DISTINCT c.NumClient, c.nomclient, c.emailClient FROM client c INNER JOIN acheter a ON c.NumClient = a.NumClient """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

# Fonction pour envoyer un email de proposition de produit similaire à un client
def envoyer_proposition_produit(client):
    # Connexion à la base de données
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})  
    
    cursor.execute("SELECT p.NomProduit, p.marque, p.prix, c.LibCategorie FROM produit p INNER JOIN acheter a ON p.NumProduit = a.NumProduit INNER JOIN categorie c ON p.numCategorie = c.NumCategorie WHERE a.NumClient = %s ", (client[0],))
    results = cursor.fetchall()
    
    # Création du contenu de l'email
    message_body = f"Cher {client[1]},\n\nNous vous proposons les produits suivants similaires à ceux que vous avez déjà achetés :\n\n"
    for result in results:
        message_body += f"- {result[0]} ({result[1]}) - Prix : {result[2]}€ - Catégorie : {result[3]}\n"
    message_body += "\nMerci de votre confiance!\nL'équipe de api.test.com"

    # Envoi de l'email
    msg = Message("Proposition de produits similaires", recipients=[client[2]])
    msg.body = message_body
    mail.send(msg)
    # Fermeture de la connexion à la base de données
    cursor.close()
    conn.close()

# Fonction pour envoyer des propositions de produits similaires à tous les clients ayant déjà acheté
@app.route('/envoyer_propositions', methods=['GET'])
def envoyer_propositions():
    clients = get_clients_ayant_achete()
    for client in clients:
        envoyer_proposition_produit(client)
    return "Propositions de produits similaires envoyées avec succès!"

@app.route('/predict', methods=['GET'])
def prediction():
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})
    
    cursor.execute("SELECT p.NomProduit, e.Prix FROM evolution e JOIN produit p ON e.NumProduit = p.NumProduit")
    result = cursor.fetchall()
    
    # Préparer les données d'entraînement pour le modèle de régression par produit
    product_prices = {}
    for row in result:
        produit = row[0]
        prix = row[1]
        if produit not in product_prices:
            product_prices[produit] = []
        product_prices[produit].append(prix)
    
    # Effectuer la prédiction pour chaque produit
    predictions = {}
    for produit, prix_list in product_prices.items():
        X_train = np.arange(len(prix_list)).reshape(-1, 1)
        model = LinearRegression()
        model.fit(X_train, prix_list)
        next_month_index = len(prix_list) + 1
        predicted_price = model.predict(np.array(next_month_index).reshape(-1, 1))
        predictions[produit] = predicted_price.tolist()  # Convertir ndarray en liste Python
    
    # Fermer la connexion à la base de données
    cursor.close()    
    return json.dumps(predictions,indent=4 )  


# get one product
@app.route("/", methods=["GET"])
def index():
    # conntect to db
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})

    # select all products from table produits then return them in json
    try:
        cursor.execute("SELECT * FROM produit p, categorie c WHERE p.Numcategorie = c.Numcategorie")
        products = cursor.fetchall()
        # Close the cursor and connection
        cursor.close()
        conn.close()
        # Convert products to JSON format
        product_list = []
        for product in products:
            product_dict = {
                'NumProduit': product[0],
                'NomProduit': product[1],
                'marque': product[2],
                'LieuFabrication': product[3],
                'prix': product[4],
                'Numcategorie': product[5],
            }
            product_list.append(product_dict)
        # Return the products in JSON format
        return jsonify(product_list)
    except Exception as e:
        # Handle any errors that occur during the database query
        return jsonify({'error': str(e)}) 


# get one product
@app.route("/product/<int:id>", methods=["GET"])
def getProductById(id):
    # conntect to db
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})

    # select all products from table produits then return them in json
    try:
        cursor.execute( "SELECT * FROM produit p, categorie c WHERE p.Numcategorie = c.Numcategorie and p.NumProduit = %s", (id,))
        products = cursor.fetchall()
        # Close the cursor and connection
        cursor.close()
        conn.close()
        # Convert products to JSON format
        product_list = []
        for product in products:
            product_dict = {
                'NumProduit': product[0],
                'NomProduit': product[1],
                'marque': product[2],
                'LieuFabrication': product[3],
                'prix': product[4],
                'Numcategorie': product[5],
            }
            product_list.append(product_dict)
        # Return the products in JSON format
        return jsonify(product_list)

    except Exception as e:
        # Handle any errors that occur during the database query
        return jsonify({'error': str(e)})
    

@app.route("/product/add", methods=["POST"])
# params : json { "NomProduit": "string", "marque": "string", "LieuFabrication": "string", "prix": "float", "Nomcategorie": "string" }
@verify_token
def createProduct():
    data = request.get_json()
    nom_produit = data.get('NomProduit')
    marque = data.get('marque')
    lieu_fabrication = data.get('LieuFabrication')
    prix = data.get('prix')
    nom_categorie = data.get('Nomcategorie')

    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()

    try:
        # Vérifier si la categorie existe dans la table "categorie"
        cursor.execute("SELECT Numcategorie FROM categorie WHERE Libcategorie = %s", (nom_categorie,))
        existing_category = cursor.fetchone()

        if existing_category:

            num_categorie = existing_category[0]
        else:
            # Si la categorie n'existe pas, la créer et récupérer son ID
            cursor.execute("INSERT INTO categorie (Libcategorie) VALUES (%s)", (nom_categorie,))
            num_categorie = cursor.lastrowid

        # Insérer le produit dans la table "produit"
        cursor.execute(
            "INSERT INTO produit (NomProduit, marque, LieuFabrication, prix, Numcategorie) VALUES (%s, %s, %s, %s, %s)",
            (nom_produit, marque, lieu_fabrication, prix, num_categorie))
        conn.commit()

        # Fermer la connexion à la base de données
        cursor.close()
        conn.close()

        return jsonify({"message": "Produit ajouté avec succès"})
    except Exception as e:
        return jsonify({'error': str(e)})


##add product from csv file
@app.route("/product/addCsv", methods=["POST"])
def createProductFromCsv():
    try:
        # Access the uploaded file
        file = request.files['file']
    except:
        return jsonify({"message": "Veuillez sélectionner un fichier CSV valide, le nom du champ doit être 'file' "})

    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()

    try:
        # Ouvrir le fichier CSV à partir du lien
        content = file.read().decode('latin-1')
        
        fieldnames = ['NomProduit', 'marque', 'LieuFabrication', 'prix', 'Nomcategorie']
        reader = csv.DictReader(StringIO(content), delimiter=';', fieldnames=fieldnames)        
        
        # print(reader)
        # next(reader)

        for row in reader:
            #return jsonify({"message": row})
            print(row)
            nom_produit = row['NomProduit']
            marque = row['marque']
            lieu_fabrication = row['LieuFabrication']
            prix = row['prix']
            nom_categorie = row['Nomcategorie']

            # Vérifier si la categorie existe dans la table "categorie"
            cursor.execute("SELECT Numcategorie FROM categorie WHERE Libcategorie = %s", (nom_categorie,))
            existing_category = cursor.fetchone()

            if existing_category:
                num_categorie = existing_category[0]
            else:
                # Si la categorie n'existe pas, la créer et récupérer son ID
                cursor.execute("INSERT INTO categorie (Libcategorie) VALUES (%s)", (nom_categorie,))
                num_categorie = cursor.lastrowid

            # Insérer le produit dans la table "produit"
            cursor.execute(
                "INSERT INTO produit (NomProduit, marque, LieuFabrication, prix, Numcategorie) VALUES (%s, %s, %s, %s, %s)", (nom_produit, marque, lieu_fabrication, prix, num_categorie,))

        conn.commit()
        # Fermer la connexion à la base de données
        cursor.close()
        conn.close()

        return jsonify({"message": "Produits ajoutés avec succès"})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route("/product/<int:id>/update", methods=["PATCH"])
def updateProduct(id):
    data = request.get_json()
    nom_produit = data.get('NomProduit')
    marque = data.get('marque')
    lieu_fabrication = data.get('LieuFabrication')
    prix = data.get('prix')
    nom_categorie = data.get('Nomcategorie')

    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()

    # Récupérer le prix actuel du produit
    cursor.execute("SELECT prix FROM produit WHERE NumProduit = %s", (id,))
    existing_price = cursor.fetchone()

    if existing_price:
        existing_price = existing_price[0]

    # Vérifier si le nouveau prix est différent de l'ancien
    if prix and prix != existing_price:
        # Insérer une entrée dans la table "evolution"
        cursor.execute("INSERT INTO evolution (DateEvolution, NumProduit, Prix) VALUES (NOW(), %s, %s)", (id, existing_price,))
        conn.commit()

    # Vérifier si la categorie existe dans la table "categorie"
    cursor.execute("SELECT Numcategorie FROM categorie WHERE Libcategorie = %s", (nom_categorie,))
    existing_category = cursor.fetchone()

    if existing_category:
        num_categorie = existing_category[0]
    else:
        # Si la categorie n'existe pas, la créer et récupérer son ID
        cursor.execute("INSERT INTO categorie (Libcategorie) VALUES (%s)", (nom_categorie,))
        num_categorie = cursor.lastrowid

    # Mettre à jour le produit dans la table "produit"
    cursor.execute(
        "UPDATE produit SET NomProduit=%s, marque=%s, LieuFabrication=%s, prix = %s, Numcategorie = %s WHERE NumProduit = %s",
        (nom_produit, marque, lieu_fabrication, prix, num_categorie, id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Produit mis à jour avec succès"})


@app.route("/product/<int:id>/delete", methods=["DELETE"])
def delete(id):
    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()
    # Supprimer les évolutions liées au produit
    cursor.execute("DELETE FROM evolution WHERE NumProduit = %s", (id,))
    conn.commit()
    # Supprimer le produit
    cursor.execute("DELETE FROM produit WHERE NumProduit = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Produit supprimé avec succès"})


# get one product price evolutions
@app.route("/product/<int:id>/evolution", methods=["GET"])
def getProductEvolution(id):
    # conntect to db
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})

    # select all products from table produits then return them in json
    try:
        cursor.execute(
            "SELECT p.NomProduit as name,e.DateEvolution as date, e.Prix as price  FROM produit p, categorie c, evolution e WHERE p.Numcategorie = c.Numcategorie and p.NumProduit = e.NumProduit and p.NumProduit = %s",
            (id,))
        products = cursor.fetchall()

        # Close the cursor and connection
        cursor.close()
        conn.close()

        # Convert products to JSON format
        product_list = []
        for product in products:
            product_dict = {
                'Produit': product[0],
                'Date ': product[1],
                'Prix': product[2],
            }
            product_list.append(product_dict)

        # Return the products in JSON format
        return jsonify(product_list)

    except Exception as e:
        # Handle any errors that occur during the database query
        return jsonify({'error': str(e)})
    
#get products average price
@app.route('/average_price', methods=['GET'])
def get_price_prediction():
    #data = request.get_json()
    #date = data.get('date')
    
    # Récupérer les évolutions des prix des produits jusqu'à la date donnée depuis la base de données
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})
    
    cursor.execute("SELECT p.NomProduit, AVG(e.Prix) FROM evolution e JOIN produit p ON e.NumProduit = p.NumProduit  GROUP BY p.NumProduit")
    result = cursor.fetchall()
    
    # Prédiction des prix des produits en utilisant la moyenne des évolutions précédentes
    prediction = {}
    for row in result:
        produit, prix_moyen = row
        prediction[produit] = prix_moyen
    
    # Fermer la connexion à la base de données
    cursor.close()
    
    return jsonify(prediction)

###############################################################/**Client**/#############################################################################
# select all clients from table client then return them in json

@app.route("/clients", methods=["GET"])
def getClients():
    # connect to db
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})
    try:

        cursor.execute("SELECT * FROM  client")
        clients = cursor.fetchall()
        # Close the cursor and connection
        cursor.close()
        conn.close()
        # Convert products to JSON format
        client_list = []
        for client in clients:
            client_dict = {
                'NumClient': client[0],
                'NomClient': client[1],
                'emailClient': client[2],

            }
            client_list.append(client_dict)
        # Return the products in JSON format
        return jsonify(client_list)
    except Exception as e:
        # Handle any errors that occur during the database query
        return jsonify({'error': str(e)})
    
    
# get one client
@app.route("/client/<int:id>", methods=["GET"])
def getClientById(id):
    # conntect to db
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})

    # select all clients from table client then return them in json
    try:
        cursor.execute(
            "SELECT * FROM client  WHERE  client.NumClient = %s", (id,))
        clients = cursor.fetchall()

        # Close the cursor and connection
        cursor.close()
        conn.close()

        # Convert products to JSON format
        client_list = []
        for client in clients:
            client_dict = {
                'NumClient': client[0],
                'NomClient': client[1],
                'emailClient': client[2],

            }
            client_list.append(client_dict)

        # Return the products in JSON format
        return jsonify(client_list)

    except Exception as e:
        # Handle any errors that occur during the database query
        return jsonify({'error': str(e)})

# Ajouter un nouveau client
@app.route("/client/add", methods=["POST"])
@verify_token
def createClient():
    data = request.get_json()
    print(data)
    nom_client = data.get('NomClient')
    email_client = data.get('emailClient')
    


    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()

    try:
        # Insérer le client dans la table "client"
        cursor.execute(
            "INSERT INTO client (NomClient, emailClient) VALUES (%s, %s)",
            (nom_client, email_client,))
        conn.commit()

        # Fermer la connexion à la base de données
        cursor.close()
        conn.close()

        return jsonify({"message": "Client ajouté avec succès"})
    except Exception as e:
        return jsonify({'error': str(e)})


##add client from csv file
@app.route("/client/addCsv", methods=["POST"])
def createClientFromCsv():
    try:
        # Access the uploaded file
        file = request.files['file']
    except:
        return jsonify({"message": "Veuillez sélectionner un fichier CSV valide, le nom du champ doit être 'file' "})

    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()
    print(file)

    try:
        # Ouvrir le fichier CSV à partir du lien
        content = file.read().decode('utf-8')
        fieldnames = ['id','NomClient', 'emailClient']
        reader = csv.DictReader(StringIO(content), delimiter=';', fieldnames=fieldnames)
        # print(reader)
        # next(reader)

        for row in reader:
            print(row['NomClient'])
            nom_client = row['NomClient']
            email_client = row['emailClient']

            # Insérer le client dans la table "client"
            cursor.execute(
                "INSERT INTO client (NomClient, emailClient) VALUES (%s, %s)",  (nom_client, email_client,))

        conn.commit()
        # Fermer la connexion à la base de données
        cursor.close()
        conn.close()

        return jsonify({"message": "Clients ajoutés avec succès"})
    except Exception as e:
        return jsonify({'error': str(e)})
###Mettre à jour Client

@app.route("/client/<int:id>/update", methods=["PATCH"])
def updateClient(id):
    data = request.get_json()
    nom_client = data.get('NomClient')
    email_client = data.get('emailClient')


    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()


    # Mettre à jour le client dans la table "client"
    cursor.execute(
        "UPDATE client SET NomClient= %s, emailCLient= %s WHERE NumClient = %s",
        (nom_client, email_client,  id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Client mis à jour avec succès"})
###Supprimer le client
@app.route("/client/<int:id>/delete", methods=["DELETE"])
def deleteClient(id):
    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()

    # Supprimer le client
    cursor.execute("DELETE FROM client WHERE NumClient = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Client supprimé avec succès"})

##################################################################/*USERS*/###########################################################################
# get one product
@app.route("/users", methods=["GET"])
def getUsers():
    # conntect to db
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})

    # select all users from table user then return them in json
    try:
        cursor.execute("SELECT username, password, token  FROM user")
        users = cursor.fetchall()
        # Close the cursor and connection
        cursor.close()
        conn.close()
        # Convert products to JSON format
        user_list = []
        
        for user in users:
            print(user)
            user_dict = {
                'username': user[0],
                'password': user[1],
                'api toekn': user[2]

            }
            user_list.append(user_dict)
        # Return the users in JSON format
        return jsonify(user_list)
    except Exception as e:
        # Handle any errors that occur during the database query
        return jsonify({'error': str(e)})



# get one user
@app.route("/user/<int:id>", methods=["GET"])
def getUserById(id):
    # conntect to db
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})

    # select all users from table user then return them in json
    try:
        cursor.execute(
            "SELECT * FROM user  WHERE  id = %s", (id,))
        users = cursor.fetchall()

        # Close the cursor and connection
        cursor.close()
        conn.close()

        # Convert users to JSON format
        user_list = []
        for user in users:
            user_dict = {
                'id': user[0],
                'username': user[1],
                'password': user[2],

            }
            user_list.append(user_dict)

        # Return the products in JSON format
        return jsonify(user_list)

    except Exception as e:
        # Handle any errors that occur during the database query
        return jsonify({'error': str(e)})



@app.route("/user/add", methods=["POST"])
def createUser():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()

    try:
        # Insérer le user dans la table "user"

        cursor.execute(
            "INSERT INTO user (username, password) VALUES (%s, %s)",
            (username, password))
        user_id = cursor.lastrowid  # Récupérer l'ID du nouvel utilisateur

        # Générer un token pour le nouvel utilisateur
        token = generate_token(user_id)
        # Enregistrer le token dans la base de données
        cursor.execute( "UPDATE user SET token = %s WHERE id = %s", (token, user_id))
        
        conn.commit()

        # Fermer la connexion à la base de données
        cursor.close()
        conn.close()

        return jsonify({"message": "Utilisateur ajouté avec succès", "token": token})
    except Exception as e:
        return jsonify({'error': str(e)})



##add user from csv file
@app.route("/user/addCsv", methods=["POST"])
def createUserFromCsv():
    try:
        # Access the uploaded file
        file = request.files['file']
    except:
        return jsonify({"message": "Veuillez sélectionner un fichier CSV valide, le nom du champ doit être 'file' "})

    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()

    try:
        # Ouvrir le fichier CSV à partir du lien
        content = file.read().decode('utf-8')
        fieldnames = ['username', 'password']
        reader = csv.DictReader(StringIO(content), delimiter=';', fieldnames=fieldnames)
        # print(reader)
        # next(reader)

        for row in reader:
            print(row['username'])
            username = row['username']
            password = row['password']

            # Insérer le user dans la table "user"
            cursor.execute(
                "INSERT INTO user (username, password) VALUES (%s, %s)",
                (username, password))

            # Récupérer l'ID du nouvel utilisateur
            user_id = cursor.lastrowid  
            # Générer un token pour le nouvel utilisateur
            token = generate_token(user_id)
            # Enregistrer le token dans la base de données
            cursor.execute( "UPDATE user SET token = %s WHERE id = %s", (token, user_id))

        conn.commit()
        # Fermer la connexion à la base de données
        cursor.close()
        conn.close()

        return jsonify({"message": "Users ajoutés avec succès"})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route("/user/<int:id>/update", methods=["PATCH"])
def updateUser(id):
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')


    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()


    # Mettre à jour le user dans la table "user"
    cursor.execute(
        "UPDATE user SET username=%s, password=%s WHERE id = %s",
        (username, password, id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "User mis à jour avec succès"})


@app.route("/user/<int:id>/delete", methods=["DELETE"])
def deleteUser(id):
    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()

    # Supprimer le user
    cursor.execute("DELETE FROM user WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "User supprimé avec succès"})
##############################################################Acheter###############################################################################

@app.route("/client/<int:id>/buy", methods=["POST"])
def buyProduct(id):
    datas = request.get_json()

    
    # Créer une connexion à la base de données
    conn = mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    cursor = conn.cursor()
    
    for data in datas:
        print(data.get('NumProduit'))
        print(data.get('Qte'))        
        # Mettre à jour le user dans la table "user"
        cursor.execute( "insert into acheter (NumClient, NumProduit, Qte, DateAchat) values (%s, %s, %s, now()) ", (id, data.get('NumProduit'), data.get('Qte')))
        conn.commit()  

    
    cursor.close()
    conn.close()
    return jsonify({"message": "Achat effectué avec succès"})

# get one user
@app.route("/client/<int:id>/allpurchases", methods=["GET"])
def getUserPurchases(id):
    # conntect to db
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        cursor = conn.cursor()
    except Exception as e:
        return jsonify({'error': str(e)})

    # select all users from table user then return them in json
    try:
        cursor.execute(
            "SELECT c.NomClient as client, p.NomProduit as produit, a.Qte as quantite, p.Prix as prix  FROM acheter a, client c, produit p  WHERE a.NumClient = c.NumClient and a.NumProduit = p.NumProduit and  a.NumClient = %s", (id,))
        purchases = cursor.fetchall()

        # Close the cursor and connection
        cursor.close()
        conn.close()


        # Convert users to JSON format
        all_purchase = []
        for pr in purchases:
            purchase_dict = {
                'Client': pr[0],
                'Produit': pr[1],
                'Quantité': pr[2],
                'Prix': pr[3],
                'Total': int(pr[2])*int(pr[3]),

            }
            all_purchase.append(purchase_dict)

        # Return the products in JSON format
        return jsonify(all_purchase)

    except Exception as e:
        # Handle any errors that occur during the database query
        return jsonify({'error': str(e)})
    
##############################################################HELP###############################################################################
@app.route('/help', methods=['GET'])
def api_help():
    documentation = {
        "routes": [
            {
                "route": "/",
                "method": "GET",
                "description": "Liste des produits"
            },
            {
                "route": "/product/id",
                "method": "GET",
                "description": "Affiche le produit avec l'ID"
            },
            {
                "route": "/product/add",
                "method": "POST",
                "description": "Ajoute un produit",
                "data": {
                    "NomProduit": "produit A",
                    "marque": "marque A",
                    "LieuFabrication": "pays A",
                    "prix": 10.99,
                    "NomCatégorie": "categorie A"
                }
            },
            {
                "route": "/product/id/update",
                "method": "PATCH",
                "description": "Modifier le produit avec l'ID",
                "data": {
                    "NomProduit": "produit A",
                    "marque": "marque A",
                    "LieuFabrication": "pays A",
                    "prix": 10.99,
                    "NomCatégorie": "categorie A"
                }
            },
            {
                "route": "/product/id/delete",
                "method": "DELETE",
                "description": "Supprime le produit avec l'ID"
            },
            {
                "route": "/product/addCsv",
                "method": "POST",
                "description": "Ajouter à partir d'un fichier CSV"
            },
            {
                "route": "/product/id/evolution",
                "method": "GET",
                "description": "Affiche l'évolution du prix du produit avec l'ID"
            },
            {
                "route": "/clients",
                "method": "GET",
                "description": "Liste des clients"
            },
            {
                "route": "/client/id",
                "method": "GET",
                "description": "Affiche le client avec l'ID"
            },
            {
                "route": "/client/add",
                "method": "POST",
                "description": "Ajoute un client",
                "data": {
                    "NomClient": "client A"
                }
            },
            {
                "route": "/client/id/update",
                "method": "PATCH",
                "description": "Modifier le client avec l'ID",
                "data": {
                    "NomClient": "client A"
                }
            },
            {
                "route": "/client/id/delete",
                "method": "DELETE",
                "description": "Supprime le client avec l'ID"
            },
            {
                "route": "/client/addCsv",
                "method": "POST",
                "description": "Ajouter à partir d'un fichier CSV"
            },
            {
                "route": "/users",
                "method": "GET",
                "description": "Liste des utilisateurs"
            },
            {
                "route": "/user/id",
                "method": "GET",
                "description": "Affiche l'utilisateur avec l'ID"
            },
            {
                "route": "/user/add",
                "method": "POST",
                "description": "Ajoute un utilisateur",
                "data": {
                    "username": "name A",
                    "password": "password"
                }
            },
            {
                "route": "/user/id/update",
                "method": "PATCH",
                "description": "Modifier l'utilisateur avec l'ID",
                "data": {
                    "username": "name A",
                    "password": "password"
                }
            },
            {
                "route": "/user/id/delete",
                "method": "DELETE",
                "description": "Supprime l'utilisateur avec l'ID"
            },
            {
                "route": "/user/addCsv",
                "method": "POST",
                "description": "Ajouter à partir d'un fichier CSV"
            },
            {
                "route": "/client/id/buy",
                "method": "POST",
                "description": "Ajoute une commande au client avec l'ID",
                "data": [
                    {
                        "NumProduit": 1,
                        "Qte": 12
                    },
                    {
                        "NumProduit": 10,
                        "Qte": 100
                    },
                    {
                        "NumProduit": 10,
                        "Qte": 100
                    }
                ]
            },
            {
                "route": "/client/id/allpurchases",
                "method": "GET",
                "description": "Affiche toutes les commandes du client avec l'ID"
            }
        ]
    }

    return jsonify(documentation)




