
import os
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

# =====================================================
# 1. CAU HINH FLASK
# =====================================================

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "doi-chuoi-nay-thanh-khoa-bi-mat-rieng"
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =====================================================
# 2. KET NOI MYSQL
# =====================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "BepNha!2026_Qn#58",
    "database": "shop_db",
}


def get_connection():
    """Tao ket noi den MySQL."""
    return mysql.connector.connect(**DB_CONFIG)


# =====================================================
# 3. CAC HAM HO TRO
# =====================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_uploaded_image(file):
    """Luu anh upload, tra ve duong dan tuong doi trong static."""
    if not file or not file.filename:
        return None

    if not allowed_file(file.filename):
        raise ValueError("Chi chap nhan anh PNG, JPG, JPEG hoac WEBP.")

    filename = secure_filename(file.filename)
    name, extension = os.path.splitext(filename)
    filename = f"{name}_{os.urandom(4).hex()}{extension.lower()}"

    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return f"uploads/{filename}"


def admin_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Vui long dang nhap truoc.", "error")
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            flash("Ban khong co quyen truy cap trang quan tri.", "error")
            return redirect(url_for("index"))

        return view_function(*args, **kwargs)

    return wrapped_view


def close_db(cursor=None, conn=None):
    if cursor is not None:
        cursor.close()
    if conn is not None and conn.is_connected():
        conn.close()


@app.errorhandler(413)
def file_too_large(error):
    flash("Anh vuot qua dung luong toi da 5 MB.", "error")
    return redirect(request.referrer or url_for("admin_products"))


# =====================================================
# 4. TRANG CHU
# =====================================================

@app.route("/")
def index():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT product_id, category_id, product_name,
                   description, price, image_url, is_active
            FROM products
            WHERE is_active = 1
            ORDER BY product_id DESC
        """)
        products = cursor.fetchall()

        cursor.execute("""
            SELECT category_id, category_name, description
            FROM categories
            ORDER BY category_name
        """)
        categories = cursor.fetchall()

        return render_template(
            "index.html",
            products=products,
            categories=categories
        )
    finally:
        close_db(cursor, conn)


# =====================================================
# 5. DANG KY
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not full_name or not email or not password:
            flash("Vui long nhap day du thong tin.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Mat khau phai co it nhat 6 ky tu.", "error")
            return render_template("register.html")

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT user_id FROM users WHERE email = %s",
                (email,)
            )
            if cursor.fetchone():
                flash("Email nay da duoc dang ky.", "error")
                return render_template("register.html")

            password_hash = generate_password_hash(password)

            cursor.execute("""
                INSERT INTO users (full_name, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
            """, (full_name, email, password_hash, "customer"))

            conn.commit()
            flash("Dang ky thanh cong. Hay dang nhap.", "success")
            return redirect(url_for("login"))

        finally:
            close_db(cursor, conn)

    return render_template("register.html")


# =====================================================
# 6. DANG NHAP
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("""
                SELECT user_id, full_name, email, password_hash, role
                FROM users
                WHERE email = %s
            """, (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["user_id"]
                session["full_name"] = user["full_name"]
                session["email"] = user["email"]
                session["role"] = user["role"]

                flash("Dang nhap thanh cong.", "success")

                if user["role"] == "admin":
                    return redirect(url_for("admin"))

                return redirect(url_for("index"))

            flash("Email hoac mat khau khong dung.", "error")

        finally:
            close_db(cursor, conn)

    return render_template("login.html")


# =====================================================
# 7. DANG XUAT
# =====================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("Ban da dang xuat.", "success")
    return redirect(url_for("index"))


# =====================================================
# 8. TRANG QUAN TRI
# =====================================================

@app.route("/admin")
@admin_required
def admin():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT COUNT(*) AS total FROM products")
        total_products = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM categories")
        total_categories = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM users")
        total_users = cursor.fetchone()["total"]

        return render_template(
            "admin.html",
            total_products=total_products,
            total_categories=total_categories,
            total_users=total_users
        )
    finally:
        close_db(cursor, conn)


# =====================================================
# 9. QUAN LY SAN PHAM
# =====================================================

@app.route("/admin/products")
@admin_required
def admin_products():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT p.product_id, p.product_name, p.description,
                   p.price, p.image_url, p.is_active,
                   p.category_id, c.category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.category_id
            ORDER BY p.product_id DESC
        """)
        products = cursor.fetchall()

        return render_template("admin_products.html", products=products)
    finally:
        close_db(cursor, conn)


