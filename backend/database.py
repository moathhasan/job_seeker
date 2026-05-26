"""
database.py -- MySQL-only database layer.
No SQLite fallback. Real connections only.
MySQL password: MUST be configured via MYSQL_PASSWORD env var.
"""
import os
import re
import time
import pymysql
import pymysql.cursors

# ---------------------------------------------------------------------------
# Connection config -- reads from env vars (password is required)
# ---------------------------------------------------------------------------
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "jobseeker")

# Validate database name to prevent SQL injection in CREATE DATABASE
if not re.match(r'^[a-zA-Z0-9_]+$', MYSQL_DATABASE):
    raise ValueError(f"Invalid MYSQL_DATABASE name: '{MYSQL_DATABASE}'. Only alphanumeric and underscores allowed.")

if not MYSQL_PASSWORD:
    print("=" * 60)
    print("WARNING: MYSQL_PASSWORD env var is not set.")
    print("Falling back to empty password. Set MYSQL_PASSWORD for production.")
    print("=" * 60)


def check_mysql_connection() -> bool:
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            connect_timeout=5
        )
        conn.close()
        return True
    except Exception as e:
        print(f"[DB] MySQL connection error: {e}")
        return False


def _wait_for_mysql(max_retries=5, delay=3):
    """Wait for MySQL to become available with retries (for Docker/K8s)."""
    for attempt in range(1, max_retries + 1):
        if check_mysql_connection():
            return True
        if attempt < max_retries:
            print(f"[DB] MySQL not ready, retry {attempt}/{max_retries} in {delay}s...")
            time.sleep(delay)
    return False


def get_connection() -> pymysql.connections.Connection:
    """Return a MySQL connection (pooled if DBUtils is available, direct otherwise)."""
    global _connection_pool, _pool_init_attempted
    # Try pool first
    if _connection_pool is not None:
        return _connection_pool.connection()
    # Lazy-init pool once
    if not _pool_init_attempted:
        _pool_init_attempted = True
        try:
            from dbutils.pooled_db import PooledDB
            _connection_pool = PooledDB(
                creator=pymysql,
                maxconnections=20,
                mincached=2,
                maxcached=5,
                blocking=True,
                maxusage=None,
                setsession=[],
                ping=1,
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
                cursorclass=pymysql.cursors.DictCursor,
                charset="utf8mb4",
            )
            print("[DB] Connection pool initialized (max=20)")
            return _connection_pool.connection()
        except ImportError:
            print("[DB] WARNING: dbutils not installed, using direct connections.")
        except Exception as e:
            print(f"[DB] Pool init failed ({e}), using direct connections.")
    # Fallback: direct connection
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
    )

