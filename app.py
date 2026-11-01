
import os
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort
)
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid


app = Flask(__name__)

# =====================================================
# CẤU HÌNH TẢI ẢNH SẢN PHẨM
# =====================================================

UPLOAD_FOLDER = os.path.join(
    app.root_path, "static", "uploads", "products"
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Giới hạn tổng dung lượng request (5 MB)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def save_product_image(file):
    """Lưu ảnh sản phẩm; trả về đường dẫn tương đối trong thư mục static."""
    if file is None or not file.filename:
        return None

    original_name = secure_filename(file.filename)
    if "." not in original_name:
        raise ValueError("Tên file ảnh không hợp lệ.")

    extension = original_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Chỉ chấp nhận ảnh PNG, JPG, JPEG hoặc WEBP.")

    filename = f"{uuid.uuid4().hex}.{extension}"
    destination = os.path.join(UPLOAD_FOLDER, filename)
    file.save(destination)

    # Giá trị này được lưu vào cột products.image_url
    return f"uploads/products/{filename}"



# =====================================================
# 1. CẤU HÌNH FLASK
# =====================================================

app.secret_key = "doi_chuoi_bi_mat_nay_thanh_chuoi_rieng_cua_ban"


# =====================================================
# 2. KẾT NỐI MYSQL
# =====================================================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="BepNha!2026_Qn#58",
        database="shop_db",
        charset="utf8mb4"
    )


# =====================================================
# 3. HÀM HỖ TRỢ
# =====================================================

def close_db(cursor=None, conn=None):
    if cursor is not None:
        cursor.close()

    if conn is not None and conn.is_connected():
        conn.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Vui lòng đăng nhập trước.", "warning")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Vui lòng đăng nhập.", "warning")
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            abort(403)

        return view(*args, **kwargs)

    return wrapped_view


# =====================================================
# 4. TRANG CHỦ, TÌM KIẾM VÀ LỌC DANH MỤC
# =====================================================

@app.route("/")
def index():
    keyword = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", "").strip()

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT category_id, category_name, description
            FROM categories
            ORDER BY category_name
        """)
        categories = cursor.fetchall()

        sql = """
            SELECT
                p.product_id,
                p.category_id,
                p.product_name,
                p.description,
                p.price,
                p.image_url,
                p.is_active,
                p.created_at,
                c.category_name
            FROM products p
            LEFT JOIN categories c
                ON p.category_id = c.category_id
            WHERE p.is_active = 1
        """
        params = []

        if keyword:
            sql += " AND p.product_name LIKE %s"
            params.append("%" + keyword + "%")

        if category_id:
            try:
                category_id_int = int(category_id)
                sql += " AND p.category_id = %s"
                params.append(category_id_int)
            except ValueError:
                category_id = ""

        sql += " ORDER BY p.product_id DESC"

        cursor.execute(sql, tuple(params))
        products = cursor.fetchall()

        return render_template(
            "index.html",
            products=products,
            categories=categories,
            keyword=keyword,
            selected_category_id=category_id
        )

    except Error:
        app.logger.exception("Lỗi tải trang chủ")
        return "Lỗi kết nối cơ sở dữ liệu. Hãy kiểm tra cấu hình MySQL.", 500

    finally:
        close_db(cursor, conn)


# =====================================================
# 5. CHI TIẾT SẢN PHẨM
# =====================================================

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                p.product_id,
                p.category_id,
                p.product_name,
                p.description,
                p.price,
                p.image_url,
                c.category_name
            FROM products p
            LEFT JOIN categories c
                ON p.category_id = c.category_id
            WHERE p.product_id = %s
              AND p.is_active = 1
        """, (product_id,))

        product = cursor.fetchone()

        if product is None:
            abort(404)

        cursor.execute("""
            SELECT
                product_id,
                product_name,
                price,
                image_url
            FROM products
            WHERE category_id = %s
              AND product_id != %s
              AND is_active = 1
            ORDER BY product_id DESC
            LIMIT 4
        """, (product["category_id"], product_id))

        related_products = cursor.fetchall()

        return render_template(
            "product_detail.html",
            product=product,
            related_products=related_products
        )

    except Error:
        app.logger.exception("Lỗi tải chi tiết sản phẩm")
        return "Không thể tải chi tiết sản phẩm.", 500

    finally:
        close_db(cursor, conn)


