from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_mail import Mail, Message
import socket

app = Flask(__name__)
app.secret_key = "your-secret-key"

# ---------------- FIREBASE CONFIG ----------------
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

students_ref = db.collection("students")
attendance_ref = db.collection("attendance")

# ---------------- FIXED ADMIN CREDENTIALS ----------------
ADMIN_EMAIL = "galennavernaveen@gmail.com"
ADMIN_PASSWORD_HASH = generate_password_hash("1234")  # ADMIN PASSWORD

# ---------------- EMAIL CONFIG ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = "galennavernaveen@gmail.com"
app.config['MAIL_PASSWORD'] = "pepj gaze dacm voiw"  # Gmail App Password
mail = Mail(app)

# ---------------- GET DEVICE LOCAL IP ----------------
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

# ---------------- HOME PAGE ----------------
@app.route("/")
def root():
    return redirect("/home")

@app.route("/home")
def home_page():
    return render_template("home.html")     # YOU MUST CREATE THIS FILE

# ---------------- STUDENT LOGIN ----------------
@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/do_login", methods=["POST"])
def do_login():
    email = request.form.get("email")
    password = request.form.get("password")

    user = students_ref.document(email).get()
    if not user.exists:
        flash("❌ User Not Found!", "error")
        return redirect("/login")

    data = user.to_dict()
    if not check_password_hash(data["password"], password):
        flash("❌ Wrong Password!", "error")
        return redirect("/login")

    return redirect(f"http://{get_ip()}:5000/attendance_capture?email={email}")

# ---------------- STUDENT REGISTER ----------------
@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/do_register", methods=["POST"])
def do_register():
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")

    if students_ref.document(email).get().exists:
        flash("⚠ Student Already Exists!", "error")
        return redirect("/register")

    students_ref.document(email).set({
        "name": name,
        "email": email,
        "password": generate_password_hash(password)
    })

    # SEND EMAIL
    msg = Message(
        subject="Welcome to Fatima College Attendance System",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )
    msg.body = f"""
Hi {name},

Your registration is successful.
You can now login and mark attendance using your smartphone camera.

Regards,
Fatima College IT Team
"""
    mail.send(msg)

    flash("🎉 Registration Successful! Check Gmail & Login", "success")
    return redirect("/login")

# ---------------- ATTENDANCE CAMERA PAGE ----------------
@app.route("/attendance_capture")
def attendance_capture():
    return render_template("capture.html", email=request.args.get("email"))

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    data = request.get_json()
    email = data["email"]
    photo = data["photo"]

    user = students_ref.document(email).get()
    if not user.exists:
        return jsonify({"message": "Invalid User!"})

    attendance_ref.add({
        "email": email,
        "name": user.to_dict()["name"],
        "photo": photo,
        "time": datetime.now()
    })

    return jsonify({
        "message": "Attendance Submitted Successfully!",
        "redirect": f"/student_dashboard?email={email}"
    })

# ---------------- STUDENT DASHBOARD ----------------
@app.route("/student_dashboard")
def student_dashboard():
    email = request.args.get("email")
    user = students_ref.document(email).get().to_dict()
    name = user["name"]

    records = attendance_ref.where("email", "==", email).stream()
    total_days = len(list(records))

    working_days = 30  # change if needed
    percentage = round((total_days / working_days) * 100, 2)
    status = "Present Today" if total_days > 0 else "Not Marked"

    return render_template("student_dashboard.html",
                           name=name,
                           email=email,
                           total_days=total_days,
                           percentage=percentage,
                           status=status,
                           required="75%")

# ---------------- ADMIN LOGIN ----------------
@app.route("/admin")
def admin_page():
    return render_template("admin_login.html")

@app.route("/admin/do_login", methods=["POST"])
def admin_do_login():
    email = request.form.get("email")
    password = request.form.get("password")

    if email != ADMIN_EMAIL:
        flash("❌ Invalid Admin Email!", "error")
        return redirect("/admin")

    if not check_password_hash(ADMIN_PASSWORD_HASH, password):
        flash("❌ Wrong Password!", "error")
        return redirect("/admin")

    session["admin"] = email
    return redirect("/admin/dashboard")

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin")

    logs = [doc.to_dict() for doc in attendance_ref.order_by("time", direction=firestore.Query.DESCENDING).stream()]
    return render_template("admin_dashboard.html", data=logs)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin")

# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
