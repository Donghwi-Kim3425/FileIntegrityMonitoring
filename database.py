#database.py
import psycopg
from psycopg.rows import dict_row
import os
from datetime import datetime
from config import DB_PARAMS

class DatabaseManager:
    def __init__(self, db_connection):
        self.db_connection = db_connection
        pass

    def execute_query(self, query, params=None, fetch_all=True, use_dict_row=False):
        with self.connect() as conn:
            row_factory = dict_row if use_dict_row else None
            with conn.cursor(row_factory=row_factory) as cursor: # row_factory 설정
                cursor.execute(query, params if params else ())
                if fetch_all:
                    return cursor.fetchall()
                else:
                    return cursor.fetchone()


    @staticmethod
    def connect():
        """
        데이터베이스 연결 생성

        :Returns
            psycopg.Connection: 데이터베이스 연결 객체
        """
        return psycopg.connect(**DB_PARAMS)

    def get_file_id(self, file_path):
        """
        파일 경로로 파일 ID 조회

        Args:
            file_path (str): 조회할 파일 경로

        Returns:
            int or None: 파일 ID, 해당 경로의 파일이 없으면 None
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM Files WHERE file_path = %s", (file_path,))
                result = cur.fetchone()
                return result[0] if result else None

    def get_file_hash(self, file_path):
        """
        파일 경로로 해시값 조회

        Args:
            file_path (str): 조회할 파일 경로

        Returns:
            str or None: 파일 해시값, 해당 경로의 파일이 없으면 None
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT file_hash FROM Files WHERE file_path = %s", (file_path,))
                result = cur.fetchone()
                return result[0] if result else None

    def get_file_status(self, file_path):
        """
        파일 경로로 상태 조회

        Args:
            file_path (str): 조회할 파일의 경로

        Returns:
            str or None: 파일 상태, 해당 경로의 파일이 없으면 None
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM Files WHERE file_path = %s", (file_path,))
                result = cur.fetchone()
                return result[0] if result else None

    def get_files_due_for_check(self):
        """
        검사가 필요한 파일 목록 조회

        Returns:
            list: 검사가 필요한 파일들의 (id, file_path, check_interval, updated_at) 튜플 리스트
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, file_path, check_interval, updated_at
                    FROM Files
                    WHERE updated_at + check_interval <= NOW()
                    """)
                return cur.fetchall()

    def update_file_record(self, file_path, new_hash, user_id):
        """
        파일 레코드 업데이트 (신규/수정/변경없음 처리)

        Args:
            file_path (str): 업데이트 할 파일의 경로
            new_hash (str): 파일의 새로운 해시값
            user_id (int): 파일을 업데이트하는 사용자의 ID
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, file_hash, status FROM Files WHERE file_path = %s", (file_path,))
                file_record = cur.fetchone()

                if file_record:
                    self._update_existing_file(cur, file_record, new_hash, file_path)
                else:
                    self._create_new_file(cur, file_path, new_hash, user_id)

            conn.commit()
        print("DB 업데이트 완료.")

    def _update_existing_file(self, cur, file_record, new_hash, file_path):
        """
        기존 파일 레코드 업데이트

        Args:
            cur (psycopg.Cursor): 데이터베이스 커서 객체
            file_record (tuple): 파일 레코드 (id, file_hash, status)
            new_hash (str): 파일의 새로운 해시값
            file_path (str): 업데이트할 파일의 경로
        """
        file_id, old_hash, status = file_record

        if new_hash == old_hash:
            print(f"[UNCHANGED] {file_path}")
            self._update_unchanged_file(cur, file_id, status, old_hash)
        else:
            print(f"[MODIFIED] {file_path}")
            self._update_modified_file(cur, file_id, old_hash, new_hash, file_path)


    def _update_unchanged_file(self, cur, file_id, current_status, file_hash):
        """
        파일 상태가 변경되지 않은 경우 처리 (내부 함수)

        Args:
            cur (psycopg.Cursor): 데이터베이스 커서 객체
            file_id (int): 파일 ID
            current_status (str): 현재 파일 상태
            file_hash (str): 파일 해시값
        """
        # 상태가 Unchanged가 아닐 때만 로그를 생성
        if current_status != 'Unchanged':
            cur.execute(
                "INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at) "
                "VALUES (%s, %s, %s, 'Unchanged', %s)",
                (file_id, file_hash, file_hash, datetime.now())
            )

            # 상태 업데이트
            cur.execute(
                "UPDATE Files SET updated_at = %s, status = 'Unchanged' WHERE id = %s",
                (datetime.now(), file_id)
            )
        else:
            # 상태가 이미 Unchanged이면 updated_at만 갱신하고 로그는 생성하지 않음
            cur.execute(
                "UPDATE Files SET updated_at = %s WHERE id = %s",
                (datetime.now(), file_id)
            )

    def _update_modified_file(self, cur, file_id, old_hash, new_hash, file_path):
        """
        파일 상태가 변경된 경우 처리

        Args:
            cur (psycopg.Cursor): 데이터베이스 커서 객체
            file_id (int): 파일 ID
            old_hash (str): 이전 파일 해시값
            new_hash (str): 새로운 파일 해시값
            file_path (str): 파일 경로
        """
        cur.execute(
            "UPDATE Files SET file_hash = %s, updated_at = %s, status = 'Modified' WHERE id = %s",
            (new_hash, datetime.now(), file_id)
        )

        # 로그 생성 또는 업데이트
        cur.execute(
            "SELECT id FROM File_logs WHERE file_id = %s ORDER BY logged_at DESC LIMIT 1", (file_id,))
        log_record = cur.fetchone()

        self._create_file_log(cur, file_id, old_hash, new_hash, 'Modified')

        alert_message = f"파일 '{os.path.basename(file_path)}' ({file_path}) 이(가) 변경되었습니다."
        self.create_alert(cur, file_id, alert_message)

        user_email = self.get_user_email_by_file_id(file_id)

        if user_email:
            print(f"알림을 발송할 사용자 이메일:" {user_email}
            # alerts.py의 이메일 발송 함수 호출 코드


    def _create_new_file(self, cur, file_path, new_hash, user_id):
        """
        새 파일 레코드 생성 (내부 함수)

        Args:
            cur (psycopg.Cursor): 데이터베이스 커서 객체
            file_path (str): 생성할 파일의 경로
            new_hash (str) 파일의 해시값
            user_id (int): 파일을 생성한 사용자의 ID
        """
        print(f"[NEW FILE] {file_path}")
        cur.execute(
            "INSERT INTO Files (user_id, file_name, file_path, file_hash, status, check_interval, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, 'Unchanged', INTERVAL '60 minutes', %s, %s) RETURNING id",
            (user_id, os.path.basename(file_path), file_path, new_hash, datetime.now(), datetime.now())
        )
        file_id = cur.fetchone()[0]
        self._create_file_log(cur, file_id, None, new_hash, 'UserUpdated')

    def _create_file_log(self, cur, file_id, old_hash, new_hash, change_type):
        """
        파일 로그 생성

        Args:
            cur (psycopg.Cursor): 데아터베이스 커서 객체
            file_id (int): 파일 ID
            old_hash (str or None): 이전 파일 해시값 (새 파일인 경우 None)
            new_hash (str): 새로운 파일 해시값
            change_type (str): 변경 유형 ('Unchanged', 'Modified', 'UserUpdated', 'Deleted', 'Recovered')

        """
        cur.execute(
            "INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (file_id, old_hash, new_hash, change_type, datetime.now())
        )

    def log_file_change(self, file_path, old_hash, new_hash, change_type):
        """
        파일 변경 로그 생성

        Args:
            file_path (str): 변경된 파일의 경로
            old_hash (str or None): 이전 파일 해시값
            new_hash (str): 새로운 파일 해시값
            change_type (str): 변경 유형 ('UserUpdated', 등)
        """
        file_id = self.get_file_id(file_path)
        if not file_id:
            return

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (file_id, old_hash, new_hash, change_type, datetime.now()))
            conn.commit()

    def mark_file_as_deleted(self, file_path):
        """
            파일을 삭제됨으로 표시

            Args:
                file_path (str): 삭제된 파일의 경로
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, file_hash FROM Files WHERE file_path = %s", (file_path,))
                result = cur.fetchone()
                if result:
                    file_id, old_hash = result
                    print(f"[DELETED] {file_path}")
                    cur.execute(
                        "UPDATE Files SET status = 'Deleted', updated_at = %s WHERE id = %s",
                        (datetime.now(), file_id)
                    )
                    cur.execute(
                        "INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at) "
                        "VALUES (%s, %s, NULL, 'Deleted', %s)",
                        (file_id, old_hash, datetime.now())
                    )
            conn.commit()

    def mark_file_as_recovered(self, file_path):
        """
        파일을 복구됨으로 표시

        Args:
            file_path (str): 복구된 파일의 경로
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, file_hash FROM Files WHERE file_path = %s", (file_path,))
                result = cur.fetchone()
                if result:
                    file_id, file_hash = result
                    print(f"[RECOVERED] 파일이 복구됨: {file_path}")
                    cur.execute(
                        "UPDATE Files SET status = 'Recovered', updated_at = %s WHERE id = %s",
                        (datetime.now(), file_id)
                    )
                    cur.execute(
                        "INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at) "
                        "VALUES (%s, NULL, %s, 'Recovered', %s)",
                        (file_id, file_hash, datetime.now())
                    )
            conn.commit()

    def get_files_for_user(self, user_id):
        """
        특정 사용자의 파일 목록을 딕셔너리 리스트로 반환

        Args:
            user_id

        :return:
            files
        """
        query = """
                   SELECT id, file_path, check_interval, updated_at
                   FROM files
                   WHERE user_id = %s
               """
        result = self.execute_query(query, (user_id,), fetch_all=True, use_dict_row=True)
        return result if result else [] # 결과가 없을 경우 빈 리스트 반환

    def create_alert(self, cur, file_id, message):
        """
        파일 변경 감지 시 정보를 alerts 테이블에 기록

        Args:
            cur (psycopg.Cursor): 데아터베이스 커서 객체
            file_id (int): 파일 ID
            message (str): 알림 메시지 내용
        """
        cur.execute(
            "INSERT INTO alerts (file_id, message, is_read, created_at, resolved) "
            "VALUES (%s, %s, %s, %s, %s)",
            (file_id, message, False, datetime.now(), False)
        )

    def get_user_email_by_file_id(self, file_id):
        """
        파일 ID를 사용하여 해당 파일을 소유한 사용자의 이메일 주소를 조회

        Args:
            cur (psycopg.Cursor): 데아터베이스 커서 객체
            file_id (int) 조회할 파일의 ID

        Returns:
            str or None: 사용자의 이메일 주소. 찾지 못한 경우 None을 반환
        """
        # users 테이블과 Files 테이블을 user_id 기준으로 Join
        # 특정 file_id(f.id)를 가진 사용자의 email(u.email)을 선택
        query = """
            SELECT u.email
            FROM Users u
            JOIN Files f ON u.user_id = f.user_id
            WHERE f.id = %s
        """

        result = self.execute_query(query, (file_id,), fetch_all=False, use_dict_row=False)
        if result:
            # 결과가 있으면 첫 번째 컬럼(email) 반환
            return result[0]
        else:
            # 해당 file_id나 연결된 사용자가 없는 경우
            print(f"⚠️ file_id {file_id}에 해당하는 사용자 이메일을 찾을 수 없습니다.")
            return None

def get_or_create_user(username, email):
    """
    이메일 주소를 기반으로 사용자를 조회하거나 새로 생성

    Args:
        username (str): 사용자 이름
        email (str): 사용자 이메일 주소

    Returns:
        dict: 사용자 정보 (user_id, username, email)
    """
    with DatabaseManager.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, username, email FROM Users WHERE email = %s", (email,))
            user = cur.fetchone()
            if user:
                return {"user_id": user[0], "username": user[1], "email": user[2]}

            cur.execute(
                "INSERT INTO Users (username, email, created_at) VALUES (%s, %s, NOW()) RETURNING user_id",
                (username, email)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            return {"user_id": user_id, "username": username, "email": email}