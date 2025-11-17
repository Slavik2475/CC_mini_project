from datetime import datetime, date

from . import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile_photo_url = db.Column(db.String(255))

    categories = db.relationship("Category", backref="user", lazy=True)
    transactions = db.relationship("Transaction", backref="user", lazy=True)
    budgets = db.relationship("Budget", backref="user", lazy=True)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)

    transactions = db.relationship("Transaction", backref="category", lazy=True)
    budgets = db.relationship("Budget", backref="category", lazy=True)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    transaction_date = db.Column(db.Date, default=date.today, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "category_id": self.category_id,
            "amount": float(self.amount) if self.amount is not None else None,
            "type": self.type,
            "description": self.description,
            "transaction_date": self.transaction_date.isoformat() if self.transaction_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "category_name": self.category.name if self.category else None,
        }


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    limit_amount = db.Column(db.Numeric(10, 2), nullable=False)
    alert_sent = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "category_id": self.category_id,
            "month": self.month,
            "year": self.year,
            "limit_amount": float(self.limit_amount),
            "alert_sent": self.alert_sent,
            "category_name": self.category.name if self.category else None,
        }


class Receipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transaction.id"), nullable=False)
    s3_key = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    transaction = db.relationship("Transaction", backref="receipts", lazy=True)
