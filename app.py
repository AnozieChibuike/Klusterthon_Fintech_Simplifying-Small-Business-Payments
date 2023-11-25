from flask import Flask, render_template, send_file, jsonify, request
from bson import ObjectId
from bson import json_util as ju
from pymongo.mongo_client import MongoClient
from datetime import datetime
import os

app = Flask(__name__)

uri = os.getenv("MONGODB_URI")
# Create a new client and connect to the server
client = MongoClient(uri)
# Send a ping to confirm a successful connection
try:
    client.admin.command("ping")
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

headers = {"Content-Type": "application/json"}

@app.route('/swagger')
def swagger_ui():
    return render_template('swagger_ui.html')

@app.route('/swagger.json')
def swagger_yaml():
    return send_file('swagger_config.json', mimetype='application/json')

@app.route("/users", methods=["GET", "POST"])
def users():
    if request.method == "POST":
        data = request.json.get
        email = data("email")
        firstName = data("firstName")
        lastName = data("lastName")
        if not email and not firstName and not lastName:
            return jsonify(
                {
                    "message": f"Missing required body,Email: {email},FirstName: {firstName}, LastName: {lastName}"
                }
            )
        created_at = datetime.now()
        if client.fintech.users.find_one({"email": email}):
            result = {"message": "User with specified email exists"}
            return jsonify(result), 422
        result = client.fintech.users.insert_one(
            {
                "email": email,
                "firstName": firstName,
                "lastName": lastName,
                "created_at": created_at,
                "invoice": [],
            }
        )
        return (
            ju.dumps(
                {
                    "data": client.fintech.users.find_one(
                        {"_id": ObjectId(result.inserted_id)}
                    ),
                    "message": "Data added successfully",
                }
            ),
            201,
            headers,
        )
    args = request.args
    id_ = args.get("id")
    if id_:
        user = client.fintech.users.find_one({"_id": ObjectId(id_)})
    user = client.fintech.users.find()
    return ju.dumps({"data": user}), 200, headers


@app.get("/invoices")
def invoices():
    args = request.args
    id_ = args.get("id")
    user_id = args.get("user_id")
    status = args.get("status")
    try:
        if id_:
            invoice = client.fintech.invoice.find_one({"_id": ObjectId(id_)})
            return ju.dumps(invoice), 200, headers
        if user_id:
            if status == "paid":
                invoice = client.fintech.invoice.find(
                    {"user_id": ObjectId(user_id), "paid": True}
                )
                return ju.dumps(invoice), 200, headers
            if status == "unpaid":
                invoice = client.fintech.invoice.find(
                    {"user_id": ObjectId(user_id), "paid": False}
                )
                return ju.dumps(invoice), 200, headers
            invoice = client.fintech.invoice.find({"user_id": ObjectId(user_id)})
            return ju.dumps(invoice), 200, headers
    except:
        invoice = {"message": "Invalid type of id"}
        return ju.dumps(invoice), 400, headers
    invoice = client.fintech.invoice.find()
    return ju.dumps(invoice), 200, headers


@app.post("/invoices/issue")
def issue():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"message": "User ID<user_id> has to be pressent in URL"})
    user = client.fintech.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"message": "No user found with such id"})
    items = request.json.get("items")
    if len(items) > 0:
        for i in items:
            if "quantity" not in i.keys() and "price" not in i.keys():
                return jsonify({"message": "Price and quantity missing"})

    fullItems = [{**d, "total": int(d["price"]) * int(d["quantity"])} for d in items]
    total = sum(y["total"] for y in fullItems if "total" in y)
    fullItems.append({"Overalltotal": total})
    if not user_id:
        return jsonify({"message": "User ID has to be pressent in URL"})
    user = client.fintech.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"message": "No user found with such id"})
    result = client.fintech.invoice.insert_one(
        {
            "created_at": datetime.now(),
            "paid": False,
            "user_id": ObjectId(user_id),
            "items": fullItems,
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
        headers,
    )


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
    client.fintech.invoice.update_one({"_id": ObjectId(_id)}, {"$set": {"paid": True}})
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
        headers,
    )


if __name__ == "__main__":
    app.run(debug=True)