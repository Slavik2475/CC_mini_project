from datetime import date

from flask import Blueprint, jsonify, request, abort, render_template
from sqlalchemy import func, and_

from . import db
from .models import Transaction, Budget, Category, User


main_bp = Blueprint("main", __name__)


def get_current_user():
    user = User.query.get(1)
    if user is None:
        abort(401, description="Demo user missing")
    return user


def get_current_user_id():
    return get_current_user().id


def parse_transaction_payload(payload):
    if payload is None:
        abort(400, description="JSON body required")

    amount = payload.get("amount")
    tx_type = payload.get("type")
    if amount is None or tx_type not in {"income", "expense"}:
        abort(400, description="'amount' and valid 'type' are required")

    tx_date = payload.get("transaction_date")
    if tx_date:
        try:
            tx_date = date.fromisoformat(tx_date)
        except ValueError:
            abort(400, description="transaction_date must be ISO format YYYY-MM-DD")
    else:
        tx_date = date.today()

    return {
        "amount": amount,
        "type": tx_type,
        "category_id": payload.get("category_id"),
        "description": payload.get("description"),
        "transaction_date": tx_date,
    }


def parse_budget_payload(payload):
    if payload is None:
        abort(400, description="JSON body required")

    required_fields = ["month", "year", "limit_amount"]
    for field in required_fields:
        if payload.get(field) is None:
            abort(400, description=f"'{field}' is required")

    try:
        month = int(payload["month"])
        year = int(payload["year"])
    except ValueError:
        abort(400, description="'month' and 'year' must be integers")

    if not 1 <= month <= 12:
        abort(400, description="'month' must be between 1 and 12")

    return {
        "month": month,
        "year": year,
        "limit_amount": payload["limit_amount"],
        "category_id": payload.get("category_id"),
    }


def get_month_bounds(year: int, month: int):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def get_expense_total(user_id: int, month: int, year: int, category_id=None):
    start, end = get_month_bounds(year, month)
    query = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.type == "expense",
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    )
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    return float(query.scalar() or 0)


def get_income_total(user_id: int, month: int, year: int):
    start, end = get_month_bounds(year, month)
    query = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.type == "income",
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    )
    return float(query.scalar() or 0)


def compute_budget_status(budget: Budget):
    spent = get_expense_total(budget.user_id, budget.month, budget.year, budget.category_id)
    remaining = float(budget.limit_amount) - spent
    return {"spent": spent, "remaining": remaining}


def send_budget_alert(user: User, budget: Budget, spent: float):
    category_name = budget.category.name if budget.category else "Overall"
    print(
        f"[Budget Alert] {user.email}: {category_name} {budget.month}/{budget.year} spent {spent:.2f} "
        f"over limit {float(budget.limit_amount):.2f}"
    )


def evaluate_budgets_for_month(user_id: int, month: int, year: int):
    budgets = Budget.query.filter_by(user_id=user_id, month=month, year=year).all()
    user = get_current_user()
    for budget in budgets:
        status = compute_budget_status(budget)
        over_limit = status["spent"] > float(budget.limit_amount)
        if over_limit and not budget.alert_sent:
            send_budget_alert(user, budget, status["spent"])
            budget.alert_sent = True
        elif not over_limit and budget.alert_sent:
            budget.alert_sent = False
    db.session.commit()


def evaluate_budgets_for_transaction(transaction: Transaction):
    evaluate_budgets_for_month(
        transaction.user_id, transaction.transaction_date.month, transaction.transaction_date.year
    )


@main_bp.route("/")
def index():
    return jsonify({"message": "Personal Finance Tracker API"})


@main_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@main_bp.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@main_bp.route("/api/profile", methods=["GET"])
def profile():
    user = get_current_user()
    return jsonify(
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "profile_photo_url": user.profile_photo_url,
        }
    )


@main_bp.route("/api/categories", methods=["GET"])
def list_categories():
    user_id = get_current_user_id()
    categories = (
        Category.query.filter_by(user_id=user_id)
        .order_by(Category.type.desc(), Category.name.asc())
        .all()
    )
    return jsonify(
        [
            {
                "id": category.id,
                "name": category.name,
                "type": category.type,
            }
            for category in categories
        ]
    )


@main_bp.route("/api/transactions", methods=["GET"])
def list_transactions():
    user_id = get_current_user_id()
    transactions = (
        Transaction.query.filter_by(user_id=user_id)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )
    return jsonify([tx.to_dict() for tx in transactions])


@main_bp.route("/api/transactions", methods=["POST"])
def create_transaction():
    user_id = get_current_user_id()
    payload = request.get_json(silent=True)
    data = parse_transaction_payload(payload)

    transaction = Transaction(user_id=user_id, **data)
    db.session.add(transaction)
    db.session.commit()

    evaluate_budgets_for_transaction(transaction)
    return jsonify(transaction.to_dict()), 201