@app.route("/admin/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT category_id, category_name
            FROM categories ORDER BY category_name
        """)
        categories = cursor.fetchall()

        if request.method == "POST":
            product_name = request.form.get("product_name", "").strip()
            description = request.form.get("description", "").strip()
            price_text = request.form.get("price", "").strip()
            category_text = request.form.get("category_id", "").strip()
            is_active = 1 if request.form.get("is_active") else 0

            if not product_name or not price_text:
                flash("Ten san pham va gia la bat buoc.", "error")
                return render_template(
                    "add_product.html", categories=categories
                )

            try:
                price = float(price_text)
                if price < 0:
                    raise ValueError
            except ValueError:
                flash("Gia san pham khong hop le.", "error")
                return render_template(
                    "add_product.html", categories=categories
                )

            category_id = int(category_text) if category_text else None
            image_url = None

            try:
                image_url = save_uploaded_image(request.files.get("image"))
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template(
                    "add_product.html", categories=categories
                )

            cursor.execute("""
                INSERT INTO products
                    (category_id, product_name, description, price,
                     image_url, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                category_id, product_name, description or None,
                price, image_url, is_active
            ))
            conn.commit()

            flash("Them san pham thanh cong.", "success")
            return redirect(url_for("admin_products"))

        return render_template("add_product.html", categories=categories)
    finally:
        close_db(cursor, conn)


@app.route("/admin/products/edit/<int:product_id>", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM products WHERE product_id = %s",
            (product_id,)
        )
        product = cursor.fetchone()

        if not product:
            flash("Khong tim thay san pham.", "error")
            return redirect(url_for("admin_products"))

        cursor.execute("""
            SELECT category_id, category_name
            FROM categories ORDER BY category_name
        """)
        categories = cursor.fetchall()

        if request.method == "POST":
            product_name = request.form.get("product_name", "").strip()
            description = request.form.get("description", "").strip()
            price_text = request.form.get("price", "").strip()
            category_text = request.form.get("category_id", "").strip()
            is_active = 1 if request.form.get("is_active") else 0

            if not product_name or not price_text:
                flash("Ten san pham va gia la bat buoc.", "error")
                return render_template(
                    "edit_product.html",
                    product=product, categories=categories
                )

            try:
                price = float(price_text)
                if price < 0:
                    raise ValueError
            except ValueError:
                flash("Gia san pham khong hop le.", "error")
                return render_template(
                    "edit_product.html",
                    product=product, categories=categories
                )

            category_id = int(category_text) if category_text else None
            image_url = product["image_url"]

            try:
                new_image = save_uploaded_image(request.files.get("image"))
                if new_image:
                    image_url = new_image
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template(
                    "edit_product.html",
                    product=product, categories=categories
                )

            cursor.execute("""
                UPDATE products
                SET category_id = %s,
                    product_name = %s,
                    description = %s,
                    price = %s,
                    image_url = %s,
                    is_active = %s
                WHERE product_id = %s
            """, (
                category_id, product_name, description or None,
                price, image_url, is_active, product_id
            ))
            conn.commit()

            flash("Cap nhat san pham thanh cong.", "success")
            return redirect(url_for("admin_products"))

        return render_template(
            "edit_product.html", product=product, categories=categories
        )
    finally:
        close_db(cursor, conn)


@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
@admin_required
def delete_product(product_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM products WHERE product_id = %s",
            (product_id,)
        )
        conn.commit()
        flash("Da xoa san pham.", "success")
    finally:
        close_db(cursor, conn)

    return redirect(url_for("admin_products"))


