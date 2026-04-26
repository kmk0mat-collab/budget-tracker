from flask import Flask, request, jsonify
from flask_cors import CORS
import json, os, threading
from datetime import datetime
import requests
import schedule
import time

app = Flask(__name__)
CORS(app)

LINE_TOKEN = os.environ.get('LINE_TOKEN', '')
LINE_USER_ID = os.environ.get('LINE_USER_ID', '')

data = {"budget": 0, "expenses": []}

def jpy(n):
    return f"¥{int(n):,}"

def send_line_message(message):
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)

def daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    today_exp = [e for e in data["expenses"] if e.get("date") == today]
    today_total = sum(e["amount"] for e in today_exp)
    week_total = sum(e["amount"] for e in data["expenses"])
    budget = data["budget"]
    today_budget = round(budget / 7) if budget > 0 else 0
    today_remaining = today_budget - today_total
    week_remaining = budget - week_total
    week_pct = round((week_total / budget) * 100) if budget > 0 else 0

    emoji = "🚨" if week_remaining < 0 else ("⚠️" if week_pct > 80 else "✅")
    date_str = datetime.now().strftime("%-m月%-d日")

    cat_totals = {}
    for e in today_exp:
        cat_totals[e["category"]] = cat_totals.get(e["category"], 0) + e["amount"]
    cat_lines = "\n".join([f"  {c}：{jpy(v)}" for c, v in cat_totals.items()])

    msg = f"""{emoji} 家計簿レポート
📅 {date_str}

━━ 今日の支出 ━━
💰 支出：{jpy(today_total)}
📊 1日予算：{jpy(today_budget)}
{"💚" if today_remaining >= 0 else "🔴"} 残り：{jpy(today_remaining)}
"""
    if cat_lines:
        msg += f"\n📂 カテゴリ別\n{cat_lines}\n"

    msg += f"""
━━ 今週の状況 ━━
💸 週の支出：{jpy(week_total)} / {jpy(budget)}
📈 使用率：{week_pct}%
{"💚" if week_remaining >= 0 else "🔴"} 週の残り：{jpy(week_remaining)}"""

    send_line_message(msg)

def run_scheduler():
    schedule.every().day.at("13:00").do(daily_report)
    while True:
        schedule.run_pending()
        time.sleep(60)

@app.route("/")
def index():
    return jsonify({"status": "ok"})

@app.route("/api/budget", methods=["GET", "POST"])
def budget():
    if request.method == "POST":
        data["budget"] = request.json.get("budget", 0)
        return jsonify({"ok": True})
    return jsonify({"budget": data["budget"]})

@app.route("/api/expenses", methods=["GET", "POST"])
def expenses():
    if request.method == "POST":
        exp = request.json
        exp["id"] = int(datetime.now().timestamp() * 1000)
        exp["date"] = datetime.now().strftime("%Y-%m-%d")
        data["expenses"].append(exp)
        return jsonify({"ok": True, "expense": exp})
    return jsonify({"expenses": data["expenses"]})

@app.route("/api/expenses/<int:exp_id>", methods=["DELETE"])
def delete_expense(exp_id):
    data["expenses"] = [e for e in data["expenses"] if e.get("id") != exp_id]
    return jsonify({"ok": True})

@app.route("/api/test-notify", methods=["POST"])
def test_notify():
    daily_report()
    return jsonify({"ok": True})

if __name__ == "__main__":
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
