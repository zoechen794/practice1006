"""
app.py
訂單管理系統 (Flask + SQLite + Bootstrap 5)
主要功能：
- 管理員驗證與登入保護 (admin / admin123)
- 客戶維護 (CRUD)
- 商品維護 (CRUD，CHECK 約束單價>=0、庫存>=0)
- 訂單建立 (客戶下拉選單、商品多選核取方塊與數量填寫、即時金額試算、扣減庫存)
- 保存下單當時成交單價 (order_item.unit_price)，商品後續改價不影響歷史訂單
- 訂單狀態快速切換 (處理中 / 已出貨 / 已完成 / 已取消)
- 專屬出貨單頁面 (/order/<訂單編號>) 與出貨單 QRCode 產生
"""

import os
import io
import base64
from functools import wraps
from datetime import date
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort
)
from werkzeug.security import check_password_hash
import qrcode
from database import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "flask_orders_management_secure_key_2024")

# 自動確認資料庫已建立並含有測試資料
init_db(reset=False)

def login_required(f):
    """管理員登入保護裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("請先登入管理員帳號！", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def generate_qr_code_base64(data_text: str) -> str:
    """產生指定文字或網址之 QR Code 圖片，並轉為 Base64 Data URI"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e293b", back_color="#ffffff")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"

@app.template_filter("currency")
def currency_filter(value):
    """格式化貨幣顯示"""
    try:
        return f"{float(value):,.0f}"
    except (ValueError, TypeError):
        return value

@app.context_processor
def inject_user():
    """全域樣板變數注入"""
    return {
        "current_user": session.get("user"),
        "today_str": date.today().isoformat()
    }