@app.route("/admin/products/toggle/<int:product_id>", methods=["POST"])
@admin_required
def toggle_product(product_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE products
            SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
            WHERE product_id = %s
        """, (product_id,))
        conn.commit()
        flash("Da cap nhat trang thai san pham.", "success")
    finally:
        close_db(cursor, conn)

    return redirect(url_for("admin_products"))


# =====================================================
# 10. QUAN LY DANH MUC
# =====================================================

@app.route("/admin/categories")
@admin_required
def admin_categories():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                c.category_id,
                c.category_name,
                c.description,
                COUNT(p.product_id) AS product_count
            FROM categories c
            LEFT JOIN products p ON c.category_id = p.category_id
            GROUP BY c.category_id, c.category_name, c.description
            ORDER BY c.category_id DESC
        """)
        categories = cursor.fetchall()

        return render_template(
            "admin_categories.html", categories=categories
        )
    finally:
        close_db(cursor, conn)


# Bấm vào tên danh mục để xem sản phẩm bên trong
@app.route("/admin/categories/<int:category_id>/products")
@admin_required
def category_products(category_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT category_id, category_name, description
            FROM categories
            WHERE category_id = %s
        """, (category_id,))
        category = cursor.fetchone()

        if not category:
            flash("Khong tim thay danh muc.", "error")
            return redirect(url_for("admin_categories"))

        cursor.execute("""
            SELECT product_id, product_name, description,
                   price, image_url, is_active
            FROM products
            WHERE category_id = %s
            ORDER BY product_id DESC
        """, (category_id,))
        products = cursor.fetchall()

        return render_template(
            "category_products.html",
            category=category,
            products=products
        )
    finally:
        close_db(cursor, conn)


@app.route("/admin/categories/add", methods=["GET", "POST"])
@admin_required
def add_category():
    if request.method == "POST":
        category_name = request.form.get("category_name", "").strip()
        description = request.form.get("description", "").strip()

        if not category_name:
            flash("Vui long nhap ten danh muc.", "error")
            return render_template("add_category.html")

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO categories (category_name, description)
                VALUES (%s, %s)
            """, (category_name, description or None))
            conn.commit()

            flash("Them danh muc thanh cong.", "success")
            return redirect(url_for("admin_categories"))
        except Error as exc:
            conn.rollback()
            flash(f"Khong the them danh muc: {exc}", "error")
        finally:
            close_db(cursor, conn)

    return render_template("add_category.html")


@app.route(
    "/admin/categories/edit/<int:category_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_category(category_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT category_id, category_name, description
            FROM categories WHERE category_id = %s
        """, (category_id,))
        category = cursor.fetchone()

        if not category:
            flash("Khong tim thay danh muc.", "error")
            return redirect(url_for("admin_categories"))

        if request.method == "POST":
            category_name = request.form.get(
                "category_name", ""
            ).strip()
            description = request.form.get("description", "").strip()

            if not category_name:
                flash("Vui long nhap ten danh muc.", "error")
                return render_template(
                    "edit_category.html", category=category
                )

            cursor.execute("""
                UPDATE categories
                SET category_name = %s, description = %s
                WHERE category_id = %s
            """, (
                category_name, description or None, category_id
            ))
            conn.commit()

            flash("Cap nhat danh muc thanh cong.", "success")
            return redirect(url_for("admin_categories"))

        return render_template("edit_category.html", category=category)
    finally:
        close_db(cursor, conn)


@app.route(
    "/admin/categories/delete/<int:category_id>",
    methods=["POST"]
)
@admin_required
def delete_category(category_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT COUNT(*) FROM products WHERE category_id = %s
        """, (category_id,))
        product_count = cursor.fetchone()[0]

        if product_count > 0:
            flash(
                "Danh muc dang co san pham. "
                "Hay chuyen san pham sang danh muc khac truoc khi xoa.",
                "error"
            )
            return redirect(url_for("admin_categories"))

        cursor.execute("""
            DELETE FROM categories WHERE category_id = %s
        """, (category_id,))
        conn.commit()

        flash("Da xoa danh muc.", "success")
    finally:
        close_db(cursor, conn)

    return redirect(url_for("admin_categories"))


# =====================================================
# 11. CHAY UNG DUNG
# =====================================================

if __name__ == "__main__":
    app.run(debug=True)
