from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime, date
import json

# Transaction class using OOP
class Transaction:
    def __init__(self, id=None, type="expense", amount=0.0, category="", description="", date=None, created_at=None):
        self.id = id
        self.type = type  # 'income' or 'expense'
        self.amount = float(amount)
        self.category = category
        self.description = description
        self.date = date or datetime.now().date().isoformat()
        self.created_at = created_at or datetime.now().isoformat()
    
    def to_dict(self):
        """Convert transaction object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'type': self.type,
            'amount': self.amount,
            'category': self.category,
            'description': self.description,
            'date': self.date,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Transaction object from dictionary"""
        return cls(
            id=data.get('id'),
            type=data.get('type', 'expense'),
            amount=data.get('amount', 0.0),
            category=data.get('category', ''),
            description=data.get('description', ''),
            date=data.get('date'),
            created_at=data.get('created_at')
        )

# Database management functions
class ExpenseDatabase:
    def __init__(self, db_name='expenses.db'):
        self.db_name = db_name
        self.init_db()
    
    def init_db(self):
        """Initialize the database and create transactions table"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_all_transactions(self, limit=None):
        """Get all transactions from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM transactions ORDER BY date DESC, created_at DESC'
        if limit:
            query += f' LIMIT {limit}'
            
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        transactions = []
        for row in rows:
            transaction = Transaction(
                id=row['id'],
                type=row['type'],
                amount=row['amount'],
                category=row['category'],
                description=row['description'],
                date=row['date'],
                created_at=row['created_at']
            )
            transactions.append(transaction)
        return transactions
    
    def get_transaction_by_id(self, transaction_id):
        """Get a specific transaction by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM transactions WHERE id = ?', (transaction_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Transaction(
                id=row['id'],
                type=row['type'],
                amount=row['amount'],
                category=row['category'],
                description=row['description'],
                date=row['date'],
                created_at=row['created_at']
            )
        return None
    
    def add_transaction(self, transaction):
        """Add a new transaction to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (type, amount, category, description, date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (transaction.type, transaction.amount, transaction.category, 
              transaction.description, transaction.date, transaction.created_at))
        transaction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        transaction.id = transaction_id
        return transaction
    
    def update_transaction(self, transaction_id, transaction_data):
        """Update an existing transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        fields = []
        values = []
        
        allowed_fields = ['type', 'amount', 'category', 'description', 'date']
        for field in allowed_fields:
            if field in transaction_data:
                fields.append(f'{field} = ?')
                values.append(transaction_data[field])
        
        if not fields:
            return None
        
        values.append(transaction_id)
        query = f"UPDATE transactions SET {', '.join(fields)} WHERE id = ?"
        
        cursor.execute(query, values)
        conn.commit()
        
        if cursor.rowcount > 0:
            updated_transaction = self.get_transaction_by_id(transaction_id)
            conn.close()
            return updated_transaction
        
        conn.close()
        return None
    
    def delete_transaction(self, transaction_id):
        """Delete a transaction from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    def get_summary(self):
        """Get financial summary"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                type,
                SUM(amount) as total,
                COUNT(*) as count
            FROM transactions 
            GROUP BY type
        ''')
        
        results = cursor.fetchall()
        
        summary = {
            'total_income': 0.0,
            'total_expenses': 0.0,
            'net_balance': 0.0,
            'income_count': 0,
            'expense_count': 0,
            'total_transactions': 0
        }
        
        for row in results:
            if row['type'] == 'income':
                summary['total_income'] = row['total']
                summary['income_count'] = row['count']
            elif row['type'] == 'expense':
                summary['total_expenses'] = row['total']
                summary['expense_count'] = row['count']
        
        summary['net_balance'] = summary['total_income'] - summary['total_expenses']
        summary['total_transactions'] = summary['income_count'] + summary['expense_count']
        
        conn.close()
        return summary
    
    def get_category_summary(self):
        """Get summary by category"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                type,
                category,
                SUM(amount) as total,
                COUNT(*) as count
            FROM transactions 
            GROUP BY type, category
            ORDER BY total DESC
        ''')
        
        results = cursor.fetchall()
        
        categories = {
            'income': [],
            'expense': []
        }
        
        for row in results:
            categories[row['type']].append({
                'category': row['category'],
                'total': row['total'],
                'count': row['count']
            })
        
        conn.close()
        return categories

# Flask application
app = Flask(__name__)
db = ExpenseDatabase()

# Predefined categories
EXPENSE_CATEGORIES = [
    'Food & Dining', 'Transportation', 'Shopping', 'Entertainment',
    'Bills & Utilities', 'Healthcare', 'Education', 'Travel',
    'Groceries', 'Rent', 'Insurance', 'Other'
]

INCOME_CATEGORIES = [
    'Salary', 'Freelance', 'Business', 'Investment',
    'Rental Income', 'Gift', 'Bonus', 'Other'
]

# HTML Templates
MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personal Expense Tracker</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .dashboard {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-card.income {
            border-left: 5px solid #28a745;
        }
        
        .stat-card.expense {
            border-left: 5px solid #dc3545;
        }
        
        .stat-card.balance {
            border-left: 5px solid #007bff;
        }
        
        .stat-card h3 {
            color: #666;
            font-size: 1em;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .stat-card .amount {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .stat-card.income .amount {
            color: #28a745;
        }
        
        .stat-card.expense .amount {
            color: #dc3545;
        }
        
        .stat-card.balance .amount {
            color: #007bff;
        }
        
        .stat-card .count {
            color: #999;
            font-size: 0.9em;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 30px;
        }
        
        .form-section {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            height: fit-content;
        }
        
        .form-section h2 {
            color: #333;
            margin-bottom: 25px;
            text-align: center;
        }
        
        .form-tabs {
            display: flex;
            margin-bottom: 25px;
            border-radius: 10px;
            overflow: hidden;
            background: #f8f9fa;
        }
        
        .tab-button {
            flex: 1;
            padding: 15px;
            border: none;
            background: #f8f9fa;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .tab-button.active {
            background: #007bff;
            color: white;
        }
        
        .tab-button.income.active {
            background: #28a745;
        }
        
        .tab-button.expense.active {
            background: #dc3545;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #007bff;
        }
        
        .btn {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .btn-income {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .btn-expense {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .transactions-section {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        .transactions-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }
        
        .transactions-header h2 {
            color: #333;
        }
        
        .transaction-item {
            display: flex;
            align-items: center;
            padding: 20px;
            border: 2px solid #f8f9fa;
            border-radius: 10px;
            margin-bottom: 15px;
            transition: all 0.3s;
        }
        
        .transaction-item:hover {
            border-color: #007bff;
            transform: translateX(5px);
        }
        
        .transaction-icon {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
            font-size: 1.5em;
            font-weight: bold;
        }
        
        .transaction-icon.income {
            background: #d4edda;
            color: #28a745;
        }
        
        .transaction-icon.expense {
            background: #f8d7da;
            color: #dc3545;
        }
        
        .transaction-details {
            flex: 1;
        }
        
        .transaction-details h4 {
            color: #333;
            margin-bottom: 5px;
        }
        
        .transaction-details p {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 3px;
        }
        
        .transaction-amount {
            font-size: 1.5em;
            font-weight: bold;
            margin-right: 15px;
        }
        
        .transaction-amount.income {
            color: #28a745;
        }
        
        .transaction-amount.expense {
            color: #dc3545;
        }
        
        .transaction-actions {
            display: flex;
            gap: 10px;
        }
        
        .btn-small {
            padding: 6px 12px;
            font-size: 12px;
            border-radius: 6px;
            text-decoration: none;
            border: none;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-edit {
            background: #ffc107;
            color: #212529;
        }
        
        .btn-delete {
            background: #dc3545;
            color: white;
        }
        
        .btn-small:hover {
            transform: translateY(-1px);
        }
        
        .no-transactions {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        
        .no-transactions h3 {
            font-size: 1.5em;
            margin-bottom: 10px;
        }
        
        .category-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 20px;
        }
        
        .category-chip {
            background: #e9ecef;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            color: #666;
        }
        
        .category-chip.income {
            background: #d4edda;
            color: #28a745;
        }
        
        .category-chip.expense {
            background: #f8d7da;
            color: #dc3545;
        }
        
        .hidden {
            display: none;
        }
        
        @media (max-width: 768px) {
            .dashboard {
                grid-template-columns: 1fr;
            }
            
            .main-content {
                grid-template-columns: 1fr;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .stat-card .amount {
                font-size: 2em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💰 Personal Expense Tracker</h1>
            <p>Track your income and expenses, stay in control of your finances!</p>
        </div>
        
        <div class="dashboard">
            <div class="stat-card income">
                <h3>Total Income</h3>
                <div class="amount">₹{{ "%.2f"|format(summary.total_income) }}</div>
                <div class="count">{{ summary.income_count }} transactions</div>
            </div>
            
            <div class="stat-card expense">
                <h3>Total Expenses</h3>
                <div class="amount">₹{{ "%.2f"|format(summary.total_expenses) }}</div>
                <div class="count">{{ summary.expense_count }} transactions</div>
            </div>
            
            <div class="stat-card balance">
                <h3>Net Balance</h3>
                <div class="amount">₹{{ "%.2f"|format(summary.net_balance) }}</div>
                <div class="count">{{ summary.total_transactions }} total</div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="form-section">
                <h2>Add Transaction</h2>
                
                <div class="form-tabs">
                    <button class="tab-button income active" onclick="switchTab('income')">
                        + Income
                    </button>
                    <button class="tab-button expense" onclick="switchTab('expense')">
                        - Expense
                    </button>
                </div>
                
                <form method="POST" action="/add" id="transactionForm">
                    <input type="hidden" name="type" id="transactionType" value="income">
                    
                    <div class="form-group">
                        <label for="amount">Amount (₹)</label>
                        <input type="number" id="amount" name="amount" step="0.01" min="0" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="category">Category</label>
                        <select id="category" name="category" required>
                            <option value="">Select category...</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="description">Description</label>
                        <textarea id="description" name="description" rows="3" placeholder="Optional description..."></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="date">Date</label>
                        <input type="date" id="date" name="date" value="{{ today }}" required>
                    </div>
                    
                    <button type="submit" class="btn btn-income" id="submitBtn">
                        💰 Add Income
                    </button>
                </form>
                
                <div class="category-chips">
                    <h4 style="width: 100%; margin-bottom: 10px;">Popular Categories:</h4>
                    <div id="incomeChips" class="category-chips">
                        {% for cat in income_categories[:6] %}
                        <span class="category-chip income">{{ cat }}</span>
                        {% endfor %}
                    </div>
                    <div id="expenseChips" class="category-chips hidden">
                        {% for cat in expense_categories[:6] %}
                        <span class="category-chip expense">{{ cat }}</span>
                        {% endfor %}
                    </div>
                </div>
            </div>
            
            <div class="transactions-section">
                <div class="transactions-header">
                    <h2>Recent Transactions</h2>
                    <span style="color: #666;">{{ transactions|length }} transactions</span>
                </div>
                
                {% if transactions %}
                    {% for transaction in transactions %}
                    <div class="transaction-item">
                        <div class="transaction-icon {{ transaction.type }}">
                            {% if transaction.type == 'income' %}+{% else %}-{% endif %}
                        </div>
                        
                        <div class="transaction-details">
                            <h4>{{ transaction.category }}</h4>
                            <p>{{ transaction.description or 'No description' }}</p>
                            <p><strong>{{ transaction.date }}</strong></p>
                        </div>
                        
                        <div class="transaction-amount {{ transaction.type }}">
                            {% if transaction.type == 'income' %}+{% else %}-{% endif %}₹{{ "%.2f"|format(transaction.amount) }}
                        </div>
                        
                        <div class="transaction-actions">
                            <a href="/edit/{{ transaction.id }}" class="btn-small btn-edit">Edit</a>
                            <a href="/delete/{{ transaction.id }}" class="btn-small btn-delete" 
                               onclick="return confirm('Are you sure you want to delete this transaction?')">Delete</a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="no-transactions">
                        <h3>💸 No transactions yet!</h3>
                        <p>Start by adding your first income or expense.</p>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        const incomeCategories = {{ income_categories|tojson }};
        const expenseCategories = {{ expense_categories|tojson }};
        
        function switchTab(type) {
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelector(`.tab-button.${type}`).classList.add('active');
            
            document.getElementById('transactionType').value = type;
            
            const categorySelect = document.getElementById('category');
            categorySelect.innerHTML = '<option value="">Select category...</option>';
            
            const categories = type === 'income' ? incomeCategories : expenseCategories;
            categories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat;
                option.textContent = cat;
                categorySelect.appendChild(option);
            });
            
            const submitBtn = document.getElementById('submitBtn');
            if (type === 'income') {
                submitBtn.className = 'btn btn-income';
                submitBtn.innerHTML = '💰 Add Income';
            } else {
                submitBtn.className = 'btn btn-expense';
                submitBtn.innerHTML = '💸 Add Expense';
            }
            
            document.getElementById('incomeChips').classList.toggle('hidden', type !== 'income');
            document.getElementById('expenseChips').classList.toggle('hidden', type !== 'expense');
        }
        
        switchTab('income');
        
        document.querySelectorAll('.category-chip').forEach(chip => {
            chip.addEventListener('click', function() {
                document.getElementById('category').value = this.textContent;
            });
        });
    </script>
</body>
</html>
'''

