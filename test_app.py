"""
測試 Flask 應用程式端點與資料庫完整性
"""

import unittest
from app import app
from database import get_db, init_db

class TestOrderSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db(reset=False)
        app.config['TESTING'] = True
        cls.client = app.test_client()

    def test_01_login_page_renders(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn('管理員登入'.encode('utf-8'), response.data)

    def test_02_login_successful(self):
        response = self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('系統營運總覽'.encode('utf-8'), response.data)

    def test_03_dashboard_authenticated(self):
        with self.client.session_transaction() as sess:
            sess['user'] = {'username': 'admin', 'name': '系統管理員', 'role': '主管'}
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn('系統營運總覽'.encode('utf-8'), response.data)

    def test_04_customers_page(self):
        with self.client.session_transaction() as sess:
            sess['user'] = {'username': 'admin', 'name': '系統管理員', 'role': '主管'}
        response = self.client.get('/customers')
        self.assertEqual(response.status_code, 200)
        self.assertIn('王小明'.encode('utf-8'), response.data)

    def test_05_products_page(self):
        with self.client.session_transaction() as sess:
            sess['user'] = {'username': 'admin', 'name': '系統管理員', 'role': '主管'}
        response = self.client.get('/products')
        self.assertEqual(response.status_code, 200)
        self.assertIn('機械式鍵盤 (青軸)'.encode('utf-8'), response.data)

    def test_06_orders_page(self):
        with self.client.session_transaction() as sess:
            sess['user'] = {'username': 'admin', 'name': '系統管理員', 'role': '主管'}
        response = self.client.get('/orders')
        self.assertEqual(response.status_code, 200)
        self.assertIn('ORD-2024001'.encode('utf-8'), response.data)

    def test_07_order_detail_page_and_qrcode(self):
        response = self.client.get('/order/ORD-2024001')
        self.assertEqual(response.status_code, 200)
        # 驗證出貨單標題
        self.assertIn('物流出貨單'.encode('utf-8'), response.data)
        # 驗證多項商品 (P001 鍵盤 + P002 滑鼠)
        self.assertIn('機械式鍵盤 (青軸)'.encode('utf-8'), response.data)
        self.assertIn('人體工學無線滑鼠'.encode('utf-8'), response.data)
        # 驗證包含 QR Code base64
        self.assertIn('data:image/png;base64,'.encode('utf-8'), response.data)

    def test_08_inline_status_update(self):
        with self.client.session_transaction() as sess:
            sess['user'] = {'username': 'admin', 'name': '系統管理員', 'role': '主管'}
        response = self.client.post('/orders/ORD-2024001/status', json={'status': '已完成'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], '已完成')

    def test_09_create_new_order_with_multiple_products(self):
        with self.client.session_transaction() as sess:
            sess['user'] = {'username': 'admin', 'name': '系統管理員', 'role': '主管'}

        # 查詢目前 P001 價格與庫存
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT price, stock FROM product WHERE product_id = 'P001';")
        row = cursor.fetchone()
        price_before = row['price']
        stock_before = row['stock']
        conn.close()

        # 提交新增訂單
        post_data = {
            'order_id': 'ORD-TEST-099',
            'customer_id': 'C001',
            'order_date': '2024-04-01',
            'status': '處理中',
            'sales_rep': '測試業務',
            'product_ids': ['P001', 'P002'],
            'quantity_P001': '2',
            'quantity_P002': '1'
        }
        response = self.client.post('/orders/new', data=post_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # 驗證 order_item 中的 unit_price 是否正確保存下單價格
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM order_item WHERE order_id = 'ORD-TEST-099' AND product_id = 'P001';")
        item = cursor.fetchone()
        self.assertIsNotNone(item)
        self.assertEqual(item['quantity'], 2)
        self.assertEqual(item['unit_price'], price_before)

        # 驗證庫存有被扣減
        cursor.execute("SELECT stock FROM product WHERE product_id = 'P001';")
        self.assertEqual(cursor.fetchone()['stock'], stock_before - 2)

        # 清理測試資料
        cursor.execute("DELETE FROM orders WHERE order_id = 'ORD-TEST-099';")
        cursor.execute("UPDATE product SET stock = ? WHERE product_id = 'P001';", (stock_before,))
        cursor.execute("UPDATE product SET stock = stock + 1 WHERE product_id = 'P002';")
        cursor.execute("UPDATE orders SET status = '已出貨' WHERE order_id = 'ORD-2024001';")
        conn.commit()
        conn.close()

if __name__ == '__main__':
    unittest.main()