_connection_pool = None
_pool_init_attempted = False


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------
def init_db():
    """Create the database + all tables (idempotent). Waits for MySQL with retries."""
    if not _wait_for_mysql(max_retries=5, delay=3):
        raise RuntimeError(
            f"Cannot connect to MySQL at {MYSQL_HOST}:{MYSQL_PORT} as '{MYSQL_USER}'. "
            "Please ensure MySQL is running and credentials are correct."
        )
    # Step 1: Create DB if not exists
    root_conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        connect_timeout=10
    )
    try:
        with root_conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        root_conn.commit()
    finally:
        root_conn.close()

    # Step 2: Create tables
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # users
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    username    VARCHAR(50)  UNIQUE NOT NULL,
                    email       VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_admin    TINYINT NOT NULL DEFAULT 0,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # user_sessions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    token         VARCHAR(255) PRIMARY KEY,
                    user_id       INT NOT NULL,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # user_profiles
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id     INT PRIMARY KEY,
                    fullname    VARCHAR(100),
                    email       VARCHAR(100),
                    phone       VARCHAR(20),
                    cv_text     MEDIUMTEXT,
                    cv_filename VARCHAR(255),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # jobs — real scraped data with cache support
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id          VARCHAR(64)  PRIMARY KEY,
                    title       VARCHAR(500) NOT NULL,
                    company     VARCHAR(500) NOT NULL,
                    location    VARCHAR(1000) NOT NULL,
                    work_type   VARCHAR(50)  NOT NULL,
                    commitment  VARCHAR(50)  NOT NULL,
                    platform    VARCHAR(100) NOT NULL,
                    description MEDIUMTEXT   NOT NULL,
                    apply_url   VARCHAR(2048) NOT NULL,
                    easy_apply  TINYINT NOT NULL DEFAULT 0,
                    posted_date VARCHAR(50)  NOT NULL,
                    source_url  VARCHAR(2048),
                    cache_key   VARCHAR(64),
                    scraped_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # api_settings — API keys & provider configuration managed from admin
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_settings (
                    setting_key   VARCHAR(100) PRIMARY KEY,
                    setting_value MEDIUMTEXT   NOT NULL,
                    description   VARCHAR(500) NOT NULL DEFAULT '',
                    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

        conn.commit()

        # Run safe migrations for existing installs
        _run_migrations(conn)

        # Create indexes for hot queries (idempotent)
        _create_indexes(conn)

        # Seed default settings rows (only if not already present)
        _seed_default_settings(conn)

        # Seed admin user
        _seed_admin(conn)

    finally:
        conn.close()


def _create_indexes(conn):
    """Create performance indexes (idempotent — ignores if already exists)."""
    indexes = [
        "CREATE INDEX idx_jobs_cache_key ON jobs(cache_key, scraped_at)",
        "CREATE INDEX idx_sessions_last_activity ON user_sessions(last_activity)",
    ]
    with conn.cursor() as cur:
        for sql in indexes:
            try:
                cur.execute(sql)
                conn.commit()
                idx_name = sql.split("INDEX ")[1].split(" ON")[0]
                print(f"[DB] Created index {idx_name}")
            except Exception:
                # Index already exists — safe to ignore
                pass


def _run_migrations(conn):
    """Safely add new columns to existing tables and widen columns if needed."""
    migrations = [
        ("jobs", "source_url",  "ALTER TABLE jobs ADD COLUMN source_url  VARCHAR(2048) NULL"),
        ("jobs", "cache_key",   "ALTER TABLE jobs ADD COLUMN cache_key   VARCHAR(64)   NULL"),
        ("jobs", "scraped_at",  "ALTER TABLE jobs ADD COLUMN scraped_at  TIMESTAMP     NULL"),
        ("users", "is_admin",   "ALTER TABLE users ADD COLUMN is_admin   TINYINT NOT NULL DEFAULT 0"),
        ("user_sessions", "last_activity",
         "ALTER TABLE user_sessions ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    ]
    with conn.cursor() as cur:
        for table, column, sql in migrations:
            try:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                    (MYSQL_DATABASE, table, column)
                )
                if cur.fetchone()["cnt"] == 0:
                    cur.execute(sql)
                    conn.commit()
                    print(f"[DB Migration] Added column {table}.{column}")
            except Exception as e:
                print(f"[DB Migration] {table}.{column}: {e}")

        # Ensure column widths are large enough
        col_modifications = [
            ("title", "ALTER TABLE jobs MODIFY COLUMN title VARCHAR(500) NOT NULL"),
            ("company", "ALTER TABLE jobs MODIFY COLUMN company VARCHAR(500) NOT NULL"),
            ("location", "ALTER TABLE jobs MODIFY COLUMN location VARCHAR(1000) NOT NULL"),
            ("apply_url", "ALTER TABLE jobs MODIFY COLUMN apply_url VARCHAR(2048) NOT NULL"),
            ("source_url", "ALTER TABLE jobs MODIFY COLUMN source_url VARCHAR(2048) NULL"),
        ]
        for col, sql in col_modifications:
            try:
                cur.execute(
                    "SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'jobs' AND COLUMN_NAME = %s",
                    (MYSQL_DATABASE, col)
                )
                row = cur.fetchone()
                if row:
                    current_length = row["CHARACTER_MAXIMUM_LENGTH"] or 0
                    target_length = 500 if col in ["title", "company"] else (1000 if col == "location" else 2048)
                    if current_length < target_length:
                        cur.execute(sql)
                        conn.commit()
                        print(f"[DB Migration] Modified column jobs.{col} to support up to {target_length} characters (was {current_length}).")
            except Exception as e:
                print(f"[DB Migration] Error altering jobs.{col}: {e}")


def _seed_default_settings(conn):
    """Insert default api_settings rows with empty values so admin can fill them."""
    defaults = [
        ("ADZUNA_APP_ID",    "", "Adzuna API App ID — get free at developer.adzuna.com"),
        ("ADZUNA_APP_KEY",   "", "Adzuna API App Key — get free at developer.adzuna.com"),
        ("JOOBLE_API_KEY",   "", "Jooble API Key — register free at jooble.org/api/about"),
        ("JSEARCH_API_KEY",  "", "JSearch RapidAPI Key — subscribe free at rapidapi.com (JSearch)"),
        ("APIFY_TOKEN",      "", "Apify Cloud Token — create account at apify.com"),
        ("BRIGHTDATA_PROXY", "", "Bright Data proxy URL — optional, for anti-block rotation"),
        ("GREENHOUSE_COMPANIES", "stripe,airbnb,notion,figma,linear,vercel,cloudflare,discord,shopify,dropbox,datadog,hashicorp,mongodb,elastic,confluent,okta,twilio,sendgrid,segment,brex,rippling,lattice,deel,gusto,carta,plaid,checkr,greenhouse,lever", "Greenhouse board tokens (comma-separated)"),
        ("LEVER_COMPANIES",  "netflix,reddit,box,figma,scale,openai,anthropic,cohere,databricks,dbt-labs,prefect,temporal,planetscale,neon,supabase,render,fly,railway,turso,tinybird,prisma", "Lever company slugs (comma-separated)"),
        ("ASHBY_COMPANIES",  "ashby,retool,ramp,brex,rippling,deel,lattice,mercury,benchling,verkada,clickhouse,dbt,airbyte,meltano,posthog,metabase,cal,liveblocks,clerk,resend,loops,trigger", "Ashby board names (comma-separated)"),
        ("SMARTRECRUITERS_COMPANIES", "spotify,philips,bosch,lidl,delivery-hero,talabat,wire,adyen,booking,trivago,zalando,n26,hellofresh,personio,celonis,contentful,sumup", "SmartRecruiters company IDs (comma-separated)"),
    ]
    with conn.cursor() as cur:
        for key, value, desc in defaults:
            cur.execute(
                """INSERT IGNORE INTO api_settings (setting_key, setting_value, description)
                   VALUES (%s, %s, %s)""",
                (key, value or "", desc or "")
            )
    conn.commit()


def _seed_admin(conn):
    """Create the default admin user if it doesn't exist.
    Password is read from ADMIN_DEFAULT_PASSWORD env var, or a random one is generated."""
    import hashlib
    import secrets as _secrets
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE username = %s", ("admin",))
        if not cur.fetchone():
            admin_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "")
            if not admin_password:
                admin_password = _secrets.token_urlsafe(16)
                print("=" * 60)
                print("[DB] ADMIN USER CREATED")
                print(f"  Username: admin")
                print(f"  Password: {admin_password}")
                print("  >>> CHANGE THIS PASSWORD IMMEDIATELY <<<")
                print("  (Set ADMIN_DEFAULT_PASSWORD env var to avoid this)")
                print("=" * 60)
            else:
                print("[DB] Seeding admin user with password from ADMIN_DEFAULT_PASSWORD env var.")
            salt = os.urandom(16)
            pwd_hash = hashlib.pbkdf2_hmac("sha256", admin_password.encode("utf-8"), salt, 100000)
            hashed = f"{salt.hex()}:{pwd_hash.hex()}"
            cur.execute(
                "INSERT INTO users (username, email, password_hash, is_admin) VALUES (%s,%s,%s,%s)",
                ("admin", "admin@jobseeker.ai", hashed, 1)
            )
    conn.commit()
