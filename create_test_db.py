#!/usr/bin/env python3
"""
Create an enhanced test database with comprehensive sample data.

This database is designed to test and demonstrate all the application's
features including:
- CRUD operations
- Column semantics (created_at, updated_at, deleted_at, created_by, updated_by)
- Soft delete functionality
- Foreign key relationships
- Various data types
- Pagination and search functionality
"""
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

# Default path for the test database
DEFAULT_DB_PATH = Path("data/uploaded_db/test_sample.db")


def random_date(days_ago_min: int = 1, days_ago_max: int = 90) -> str:
    """Generate a random datetime string within the specified range."""
    now = datetime.now()
    days_ago = random.randint(days_ago_min, days_ago_max)
    hours_ago = random.randint(0, 23)
    minutes_ago = random.randint(0, 59)
    dt = now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def create_test_database(db_path: Path = DEFAULT_DB_PATH):
    """
    Create a comprehensive test database with sample data.

    Args:
        db_path: Path to create the database file
    """
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing database
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print(f"Creating test database at: {db_path}")

    # =========================================================================
    # TABLE DEFINITIONS
    # =========================================================================

    # Categories table (basic table with timestamps)
    cursor.execute('''
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    # Products table (with foreign key to categories)
    cursor.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL DEFAULT 0,
            cost REAL DEFAULT 0,
            stock_quantity INTEGER DEFAULT 0,
            min_stock_level INTEGER DEFAULT 10,
            category_id INTEGER,
            status TEXT DEFAULT 'active',
            weight REAL,
            dimensions TEXT,
            created_at TEXT,
            updated_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')

    # Customers table (with various field types)
    cursor.execute('''
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE,
            phone TEXT,
            address_line1 TEXT,
            address_line2 TEXT,
            city TEXT,
            state TEXT,
            postal_code TEXT,
            country TEXT DEFAULT 'USA',
            notes TEXT,
            is_vip INTEGER DEFAULT 0,
            loyalty_points INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    # Orders table (with foreign key and multiple statuses)
    cursor.execute('''
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            total_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            shipping_amount REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            payment_status TEXT DEFAULT 'unpaid',
            shipping_method TEXT,
            tracking_number TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            created_by TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')

    # Order items table (junction table with multiple foreign keys)
    cursor.execute('''
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            discount_percent REAL DEFAULT 0,
            subtotal REAL GENERATED ALWAYS AS (quantity * unit_price * (1 - discount_percent/100)) STORED,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # Tasks table (demonstrates soft delete and created_by/updated_by)
    cursor.execute('''
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'todo',
            due_date TEXT,
            assigned_to TEXT,
            estimated_hours REAL,
            actual_hours REAL,
            tags TEXT,
            created_by TEXT,
            updated_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT
        )
    ''')

    # Projects table (for task organization)
    cursor.execute('''
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            start_date TEXT,
            end_date TEXT,
            budget REAL,
            owner TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    # Employees table (demonstrates different semantic columns)
    cursor.execute('''
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE,
            department TEXT,
            position TEXT,
            hire_date TEXT,
            salary REAL,
            is_manager INTEGER DEFAULT 0,
            manager_id INTEGER,
            notes TEXT,
            author TEXT,
            editor TEXT,
            creation_date TEXT,
            last_modified TEXT,
            FOREIGN KEY (manager_id) REFERENCES employees(id)
        )
    ''')

    # Audit log table (demonstrates various date formats)
    cursor.execute('''
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            old_values TEXT,
            new_values TEXT,
            user_id TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_on TEXT
        )
    ''')

    # Settings table (key-value store for testing)
    cursor.execute('''
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT,
            updated_at TEXT,
            modified_by TEXT
        )
    ''')

    conn.commit()
    print("Tables created successfully.")

    # =========================================================================
    # SAMPLE DATA
    # =========================================================================

    # Categories
    categories = [
        ("Electronics", "Electronic devices and accessories", 1),
        ("Clothing", "Apparel and fashion items", 2),
        ("Books", "Books and publications", 3),
        ("Home & Garden", "Home improvement and garden supplies", 4),
        ("Sports & Outdoors", "Sports equipment and outdoor gear", 5),
        ("Toys & Games", "Toys, games, and entertainment", 6),
        ("Health & Beauty", "Health and beauty products", 7),
        ("Automotive", "Car parts and accessories", 8),
        ("Food & Beverages", "Food items and drinks", 9),
        ("Office Supplies", "Office and school supplies", 10),
    ]

    for name, desc, order in categories:
        created = random_date(60, 180)
        cursor.execute(
            "INSERT INTO categories (name, description, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, desc, order, created, created)
        )

    # Products
    products = [
        ("SKU001", "Wireless Mouse", "Ergonomic wireless mouse with USB receiver", 29.99, 15.00, 150, 1),
        ("SKU002", "USB-C Hub", "7-port USB-C hub with HDMI output", 49.99, 25.00, 75, 1),
        ("SKU003", "Mechanical Keyboard", "RGB mechanical keyboard with blue switches", 89.99, 45.00, 50, 1),
        ("SKU004", "4K Monitor", "27-inch 4K UHD IPS monitor", 349.99, 200.00, 25, 1),
        ("SKU005", "Wireless Earbuds", "True wireless earbuds with noise cancellation", 79.99, 35.00, 100, 1),
        ("SKU006", "Cotton T-Shirt", "Premium cotton t-shirt, various sizes", 19.99, 8.00, 200, 2),
        ("SKU007", "Denim Jeans", "Classic fit denim jeans", 59.99, 25.00, 100, 2),
        ("SKU008", "Winter Jacket", "Insulated winter jacket", 129.99, 65.00, 40, 2),
        ("SKU009", "Running Shoes", "Lightweight running shoes", 79.99, 35.00, 80, 5),
        ("SKU010", "Python Programming", "Complete Python programming guide", 39.99, 15.00, 30, 3),
        ("SKU011", "Data Science Handbook", "Practical data science techniques", 49.99, 20.00, 25, 3),
        ("SKU012", "Web Development Guide", "Full-stack web development course", 44.99, 18.00, 35, 3),
        ("SKU013", "Garden Hose", "50ft expandable garden hose", 34.99, 15.00, 60, 4),
        ("SKU014", "Plant Pots Set", "Set of 5 ceramic plant pots", 24.99, 10.00, 40, 4),
        ("SKU015", "Yoga Mat", "Non-slip yoga mat", 29.99, 12.00, 90, 5),
        ("SKU016", "Dumbbells Set", "Adjustable dumbbells 5-25 lbs", 149.99, 75.00, 35, 5),
        ("SKU017", "Board Game Collection", "Classic board games set", 39.99, 18.00, 45, 6),
        ("SKU018", "Vitamin D Supplements", "Vitamin D3 1000 IU, 90 capsules", 14.99, 5.00, 200, 7),
        ("SKU019", "Car Phone Mount", "Magnetic car phone mount", 19.99, 8.00, 150, 8),
        ("SKU020", "Organic Coffee Beans", "Premium organic coffee, 1 lb", 18.99, 9.00, 80, 9),
    ]

    users = ["admin", "user1", "user2"]
    for sku, name, desc, price, cost, stock, cat_id in products:
        created = random_date(30, 120)
        updated = random_date(1, 30) if random.random() > 0.5 else created
        weight = round(random.uniform(0.1, 10.0), 2) if random.random() > 0.3 else None
        dimensions = f"{random.randint(5,30)}x{random.randint(5,30)}x{random.randint(5,30)} cm" if random.random() > 0.4 else None
        status = random.choice(["active", "active", "active", "inactive", "discontinued"])
        created_by = random.choice(users)
        updated_by = random.choice(users) if created != updated else created_by

        cursor.execute('''
            INSERT INTO products (sku, name, description, price, cost, stock_quantity,
                                  category_id, status, weight, dimensions,
                                  created_at, updated_at, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sku, name, desc, price, cost, stock, cat_id, status, weight, dimensions,
              created, updated, created_by, updated_by))

    # Customers
    customers = [
        ("John", "Smith", "john.smith@email.com", "555-0101", "123 Main St", None, "New York", "NY", "10001", "USA"),
        ("Jane", "Doe", "jane.doe@email.com", "555-0102", "456 Oak Ave", "Apt 2B", "Los Angeles", "CA", "90001", "USA"),
        ("Bob", "Johnson", "bob.j@email.com", "555-0103", "789 Pine Rd", None, "Chicago", "IL", "60601", "USA"),
        ("Alice", "Williams", "alice.w@email.com", "555-0104", "321 Elm St", "Suite 100", "Houston", "TX", "77001", "USA"),
        ("Charlie", "Brown", "charlie.b@email.com", "555-0105", "654 Maple Dr", None, "Phoenix", "AZ", "85001", "USA"),
        ("Diana", "Miller", "diana.m@email.com", "555-0106", "987 Cedar Ln", None, "Seattle", "WA", "98101", "USA"),
        ("Edward", "Davis", "edward.d@email.com", "555-0107", "147 Birch Way", "Unit 5", "Denver", "CO", "80201", "USA"),
        ("Fiona", "Garcia", "fiona.g@email.com", "555-0108", "258 Spruce Ct", None, "Boston", "MA", "02101", "USA"),
        ("George", "Martinez", "george.m@email.com", "555-0109", "369 Walnut Blvd", None, "Miami", "FL", "33101", "USA"),
        ("Helen", "Anderson", "helen.a@email.com", "555-0110", "741 Ash Ave", "Apt 7", "Atlanta", "GA", "30301", "USA"),
        ("Ivan", "Thomas", "ivan.t@email.com", "555-0111", "852 Willow St", None, "Portland", "OR", "97201", "USA"),
        ("Julia", "Jackson", "julia.j@email.com", "555-0112", "963 Poplar Dr", "Suite 200", "Austin", "TX", "73301", "USA"),
    ]

    for first, last, email, phone, addr1, addr2, city, state, postal, country in customers:
        created = random_date(30, 365)
        is_vip = 1 if random.random() > 0.8 else 0
        loyalty = random.randint(0, 5000)
        notes = f"Customer since {datetime.strptime(created, '%Y-%m-%d %H:%M:%S').year}" if random.random() > 0.7 else None

        cursor.execute('''
            INSERT INTO customers (first_name, last_name, email, phone, address_line1,
                                   address_line2, city, state, postal_code, country,
                                   notes, is_vip, loyalty_points, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (first, last, email, phone, addr1, addr2, city, state, postal, country,
              notes, is_vip, loyalty, created, created))

    # Orders
    order_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']
    payment_statuses = ['unpaid', 'paid', 'refunded', 'failed']
    shipping_methods = ['Standard', 'Express', 'Overnight', 'Pickup']

    for i in range(1, 31):
        customer_id = random.randint(1, 12)
        order_date = random_date(1, 60)
        order_number = f"ORD-{datetime.now().year}-{i:04d}"
        status = random.choice(order_statuses)
        payment = 'paid' if status in ['shipped', 'delivered'] else random.choice(payment_statuses)
        shipping = random.choice(shipping_methods)
        tracking = f"TRK{random.randint(100000000, 999999999)}" if status in ['shipped', 'delivered'] else None

        cursor.execute('''
            INSERT INTO orders (order_number, customer_id, order_date, status,
                               payment_status, shipping_method, tracking_number,
                               created_at, updated_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_number, customer_id, order_date, status, payment, shipping,
              tracking, order_date, order_date, random.choice(users)))

        order_id = cursor.lastrowid

        # Order items
        num_items = random.randint(1, 5)
        subtotal = 0
        for _ in range(num_items):
            product_id = random.randint(1, 20)
            quantity = random.randint(1, 4)
            cursor.execute("SELECT price FROM products WHERE id = ?", (product_id,))
            unit_price = cursor.fetchone()[0]
            discount = random.choice([0, 0, 0, 5, 10, 15])
            item_subtotal = quantity * unit_price * (1 - discount/100)
            subtotal += item_subtotal

            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, quantity, unit_price,
                                        discount_percent, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (order_id, product_id, quantity, unit_price, discount, order_date))

        # Update order totals
        tax = round(subtotal * 0.08, 2)
        shipping_cost = round(random.uniform(5, 25), 2) if shipping != 'Pickup' else 0
        discount_amt = round(subtotal * 0.1, 2) if random.random() > 0.8 else 0
        total = round(subtotal + tax + shipping_cost - discount_amt, 2)

        cursor.execute('''
            UPDATE orders SET total_amount = ?, tax_amount = ?,
                             shipping_amount = ?, discount_amount = ?
            WHERE id = ?
        ''', (total, tax, shipping_cost, discount_amt, order_id))

    # Tasks (with soft delete demonstrations)
    task_priorities = ['low', 'medium', 'high', 'urgent']
    task_statuses = ['todo', 'in_progress', 'review', 'blocked', 'done']

    tasks = [
        ("Set up production server", "Configure and deploy to production environment", "high", "devops"),
        ("Write API documentation", "Document all REST endpoints with examples", "medium", "docs"),
        ("Fix login bug", "Users unable to login on mobile devices", "urgent", "bug"),
        ("Add export feature", "Allow users to export data to CSV and Excel", "medium", "feature"),
        ("Optimize database queries", "Improve slow queries on orders table", "high", "performance"),
        ("Design new dashboard", "Create mockups for new admin dashboard", "low", "design"),
        ("Update dependencies", "Update all npm packages to latest versions", "medium", "maintenance"),
        ("Code review PR #42", "Review authentication changes", "high", "review"),
        ("Security audit", "Run security scan and fix vulnerabilities", "urgent", "security"),
        ("User training", "Prepare training materials for new features", "low", "docs"),
        ("Mobile app testing", "Test mobile app on various devices", "medium", "testing"),
        ("Backup system setup", "Configure automated daily backups", "high", "devops"),
        ("Performance monitoring", "Set up APM and alerting", "medium", "devops"),
        ("Customer feedback analysis", "Review and categorize customer feedback", "low", "analysis"),
        ("Integration testing", "Write integration tests for payment flow", "high", "testing"),
    ]

    assignees = ["admin", "user1", "user2", None]
    for title, desc, priority, tag in tasks:
        status = random.choice(task_statuses)
        assigned = random.choice(assignees)
        due = (datetime.now() + timedelta(days=random.randint(-5, 30))).strftime('%Y-%m-%d')
        estimated = round(random.uniform(1, 40), 1)
        actual = round(random.uniform(0, estimated * 1.5), 1) if status == 'done' else None
        created = random_date(5, 60)
        updated = random_date(1, 5) if random.random() > 0.5 else created

        # Some tasks are soft-deleted
        deleted = random_date(1, 3) if random.random() < 0.15 else None

        created_by = random.choice(users)
        updated_by = random.choice(users) if created != updated else None

        cursor.execute('''
            INSERT INTO tasks (title, description, priority, status, due_date,
                              assigned_to, estimated_hours, actual_hours, tags,
                              created_by, updated_by, created_at, updated_at, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, desc, priority, status, due, assigned, estimated, actual, tag,
              created_by, updated_by, created, updated, deleted))

    # Projects
    projects = [
        ("Website Redesign", "Complete overhaul of company website", "active", 50000),
        ("Mobile App v2", "New version of mobile application", "active", 75000),
        ("Data Migration", "Migrate data to new infrastructure", "completed", 25000),
        ("Security Upgrade", "Implement enhanced security measures", "on_hold", 35000),
        ("Customer Portal", "Build self-service customer portal", "planning", 60000),
    ]

    for name, desc, status, budget in projects:
        start = random_date(30, 180)
        end = (datetime.strptime(start, '%Y-%m-%d %H:%M:%S') + timedelta(days=random.randint(60, 180))).strftime('%Y-%m-%d')
        owner = random.choice(users)

        cursor.execute('''
            INSERT INTO projects (name, description, status, start_date, end_date,
                                 budget, owner, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, desc, status, start, end, budget, owner, start, start))

    # Employees
    departments = ['Engineering', 'Sales', 'Marketing', 'HR', 'Finance', 'Operations']
    positions = ['Manager', 'Senior', 'Junior', 'Lead', 'Director', 'Intern']

    employees = [
        ("EMP001", "Michael", "Scott", "michael.scott@company.com", "Management", "Regional Manager"),
        ("EMP002", "Jim", "Halpert", "jim.halpert@company.com", "Sales", "Sales Lead"),
        ("EMP003", "Pam", "Beesly", "pam.beesly@company.com", "Admin", "Receptionist"),
        ("EMP004", "Dwight", "Schrute", "dwight.schrute@company.com", "Sales", "Senior Sales"),
        ("EMP005", "Angela", "Martin", "angela.martin@company.com", "Finance", "Accountant"),
        ("EMP006", "Kevin", "Malone", "kevin.malone@company.com", "Finance", "Accountant"),
        ("EMP007", "Oscar", "Martinez", "oscar.martinez@company.com", "Finance", "Senior Accountant"),
        ("EMP008", "Stanley", "Hudson", "stanley.hudson@company.com", "Sales", "Sales"),
    ]

    for emp_id, first, last, email, dept, pos in employees:
        hire_date = random_date(365, 3650)
        salary = round(random.uniform(35000, 120000), 2)
        is_manager = 1 if 'Manager' in pos or 'Director' in pos or 'Lead' in pos else 0
        manager_id = 1 if emp_id != "EMP001" else None
        created = hire_date

        cursor.execute('''
            INSERT INTO employees (employee_id, first_name, last_name, email,
                                  department, position, hire_date, salary,
                                  is_manager, manager_id, author, creation_date, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (emp_id, first, last, email, dept, pos, hire_date, salary,
              is_manager, manager_id, "admin", created, created))

    # Audit log entries
    actions = ['INSERT', 'UPDATE', 'DELETE']
    tables = ['products', 'customers', 'orders', 'tasks']

    for i in range(50):
        table = random.choice(tables)
        record_id = random.randint(1, 20)
        action = random.choice(actions)
        user_id = random.choice(users)
        created = random_date(1, 30)
        ip = f"192.168.1.{random.randint(1, 254)}"

        cursor.execute('''
            INSERT INTO audit_log (table_name, record_id, action, user_id,
                                  ip_address, created_on)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (table, record_id, action, user_id, ip, created))

    # Settings
    settings = [
        ("site_name", "Test Application", "Name of the application"),
        ("maintenance_mode", "false", "Whether maintenance mode is enabled"),
        ("max_upload_size", "10485760", "Maximum file upload size in bytes"),
        ("session_timeout", "3600", "Session timeout in seconds"),
        ("enable_notifications", "true", "Whether email notifications are enabled"),
        ("default_language", "en", "Default language code"),
        ("items_per_page", "25", "Default pagination size"),
        ("date_format", "%Y-%m-%d", "Date display format"),
    ]

    for key, value, desc in settings:
        updated = random_date(1, 30)
        cursor.execute('''
            INSERT INTO settings (key, value, description, updated_at, modified_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (key, value, desc, updated, "admin"))

    conn.commit()
    conn.close()

    print(f"Test database created successfully!")
    print(f"\nTables created:")
    print("  - categories (10 rows)")
    print("  - products (20 rows)")
    print("  - customers (12 rows)")
    print("  - orders (30 rows)")
    print("  - order_items (varying)")
    print("  - tasks (15 rows, ~15% soft-deleted)")
    print("  - projects (5 rows)")
    print("  - employees (8 rows)")
    print("  - audit_log (50 rows)")
    print("  - settings (8 rows)")
    print(f"\nFeatures demonstrated:")
    print("  - CRUD operations on all tables")
    print("  - Foreign key relationships")
    print("  - Soft delete (tasks table)")
    print("  - Semantic columns (created_at, updated_at, created_by, updated_by)")
    print("  - Various data types (TEXT, INTEGER, REAL, etc.)")
    print("  - Different naming conventions (created_at, creation_date, created_on)")


if __name__ == "__main__":
    create_test_database()