@main_bp.route("/api/transactions/<int:transaction_id>", methods=["PUT"])
def update_transaction(transaction_id):
    user_id = get_current_user_id()
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
    if transaction is None:
        abort(404, description="Transaction not found")

    payload = request.get_json(silent=True)
    data = parse_transaction_payload(payload)

    for key, value in data.items():
        setattr(transaction, key, value)

    db.session.commit()
    evaluate_budgets_for_transaction(transaction)
    return jsonify(transaction.to_dict())


@main_bp.route("/api/transactions/<int:transaction_id>", methods=["DELETE"])
def delete_transaction(transaction_id):
    user_id = get_current_user_id()
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
    if transaction is None:
        abort(404, description="Transaction not found")

    transaction_month = transaction.transaction_date.month
    transaction_year = transaction.transaction_date.year

    db.session.delete(transaction)
    db.session.commit()
    evaluate_budgets_for_month(user_id, transaction_month, transaction_year)
    return jsonify({"deleted": transaction_id})


@main_bp.route("/api/budgets", methods=["GET"])
def list_budgets():
    user_id = get_current_user_id()
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    query = Budget.query.filter_by(user_id=user_id)
    if month:
        query = query.filter_by(month=month)
    if year:
        query = query.filter_by(year=year)

    budgets = query.order_by(Budget.year.desc(), Budget.month.desc()).all()
    response = []
    for budget in budgets:
        status = compute_budget_status(budget)
        response.append({**budget.to_dict(), **status})
    return jsonify(response)


@main_bp.route("/api/budgets", methods=["POST"])
def create_budget():
    user_id = get_current_user_id()
    payload = request.get_json(silent=True)
    data = parse_budget_payload(payload)

    budget = Budget(user_id=user_id, **data)
    db.session.add(budget)
    db.session.commit()
    evaluate_budgets_for_month(user_id, budget.month, budget.year)
    return jsonify({**budget.to_dict(), **compute_budget_status(budget)}), 201


@main_bp.route("/api/budgets/<int:budget_id>", methods=["PUT"])
def update_budget(budget_id):
    user_id = get_current_user_id()
    budget = Budget.query.filter_by(id=budget_id, user_id=user_id).first()
    if budget is None:
        abort(404, description="Budget not found")

    payload = request.get_json(silent=True)
    data = parse_budget_payload(payload)

    for key, value in data.items():
        setattr(budget, key, value)

    db.session.commit()
    evaluate_budgets_for_month(user_id, budget.month, budget.year)
    return jsonify({**budget.to_dict(), **compute_budget_status(budget)})


@main_bp.route("/api/budgets/<int:budget_id>", methods=["DELETE"])
def delete_budget(budget_id):
    user_id = get_current_user_id()
    budget = Budget.query.filter_by(id=budget_id, user_id=user_id).first()
    if budget is None:
        abort(404, description="Budget not found")

    month, year = budget.month, budget.year
    db.session.delete(budget)
    db.session.commit()
    evaluate_budgets_for_month(user_id, month, year)
    return jsonify({"deleted": budget_id})


@main_bp.route("/api/summary/monthly", methods=["GET"])
def monthly_summary():
    user_id = get_current_user_id()
    today = date.today()
    month = request.args.get("month", type=int) or today.month
    year = request.args.get("year", type=int) or today.year

    start, end = get_month_bounds(year, month)

    total_income = get_income_total(user_id, month, year)
    total_expense = get_expense_total(user_id, month, year)

    category_rows = (
        db.session.query(
            Category.id,
            Category.name,
            Category.type,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .outerjoin(
            Transaction,
            and_(
                Transaction.category_id == Category.id,
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date < end,
            ),
        )
        .filter(Category.user_id == user_id)
        .group_by(Category.id)
        .order_by(Category.name.asc())
        .all()
    )

    budgets = (
        Budget.query.filter_by(user_id=user_id, month=month, year=year)
        .order_by(Budget.category_id.is_(None).desc())
        .all()
    )
    budgets_payload = [{**budget.to_dict(), **compute_budget_status(budget)} for budget in budgets]

    return jsonify(
        {
            "month": month,
            "year": year,
            "total_income": total_income,
            "total_expense": total_expense,
            "net": total_income - total_expense,
            "by_category": [
                {
                    "category_id": row.id,
                    "category_name": row.name,
                    "type": row.type,
                    "total": float(row.total or 0),
                }
                for row in category_rows
            ],
            "budgets": budgets_payload,
        }
    )