# =====================================================
# 6. ĐĂNG KÝ
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not email or not password:
            flash("Vui lòng nhập đầy đủ thông tin.", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Mật khẩu xác nhận không khớp.", "danger")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Mật khẩu phải có ít nhất 8 ký tự.", "danger")
            return redirect(url_for("register"))

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                "SELECT user_id FROM users WHERE email = %s",
                (email,)
            )

            if cursor.fetchone():
                flash("Email này đã được đăng ký.", "warning")
                return redirect(url_for("register"))

            password_hash = generate_password_hash(password)

            cursor.execute("""
                INSERT INTO users
                    (full_name, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
            """, (
                full_name,
                email,
                password_hash,
                "customer"
            ))

            conn.commit()

            flash("Đăng ký thành công. Hãy đăng nhập.", "success")
            return redirect(url_for("login"))

        except Error:
            if conn and conn.is_connected():
                conn.rollback()

            app.logger.exception("Lỗi đăng ký")
            flash("Không thể đăng ký tài khoản.", "danger")

        finally:
            close_db(cursor, conn)

    return render_template("register.html")


# =====================================================
# 7. ĐĂNG NHẬP
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT
                    user_id,
                    full_name,
                    email,
                    password_hash,
                    role
                FROM users
                WHERE email = %s
            """, (email,))

            user = cursor.fetchone()

            if user and check_password_hash(
                user["password_hash"], password
            ):
                session.clear()
                session["user_id"] = user["user_id"]
                session["full_name"] = user["full_name"]
                session["email"] = user["email"]
                session["role"] = user["role"]

                flash("Đăng nhập thành công.", "success")

                if user["role"] == "admin":
                    return redirect(url_for("admin_dashboard"))

                return redirect(url_for("index"))

            flash("Email hoặc mật khẩu không đúng.", "danger")

        except Error:
            app.logger.exception("Lỗi đăng nhập")
            flash("Không thể đăng nhập.", "danger")

        finally:
            close_db(cursor, conn)

    return render_template("login.html")


# =====================================================
# 8. ĐĂNG XUẤT
# =====================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("Bạn đã đăng xuất.", "success")
    return redirect(url_for("index"))


# =====================================================
# 9. TRANG QUẢN TRỊ
# =====================================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM products")
        total_products = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM categories")
        total_categories = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM users")
        total_users = cursor.fetchone()["total"]

        return render_template(
            "admin/dashboard.html",
            total_products=total_products,
            total_categories=total_categories,
            total_users=total_users
        )

    except Error:
        app.logger.exception("Lỗi trang quản trị")
        return "Không thể tải trang quản trị.", 500

    finally:
        close_db(cursor, conn)


# =====================================================
# 10. DANH SÁCH SẢN PHẨM QUẢN TRỊ
# =====================================================

@app.route("/admin/products")
@admin_required
def admin_products():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT p.*, c.category_name
            FROM products p
            LEFT JOIN categories c
                ON p.category_id = c.category_id
            ORDER BY p.product_id DESC
        """)

        products = cursor.fetchall()

        return render_template(
            "admin/products.html",
            products=products
        )

    except Error:
        app.logger.exception("Lỗi danh sách sản phẩm")
        return "Không thể tải danh sách sản phẩm.", 500

    finally:
        close_db(cursor, conn)


# =====================================================
# 11. THÊM SẢN PHẨM
# =====================================================

