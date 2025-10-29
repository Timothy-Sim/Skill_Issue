import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT # Needed for CREATE DATABASE
from dotenv import load_dotenv
import re # Will be used to parse the DATABASE_URL

def create_database_and_tables():
    """
    Connects to the default 'postgres' database,
    creates the target database if it doesn't exist,
    then connects to the target database and creates tables.
    """
    conn = None
    cur = None
    
    try:
        # Load environment variables from .env file
        load_dotenv()
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("Error: DATABASE_URL not found in .env file.")
            return

        # --- Step 1: Parse the DATABASE_URL ---
        # We need to find the database name and create a new URL to connect to the default 'postgres' db
        match = re.match(r"postgresql://(.*?@.*?\/)(.*)", database_url)
        if not match:
            print(f"Error: DATABASE_URL format is incorrect. Could not parse: {database_url}")
            return
            
        base_url_part = match.group(1)   # e.g., 'postgres:pass@skill-issue.c2nuqkyeqeam.us-east-1.rds.amazonaws.com:5432/'
        db_name_to_create = match.group(2) # e.g., 'skill-issue'
        
        # Connection string for the default 'postgres' database
        admin_db_url = f"postgresql://{base_url_part}postgres"

        # --- Step 2: Connect to 'postgres' DB and CREATE our new DB ---
        print(f"Connecting to default 'postgres' database to create '{db_name_to_create}'...")
        conn = psycopg2.connect(admin_db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT) # CREATE DATABASE cannot run inside a transaction
        cur = conn.cursor()
        
        # Check if database already exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name_to_create,))
        exists = cur.fetchone()
        
        if not exists:
            print(f"Database '{db_name_to_create}' not found. Creating it now...")
            cur.execute(f'CREATE DATABASE "{db_name_to_create}"') # Use f-string with quotes for safety, as %s doesn't work here
            print(f"Database '{db_name_to_create}' created successfully.")
        else:
            print(f"Database '{db_name_to_create}' already exists.")
            
        cur.close()
        conn.close()

        # --- Step 3: Connect to the new DB and create tables ---
        print(f"Connecting to the '{db_name_to_create}' database...")
        conn = psycopg2.connect(database_url) # Use the original DATABASE_URL
        cur = conn.cursor()

        # --- Create Users Table ---
        create_users_table_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            google_id VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE,
            name VARCHAR(255),
            chess_com_username VARCHAR(100) UNIQUE NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        print("Creating 'users' table (if it doesn't exist)...")
        cur.execute(create_users_table_sql)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);")

        # --- Create Games Table ---
        create_games_table_sql = """
        CREATE TABLE IF NOT EXISTS games (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source VARCHAR(50),
            source_game_id VARCHAR(100),
            game_url VARCHAR(512) NULL,
            pgn_data TEXT NOT NULL,
            game_date TIMESTAMP WITH TIME ZONE NOT NULL,
            analyzed_at TIMESTAMP WITH TIME ZONE NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, source, source_game_id)
        );
        """
        print("Creating 'games' table (if it doesn't exist)...")
        cur.execute(create_games_table_sql)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_games_user_id ON games(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_games_game_date ON games(game_date);")


        # --- Create Habits Table ---
        create_habits_table_sql = """
        CREATE TABLE IF NOT EXISTS habits (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            habit_name VARCHAR(255) NOT NULL,
            description TEXT NULL,
            date_identified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            date_remedied TIMESTAMP WITH TIME ZONE NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, habit_name)
        );
        """
        print("Creating 'habits' table (if it doesn't exist)...")
        cur.execute(create_habits_table_sql)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_habits_user_id ON habits(user_id);")

        # --- Create Mistakes Table ---
        create_mistakes_table_sql = """
        CREATE TABLE IF NOT EXISTS mistakes (
            id SERIAL PRIMARY KEY,
            game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
            habit_id INTEGER NULL REFERENCES habits(id) ON DELETE SET NULL,
            move_number INTEGER NOT NULL,
            player_color VARCHAR(5) NOT NULL CHECK (player_color IN ('white', 'black')),
            prior_fen TEXT NOT NULL,
            move_made VARCHAR(10) NOT NULL,
            mistake_type VARCHAR(100) NULL,
            stockfish_eval_before VARCHAR(20) NULL,
            stockfish_eval_after VARCHAR(20) NULL,
            best_move VARCHAR(10) NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        print("Creating 'mistakes' table (if it doesn't exist)...")
        cur.execute(create_mistakes_table_sql)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mistakes_game_id ON mistakes(game_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mistakes_habit_id ON mistakes(habit_id);")

        # --- Create Feedback Table ---
        create_feedback_table_sql = """
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
            feedback_text TEXT NOT NULL,
            generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
        print("Creating 'feedback' table (if it doesn't exist)...")
        cur.execute(create_feedback_table_sql)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_habit_id ON feedback(habit_id);")


        # Commit the changes for table creation
        conn.commit()
        print("Tables created successfully (or already existed).")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while connecting to or setting up PostgreSQL: {error}")
        if conn:
            conn.rollback() # Rollback changes if error occurred
    finally:
        if cur:
            cur.close()
        if conn is not None:
            conn.close()
            print('Database connection closed.')

if __name__ == '__main__':
    create_database_and_tables()

