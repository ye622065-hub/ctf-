# -*- coding: utf-8 -*-
"""
湖州师范大学校园失物招领系统
考点：水平越权 + 垂直越权
"""
import os
import sqlite3
import base64
from flask import Flask, render_template, request, redirect, url_for, session, flash, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'huzsfxy_campus_lost_found_2024')

# 数据库路径 —— 支持通过环境变量连接外部数据库（MySQL/PostgreSQL等投放数据库）
# 默认使用内置 SQLite 便于本地快速启动
DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'lostfound.db'))

# ============ 动态 Flags（两段 base64 拼接 = 完整 flag{...}）============
# 比赛平台注入方式（按优先级依次尝试）：
#   1) 环境变量 FLAG         （CTFHub / NSSCTF / BUUCTF 等）
#   2) 文件 /flag 或 /flag.txt（GZCTF / CTFd Container Plugin 等）
#   3) 默认值（本地调试）
# 系统会把完整 flag 从第一个 _ 处动态拆成两段，分别 base64 后藏在：
#   - 第一段 → 水平越权点（用户 id=1 的自我介绍）
#   - 第二段 → 垂直越权点（/admin/users 弹窗）

_DEFAULT_FLAG = 'flag{horizontal_leak_via_profile_id_param_and_vertical_bypass_no_role_check}'

def _build_flags():
    """动态读取完整 flag → 拆分两段 → base64 编码"""
    # --- 优先级 1：环境变量 ---
    full_flag = os.environ.get('FLAG', '').strip()

    # --- 优先级 2：常见平台 flag 文件 ---
    if not full_flag:
        for flag_path in ('/flag', '/flag.txt', '/app/flag'):
            if os.path.isfile(flag_path):
                try:
                    with open(flag_path, 'r') as f:
                        full_flag = f.read().strip()
                    if full_flag:
                        print(f"[*] 从文件 {flag_path} 读取到 FLAG")
                        break
                except Exception:
                    pass

    # --- 优先级 3：本地调试兜底 ---
    if not full_flag:
        full_flag = _DEFAULT_FLAG

    # 格式校验（调试友好）
    if not (full_flag.startswith('flag{') and full_flag.endswith('}')):
        print(f"[!] WARNING: FLAG 格式异常，应为 flag{{...}}，当前: {full_flag}")

    # 拆分策略：找到 flag{ 之后的第一个 _ 作为分割点
    # 保证第一段以 flag{ 结尾带 _ ，第二段以 } 开头，拼接 = 完整 flag
    inner = full_flag[5:-1]  # 去掉 flag{ 和 }
    split_idx = inner.find('_')
    if split_idx < 0:
        # flag 内容里没有下划线，就从中间硬切
        split_idx = len(inner) // 2

    part1 = 'flag{' + inner[:split_idx + 1]   # 第一段：flag{xxxx_
    part2 = inner[split_idx + 1:] + '}'        # 第二段：yyyy}

    # base64 编码
    f1_b64 = base64.b64encode(part1.encode()).decode()
    f2_b64 = base64.b64encode(part2.encode()).decode()

    print(f"[*] FLAG 初始化: full={full_flag}")
    print(f"    part1 (水平越权): {part1}")
    print(f"    part2 (垂直越权): {part2}")
    return f1_b64, f2_b64

# 模块加载时立即计算一次（gunicorn 多 worker 场景下每个 worker 都会算）
FLAG1_B64, FLAG2_B64 = _build_flags()