@app.route("/admin/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT category_id, category_name
            FROM categories
            ORDER BY category_name
        """)
        categories = cursor.fetchall()

        if request.method == "POST":
            product_name = request.form.get("product_name", "").strip()
            description = request.form.get("description", "").strip()
            category_text = request.form.get("category_id", "").strip()
            price_text = request.form.get("price", "").strip()
            image_file = request.files.get("image_file")

            try:
                image_url = save_product_image(image_file)
            except ValueError as e:
                flash(str(e), "danger")
                return render_template(
                    "admin/product_form.html",
                    categories=categories,
                    product=None
                )

            try:
                category_id = int(category_text)
                price = float(price_text)

                if price < 0:
                    raise ValueError
            except (ValueError, TypeError):
                flash("Danh mục hoặc giá không hợp lệ.", "danger")
                return render_template(
                    "admin/product_form.html",
                    categories=categories,
                    product=None
                )

            if not product_name:
                flash("Vui lòng nhập tên sản phẩm.", "danger")
                return render_template(
                    "admin/product_form.html",
                    categories=categories,
                    product=None
                )

            cursor.execute("""
                INSERT INTO products (
                    category_id, product_name, description,
                    price, image_url, is_active
                )
                VALUES (%s, %s, %s, %s, %s, 1)
            """, (
                category_id,
                product_name,
                description,
                price,
                image_url or None
            ))

            conn.commit()

            flash("Đã thêm sản phẩm.", "success")
            return redirect(url_for("admin_products"))

        return render_template(
            "admin/product_form.html",
            categories=categories,
            product=None
        )

    except Error:
        if conn and conn.is_connected():
            conn.rollback()

        app.logger.exception("Lỗi thêm sản phẩm")
        return "Không thể thêm sản phẩm.", 500

    finally:
        close_db(cursor, conn)


# =====================================================
# 12. SỬA SẢN PHẨM
# =====================================================

@app.route(
    "/admin/products/edit/<int:product_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_product(product_id):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM products WHERE product_id = %s",
            (product_id,)
        )
        product = cursor.fetchone()

        if product is None:
            abort(404)

        cursor.execute("""
            SELECT category_id, category_name
            FROM categories
            ORDER BY category_name
        """)
        categories = cursor.fetchall()

        if request.method == "POST":
            product_name = request.form.get("product_name", "").strip()
            description = request.form.get("description", "").strip()
            category_text = request.form.get("category_id", "").strip()
            price_text = request.form.get("price", "").strip()
            image_file = request.files.get("image_file")
            # Nếu không chọn ảnh mới thì giữ nguyên ảnh đang có
            image_url = product.get("image_url")

            try:
                new_image_url = save_product_image(image_file)
                if new_image_url:
                    image_url = new_image_url
            except ValueError as e:
                flash(str(e), "danger")
                return render_template(
                    "admin/product_form.html",
                    categories=categories,
                    product=product
                )

            is_active = 1 if request.form.get("is_active") == "1" else 0

            try:
                category_id = int(category_text)
                price = float(price_text)

                if price < 0:
                    raise ValueError
            except (ValueError, TypeError):
                flash("Danh mục hoặc giá không hợp lệ.", "danger")
                return render_template(
                    "admin/product_form.html",
                    categories=categories,
                    product=product
                )

            if not product_name:
                flash("Vui lòng nhập tên sản phẩm.", "danger")
                return render_template(
                    "admin/product_form.html",
                    categories=categories,
                    product=product
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
                category_id,
                product_name,
                description,
                price,
                image_url or None,
                is_active,
                product_id
            ))

            conn.commit()

            flash("Đã cập nhật sản phẩm.", "success")
            return redirect(url_for("admin_products"))

        return render_template(
            "admin/product_form.html",
            categories=categories,
            product=product
        )

    except Error:
        if conn and conn.is_connected():
            conn.rollback()

        app.logger.exception("Lỗi sửa sản phẩm")
        return "Không thể cập nhật sản phẩm.", 500

    finally:
        close_db(cursor, conn)


# =====================================================
# 13. ẨN SẢN PHẨM
# =====================================================

@app.route(
    "/admin/products/delete/<int:product_id>",
    methods=["POST"]
)
@admin_required
def delete_product(product_id):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ẩn sản phẩm, không xóa vĩnh viễn khỏi database
        cursor.execute("""
            UPDATE products
            SET is_active = 0
            WHERE product_id = %s
        """, (product_id,))

        conn.commit()
        flash("Đã ẩn sản phẩm khỏi cửa hàng.", "success")

    except Error:
        if conn and conn.is_connected():
            conn.rollback()

        app.logger.exception("Lỗi ẩn sản phẩm")
        flash("Không thể ẩn sản phẩm.", "danger")

    finally:
        close_db(cursor, conn)

    return redirect(url_for("admin_products"))


# =====================================================
# 14. DANH SÁCH DANH MỤC
# =====================================================

@app.route("/admin/categories")
@admin_required
def admin_categories():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                c.category_id,
                c.category_name,
                c.description,
                COUNT(p.product_id) AS product_count
            FROM categories c
            LEFT JOIN products p
                ON c.category_id = p.category_id
            GROUP BY
                c.category_id,
                c.category_name,
                c.description
            ORDER BY c.category_id DESC
        """)

        categories = cursor.fetchall()

        return render_template(
            "admin/categories.html",
            categories=categories
        )

    except Error:
        app.logger.exception("Lỗi tải danh mục")
        return "Không thể tải danh mục.", 500

    finally:
        close_db(cursor, conn)


