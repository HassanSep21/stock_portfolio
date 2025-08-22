import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    stocks = db.execute(
        "SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id
    )

    final_total = 0

    portfolio = []
    for stock in stocks:
        stock_info = lookup(stock["symbol"])
        if stock_info:
            total_value = stock["total_shares"] * stock_info["price"]
            final_total += total_value
            portfolio.append({
                "symbol": stock["symbol"],
                "shares": stock["total_shares"],
                "price": usd(stock_info["price"]),
                "total_value": usd(total_value)
            })

    cash = db.execute(
        "SELECT cash FROM users WHERE id = ?", user_id
    )
    cash = cash[0]["cash"]

    final_total += cash

    return render_template("index.html", stocks=portfolio, cash=usd(cash), final_total=usd(final_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        user_id = session["user_id"]
        cash = db.execute(
            "SELECT cash FROM users WHERE id = ?", user_id
        )
        cash = float(cash[0]["cash"])

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol", 400)

        try:
            shares = int(request.form.get("shares"))
            if not shares:
                return apology("missing shares", 400)
            if shares < 1:
                return apology("too few shares", 400)
        except ValueError:
            return apology("shares must be non-negitive integers", 400)

        try:
            stock = lookup(symbol)
            if cash < (stock["price"] * shares):
                return apology("can't afford", 400)

            cash -= stock["price"] * shares
            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?", cash, user_id
            )
            db.execute(
                "INSERT INTO transactions (user_id, symbol, shares, price, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", user_id, symbol, shares, stock[
                    "price"]
            )

            flash("Bought!")
            return redirect("/")

        except:
            return apology("invalid symbol", 400)

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]

    transactions = db.execute(
        "SELECT * FROM transactions WHERE user_id = ?", user_id
    )

    for transaction in transactions:
        transaction["price"] = usd(transaction["price"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol", 400)

        try:
            stock = lookup(symbol)
            stock_symbol = stock["symbol"]
            price = usd(stock["price"])
            return render_template("quoted.html", symbol=symbol, stock_symbol=stock_symbol, price=price)

        except:
            return apology("invalid symbol", 400)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        if not username:
            return apology("must provide username", 400)

        password = request.form.get("password")
        if not password:
            return apology("must provide password", 400)

        confirm_password = request.form.get("confirmation")
        if not confirm_password:
            return apology("must confirm password", 400)

        if password != confirm_password:
            return apology("password confirmation failed", 400)

        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                       username, generate_password_hash(password))
        except ValueError:
            return apology("username already exits", 400)

        session["user_id"] = db.execute(
            "SELECT id FROM users WHERE username = ?", username)[0]["id"]

        flash("Registered!")
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]

    stocks = db.execute(
        "SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id
    )

    if request.method == "POST":
        cash = db.execute(
            "SELECT cash FROM users WHERE id = ?", user_id
        )
        cash = float(cash[0]["cash"])

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol", 400)

        for stock in stocks:
            if stock["symbol"] == symbol:
                current_shares = stock["total_shares"]

        shares = int(request.form.get("shares"))
        if not shares:
            return apology("missing shares", 400)

        if shares < 1:
            return apology("shares must be positive")

        if shares > current_shares:
            return apology("too many shares", 400)

        try:
            stock = lookup(symbol)
            cash += stock["price"] * shares

            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?", cash, user_id
            )
            db.execute(
                "INSERT INTO transactions (user_id, symbol, shares, price, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", user_id, symbol, (
                    -1 * shares), stock["price"]
            )

            flash("Sold!")
            return redirect("/")

        except:
            return apology("invalid symbol", 400)

    else:
        return render_template("sell.html", stocks=stocks)
