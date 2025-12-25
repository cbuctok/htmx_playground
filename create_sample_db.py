"""Create a sample target database for testing."""
import sqlite3
from datetime import datetime, timedelta
import random

DB_PATH = "data/uploaded_db/sample.db"


def create_sample_db():
    """Create a sample database with test data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            category_id INTEGER,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')

    # Categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT
        )
    ''')

    # Customers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE,
            phone TEXT,
            address TEXT,
            city TEXT,
            country TEXT DEFAULT 'USA',
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    # Orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            total_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')

    # Order items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            created_at TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # Tasks table (for project management demo)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'todo',
            assigned_to TEXT,
            due_date TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT
        )
    ''')

    conn.commit()

    # Seed data
    now = datetime.now()

    # Categories
    categories = [
        ("Electronics", "Electronic devices and accessories"),
        ("Clothing", "Apparel and fashion items"),
        ("Books", "Books and publications"),
        ("Home & Garden", "Home improvement and garden supplies"),
        ("Sports", "Sports equipment and accessories"),
    ]
    for name, desc in categories:
        cursor.execute(
            "INSERT INTO categories (name, description, created_at) VALUES (?, ?, ?)",
            (name, desc, (now - timedelta(days=random.randint(30, 90))).strftime('%Y-%m-%d %H:%M:%S'))
        )

    # Products
    products = [
        ("Wireless Mouse", "Ergonomic wireless mouse with USB receiver", 29.99, 150, 1),
        ("USB-C Hub", "7-port USB-C hub with HDMI", 49.99, 75, 1),
        ("Mechanical Keyboard", "RGB mechanical keyboard with blue switches", 89.99, 50, 1),
        ("Cotton T-Shirt", "Premium cotton t-shirt, various sizes", 19.99, 200, 2),
        ("Denim Jeans", "Classic fit denim jeans", 59.99, 100, 2),
        ("Running Shoes", "Lightweight running shoes", 79.99, 80, 5),
        ("Python Programming", "Complete Python programming guide", 39.99, 30, 3),
        ("Data Science Handbook", "Practical data science techniques", 49.99, 25, 3),
        ("Garden Hose", "50ft expandable garden hose", 34.99, 60, 4),
        ("Plant Pots Set", "Set of 5 ceramic plant pots", 24.99, 40, 4),
        ("Yoga Mat", "Non-slip yoga mat", 29.99, 90, 5),
        ("Dumbbells Set", "Adjustable dumbbells 5-25 lbs", 149.99, 35, 5),
    ]
    for name, desc, price, stock, cat_id in products:
        created = (now - timedelta(days=random.randint(1, 60))).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO products (name, description, price, stock, category_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, desc, price, stock, cat_id, created, created)
        )

    # Customers
    customers = [
        ("John", "Smith", "john.smith@email.com", "555-0101", "123 Main St", "New York", "USA"),
        ("Jane", "Doe", "jane.doe@email.com", "555-0102", "456 Oak Ave", "Los Angeles", "USA"),
        ("Bob", "Johnson", "bob.j@email.com", "555-0103", "789 Pine Rd", "Chicago", "USA"),
        ("Alice", "Williams", "alice.w@email.com", "555-0104", "321 Elm St", "Houston", "USA"),
        ("Charlie", "Brown", "charlie.b@email.com", "555-0105", "654 Maple Dr", "Phoenix", "USA"),
        ("Diana", "Miller", "diana.m@email.com", "555-0106", "987 Cedar Ln", "Seattle", "USA"),
        ("Edward", "Davis", "edward.d@email.com", "555-0107", "147 Birch Way", "Denver", "USA"),
        ("Fiona", "Garcia", "fiona.g@email.com", "555-0108", "258 Spruce Ct", "Boston", "USA"),
    ]
    for first, last, email, phone, addr, city, country in customers:
        created = (now - timedelta(days=random.randint(30, 180))).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO customers (first_name, last_name, email, phone, address, city, country, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (first, last, email, phone, addr, city, country, created, created)
        )

    # Orders
    order_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
    for i in range(15):
        customer_id = random.randint(1, 8)
        order_date = (now - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d')
        status = random.choice(order_statuses)
        created = (now - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO orders (customer_id, order_date, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (customer_id, order_date, status, created, created)
        )
        order_id = cursor.lastrowid

        # Order items
        num_items = random.randint(1, 4)
        total = 0
        for _ in range(num_items):
            product_id = random.randint(1, 12)
            quantity = random.randint(1, 3)
            cursor.execute("SELECT price FROM products WHERE id = ?", (product_id,))
            price = cursor.fetchone()[0]
            total += price * quantity
            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price, created_at) VALUES (?, ?, ?, ?, ?)",
                (order_id, product_id, quantity, price, created)
            )

        cursor.execute("UPDATE orders SET total_amount = ? WHERE id = ?", (round(total, 2), order_id))

    # Tasks
    task_priorities = ['low', 'medium', 'high', 'urgent']
    task_statuses = ['todo', 'in_progress', 'review', 'done']
    task_assignees = ['admin', 'user1', 'user2', None]
    tasks = [
        ("Set up production server", "Configure and deploy to production environment"),
        ("Write API documentation", "Document all REST endpoints"),
        ("Fix login bug", "Users unable to login on mobile devices"),
        ("Add export feature", "Allow users to export data to CSV"),
        ("Optimize database queries", "Improve slow queries on orders table"),
        ("Design new dashboard", "Create mockups for new admin dashboard"),
        ("Update dependencies", "Update all npm packages to latest versions"),
        ("Code review", "Review pull request #42"),
        ("Security audit", "Run security scan on the application"),
        ("User training", "Prepare training materials for new features"),
    ]
    for title, desc in tasks:
        priority = random.choice(task_priorities)
        status = random.choice(task_statuses)
        assigned = random.choice(task_assignees)
        due = (now + timedelta(days=random.randint(-5, 14))).strftime('%Y-%m-%d')
        created = (now - timedelta(days=random.randint(1, 20))).strftime('%Y-%m-%d %H:%M:%S')
        deleted = None
        if random.random() < 0.1:  # 10% soft deleted
            deleted = now.strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO tasks (title, description, priority, status, assigned_to, due_date, created_by, created_at, updated_at, deleted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, desc, priority, status, assigned, due, 'admin', created, created, deleted)
        )

    conn.commit()
    conn.close()
    print(f"Sample database created at: {DB_PATH}")


if __name__ == "__main__":
    create_sample_db()