# =====================================================
# 15. THÊM DANH MỤC
# =====================================================

@app.route("/admin/categories/add", methods=["GET", "POST"])
@admin_required
def add_category():
    if request.method == "POST":
        category_name = request.form.get("category_name", "").strip()
        description = request.form.get("description", "").strip()

        if not category_name:
            flash("Vui lòng nhập tên danh mục.", "danger")
            return redirect(url_for("add_category"))

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO categories (category_name, description)
                VALUES (%s, %s)
            """, (category_name, description))

            conn.commit()

            flash("Đã thêm danh mục.", "success")
            return redirect(url_for("admin_categories"))

        except Error:
            if conn and conn.is_connected():
                conn.rollback()

            app.logger.exception("Lỗi thêm danh mục")
            flash("Không thể thêm danh mục.", "danger")

        finally:
            close_db(cursor, conn)

    return render_template(
        "admin/category_form.html",
        category=None
    )


# =====================================================
# 16. SỬA DANH MỤC
# =====================================================

@app.route(
    "/admin/categories/edit/<int:category_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_category(category_id):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT category_id, category_name, description
            FROM categories
            WHERE category_id = %s
        """, (category_id,))

        category = cursor.fetchone()

        if category is None:
            abort(404)

        if request.method == "POST":
            category_name = request.form.get(
                "category_name", ""
            ).strip()
            description = request.form.get("description", "").strip()

            if not category_name:
                flash("Vui lòng nhập tên danh mục.", "danger")
                return render_template(
                    "admin/category_form.html",
                    category=category
                )

            cursor.execute("""
                UPDATE categories
                SET category_name = %s,
                    description = %s
                WHERE category_id = %s
            """, (
                category_name,
                description,
                category_id
            ))

            conn.commit()

            flash("Đã cập nhật danh mục.", "success")
            return redirect(url_for("admin_categories"))

        return render_template(
            "admin/category_form.html",
            category=category
        )

    except Error:
        if conn and conn.is_connected():
            conn.rollback()

        app.logger.exception("Lỗi sửa danh mục")
        return "Không thể cập nhật danh mục.", 500

    finally:
        close_db(cursor, conn)


# =====================================================
# 17. XÓA DANH MỤC
# =====================================================

@app.route(
    "/admin/categories/delete/<int:category_id>",
    methods=["POST"]
)
@admin_required
def delete_category(category_id):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM products
            WHERE category_id = %s
        """, (category_id,))

        product_count = cursor.fetchone()[0]

        if product_count > 0:
            flash(
                "Danh mục đang có sản phẩm. Hãy chuyển sản phẩm trước khi xóa.",
                "warning"
            )
        else:
            cursor.execute("""
                DELETE FROM categories
                WHERE category_id = %s
            """, (category_id,))

            conn.commit()
            flash("Đã xóa danh mục.", "success")

    except Error:
        if conn and conn.is_connected():
            conn.rollback()

        app.logger.exception("Lỗi xóa danh mục")
        flash("Không thể xóa danh mục.", "danger")

    finally:
        close_db(cursor, conn)

    return redirect(url_for("admin_categories"))


# =====================================================
# 18. XEM SẢN PHẨM THEO DANH MỤC TRONG QUẢN TRỊ
# =====================================================

@app.route("/admin/categories/<int:category_id>/products")
@admin_required
def category_products(category_id):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT category_id, category_name, description
            FROM categories
            WHERE category_id = %s
        """, (category_id,))

        category = cursor.fetchone()

        if category is None:
            abort(404)

        cursor.execute("""
            SELECT p.*, c.category_name
            FROM products p
            LEFT JOIN categories c
                ON p.category_id = c.category_id
            WHERE p.category_id = %s
            ORDER BY p.product_id DESC
        """, (category_id,))

        products = cursor.fetchall()

        return render_template(
            "admin/category_products.html",
            category=category,
            products=products
        )

    except Error:
        app.logger.exception("Lỗi sản phẩm theo danh mục")
        return "Không thể tải sản phẩm của danh mục.", 500

    finally:
        close_db(cursor, conn)


# =====================================================
# 19. TRANG LỖI
# =====================================================

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(error):
    return "Bạn không có quyền truy cập trang này.", 403


# =====================================================
# 20. CHẠY WEBSITE
# =====================================================

if __name__ == "__main__":
    app.run(debug=True)
