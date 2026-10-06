"""
建立 orders.db 資料庫與相關資料表
包含 customer, product, orders, order_item 四張資料表，並插入測試資料。
"""

import sqlite3
import os
import sys

# 確保在 Windows 命令提示字元 / PowerShell 中正常顯示繁體中文
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DB_FILE = os.path.join(os.path.dirname(__file__), "orders.db")

def create_database():
    # 若舊資料庫存在則先移除，確保全新建立
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"[*] 移除舊的 {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 啟用 SQLite 外鍵約束支援
    cursor.execute("PRAGMA foreign_keys = ON;")

    print("[*] 正在建立資料表與約束條件...")

    # 1. 客戶資料表 customer
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer (
        customer_id TEXT PRIMARY KEY,       -- 客戶編號 (PK)
        name TEXT NOT NULL,                 -- 名稱
        phone TEXT,                         -- 電話
        address TEXT,                       -- 地址
        created_date TEXT NOT NULL          -- 建檔日期
    );
    """)

    # 2. 商品資料表 product
    # CHECK 約束: 單價不可為負 (price >= 0)、庫存不可為負 (stock >= 0)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product (
        product_id TEXT PRIMARY KEY,        -- 商品編號 (PK)
        name TEXT NOT NULL,                 -- 名稱
        price REAL NOT NULL CHECK(price >= 0), -- 單價 (CHECK >= 0)
        stock INTEGER NOT NULL CHECK(stock >= 0), -- 庫存 (CHECK >= 0)
        category TEXT NOT NULL              -- 分類
    );
    """)

    # 3. 訂單資料表 orders
    # 外鍵約束: 客戶編號關聯至 customer(customer_id)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,          -- 訂單編號 (PK)
        customer_id TEXT NOT NULL,          -- 客戶編號 (FK)
        order_date TEXT NOT NULL,           -- 訂單日期
        status TEXT NOT NULL,               -- 狀態 (已出貨/已完成/處理中/待付款等)
        sales_rep TEXT NOT NULL,            -- 業務人員
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 4. 訂單明細資料表 order_item
    # 複合主鍵: (order_id, product_id)
    # CHECK 約束: 數量大於 0 (quantity > 0)、單價不可為負 (unit_price >= 0)
    # unit_price 用於記錄下單當時的價格，保護歷史訂單不受後續商品定價調整影響
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_item (
        order_id TEXT NOT NULL,             -- 訂單編號 (FK)
        product_id TEXT NOT NULL,           -- 商品編號 (FK)
        quantity INTEGER NOT NULL CHECK(quantity > 0),    -- 數量 (CHECK > 0)
        unit_price REAL NOT NULL CHECK(unit_price >= 0),  -- 下單當下单價 (CHECK >= 0)
        PRIMARY KEY (order_id, product_id),
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES product(product_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    print("[*] 正在插入 5 筆繁體中文測試資料...")

    # 1. 客戶資料 (5 筆)
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

    # 2. 商品資料 (5 筆)
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

    # 3. 訂單資料 (5 筆)
    orders = [
        ('ORD-2024001', 'C001', '2024-03-10', '已出貨', '陳大為'),
        ('ORD-2024002', 'C002', '2024-03-12', '已完成', '林思妤'),
        ('ORD-2024003', 'C003', '2024-03-15', '處理中', '陳大為'),
        ('ORD-2024004', 'C001', '2024-03-20', '已完成', '黃建宏'),
        ('ORD-2024005', 'C004', '2024-03-22', '待付款', '林思妤'),
    ]
    cursor.executemany("""
    INSERT INTO orders (order_id, customer_id, order_date, status, sales_rep)
    VALUES (?, ?, ?, ?, ?);
    """, orders)

    # 4. 訂單明細資料 (5 筆)
    # 說明：
    # - ORD-2024001 包含兩項商品 (P001 鍵盤 與 P002 滑鼠)，符合「訂單至少要有含多項商品的案例」
    # - unit_price 保存下單當時單價
    order_items = [
        ('ORD-2024001', 'P001', 1, 2490.0),  # ORD-2024001 第 1 項
        ('ORD-2024001', 'P002', 2, 1290.0),  # ORD-2024001 第 2 項 (多品項訂單)
        ('ORD-2024002', 'P003', 1, 8900.0),
        ('ORD-2024003', 'P004', 1, 3600.0),
        ('ORD-2024004', 'P005', 3, 890.0),
    ]
    cursor.executemany("""
    INSERT INTO order_item (order_id, product_id, quantity, unit_price)
    VALUES (?, ?, ?, ?);
    """, order_items)

    conn.commit()
    conn.close()
    print("[V] orders.db 建立完成，四張資料表已各成功插入 5 筆測試資料！")

if __name__ == "__main__":
    create_database()
