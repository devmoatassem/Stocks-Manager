import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, create_user_db, get_time_stamp


# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


create_user_db("test1","finance")

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///user-databases/test1/finance.db")
db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, username TEXT NOT NULL, hash TEXT NOT NULL, cash NUMERIC NOT NULL DEFAULT 10000.00)")
db.execute("CREATE UNIQUE INDEX IF NOT EXISTS username ON users (username)")
# userdbcon = None
# print(session.get("user_id"))


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
    # Connection to user-specific database
    id = session["user_id"]
    rows = db.execute("SELECT * FROM users WHERE id = ?", id)
    if len(rows) != 1:
        session.clear()
        return redirect("/login")
    username = rows[0]["username"]
    userdbcon = SQL(f"sqlite:///user-databases/{id}/{username}.db")
    # //////////////////////////////////////////////////////////////
    dashboard = userdbcon.execute("SELECT * FROM dashboard")
    availablecash = rows[0]["cash"]
    # print(dashboard)
    sum_in_stocks = 0

    for row in dashboard:
        row["price"] = lookup(row["symbol"])["price"]
        row["total"] = row["price"] * row["shares"]
        sum_in_stocks += row["total"]
    # print(sum_in_stocks)
    return render_template(
        "index.html",
        dashdata=dashboard,
        currentCash=availablecash,
        total=availablecash + sum_in_stocks,
    )
    # return apology("TODO",200)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # return apology("TODO")
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("data missing")
        noFShares = request.form.get("shares")
        if not noFShares.isdigit():
            return apology("You cannot purchase partial shares.")
        noFShares = int(noFShares)
        quoted = lookup(request.form.get("symbol"))
        if quoted == None:
            return apology("Incorrect Symbol")
        elif noFShares <= 0:
            return apology("Incorrect Incorrect No of Shares")

        # Connection to user-specific database
        id = session["user_id"]
        rows = db.execute("SELECT * FROM users WHERE id = ?", id)
        username = rows[0]["username"]
        userdbcon = SQL(f"sqlite:///user-databases/{id}/{username}.db")
        # //////////////////////////////////////////////////////////////
        availablecash = rows[0]["cash"]
        total = noFShares * quoted["price"]
        if total > availablecash:
            return apology("SORRY you're out of money")

        already_purchased = userdbcon.execute("SELECT symbol FROM dashboard")
        # print(already_purchased)
        # print(already_purchased.values())
        for dict in already_purchased:
            if (
                "symbol" in dict
                and dict["symbol"] == request.form.get("symbol").upper()
            ):
                userdbcon.execute(
                    "UPDATE dashboard SET shares = shares + ? WHERE symbol = ?",
                    noFShares,
                    request.form.get("symbol").upper(),
                )
                # print("WOrked")
                break
        else:
            userdbcon.execute(
                "INSERT INTO dashboard (symbol, name, shares) VALUES (?,?,?)",
                quoted["symbol"],
                quoted["name"],
                noFShares,
            )
            # print("ISSUE")

        userdbcon.execute(
            "INSERT INTO history (symbol, name, shares, price, date) VALUES (?,?,?,?,?)",
            quoted["symbol"],
            quoted["name"],
            noFShares,
            quoted["price"],
            get_time_stamp(),
        )

        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", total, id)
        return redirect("/")
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # return apology("TODO")
    # Connection to user-specific database
    id = session["user_id"]
    rows = db.execute("SELECT * FROM users WHERE id = ?", id)
    username = rows[0]["username"]
    userdbcon = SQL(f"sqlite:///user-databases/{id}/{username}.db")
    # //////////////////////////////////////////////////////////////

    htable = userdbcon.execute("SELECT * FROM history")
    # print(htable)
    return render_template("history.html", history=htable)


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
        username = rows[0]["username"]

        id = session["user_id"]
        global userdbcon
        userdbcon = SQL(f"sqlite:///user-databases/{id}/{username}.db")
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
        if not request.form.get("symbol"):
            return apology("data missing")
        quoted = lookup(request.form.get("symbol"))
        # print(lookup(request.form.get("symbol"))["price"])
        if quoted == None:
            return apology("Incorrect Symbol")
        return render_template("quote.html", quote=quoted)
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Please Provide a username", 400)
        usname = db.execute(
            "SELECT username FROM users WHERE username = ?",
            request.form.get("username"),
        )
        # print(usname,len(usname))
        if len(usname) != 0:
            return apology("username already exists", 400)

        # Ensure password was submitted
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords Do not Match", 400)

        # insert

        db.execute(
            "INSERT INTO users (username,hash) VALUES (?, ?)",
            request.form.get("username"),
            generate_password_hash(request.form.get("password")),
        )

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        username = rows[0]["username"]
        id = session["user_id"]
        if create_user_db(id, username):
            userdbcon = SQL(f"sqlite:///user-databases/{id}/{username}.db")
        # SQL commands to create dashboard table and history table
        userdbcon.execute(
            "CREATE TABLE IF NOT EXISTS dashboard (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, symbol TEXT NOT NULL, name TEXT NOT NULL, shares INTEGER NOT NULL)"
        )
        userdbcon.execute(
            "CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, symbol TEXT NOT NULL, name TEXT NOT NULL, shares INTEGER NOT NULL, price NUMERIC NOT NULL, date TEXT NOT NULL)"
        )

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
    # return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Connection to user-specific database
    id = session["user_id"]
    rows = db.execute("SELECT * FROM users WHERE id = ?", id)
    username = rows[0]["username"]
    userdbcon = SQL(f"sqlite:///user-databases/{id}/{username}.db")
    # //////////////////////////////////////////////////////////////

    symbols = userdbcon.execute("SELECT symbol FROM dashboard")
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("data missing")
        noFShares = int(request.form.get("shares"))
        symbol = request.form.get("symbol")
        quoted = lookup(symbol)
        if quoted == None:
            return apology("Incorrect Symbol")
        elif noFShares <= 0:
            return apology("Incorrect No of Shares")

        oldShares = userdbcon.execute(
            "SELECT shares FROM dashboard WHERE symbol=?", symbol
        )
        # print(oldShares[0]["shares"])
        if noFShares > oldShares[0]["shares"]:
            return apology("Too Many Shares Selected")
        elif noFShares == oldShares[0]["shares"]:
            # print("")
            userdbcon.execute("DELETE FROM dashboard WHERE symbol = ?", symbol)
        elif noFShares < oldShares[0]["shares"]:
            # print("A")
            userdbcon.execute(
                "UPDATE dashboard SET shares = shares - ? WHERE symbol = ?",
                noFShares,
                symbol,
            )
        # availablecash = rows[0]["cash"]
        total = noFShares * quoted["price"]
        # if total>availablecash:
        #     return apology("SORRY you're out of money")
        # userdbcon.execute("INSERT INTO dashboard (symbol, name, shares) VALUES (?,?,?)", quoted["symbol"], quoted["name"], noFShares)
        userdbcon.execute(
            "INSERT INTO history (symbol, name, shares, price, date) VALUES (?,?,?,?,?)",
            quoted["symbol"],
            quoted["name"],
            -noFShares,
            quoted["price"],
            get_time_stamp(),
        )

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", total, id)
        return redirect("/")

    return render_template("sell.html", symbols=symbols)
    # return apology("TODO")

if __name__ == "__main__":
    app.run(debug=False)