# ============ 数据库操作 ============
def get_db():
    if 'db' not in g:
        # 确保 instance 目录存在
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """初始化数据库表结构并写入种子数据"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 用户表
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            bio TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 失物招领表
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            contact TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
    ''')

    # ------- 种子数据（仅在用户表为空时插入） -------
    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        # 用户 id=1: 管理员（role=admin）
        c.execute(
            'INSERT INTO users (id, username, password, role, bio) VALUES (?, ?, ?, ?, ?)',
            (1, 'admin', 'admin123', 'admin', '系统管理员，负责管理用户和失物信息。')
        )

        # 用户 id=3: 神秘学长（自我介绍藏有第一段 base64 flag）
        # 做题者注册后 SQLite AUTOINCREMENT 会分配 id=2，神秘学长是 id=3
        c.execute(
            'INSERT INTO users (id, username, password, role, bio) VALUES (?, ?, ?, ?, ?)',
            (3, '神秘学长', '123456', 'user',
             '大家好我是计算机学院的一名学长，喜欢打CTF和看书。\n对了，上次在图书馆捡到一个U盘，失主可以来联系我哦~\n\n我的加密笔记：' + FLAG1_B64)
        )

        # 失物招领帖子若干（神秘学长发的，owner_id=3）
        posts_seed = [
            ('图书馆三楼丢失的黑色钱包', '今天下午在图书馆三楼自习时丢失了一个黑色钱包，里面有身份证和若干现金，望拾到者归还！', '湖州师范学院图书馆三楼', '138****1234', 3),
            ('二食堂捡到的白色耳机', '在二食堂二楼餐桌上捡到一副白色AirPods，失主请联系我认领~', '湖州师范学院二食堂二楼', '139****5678', 3),
            ('操场上丢失的校园卡', '昨晚在东操场跑步时校园卡掉了，卡号尾号6688，好心人捡到麻烦联系！', '湖州师范学院东操场', '微信：huzsfxy_2024', 3),
            ('求帮忙寻找遗失的笔记本电脑', '在公交车上落下了一台银色MacBook Pro，电脑里有重要论文，必有重谢！', '湖州师范学院22路公交', '137****9999', 3),
        ]
        c.executemany(
            'INSERT INTO posts (title, description, location, contact, owner_id) VALUES (?, ?, ?, ?, ?)',
            posts_seed
        )

    conn.commit()
    conn.close()


# ============ 鉴权辅助 ============
def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    db = get_db()
    return db.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()


def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('请先登录哦~', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


# ============ 路由 ============
@app.route('/')
def index():
    """首页 —— 失物招领列表"""
    db = get_db()
    posts = db.execute('''
        SELECT posts.*, users.username 
        FROM posts JOIN users ON posts.owner_id = users.id 
        ORDER BY posts.created_at DESC
    ''').fetchall()
    user = current_user()
    return render_template('index.html', posts=posts, user=user)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('用户名和密码不能为空！', 'danger')
            return redirect(url_for('register'))

        db = get_db()
        exist = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if exist:
            flash('用户名已被占用~', 'danger')
            return redirect(url_for('register'))

        db.execute(
            'INSERT INTO users (username, password, role, bio) VALUES (?, ?, ?, ?)',
            (username, password, 'user', '')
        )
        db.commit()
        flash('注册成功，请登录！', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', user=current_user())


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        db = get_db()
        row = db.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, password)
        ).fetchone()
        if not row:
            flash('用户名或密码错误！', 'danger')
            return redirect(url_for('login'))

        session['user_id'] = row['id']
        flash('欢迎回来，%s！' % row['username'], 'success')
        next_url = request.args.get('next') or url_for('index')
        return redirect(next_url)

    return render_template('login.html', user=current_user())


@app.route('/logout')
def logout():
    session.clear()
    flash('已安全退出~', 'info')
    return redirect(url_for('index'))


@app.route('/publish', methods=['GET', 'POST'])
@login_required
def publish():
    """发布失物招领"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        contact = request.form.get('contact', '').strip()
        if not all([title, description, location, contact]):
            flash('请填写完整信息！', 'danger')
            return redirect(url_for('publish'))

        db = get_db()
        db.execute(
            'INSERT INTO posts (title, description, location, contact, owner_id) VALUES (?, ?, ?, ?, ?)',
            (title, description, location, contact, session['user_id'])
        )
        db.commit()
        flash('发布成功！', 'success')
        return redirect(url_for('index'))

    return render_template('publish.html', user=current_user())


@app.route('/user/profile')
@login_required
def user_profile():
    """
    用户主页 —— 水平越权（IDOR）漏洞点

    【正常功能】
      访问 /user/profile → 不带任何参数 → 看自己的主页

    【漏洞】
      后端偷偷接受了 ?id=N 参数，但完全没有校验！
      任何人只要改 URL 加 ?id=1，就能看到 id=1 的用户的完整资料，
      包括本应"仅自己可见"的 bio 字段。

    【做题路径】
      1. 注册登录（id=2）→ 点导航栏自己的用户名 → 看到自己的主页（正常）
      2. 浏览首页，注意到有"神秘学长"这个人
      3. 试一下改 URL：/user/profile?id=1 → 提示"不存在"（admin 被保护）
      4. 再试 /user/profile?id=3 → 看到神秘学长完整简介 + base64 flag1！
      5. 水平越权成功！
    """
    # ⚠️ 漏洞：无条件信任前端传入的 id 参数！
    # 正常设计：不应该接受 id 参数，或者校验 id == session['user_id']
    uid = request.args.get('id', type=int) or session['user_id']

    db = get_db()
    target = db.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()
    if not target:
        flash('该用户不存在~', 'danger')
        return redirect(url_for('index'))

    # 保护管理员账户：不允许通过水平越权查看 admin 的资料
    # 只有管理员本人登录后才能看自己
    if target['role'] == 'admin' and target['id'] != session['user_id']:
        flash('该用户不存在~', 'danger')
        return redirect(url_for('index'))

    posts = db.execute(
        'SELECT * FROM posts WHERE owner_id = ? ORDER BY created_at DESC',
        (uid,)
    ).fetchall()

    return render_template(
        'profile.html',
        target=target,
        posts=posts,
        user=current_user(),
        is_self=(target['id'] == session['user_id'])
    )


@app.route('/admin/users')
@login_required
def admin_users():
    """
    管理员用户管理 —— 垂直越权漏洞点
    这里只判断了是否登录，完全没有检查 role == 'admin'
    普通用户直接访问 /admin/users 就能看到 FLAG2_B64
    """
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY id ASC').fetchall()
    posts_count = db.execute(
        'SELECT owner_id, COUNT(*) as cnt FROM posts GROUP BY owner_id'
    ).fetchall()
    count_map = {r['owner_id']: r['cnt'] for r in posts_count}

    return render_template(
        'admin_users.html',
        users=users,
        count_map=count_map,
        user=current_user(),
        flag2_b64=FLAG2_B64  # 直接传给模板，做题者访问即可拿到
    )


# ============ 启动 ============
@app.before_request
def before_request_init():
    """首次请求时初始化数据库（兼容 gunicorn 多 worker 场景）"""
    if not getattr(app, '_db_inited', False):
        init_db()
        app._db_inited = True


if __name__ == '__main__':
    # 开发模式：直接运行
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
