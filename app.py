from flask import Flask,flash, render_template, send_file,redirect, jsonify, request
from bson import ObjectId
from bson import json_util as ju
from pymongo.mongo_client import MongoClient
from datetime import datetime
import os
from api import api

app = Flask(__name__)
app.register_blueprint(api,url_prefix='/api')

uri = os.getenv("MONGODB_URI")
# Create a new client and connect to the server
client = MongoClient(uri)
# Send a ping to confirm a successful connection
try:
    client.admin.command("ping")
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

@app.route("/dashboard", methods=["GET", "POST"])
def users():
    if request.method == "POST":
        data = request.form.get
        email = data("email")
        firstName = data("firstName")
        lastName = data("lastName")
        created_at = datetime.now()
        if client.fintech.users.find_one({"email": email}):
            flash("User with specified email exists")
            return redirect("/users")
        client.fintech.users.insert_one(
            {
                "email": email,
                "firstName": firstName,
                "lastName": lastName,
                "created_at": created_at,
                "invoice": [],
            }
        )
        flash("Client created successfully")
        return redirect("/users")
    args = request.args
    id_ = args.get("id")
    if id_:
        user = client.fintech.users.find_one({"_id": ObjectId(id_)})
        return render_template('users.html',user=user)
    users = list(client.fintech.users.find())
    invoice = list(client.fintech.invoice.find())
    paid = [value for value in invoice if value["paid"]]
    Notpaid = [value for value in invoice if not value["paid"]]
    product = list(client.fintech.invoice.find())
    total = sum([i['items'][-1]['Overalltotal'] for i in invoice])
    return render_template('users.html',total=total,users=users,invoice=invoice,paid=paid,Notpaid=Notpaid,product=product)

@app.get("/invoices")
def invoices(): 
    use = client.fintech.users
    inv = client.fintech.invoice.find()
    invoice = [{"user": use.find_one(i['user_id']),"invoice":i,'number':j+1} for j,i in enumerate(inv)]
    return render_template('invoice.html',invoice=invoice)

@app.post("/invoices/issue")
def issue():
    user_id = request.args.get("user_id")
    products = request.json.get("products", [])  # list of dictionaries

    try:
        if not user_id:
            raise ValueError("User ID <user_id> must be present in URL")

        user = client.fintech.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"error": "No user found with such id"}), 404

        if not products:
            raise ValueError("Products must be present in the request JSON")

        product_ids = [item.get("product_id") for item in products]
        product_quantities = [item.get("quantity") for item in products]

        if None in product_ids or None in product_quantities:
            raise ValueError("Product ID and quantity must be specified for each item")

        product_query = {"_id": {"$in": [ObjectId(pid) for pid in product_ids]}}
        products_data = list(client.fintech.products.find(product_query))

        if len(products_data) != len(product_ids):
            raise ValueError("Not all products found with the given product IDs")

        full_items = [
            {
                **product,
                "total": int(product["price"]) * int(quantity),
                "quantity": int(quantity),
            }
            for product, quantity in zip(products_data, product_quantities)
        ]

        total = sum(item["total"] for item in full_items)
        full_items.append({"Overalltotal": total})

        result = client.fintech.invoice.insert_one(
            {
                "created_at": datetime.now(),
                "paid": False,
                "user_id": ObjectId(user_id),
                "items": full_items,
            }
        )

        client.fintech.users.update_one(
            {"_id": ObjectId(user_id)}, {"$push": {"invoice": ObjectId(result.inserted_id)}}
        )

        return (
            ju.dumps(
                {
                    "data": client.fintech.invoice.find_one(
                        {"_id": ObjectId(result.inserted_id)}
                    ),
                    "message": "Data added successfully",
                    "user": client.fintech.users.find_one({"_id": ObjectId(user_id)}),
                }
            ),
            201,
        )

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.post("/invoices/pay")
def pay():
    _id = request.args.get("id")
    if not _id:
        return jsonify({"message": "Invoice ID <id> has to be pressent in URL"})
    invoice = client.fintech.invoice.find_one({"_id": ObjectId(_id)})
    if not invoice:
        return jsonify({"message": "No invoice found with such id"})
    if invoice["paid"]:
        return jsonify({"message": "Invoice already paid"})
    client.fintech.invoice.update_one({"_id": ObjectId(_id)}, {"$set": {"paid": True,"updated_at":datetime.now()}})
    return (
        ju.dumps(
            {
                "data": client.fintech.invoice.find_one({"_id": ObjectId(_id)}),
                "message": "Data added successfully",
                "user": client.fintech.users.find_one(
                    {"_id": ObjectId(invoice["user_id"])}
                ),
            }
        ),
        201,
    )

@app.route("/products",methods=['GET','POST','PUT','DELETE'])
def products():
    if request.method == "POST":
        data = request.json.get
        itemName = data("itemName")
        price = data("price")
        description = data("productDescription")
        if not itemName and not price:
            return jsonify({"message": "Name or Price missing"})
        result = client.fintech.products.insert_one(
        {
            "created_at": datetime.now(),
            "itemName": itemName,
            "price": price,
            "description": description
        }
        )
        return (
        ju.dumps(
            {
                "data": client.fintech.products.find_one(
                    {"_id": ObjectId(result.inserted_id)}
                ),
                "message": "Data added successfully",
            }
        ),
        201,
    )
    if request.method == "PUT":
        args = request.args
        id_ = args.get('id')
        data = request.json.get
        itemName = data("itemName")
        price = data("price")
        description = data("productDescription")
        if not id_:
            return jsonify({"message":"product ID missing in argument"}), 403
        product = client.fintech.products.find_one({"_id":ObjectId(id)})
        if not product:
            return jsonify({"message":"product not found"}), 404
        if not data:
             return jsonify({"message":"Product data cannot be empty"}), 403
        if itemName and itemName != '':
             client.fintech.products.update_one({"_id":ObjectId(id)},{"$set":{"itemName":itemName}})
        if price and price != '':
             client.fintech.products.update_one({"_id":ObjectId(id)},{"$set":{"price":price}})
        if description and description != '':
             client.fintech.products.update_one({"_id":ObjectId(id)},{"$set":{"description": description}})
        return ju.dumps({"data": product,"message":"Updated successfully"}), 200, 
    if request.method == "DELETE":
        args = request.args
        id_ = args.get('id')
        data = request.json.get
        if not id_:
            return jsonify({"message":"product ID missing in argument"}), 403
        client.fintech.products.delete_one({"_id":ObjectId(id)})
        return ju.dumps({"newData": product,"message":"Data deleted successfully"}), 200, 
    args = request.args
    id_ = args.get("id")
    if id_:
        product = client.fintech.products.find_one({"_id": ObjectId(id_)})
        return ju.dumps({"data": product}), 200, 
    product = client.fintech.products.find()
    return ju.dumps({"data": product}), 200


if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0')