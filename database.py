# database.py
import psycopg, os
from psycopg.rows import dict_row
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union
from alerts import send_notification_email, send_windows_notification
from config import DB_PARAMS

class DatabaseManager:
    def __init__(self, db_connection):
        """
        DatabaseManager 초기화
        
        Args:
            db_connection: 데이터베이스 연결 객체
        """
        self.db_connection = db_connection
    
    @staticmethod
    def connect():
        """
        데이터베이스 연결 생성
        
        Returns:
            psycopg.Connection: 데이터베이스 연결 객체
        """
        return psycopg.connect(**DB_PARAMS)
    
    def execute_query(self, query: str, params: Optional[Tuple] = None, 
                      fetch_all: bool = True, use_dict_row: bool = False) -> Union[List, Tuple, None]:
        """
        SQL 쿼리 실행 및 결과 반환
        
        Args:
            query: 실행할 SQL 쿼리
            params: 쿼리 파라미터
            fetch_all: 모든 결과를 가져올지 여부 (False면 첫 번째 결과만 반환)
            use_dict_row: 결과를 딕셔너리 형태로 반환할지 여부
            
        Returns:
            쿼리 실행 결과
        """
        try:
            with self.db_connection.cursor(row_factory=dict_row if use_dict_row else None) as cursor:
                cursor.execute(query, params if params else ())
                
                # 쿼리가 SELECT가 아닌 경우 결과를 반환하지 않음
                if not query.strip().upper().startswith(('SELECT', 'RETURNING')):
                    return None
                
                if fetch_all:
                    return cursor.fetchall()
                else:
                    return cursor.fetchone()
        except Exception as e:
            print(f"쿼리 실행 오류: {e}")
            return None
    
    # =============== 파일 정보 조회 메서드 ===============
    
    def get_file_id(self, file_path: str) -> Optional[int]:
        """
        파일 경로로 파일 ID 조회
        
        Args:
            file_path: 조회할 파일 경로
            
        Returns:
            파일 ID 또는 없을 경우 None
        """
        query = "SELECT id FROM Files WHERE file_path = %s"
        result = self.execute_query(query, (file_path,), fetch_all=False)
        return result[0] if result else None
    
    def get_file_hash(self, file_path: str) -> Optional[str]:
        """
        파일 경로로 해시값 조회
        
        Args:
            file_path: 조회할 파일 경로
            
        Returns:
            파일 해시값 또는 없을 경우 None
        """
        query = "SELECT file_hash FROM Files WHERE file_path = %s"
        result = self.execute_query(query, (file_path,), fetch_all=False)
        return result[0] if result else None
    
    def get_file_status(self, file_path: str) -> Optional[str]:
        """
        파일 경로로 상태 조회
        
        Args:
            file_path: 조회할 파일 경로
            
        Returns:
            파일 상태 또는 없을 경우 None
        """
        query = "SELECT status FROM Files WHERE file_path = %s"
        result = self.execute_query(query, (file_path,), fetch_all=False)
        return result[0] if result else None
    
    def get_files_due_for_check(self) -> List:
        """
        검사가 필요한 파일 목록 조회
        
        Returns:
            검사가 필요한 파일 목록
        """
        query = """
            SELECT id, file_path, check_interval, updated_at
            FROM Files
            WHERE updated_at + check_interval <= NOW()
        """
        return self.execute_query(query)
    
    def get_files_for_user(self, user_id: int) -> List[Dict]:
        """
        특정 사용자의 파일 목록 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            사용자의 파일 목록
        """
        query = """
            SELECT id, file_path, check_interval, updated_at
            FROM files
            WHERE user_id = %s
        """
        result = self.execute_query(query, (user_id,), fetch_all=True, use_dict_row=True)
        return result if result else []
    
    def get_user_email_by_file_id(self, file_id: int) -> Optional[str]:
        """
        파일 ID로 사용자 이메일 조회
        
        Args:
            file_id: 파일 ID
            
        Returns:
            사용자 이메일 또는 없을 경우 None
        """
        query = """
            SELECT u.email
            FROM Users u
            JOIN Files f ON u.user_id = f.user_id
            WHERE f.id = %s
        """
        result = self.execute_query(query, (file_id,), fetch_all=False)
        if result:
            return result[0]
        else:
            print(f"file_id {file_id}에 해당하는 사용자 이메일을 찾을 수 없습니다.")
            return None
    
    # =============== 로그 및 알림 관련 메서드 ===============
    
    def create_file_log(self, cur, file_id: int, old_hash: Optional[str], new_hash: Optional[str], 
                        change_type: str, event_time: Optional[datetime] = None) -> None:
        """
        파일 변경 로그 생성
        
        Args:
            cur: 데이터베이스 커서
            file_id: 파일 ID
            old_hash: 이전 해시값
            new_hash: 새 해시값
            change_type: 변경 유형
            event_time: 이벤트 발생 시간 (기본값: 현재 시간)
        """
        log_time = event_time if event_time else datetime.now()
        cur.execute(
            "INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (file_id, old_hash, new_hash, change_type, log_time)
        )
    
    def create_alert(self, cur, file_id: int, message: str, event_time: Optional[datetime] = None) -> None:
        """
        파일 변경 알림 생성
        
        Args:
            cur: 데이터베이스 커서
            file_id: 파일 ID
            message: 알림 메시지
            event_time: 알림 발생 시간 (기본값: 현재 시간)
        """
        alert_time = event_time if event_time else datetime.now()
        cur.execute(
            "INSERT INTO alerts (file_id, message, created_at) "
            "VALUES (%s, %s, %s)",
            (file_id, message, alert_time)
        )
    
    def send_notifications(self, cur, file_id: int, file_path: str, old_hash: str, 
                          new_hash: str, time_now: datetime) -> None:
        """
        파일 변경에 대한 알림 발송
        
        Args:
            cur: 데이터베이스 커서
            file_id: 파일 ID
            file_path: 파일 경로
            old_hash: 이전 해시값
            new_hash: 새 해시값
            time_now: 현재 시간
        """
        # 알림 메시지 생성
        alert_message = f"파일 '{os.path.basename(file_path)}' ({file_path}) 이(가) 변경되었습니다."
        self.create_alert(cur, file_id, alert_message, time_now)
        
        # 이메일 알림 발송을 위한 사용자 이메일 조회
        cur.execute(
            "SELECT u.email FROM Users u JOIN Files f ON u.user_id = f.user_id WHERE f.id = %s",
            (file_id,)
        )
        result = cur.fetchone()
        user_email = result[0] if result else None
        
        if user_email:
            print(f"알림을 발송할 사용자 이메일: {user_email}")
            subject = f"파일 변경 알림: {os.path.basename(file_path)}"
            body = alert_message + (f"\n\n- 이전 해시: {old_hash}\n"
                                   f"- 새 해시: {new_hash}\n"
                                   f"- 변경 감지 시각: {time_now.strftime('%Y-%m-%d %H:%M:%S')}")
            send_notification_email(user_email, subject, body)
            print(f"이메일 알림 발송 시도: {user_email}")
        else:
            print(f"file_id {file_id}의 사용자 이메일 찾지 못해 이메일 알림을 보낼 수 없습니다.")
        
        # Windows 알림 발송
        print(f"Windows 시스템 알림(plyer) 발송 시도: {file_path}")
        notification_sent = send_windows_notification(
            file_path=file_path,
            old_hash=old_hash,
            new_hash=new_hash,
            change_time=time_now
        )
        
        if notification_sent:
            print(f"Windows 시스템 알림(plyer) 발송 성공: {file_path}")
        else:
            print(f"Windows 시스템 알림(plyer) 발송 실패 또는 지원되지 않음: {file_path}")
    
    # =============== 파일 상태 관리 메서드 ===============
    
    def update_unchanged_file(self, cur, file_id: int, current_status: str, file_hash: str, 
                             time_now: datetime) -> None:
        """
        변경되지 않은 파일 상태 업데이트
        
        Args:
            cur: 데이터베이스 커서
            file_id: 파일 ID
            current_status: 현재 파일 상태
            file_hash: 파일 해시값
            time_now: 현재 시간
        """
        if current_status != 'Unchanged':
            self.create_file_log(cur, file_id, file_hash, file_hash, 'Unchanged', time_now)
            cur.execute(
                "UPDATE Files SET updated_at = %s, status = 'Unchanged' WHERE id = %s",
                (time_now, file_id)
            )
        else:
            # 상태가 이미 Unchanged이면 updated_at만 갱신
            cur.execute(
                "UPDATE Files SET updated_at = %s WHERE id = %s",
                (time_now, file_id)
            )
    
    def update_modified_file(self, cur, file_id: int, old_hash: str, new_hash: str, 
                            file_path: str, time_now: datetime) -> None:
        """
        변경된 파일 상태 업데이트
        
        Args:
            cur: 데이터베이스 커서
            file_id: 파일 ID
            old_hash: 이전 해시값
            new_hash: 새 해시값
            file_path: 파일 경로
            time_now: 현재 시간
        """
        # 파일 상태 업데이트
        cur.execute(
            "UPDATE Files SET file_hash = %s, updated_at = %s, status = 'Modified' WHERE id = %s",
            (new_hash, time_now, file_id)
        )
        
        # 변경 로그 생성
        self.create_file_log(cur, file_id, old_hash, new_hash, 'Modified', time_now)
        
        # 알림 발송
        self.send_notifications(cur, file_id, file_path, old_hash, new_hash, time_now)
    
    def create_new_file(self, cur, file_path: str, new_hash: str, user_id: int, 
                       time_now: datetime) -> None:
        """
        새 파일 레코드 생성
        
        Args:
            cur: 데이터베이스 커서
            file_path: 파일 경로
            new_hash: 파일 해시값
            user_id: 사용자 ID
            time_now: 현재 시간
        """
        print(f"[NEW FILE] {file_path}")
        cur.execute(
            "INSERT INTO Files "
            "(user_id, file_name, file_path, file_hash, status, check_interval, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, 'Unchanged', INTERVAL '60 minutes', %s, %s) RETURNING id",
            (user_id, os.path.basename(file_path), file_path, new_hash, time_now, time_now)
        )
        file_id = cur.fetchone()[0]
        self.create_file_log(cur, file_id, None, new_hash, 'UserUpdated', time_now)
    
    def update_existing_file(self, cur, file_record: Tuple, new_hash: str, file_path: str, 
                            time_now: datetime) -> None:
        """
        기존 파일 레코드 업데이트
        
        Args:
            cur: 데이터베이스 커서
            file_record: 파일 레코드 (id, file_hash, status)
            new_hash: 새 해시값
            file_path: 파일 경로
            time_now: 현재 시간
        """
        file_id, old_hash, status = file_record
        
        if new_hash == old_hash:
            print(f"[UNCHANGED] {file_path}")
            self.update_unchanged_file(cur, file_id, status, old_hash, time_now)
        else:
            print(f"[MODIFIED] {file_path}")
            self.update_modified_file(cur, file_id, old_hash, new_hash, file_path, time_now)
    
    # =============== 공개 API 메서드 ===============
    
    def update_file_record(self, file_path: str, new_hash: str, user_id: int) -> None:
        """
        파일 레코드 업데이트 (신규/수정/변경없음 처리)
        
        Args:
            file_path: 파일 경로
            new_hash: 새 해시값
            user_id: 사용자 ID
        """
        time_now = datetime.now()
        
        with self.db_connection.cursor() as cur:
            # 기존 파일 정보 조회
            cur.execute("SELECT id, file_hash, status FROM Files WHERE file_path = %s", (file_path,))
            file_record = cur.fetchone()
            
            try:
                if file_record:
                    self.update_existing_file(cur, file_record, new_hash, file_path, time_now)
                else:
                    self.create_new_file(cur, file_path, new_hash, user_id, time_now)
                
                # 커밋
                self.db_connection.commit()
                print("DB 업데이트 완료.")
                
            except Exception as e:
                self.db_connection.rollback()
                print(f"파일 레코드 업데이트 중 오류 발생: {e}")
                raise
    
    def mark_file_as_deleted(self, file_path: str) -> None:
        """
        파일을 삭제됨으로 표시
        
        Args:
            file_path: 삭제된 파일 경로
        """
        time_now = datetime.now()
        
        with self.db_connection.cursor() as cur:
            # 파일 정보 조회
            cur.execute("SELECT id, file_hash FROM Files WHERE file_path = %s", (file_path,))
            result = cur.fetchone()
            
            if not result:
                return
                
            file_id, old_hash = result
            print(f"[DELETED] {file_path}")
            
            try:
                # 파일 상태 업데이트
                cur.execute(
                    "UPDATE Files SET status = 'Deleted', updated_at = %s WHERE id = %s",
                    (time_now, file_id)
                )
                
                # 로그 생성
                self.create_file_log(cur, file_id, old_hash, None, 'Deleted', time_now)
                
                # 커밋
                self.db_connection.commit()
                
            except Exception as e:
                self.db_connection.rollback()
                print(f"파일 삭제 표시 중 오류 발생: {e}")
                raise
    
    def mark_file_as_recovered(self, file_path: str) -> None:
        """
        파일을 복구됨으로 표시
        
        Args:
            file_path: 복구된 파일 경로
        """
        time_now = datetime.now()
        
        with self.db_connection.cursor() as cur:
            # 파일 정보 조회
            cur.execute("SELECT id, file_hash FROM Files WHERE file_path = %s", (file_path,))
            result = cur.fetchone()
            
            if not result:
                return
                
            file_id, file_hash = result
            print(f"[RECOVERED] 파일이 복구됨: {file_path}")
            
            try:
                # 파일 상태 업데이트
                cur.execute(
                    "UPDATE Files SET status = 'Recovered', updated_at = %s WHERE id = %s",
                    (time_now, file_id)
                )
                
                # 로그 생성
                self.create_file_log(cur, file_id, None, file_hash, 'Recovered', time_now)
                
                # 커밋
                self.db_connection.commit()
                
            except Exception as e:
                self.db_connection.rollback()
                print(f"파일 복구 표시 중 오류 발생: {e}")
                raise
    
    def log_file_change(self, file_path: str, old_hash: Optional[str], 
                       new_hash: str, change_type: str) -> None:
        """
        파일 변경 로그 생성
        
        Args:
            file_path: 파일 경로
            old_hash: 이전 해시값
            new_hash: 새 해시값
            change_type: 변경 유형
        """
        time_now = datetime.now()
        
        with self.db_connection.cursor() as cur:
            # 파일 ID 조회
            cur.execute("SELECT id FROM Files WHERE file_path = %s", (file_path,))
            result = cur.fetchone()
            
            if not result:
                return
                
            file_id = result[0]
            
            try:
                # 로그 생성
                self.create_file_log(cur, file_id, old_hash, new_hash, change_type, time_now)
                
                # 커밋
                self.db_connection.commit()
                
            except Exception as e:
                self.db_connection.rollback()
                print(f"파일 변경 로그 생성 중 오류 발생: {e}")
                raise


# =============== 독립적인 사용자 관리 함수 ===============

def get_or_create_user(username: str, email: str) -> Dict[str, Any]:
    """
    이메일 주소를 기반으로 사용자 조회 또는 생성
    
    Args:
        username: 사용자 이름
        email: 사용자 이메일
        
    Returns:
        사용자 정보 딕셔너리
    """
    time_now = datetime.now()
    
    with DatabaseManager.connect() as conn:
        with conn.cursor() as cur:
            try:
                # 사용자 조회
                cur.execute("SELECT user_id, username, email FROM Users WHERE email = %s", (email,))
                user = cur.fetchone()
                
                if user:
                    return {"user_id": user[0], "username": user[1], "email": user[2]}
                
                # 새 사용자 생성
                cur.execute(
                    "INSERT INTO Users (username, email, created_at) VALUES (%s, %s, %s) RETURNING user_id",
                    (username, email, time_now)
                )
                user_id = cur.fetchone()[0]
                
                # 트랜잭션 커밋
                conn.commit()
                
                return {"user_id": user_id, "username": username, "email": email}
                
            except Exception as e:
                conn.rollback()
                print(f"사용자 생성 중 오류 발생: {e}")
                raise