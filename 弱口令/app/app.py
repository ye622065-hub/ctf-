# -*- coding: utf-8 -*-
"""
用户订单管理系统（CTF 题目）
------------------------------------------------------------
考点：
1. 只有 admin / 666666 可以登录，其他账号一律登录失败。
2. 用户一未付款金额 1000，BP 抓包把 amount 改成 < 10 后付款，
   后端直接信任客户端金额 -> 付款成功并弹出第一段 flag（Base64）。
3. 用户二订单页进入即弹出第二段 flag（Base64）。
4. 两段 flag 返回时均做 Base64 编码，选手需各自解码后拼接得到完整 flag。
"""

import base64
import os
import time

import pymysql
from flask import (Flask, session, request, redirect, url_for,
                   render_template, abort)

# ----------------------------- 配置 -----------------------------
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'db'),
    'port': int(os.environ.get('DB_PORT', '3306')),
    'user': os.environ.get('DB_USER', 'ctf'),
    'password': os.environ.get('DB_PASS', 'ctf123456'),
    'database': os.environ.get('DB_NAME', 'user_system'),
    'charset': 'utf8mb4',
    'autocommit': True,
}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ctf-user-mgr-secret')


def b64_flag(value):
    """题目返回的 flag 统一做 Base64 编码，选手拿到后需自行解码"""
    if not value:
        return ''
    return base64.b64encode(value.encode('utf-8')).decode('ascii')


# --------------------------- 数据库工具 ---------------------------
def get_conn():
    return pymysql.connect(**DB_CONFIG)


def wait_for_db(retries=60, interval=1):
    """MySQL 容器首次初始化较慢，用 Python 自身做连接重试（不依赖 nc/mysql）"""
    last_err = None
    for i in range(retries):
        try:
            conn = get_conn()
            conn.close()
            print('[db] MySQL 连接就绪', flush=True)
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f'[db] 等待 MySQL 就绪... ({i + 1}/{retries}) {e}', flush=True)
            time.sleep(interval)
    raise SystemExit(f'数据库连接失败，退出: {last_err}')


def query_all(sql, args=None):
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, args or ())
            return cur.fetchall()
    finally:
        conn.close()


def query_one(sql, args=None):
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, args or ())
            return cur.fetchone()
    finally:
        conn.close()


def execute(sql, args=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            return cur.execute(sql, args or ())
    finally:
        conn.close()


def init_dynamic_flag():
    """
    从环境变量 FLAG 读取动态 flag，拆成两段写入数据库：
      - 第一段 -> secrets.pay_flag（用户一改包付款后弹窗）
      - 第二段 -> customers.notice  id=2（用户二进入页面弹窗）
    两段拼接即为完整 flag。平台每次启动容器注入不同 FLAG，flag 即动态变化。
    """
    full_flag = os.environ.get('FLAG', 'flag{Cl1ent_S1de_Pr1ce_Tamp3r1ng!}').strip()

    # 拆 flag{xxx}：第一段 = flag{ + 内容前半；第二段 = 内容后半 + }
    if full_flag.startswith('flag{') and full_flag.endswith('}'):
        inner = full_flag[5:-1]
        mid = max(1, len(inner) // 2)
        part1 = 'flag{' + inner[:mid]
        part2 = inner[mid:] + '}'
    else:
        # 格式异常兜底：整段放第一段，第二段为空
        part1 = full_flag
        part2 = ''

    execute("UPDATE secrets SET value = %s WHERE name = 'pay_flag'", (part1,))
    execute("UPDATE customers SET notice = %s WHERE id = 2", (part2,))
    print(f'[flag] 动态 flag 已注入: {part1} + {part2}', flush=True)


def require_login():
    """未登录返回重定向响应，已登录返回 None"""
    if not session.get('admin'):
        return redirect(url_for('index'))
    return None


# ----------------------------- 路由 -----------------------------
@app.route('/')
def index():
    """登录页"""
    if session.get('admin'):
        return redirect(url_for('home'))
    return render_template('login.html', err=request.args.get('err') is not None)


@app.route('/login', methods=['POST'])
def login():
    """登录处理：只有管理员 admin 能登录成功"""
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''

    if not username or not password:
        return redirect(url_for('index', err=1))

    # 密码以 MD5 形式存库，使用参数化查询
    row = query_one(
        'SELECT username FROM users '
        'WHERE username = %s AND password = MD5(%s) LIMIT 1',
        (username, password)
    )

    # 再次强制要求必须是管理员账号
    if row and row['username'] == 'admin':
        session.clear()
        session['admin'] = True
        session['login_user'] = 'admin'
        return redirect(url_for('home'))

    # 其他任何账号均登录失败
    return redirect(url_for('index', err=1))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/home')
def home():
    """首页：用户一 / 用户二 订单列表"""
    guard = require_login()
    if guard:
        return guard

    users = query_all(
        "SELECT c.id, c.name, o.order_no, o.product, o.amount, o.status "
        "FROM customers c "
        "LEFT JOIN orders o ON o.customer_id = c.id "
        "ORDER BY c.id ASC"
    )
    return render_template('home.html', users=users)


@app.route('/order/<int:cid>')
def order_detail(cid):
    """订单详情：用户二进入页面立即弹出 Base64 编码的 flag2"""
    guard = require_login()
    if guard:
        return guard

    order = query_one(
        "SELECT c.id, c.name, c.notice, o.order_no, o.product, o.amount, o.status "
        "FROM customers c "
        "LEFT JOIN orders o ON o.customer_id = c.id "
        "WHERE c.id = %s LIMIT 1",
        (cid,)
    )
    if not order:
        abort(404)

    # 用户二 notice 即第二段 flag，返回时做 Base64 编码
    order['notice'] = b64_flag(order.get('notice'))
    return render_template('order.html', order=order)


@app.route('/pay', methods=['POST'])
def pay():
    """
    用户一点击付款。
    漏洞点：服务端直接信任客户端提交的 amount。
      - amount >= 10（正常 1000）-> 付款失败
      - amount < 10（BP 改包）   -> 付款成功，弹出 Base64 编码的第一段 flag
    """
    guard = require_login()
    if guard:
        return guard

    raw = request.form.get('amount', '')
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return render_template(
            'alert.html',
            msg='付款失败：金额参数不合法',
            target=url_for('order_detail', cid=1)
        )

    if amount < 0:
        return render_template(
            'alert.html',
            msg='付款失败：金额参数不合法',
            target=url_for('order_detail', cid=1)
        )

    if amount < 10:
        # 金额被篡改到 10 以下：付款成功，从库里读取第一段 flag
        execute("UPDATE orders SET status = '已付款' WHERE customer_id = 1")
        row = query_one("SELECT value FROM secrets WHERE name = 'pay_flag' LIMIT 1")
        flag = b64_flag(row['value']) if row else ''
        return render_template('result.html', amount=amount, flag=flag)

    # 正常提交 1000（或任何 >= 10 的金额）均失败
    return render_template(
        'alert.html',
        msg=f'付款失败：实付金额 {amount:.2f} 与应付金额不符',
        target=None  # None -> history.back()
    )


if __name__ == '__main__':
    wait_for_db()
    init_dynamic_flag()
    app.run(host='0.0.0.0', port=5000)