# ==================== 首頁與認證路由 ====================

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT username, password_hash, name, role FROM admin_users WHERE username = ?;", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = {
                "username": user["username"],
                "name": user["name"],
                "role": user["role"]
            }
            flash(f"歡迎回來，{user['name']}！已成功登入系統。", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        else:
            flash("帳號或密碼錯誤，請重新輸入！(預設: admin / admin123)", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("您已安全登出系統。", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    """系統總覽儀表板"""
    conn = get_db()
    cursor = conn.cursor()

    # 統計指標
    cursor.execute("SELECT COUNT(*) FROM orders;")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM customer;")
    total_customers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM product;")
    total_products = cursor.fetchone()[0]

    # 計算總營收 (排除已取消)
    cursor.execute("""
    SELECT COALESCE(SUM(oi.quantity * oi.unit_price), 0)
    FROM order_item oi
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.status != '已取消';
    """)
    total_revenue = cursor.fetchone()[0]

    # 庫存警示 (< 40)
    cursor.execute("SELECT product_id, name, stock, price, category FROM product WHERE stock < 40 ORDER BY stock ASC;")
    low_stock_products = cursor.fetchall()

    # 最新 5 筆訂單
    cursor.execute("""
    SELECT o.order_id, o.order_date, o.status, o.sales_rep, c.name AS customer_name,
           COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_amount,
           COUNT(oi.product_id) AS item_count
    FROM orders o
    JOIN customer c ON o.customer_id = c.customer_id
    LEFT JOIN order_item oi ON o.order_id = oi.order_id
    GROUP BY o.order_id
    ORDER BY o.order_date DESC, o.order_id DESC
    LIMIT 5;
    """)
    recent_orders = cursor.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total_orders=total_orders,
        total_customers=total_customers,
        total_products=total_products,
        total_revenue=total_revenue,
        low_stock_products=low_stock_products,
        recent_orders=recent_orders
    )

# ==================== 客戶維護路由 (Customer CRUD) ====================

@app.route("/customers")
@login_required
def customer_list():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.customer_id, c.name, c.phone, c.address, c.created_date,
           COUNT(o.order_id) AS order_count
    FROM customer c
    LEFT JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_id
    ORDER BY c.customer_id ASC;
    """)
    customers = cursor.fetchall()
    conn.close()
    return render_template("customers.html", customers=customers)

@app.route("/customers/new", methods=["GET", "POST"])
@login_required
def customer_new():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        customer_id = request.form.get("customer_id", "").strip().upper()
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not customer_id or not name:
            flash("客戶編號與客戶名稱為必填項目！", "danger")
            conn.close()
            return render_template("customer_form.html", action="新增", customer=None)

        try:
            cursor.execute("""
            INSERT INTO customer (customer_id, name, phone, address, created_date)
            VALUES (?, ?, ?, ?, DATE('now'));
            """, (customer_id, name, phone, address))
            conn.commit()
            flash(f"客戶 [{customer_id}] {name} 新增成功！", "success")
            conn.close()
            return redirect(url_for("customer_list"))
        except Exception as e:
            conn.rollback()
            flash(f"新增客戶失敗 (編號可能重複)：{e}", "danger")

    # 自動推薦下一組編號
    cursor.execute("SELECT customer_id FROM customer ORDER BY customer_id DESC LIMIT 1;")
    last_row = cursor.fetchone()
    suggested_id = "C001"
    if last_row and last_row[0].startswith("C") and last_row[0][1:].isdigit():
        suggested_id = f"C{int(last_row[0][1:]) + 1:03d}"

    conn.close()
    return render_template("customer_form.html", action="新增", customer={"customer_id": suggested_id})

@app.route("/customers/<customer_id>/edit", methods=["GET", "POST"])
@login_required
def customer_edit(customer_id):
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            flash("客戶姓名不能為空！", "danger")
        else:
            try:
                cursor.execute("""
                UPDATE customer SET name = ?, phone = ?, address = ?
                WHERE customer_id = ?;
                """, (name, phone, address, customer_id))
                conn.commit()
                flash(f"客戶 [{customer_id}] 資料已更新！", "success")
                conn.close()
                return redirect(url_for("customer_list"))
            except Exception as e:
                flash(f"更新失敗：{e}", "danger")

    cursor.execute("SELECT * FROM customer WHERE customer_id = ?;", (customer_id,))
    customer = cursor.fetchone()
    conn.close()

    if not customer:
        flash("找不到指定的客戶！", "warning")
        return redirect(url_for("customer_list"))

    return render_template("customer_form.html", action="編輯", customer=customer)

@app.route("/customers/<customer_id>/delete", methods=["POST"])
@login_required
def customer_delete(customer_id):
    conn = get_db()
    cursor = conn.cursor()

    # 外鍵檢查：是否有訂單關聯
    cursor.execute("SELECT COUNT(*) FROM orders WHERE customer_id = ?;", (customer_id,))
    order_count = cursor.fetchone()[0]
    if order_count > 0:
        flash(f"無法刪除客戶 [{customer_id}]！該客戶已有 {order_count} 筆關聯訂單，受到外鍵約束保護。", "danger")
        conn.close()
        return redirect(url_for("customer_list"))

    try:
        cursor.execute("DELETE FROM customer WHERE customer_id = ?;", (customer_id,))
        conn.commit()
        flash(f"客戶 [{customer_id}] 已成功刪除！", "success")
    except Exception as e:
        flash(f"刪除失敗：{e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("customer_list"))

# ==================== 商品維護路由 (Product CRUD) ====================

@app.route("/products")
@login_required
def product_list():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT p.product_id, p.name, p.price, p.stock, p.category,
           COALESCE(SUM(oi.quantity), 0) AS total_sold
    FROM product p
    LEFT JOIN order_item oi ON p.product_id = oi.product_id
    GROUP BY p.product_id
    ORDER BY p.product_id ASC;
    """)
    products = cursor.fetchall()
    conn.close()
    return render_template("products.html", products=products)

@app.route("/products/new", methods=["GET", "POST"])
@login_required
def product_new():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        product_id = request.form.get("product_id", "").strip().upper()
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        try:
            price = float(request.form.get("price", 0))
            stock = int(request.form.get("stock", 0))
        except ValueError:
            flash("單價與庫存必須為有效數值！", "danger")
            conn.close()
            return render_template("product_form.html", action="新增", product=None)

        if price < 0 or stock < 0:
            flash("單價與庫存不可為負數 (CHECK 約束)！", "danger")
            conn.close()
            return render_template("product_form.html", action="新增", product=None)

        try:
            cursor.execute("""
            INSERT INTO product (product_id, name, price, stock, category)
            VALUES (?, ?, ?, ?, ?);
            """, (product_id, name, price, stock, category))
            conn.commit()
            flash(f"商品 [{product_id}] {name} 已成功新增！", "success")
            conn.close()
            return redirect(url_for("product_list"))
        except Exception as e:
            conn.rollback()
            flash(f"新增商品失敗 (編號可能重複或違反 CHECK 約束)：{e}", "danger")

    # 自動推薦編號
    cursor.execute("SELECT product_id FROM product ORDER BY product_id DESC LIMIT 1;")
    last_row = cursor.fetchone()
    suggested_id = "P001"
    if last_row and last_row[0].startswith("P") and last_row[0][1:].isdigit():
        suggested_id = f"P{int(last_row[0][1:]) + 1:03d}"

    conn.close()
    return render_template("product_form.html", action="新增", product={"product_id": suggested_id, "price": 0, "stock": 10})

@app.route("/products/<product_id>/edit", methods=["GET", "POST"])
@login_required
def product_edit(product_id):
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        try:
            price = float(request.form.get("price", 0))
            stock = int(request.form.get("stock", 0))
        except ValueError:
            flash("單價與庫存必須為有效數值！", "danger")
            price = -1

        if price < 0 or stock < 0:
            flash("單價與庫存不可為負數 (CHECK 約束)！", "danger")
        else:
            try:
                cursor.execute("""
                UPDATE product SET name = ?, price = ?, stock = ?, category = ?
                WHERE product_id = ?;
                """, (name, price, stock, category, product_id))
                conn.commit()
                flash(f"商品 [{product_id}] 已更新！請注意：歷史訂單中已記錄之成交單價不受改價影響。", "success")
                conn.close()
                return redirect(url_for("product_list"))
            except Exception as e:
                flash(f"更新失敗：{e}", "danger")

    cursor.execute("SELECT * FROM product WHERE product_id = ?;", (product_id,))
    product = cursor.fetchone()
    conn.close()

    if not product:
        flash("找不到指定的商品！", "warning")
        return redirect(url_for("product_list"))

    return render_template("product_form.html", action="編輯", product=product)

@app.route("/products/<product_id>/delete", methods=["POST"])
@login_required
def product_delete(product_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM order_item WHERE product_id = ?;", (product_id,))
    item_count = cursor.fetchone()[0]
    if item_count > 0:
        flash(f"無法刪除商品 [{product_id}]！已有 {item_count} 筆歷史訂單明細包含此商品，外鍵保護中。", "danger")
        conn.close()
        return redirect(url_for("product_list"))

    try:
        cursor.execute("DELETE FROM product WHERE product_id = ?;", (product_id,))
        conn.commit()
        flash(f"商品 [{product_id}] 已成功刪除！", "success")
    except Exception as e:
        flash(f"刪除失敗：{e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("product_list"))

# ==================== 訂單管理路由 (Orders Management) ====================

@app.route("/orders")
@login_required
def order_list():
    """訂單列表頁面 (可在列表直接快速更新訂單狀態)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT o.order_id, o.order_date, o.status, o.sales_rep,
           c.customer_id, c.name AS customer_name,
           COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_amount,
           COUNT(oi.product_id) AS item_count
    FROM orders o
    JOIN customer c ON o.customer_id = c.customer_id
    LEFT JOIN order_item oi ON o.order_id = oi.order_id
    GROUP BY o.order_id
    ORDER BY o.order_date DESC, o.order_id DESC;
    """)
    orders = cursor.fetchall()
    conn.close()
    return render_template("orders.html", orders=orders)

@app.route("/orders/<order_id>/status", methods=["POST"])
@login_required
def order_update_status(order_id):
    """直接在列表更新訂單狀態 (支援 AJAX 與傳統表單)"""
    new_status = request.form.get("status") or (request.get_json() or {}).get("status")
    allowed_statuses = ["處理中", "已出貨", "已完成", "已取消"]

    if new_status not in allowed_statuses:
        if request.is_json:
            return jsonify({"success": False, "error": "無效的訂單狀態"}), 400
        flash("無效的訂單狀態！", "danger")
        return redirect(url_for("order_list"))

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?;", (new_status, order_id))
        conn.commit()
        conn.close()

        if request.is_json:
            return jsonify({"success": True, "order_id": order_id, "status": new_status})

        flash(f"訂單 [{order_id}] 狀態已變更為「{new_status}」！", "success")
    except Exception as e:
        conn.close()
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        flash(f"更新狀態失敗：{e}", "danger")

    return redirect(url_for("order_list"))

@app.route("/orders/new", methods=["GET", "POST"])
@login_required
def order_new():
    """新增訂單：客戶下拉選單、商品一次勾選多項並填寫數量、鎖定下單當下價格"""
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        order_id = request.form.get("order_id", "").strip().upper()
        customer_id = request.form.get("customer_id", "").strip()
        order_date = request.form.get("order_date", "").strip() or date.today().isoformat()
        status = request.form.get("status", "處理中").strip()
        sales_rep = request.form.get("sales_rep", "").strip() or session.get("user", {}).get("name", "業務代表")

        # 取得勾選的多項商品
        selected_product_ids = request.form.getlist("product_ids")

        if not order_id or not customer_id:
            flash("請填寫訂單編號並選擇客戶！", "danger")
            conn.close()
            return redirect(url_for("order_new"))

        if not selected_product_ids:
            flash("請至少勾選一項要訂購的商品！", "danger")
            conn.close()
            return redirect(url_for("order_new"))

        # 檢驗選取的商品與數量
        items_to_insert = []
        for pid in selected_product_ids:
            try:
                qty = int(request.form.get(f"quantity_{pid}", 1))
            except ValueError:
                qty = 1

            if qty <= 0:
                flash(f"商品編號 [{pid}] 數量必須大於 0 (CHECK 約束)！", "danger")
                conn.close()
                return redirect(url_for("order_new"))

            # 查詢商品目前價格與庫存 (取得當前單價以保存至 order_item)
            cursor.execute("SELECT product_id, name, price, stock FROM product WHERE product_id = ?;", (pid,))
            prod = cursor.fetchone()
            if not prod:
                flash(f"商品 [{pid}] 不存在！", "danger")
                conn.close()
                return redirect(url_for("order_new"))

            if prod["stock"] < qty:
                flash(f"商品 [{prod['name']}] 庫存不足 (現有庫存: {prod['stock']}，欲訂購: {qty})！", "danger")
                conn.close()
                return redirect(url_for("order_new"))

            # 保存 (order_id, product_id, quantity, unit_price)
            # 重點要求：unit_price 鎖定下單當下的 prod['price']
            items_to_insert.append({
                "product_id": pid,
                "quantity": qty,
                "unit_price": prod["price"]
            })

        # 開始資料庫寫入 (事務交易)
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("""
            INSERT INTO orders (order_id, customer_id, order_date, status, sales_rep)
            VALUES (?, ?, ?, ?, ?);
            """, (order_id, customer_id, order_date, status, sales_rep))

            for item in items_to_insert:
                cursor.execute("""
                INSERT INTO order_item (order_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?);
                """, (order_id, item["product_id"], item["quantity"], item["unit_price"]))

                # 扣減商品庫存
                cursor.execute("""
                UPDATE product SET stock = stock - ? WHERE product_id = ?;
                """, (item["quantity"], item["product_id"]))

            conn.commit()
            flash(f"訂單 [{order_id}] 建立成功！已鎖定當時商品單價並扣減相應庫存。", "success")
            conn.close()
            return redirect(url_for("order_detail", order_id=order_id))

        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f"建立訂單失敗：{e}", "danger")
            return redirect(url_for("order_new"))

    # GET 請求：準備下拉客戶清單與商品清單
    cursor.execute("SELECT customer_id, name, phone, address FROM customer ORDER BY customer_id ASC;")
    customers = cursor.fetchall()

    cursor.execute("SELECT product_id, name, price, stock, category FROM product ORDER BY category, product_id;")
    products = cursor.fetchall()

    # 自動推薦訂單編號
    cursor.execute("SELECT order_id FROM orders ORDER BY order_id DESC LIMIT 1;")
    last_order = cursor.fetchone()
    next_order_id = "ORD-2024006"
    if last_order and "ORD-" in last_order[0]:
        try:
            num = int(last_order[0].replace("ORD-", ""))
            next_order_id = f"ORD-{num + 1}"
        except ValueError:
            pass

    conn.close()
    return render_template(
        "order_new.html",
        customers=customers,
        products=products,
        next_order_id=next_order_id
    )

@app.route("/orders/<order_id>/delete", methods=["POST"])
@login_required
def order_delete(order_id):
    """刪除訂單 (外鍵串聯刪除 order_item)"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM orders WHERE order_id = ?;", (order_id,))
        conn.commit()
        flash(f"訂單 [{order_id}] 及其相關明細已成功刪除！", "success")
    except Exception as e:
        flash(f"刪除失敗：{e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("order_list"))

# ==================== 專屬訂單頁面與出貨單 QRCode ====================

@app.route("/order/<order_id>")
def order_detail(order_id):
    """
    每張訂單有專屬頁面 /order/<訂單編號>，並產生出貨單 QRCode
    此頁面可作為出貨單 / 揀貨單列印，手機掃描 QRCode 亦可直接開啟查驗。
    """
    conn = get_db()
    cursor = conn.cursor()

    # 查詢訂單主檔與客戶資訊
    cursor.execute("""
    SELECT o.order_id, o.order_date, o.status, o.sales_rep,
           c.customer_id, c.name AS customer_name, c.phone, c.address
    FROM orders o
    JOIN customer c ON o.customer_id = c.customer_id
    WHERE o.order_id = ?;
    """, (order_id,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        flash(f"找不到訂單編號 [{order_id}]！", "warning")
        return redirect(url_for("order_list"))

    # 查詢訂單明細 (order_item 保存的當時單價 unit_price 與當前 product 資訊)
    cursor.execute("""
    SELECT oi.product_id, oi.quantity, oi.unit_price,
           (oi.quantity * oi.unit_price) AS subtotal,
           p.name AS product_name, p.category, p.price AS current_product_price
    FROM order_item oi
    JOIN product p ON oi.product_id = p.product_id
    WHERE oi.order_id = ?
    ORDER BY oi.product_id ASC;
    """, (order_id,))
    items = cursor.fetchall()
    conn.close()

    total_amount = sum(item["subtotal"] for item in items)
    total_qty = sum(item["quantity"] for item in items)

    # 產生專屬出貨單 QRCode：編碼此專屬頁面的完整 URL
    target_url = request.url
    qr_code_b64 = generate_qr_code_base64(target_url)

    return render_template(
        "order_detail.html",
        order=order,
        items=items,
        total_amount=total_amount,
        total_qty=total_qty,
        qr_code_b64=qr_code_b64,
        target_url=target_url
    )

if __name__ == "__main__":
    # 本地測試啟動
    print("=" * 60)
    print("  Flask 訂單管理系統已就緒")
    print("  本機存取網址: http://127.0.0.1:5000")
    print("  預設管理員帳號: admin")
    print("  預設管理員密碼: admin123")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
