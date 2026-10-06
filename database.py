"""
database.py
負責 SQLite 資料庫連線、Schema 建立與繁體中文種子資料初始化。
支援四張資料表: customer, product, orders, order_item 以及管理員資料表 admin_users。
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "orders.db")

def get_db():
    """取得 SQLite 資料庫連線並開啟外鍵約束"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(reset=False):
    """建立資料表與初始管理員帳號及 5 筆繁體中文測試資料"""
    if reset and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass

    conn = get_db()
    cursor = conn.cursor()

    # 1. 管理員帳號資料表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT '管理員'
    );
    """)

    # 2. 客戶資料表 customer (客戶編號 PK、名稱、電話、地址)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer (
        customer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        created_date TEXT NOT NULL DEFAULT (DATE('now'))
    );
    """)

    # 3. 商品資料表 product (商品編號 PK、名稱、單價、庫存、分類)
    # CHECK 約束: 單價 >= 0, 庫存 >= 0
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product (
        product_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL NOT NULL CHECK(price >= 0),
        stock INTEGER NOT NULL CHECK(stock >= 0),
        category TEXT NOT NULL
    );
    """)

    # 4. 訂單資料表 orders (訂單編號 PK、客戶編號 FK、訂單日期、狀態、業務人員)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        order_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('處理中', '已出貨', '已完成', '已取消')),
        sales_rep TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 5. 訂單明細資料表 order_item (訂單編號 FK、商品編號 FK、數量、單價), 複合主鍵
    # CHECK 約束: 數量 > 0, 單價 >= 0
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_item (
        order_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        unit_price REAL NOT NULL CHECK(unit_price >= 0),
        PRIMARY KEY (order_id, product_id),
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES product(product_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 檢查是否已有管理員，無則建立預設管理員 (admin / admin123)
    cursor.execute("SELECT COUNT(*) FROM admin_users;")
    if cursor.fetchone()[0] == 0:
        admin_hash = generate_password_hash("admin123")
        cursor.execute("""
        INSERT INTO admin_users (username, password_hash, name, role)
        VALUES ('admin', ?, '系統管理員', '主管');
        """, (admin_hash,))

    # 檢查是否已有測試資料，若無則插入 5 筆繁體中文測試資料
    cursor.execute("SELECT COUNT(*) FROM customer;")
    if cursor.fetchone()[0] == 0:
        seed_sample_data(cursor)

    conn.commit()
    conn.close()

def seed_sample_data(cursor):
    """插入 5 筆繁體中文測試資料，並包含多項商品之訂單案例"""
    # 客戶資料 (5 筆)
    customers = [
        ('C001', '王小明', '0912-345-678', '台北市信義區市府路45號', '2024-01-10'),
        ('C002', '李美玲', '0921-876-543', '新北市板橋區文化路二段182號', '2024-01-15'),
        ('C003', '張家豪', '0933-112-233', '台中市西屯區台灣大道三段99號', '2024-02-01'),
        ('C004', '陳怡君', '0955-667-788', '台南市東區中華東路一段366號', '2024-02-18'),
        ('C005', '林志偉', '0978-990-112', '高雄市前鎮區中華五路789號', '2024-03-05'),
    ]
    cursor.executemany("""
    INSERT INTO customer (customer_id, name, phone, address, created_date)
    VALUES (?, ?, ?, ?, ?);
    """, customers)

    # 商品資料 (5 筆)
    products = [
        ('P001', '機械式鍵盤 (青軸)', 2490.0, 50, '電腦周邊'),
        ('P002', '人體工學無線滑鼠', 1290.0, 80, '電腦周邊'),
        ('P003', '27吋 4K 護眼螢幕', 8900.0, 25, '顯示設備'),
        ('P004', '降噪藍牙耳罩耳機', 3600.0, 40, '視聽影音'),
        ('P005', '鋁合金折疊筆電架', 890.0, 120, '辦公周邊'),
    ]
    cursor.executemany("""
    INSERT INTO product (product_id, name, price, stock, category)
    VALUES (?, ?, ?, ?, ?);
    """, products)

    # 訂單資料 (5 筆)
    orders = [
        ('ORD-2024001', 'C001', '2024-03-10', '已出貨', '陳大為'),
        ('ORD-2024002', 'C002', '2024-03-12', '已完成', '林思妤'),
        ('ORD-2024003', 'C003', '2024-03-15', '處理中', '陳大為'),
        ('ORD-2024004', 'C001', '2024-03-20', '已完成', '黃建宏'),
        ('ORD-2024005', 'C004', '2024-03-22', '處理中', '林思妤'),
    ]
    cursor.executemany("""
    INSERT INTO orders (order_id, customer_id, order_date, status, sales_rep)
    VALUES (?, ?, ?, ?, ?);
    """, orders)

    # 訂單明細資料 (5 筆，ORD-2024001 包含 2 項商品，驗證多品項訂單案例)
    order_items = [
        ('ORD-2024001', 'P001', 1, 2490.0),  # ORD-2024001 第 1 項 (鍵盤)
        ('ORD-2024001', 'P002', 2, 1290.0),  # ORD-2024001 第 2 項 (滑鼠) - 多項商品案例
        ('ORD-2024002', 'P003', 1, 8900.0),
        ('ORD-2024003', 'P004', 1, 3600.0),
        ('ORD-2024004', 'P005', 3, 890.0),
    ]
    cursor.executemany("""
    INSERT INTO order_item (order_id, product_id, quantity, unit_price)
    VALUES (?, ?, ?, ?);
    """, order_items)

if __name__ == "__main__":
    init_db(reset=True)
    print("Database initialized successfully with schema and sample data.")
