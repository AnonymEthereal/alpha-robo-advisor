import sqlite3
import uuid
import os
from config import DB_PATH

# 确保数据库目录存在
_db_dir = os.path.dirname(DB_PATH)
if not os.path.exists(_db_dir):
    os.makedirs(_db_dir, exist_ok=True)


def get_conn():
    """获取数据库连接，启用 WAL 模式提升并发性能，增加超时避免锁等待"""
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db():
    conn = get_conn()
    try:
        c = conn.cursor()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id        TEXT PRIMARY KEY,
            risk_level     INTEGER,
            risk_score     INTEGER,
            assessment_date TEXT,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS risk_assessments (
            assessment_id TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            answers       TEXT NOT NULL,
            score         INTEGER NOT NULL,
            level         INTEGER NOT NULL,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS portfolios (
            portfolio_id  TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            fund_code     TEXT NOT NULL,
            fund_name     TEXT,
            fund_type     TEXT,
            amount        REAL NOT NULL,
            buy_date      TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS asset_allocations (
            allocation_id TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            input_params  TEXT NOT NULL,
            result        TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS market_data_cache (
            date          TEXT NOT NULL,
            index_code    TEXT NOT NULL,
            open          REAL,
            close         REAL,
            high          REAL,
            low           REAL,
            volume        REAL,
            updated_at    TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (date, index_code)
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            chat_id       TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            question      TEXT NOT NULL,
            answer        TEXT NOT NULL,
            is_blocked    INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id);
        CREATE INDEX IF NOT EXISTS idx_market_data_date ON market_data_cache(date);
        CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_history(user_id);
        """)
        conn.commit()
    finally:
        conn.close()


def get_or_create_user() -> str:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users LIMIT 1")
        row = c.fetchone()
        if row:
            user_id = row["user_id"]
        else:
            user_id = uuid.uuid4().hex
            c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            conn.commit()
        return user_id
    finally:
        conn.close()


def get_user_info(user_id: str) -> dict:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def save_risk_assessment(user_id: str, answers: dict, score: int, level: int):
    import json
    conn = get_conn()
    try:
        c = conn.cursor()
        assessment_id = uuid.uuid4().hex
        c.execute(
            "INSERT INTO risk_assessments (assessment_id, user_id, answers, score, level) VALUES (?, ?, ?, ?, ?)",
            (assessment_id, user_id, json.dumps(answers, ensure_ascii=False), score, level),
        )
        c.execute(
            "UPDATE users SET risk_level = ?, risk_score = ?, assessment_date = date('now') WHERE user_id = ?",
            (level, score, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def add_holding(user_id: str, fund_code: str, fund_name: str, fund_type: str,
                amount: float, buy_date: str) -> str:
    conn = get_conn()
    try:
        c = conn.cursor()
        portfolio_id = uuid.uuid4().hex
        c.execute(
            "INSERT INTO portfolios (portfolio_id, user_id, fund_code, fund_name, fund_type, amount, buy_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (portfolio_id, user_id, fund_code, fund_name, fund_type, amount, buy_date),
        )
        conn.commit()
        return portfolio_id
    finally:
        conn.close()


def delete_holding(portfolio_id: str):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM portfolios WHERE portfolio_id = ?", (portfolio_id,))
        conn.commit()
    finally:
        conn.close()


def get_holdings(user_id: str) -> list:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM portfolios WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_allocation(user_id: str, input_params: dict, result: dict):
    import json
    conn = get_conn()
    try:
        c = conn.cursor()
        allocation_id = uuid.uuid4().hex
        c.execute(
            "INSERT INTO asset_allocations (allocation_id, user_id, input_params, result) VALUES (?, ?, ?, ?)",
            (allocation_id, user_id, json.dumps(input_params, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def save_chat(user_id: str, question: str, answer: str, is_blocked: bool = False):
    conn = get_conn()
    try:
        c = conn.cursor()
        chat_id = uuid.uuid4().hex
        c.execute(
            "INSERT INTO chat_history (chat_id, user_id, question, answer, is_blocked) VALUES (?, ?, ?, ?, ?)",
            (chat_id, user_id, question, answer, 1 if is_blocked else 0),
        )
        conn.commit()
    finally:
        conn.close()


def get_chat_history(user_id: str, limit: int = 20) -> list:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM chat_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