EDIT_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Transaction - Expense Tracker</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 50px auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #ff9a56 0%, #ff6b35 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .form-section {
            padding: 40px;
        }
        
        .transaction-type {
            display: flex;
            margin-bottom: 25px;
            border-radius: 10px;
            overflow: hidden;
            background: #f8f9fa;
        }
        
        .type-option {
            flex: 1;
            padding: 15px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .type-option input {
            margin-right: 8px;
        }
        
        .type-option.income {
            background: #d4edda;
            color: #28a745;
        }
        
        .type-option.expense {
            background: #f8d7da;
            color: #dc3545;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 15px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #ff6b35;
        }
        
        .form-group textarea {
            resize: vertical;
            min-height: 100px;
        }
        
        .button-group {
            display: flex;
            gap: 15px;
            justify-content: center;
        }
        
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #ff6b35 0%, #ff9a56 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 107, 53, 0.4);
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #5a6268;
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✏️ Edit Transaction</h1>
            <p>Update your transaction details</p>
        </div>
        
        <div class="form-section">
            <form method="POST">
                <div class="transaction-type">
                    <label class="type-option income">
                        <input type="radio" name="type" value="income" {% if transaction.type == 'income' %}checked{% endif %}>
                        💰 Income
                    </label>
                    <label class="type-option expense">
                        <input type="radio" name="type" value="expense" {% if transaction.type == 'expense' %}checked{% endif %}>
                        💸 Expense
                    </label>
                </div>
                
                <div class="form-group">
                    <label for="amount">Amount (₹)</label>
                    <input type="number" id="amount" name="amount" step="0.01" min="0" 
                           value="{{ transaction.amount }}" required>
                </div>
                
                <div class="form-group">
                    <label for="category">Category</label>
                    <select id="category" name="category" required>
                        <option value="">Select category...</option>
                        {% if transaction.type == 'income' %}
                            {% for cat in income_categories %}
                                <option value="{{ cat }}" {% if cat == transaction.category %}selected{% endif %}>
                                    {{ cat }}
                                </option>
                            {% endfor %}
                        {% else %}
                            {% for cat in expense_categories %}
                                <option value="{{ cat }}" {% if cat == transaction.category %}selected{% endif %}>
                                    {{ cat }}
                                </option>
                            {% endfor %}
                        {% endif %}
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="description">Description</label>
                    <textarea id="description" name="description" rows="3">{{ transaction.description }}</textarea>
                </div>
                
                <div class="form-group">
                    <label for="date">Date</label>
                    <input type="date" id="date" name="date" value="{{ transaction.date }}" required>
                </div>
                
                <div class="button-group">
                    <button type="submit" class="btn btn-primary">💾 Update Transaction</button>
                    <a href="{{ url_for('index') }}" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        const incomeCategories = {{ income_categories|tojson }};
        const expenseCategories = {{ expense_categories|tojson }};
        
        document.querySelectorAll('input[name="type"]').forEach(radio => {
            radio.addEventListener('change', function() {
                const categorySelect = document.getElementById('category');
                categorySelect.innerHTML = '<option value="">Select category...</option>';
                
                const categories = this.value === 'income' ? incomeCategories : expenseCategories;
                categories.forEach(cat => {
                    const option = document.createElement('option');
                    option.value = cat;
                    option.textContent = cat;
                    categorySelect.appendChild(option);
                });
            });
        });
    </script>
</body>
</html>
'''

# Routes
@app.route('/')
def index():
    """Render the main page with transactions and summary"""
    transactions = db.get_all_transactions(limit=10)  # Show last 10 transactions
    summary = db.get_summary()
    
    return render_template_string(
        MAIN_TEMPLATE,
        transactions=[t.to_dict() for t in transactions],
        summary=summary,
        income_categories=INCOME_CATEGORIES,
        expense_categories=EXPENSE_CATEGORIES,
        today=date.today().isoformat()
    )

@app.route('/add', methods=['POST'])
def add_transaction():
    """Add a new transaction"""
    try:
        data = request.form
        transaction = Transaction(
            type=data['type'],
            amount=data['amount'],
            category=data['category'],
            description=data.get('description', ''),
            date=data['date']
        )
        
        db.add_transaction(transaction)
        return redirect(url_for('index'))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/edit/<int:transaction_id>')
def edit_transaction(transaction_id):
    """Render edit page for a specific transaction"""
    transaction = db.get_transaction_by_id(transaction_id)
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    return render_template_string(
        EDIT_TEMPLATE,
        transaction=transaction.to_dict(),
        income_categories=INCOME_CATEGORIES,
        expense_categories=EXPENSE_CATEGORIES
    )

@app.route('/edit/<int:transaction_id>', methods=['POST'])
def update_transaction(transaction_id):
    """Update an existing transaction"""
    try:
        data = {
            'type': request.form['type'],
            'amount': float(request.form['amount']),
            'category': request.form['category'],
            'description': request.form.get('description', ''),
            'date': request.form['date']
        }
        
        updated_transaction = db.update_transaction(transaction_id, data)
        if updated_transaction:
            return redirect(url_for('index'))
        else:
            return jsonify({'error': 'Failed to update transaction'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/delete/<int:transaction_id>')
def delete_transaction(transaction_id):
    """Delete a transaction"""
    if db.delete_transaction(transaction_id):
        return redirect(url_for('index'))
    return jsonify({'error': 'Transaction not found'}), 404

@app.route('/api/summary')
def get_summary():
    """Get financial summary (API endpoint)"""
    return jsonify(db.get_summary())

@app.route('/api/categories')
def get_category_summary():
    """Get category summary (API endpoint)"""
    return jsonify(db.get_category_summary())

if __name__ == '__main__':
    app.run(debug=True)
