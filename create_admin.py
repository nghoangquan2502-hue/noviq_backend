
from werkzeug.security import generate_password_hash
from app import get_connection


def create_admin():
    print("=" * 40)
    print("       TAO TAI KHOAN ADMIN")
    print("=" * 40)

    # Nhap thong tin tai khoan
    full_name = input("Nhap ten Admin: ").strip()
    email = input("Nhap email Admin: ").strip().lower()
    password = input("Nhap mat khau Admin: ")
    confirm_password = input("Nhap lai mat khau: ")

    # Kiem tra du lieu
    if not full_name:
        print("Loi: Ten Admin khong duoc de trong!")
        return

    if not email or "@" not in email:
        print("Loi: Email khong hop le!")
        return

    if len(password) < 8 or len(password) > 128:
        print("Loi: Mat khau phai co tu 8 den 128 ky tu!")
        return

    if password != confirm_password:
        print("Loi: Hai mat khau khong giong nhau!")
        return

    connection = None
    cursor = None

    try:
        # Ket noi MySQL
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Kiem tra email da ton tai chua
        cursor.execute(
            "SELECT user_id FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()

        # Ma hoa mat khau
        password_hash = generate_password_hash(password)

        if user:
            # Cap nhat tai khoan hien co thanh Admin
            print("Email da ton tai. Dang cap nhat quyen Admin...")

            cursor.execute(
                """
                UPDATE users
                SET full_name = %s,
                    password_hash = %s,
                    role = 'admin'
                WHERE user_id = %s
                """,
                (full_name, password_hash, user["user_id"])
            )

            print("Da cap nhat tai khoan thanh Admin!")

        else:
            # Tao tai khoan Admin moi
            cursor.execute(
                """
                INSERT INTO users
                    (full_name, email, password_hash, role)
                VALUES (%s, %s, %s, 'admin')
                """,
                (full_name, email, password_hash)
            )

            print("Da tao tai khoan Admin moi!")

        # Luu thay doi vao database
        connection.commit()

        print("-" * 40)
        print("TAO ADMIN THANH CONG!")
        print("Ten:", full_name)
        print("Email:", email)
        print("Quyen: admin")
        print("Ban co the dang nhap vao website.")
        print("-" * 40)

    except Exception as error:
        if connection:
            connection.rollback()

        print("KHONG THE TAO TAI KHOAN ADMIN!")
        print("Chi tiet loi:", error)

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    create_admin()
