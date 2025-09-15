# database.py
from datetime import datetime, timedelta, timezone
from time import timezone
from typing import List, Dict, Tuple, Optional, Any, Union

import os
import psycopg
from psycopg.rows import dict_row

from alerts import send_notification_email, send_windows_notification
from config import DB_PARAMS

class DatabaseManager:
    def __init__(self, conn):
        """
        DatabaseManager 초기화
        
        Args:
            conn: 데이터베이스 연결 객체
        """
        self.conn = conn
    
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
            with self.conn.cursor(row_factory=dict_row if use_dict_row else None) as cursor:
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
    
    def get_file_id(self, file_path: str, user_id: int) -> Optional[int]:
        """
        파일 경로로 파일 ID 조회
        
        Args:
            file_path: 조회할 파일 경로
            user_id: 사용자 ID

        Returns:
            파일 ID 또는 없을 경우 None
        """
        query = "SELECT id FROM Files WHERE file_path = %s AND user_id = %s AND status != 'Deleted'"
        result = self.execute_query(query, (file_path, user_id), fetch_all=False)
        return result[0] if result else None
    
    def get_file_hash(self, file_path: str, user_id: int) -> Optional[str]:
        """
        파일 경로로 해시값 조회
        
        Args:
            file_path: 조회할 파일 경로
            user_id: 사용자 ID
            
        Returns:
            파일 해시값 또는 없을 경우 None
        """
        query = "SELECT file_hash FROM Files WHERE file_path = %s AND user_id = %s AND status != 'Deleted'"
        result = self.execute_query(query, (file_path, user_id), fetch_all=False)
        return result[0] if result else None
    
    def get_file_status(self, file_path: str, user_id: int) -> Optional[str]:
        """
        파일 경로로 상태 조회
        
        Args:
            file_path: 조회할 파일 경로
            user_id: 사용자 ID
            
        Returns:
            파일 상태 또는 없을 경우 None
        """
        query = "SELECT status FROM Files WHERE file_path = %s AND user_id = %s"
        result = self.execute_query(query, (file_path, user_id), fetch_all=False)
        return result[0] if result else None
    
    def get_files_for_user(self, user_id: int) -> List[Dict]:
        """
        특정 사용자의 파일 목록 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            사용자의 파일 목록
        """
        query = """
            SELECT 
                id, 
                file_path, 
                file_hash AS current_hash,
                check_interval, 
                updated_at
            FROM files
            WHERE user_id = %s AND status != 'Deleted'
        """
        raw_files = self.execute_query(query, (user_id,), fetch_all=True, use_dict_row=True)

        if not raw_files:
            return []

        processed_files = []
        for f_dict in raw_files:
            check_interval_val = f_dict.get('check_interval')
            check_interval_seconds = None
            if isinstance(check_interval_val, timedelta):
                check_interval_seconds = check_interval_val.total_seconds()
            elif isinstance(check_interval_val, (int, float)):
                check_interval_seconds = float(check_interval_val)

            processed_files.append({
                "id": f_dict.get('id'),
                "file_path": f_dict.get('file_path'),
                "current_hash": f_dict.get('current_hash'),
                "check_interval": check_interval_seconds,  # 초 단위 float으로 통일
                "updated_at": f_dict.get('updated_at').isoformat() if f_dict.get('updated_at') else None
            })
        return processed_files

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

    def get_file_logs_for_user(self, user_id: int) -> list:
        """
        특정 사용자의 파일 변경 로그 조회
        files 테이블과 JOIN하여 파일 경로를 가져오고, 시간 순으로 정렬
        :param user_id:
        :return:
        """
        query = """
            SELECT DISTINCT ON (f.id)
                f.file_path AS file,
                l.change_type AS status,
                l.logged_at AS time,
                l.old_hash AS oldHash,
                l.new_hash AS newHash,
                f.check_interval AS checkInterval
            FROM file_logs l
            JOIN files f ON l.file_id = f.id
            WHERE f.user_id = %s
            ORDER BY f.id, l.logged_at DESC;
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (user_id,))
                logs = cur.fetchall()
                return logs if logs else []
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error fetching file logs for user {user_id}: {e}")
            return []

    # =============== 로그 및 알림 관련 메서드 ===============

    def create_file_log(self, cur, file_id: int, old_hash: Optional[str], new_hash: Optional[str],
                        change_type: str, detection_source: Optional[str] = "Unknown",
                        event_time: Optional[datetime] = None) -> None:
        """
        파일 변경 로그 생성
        
        Args:
            cur: 데이터베이스 커서
            file_id: 파일 ID
            old_hash: 이전 해시값
            new_hash: 새 해시값
            change_type: 변경 유형
            detection_source: 변경 감지 유형
            event_time: 이벤트 발생 시간 (기본값: 현재 시간)
        """
        log_time = event_time if event_time else datetime.now()
        cur.execute(
            "INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at, detection_source) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (file_id, old_hash, new_hash, change_type, log_time, detection_source)
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
    
    def send_notifications(self, cur, file_id: int, file_path: str, old_hash: Optional[str],
                            new_hash: Optional[str], time_now: datetime,
                            change_type: str = "Modified", detection_source: Optional[str] = "unknown") -> None:
        """
        파일 변경에 대한 알림 발송

        Args:
            cur: 데이터베이스 커서
            file_id: 파일 ID
            file_path: 파일 경로
            old_hash: 이전 해시값
            new_hash: 새 해시값
            time_now: 현재 시간
            change_type: 변경 유형
            detection_source: 변경 감지 유형
        """
        # 알림 메시지 생성
        file_basename = os.path.basename(file_path)

        source_text = f"(감지: {detection_source})" if detection_source else ""
        alert_message_base = f"파일 '{file_basename}' ({file_path}) 상태 변경: {change_type}{source_text}"

        alert_message_detail = ""
        if change_type == "Modified" and old_hash and new_hash:
            alert_message_detail = f"\n- 이전 해시: {old_hash}\n- 현재 해시: {new_hash}"

        elif change_type == "Deleted":
            alert_message_detail = f"\n- 이전 해시: {old_hash or 'N/A'}"

        elif change_type in ["Created", "UserUpdated", "Registered"]:  # Registered 추가
            alert_message_detail = f"\n- 현재 해시: {new_hash or 'N/A'}"

        full_alert_message = alert_message_base + alert_message_detail
        self.create_alert(cur, file_id, full_alert_message, time_now)

        user_email = self.get_user_email_by_file_id(file_id)

        if user_email:
            print(f"알림을 발송할 사용자 이메일: {user_email}")
            subject = f"파일 {change_type} 알림: {file_basename}{source_text}"
            body = full_alert_message + f"\n- 변경/감지 시각: {time_now.strftime('%Y-%m-%d %H:%M:%S')}"
            # body += "\n\n웹사이트에서 확인: [여기에 웹사이트 링크]" # TODO: 사이트 주소 추가
            send_notification_email(user_email, subject, body)
            print(f"이메일 알림 발송 시도 완료: {user_email}")

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

    def save_backup_entry(self, file_id: int, backup_path: str, backup_hash: str, created_at: datetime) -> Optional[int]:
        """
        백업 정보를 backups 테이블에 저장

        :param file_id: 원본 파일의 ID
        :param backup_path: Google Drive에 저장된 파일의 경로
        :param backup_hash: 백업된 파일 내용의 해시
        :param created_at: 백업 생성 시간

        :return: 성공시 백업 레코드의 ID, 실패 시 None.
        """
        query = """
            INSERT INTO backups (file_id, backup_path, backup_hash, created_at)
            VALUES (%s, %s, %s, %s) RETURNING id
        """
        try:
            aware_created_at = created_at.astimezone(timezone.utc) if created_at.tzinfo is None else created_at

            with self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (file_id, backup_path, backup_hash, aware_created_at))
                backup_id_row = cur.fetchone()
                self.conn.commit()

                if backup_id_row:
                    return backup_id_row['id']
                return None

        except psycopg.Error as db_err:
            self.conn.rollback()
            print(f"DB 오류 발생 (save_backup_entry): {db_err}")
            import traceback
            traceback.print_exc()
            return None

        except Exception as e:
            self.conn.rollback()
            print(f"일반 오류 발생 (save_backup_entry): {e}")
            import traceback
            traceback.print_exc()
            return None

    # =============== 내부 파일 상태 관리 메서드 (handle_file_report 등에서 사용) ===============
    
    def _update_unchanged_file_status(self, cur, file_id: int, current_db_status: str, current_db_hash: str, 
                                      time_now: datetime, detection_source: Optional[str]) -> None:
        """
        변경되지 않은 파일 상태 업데이트
        
        Args:
            cur: 데이터베이스 커서
            file_id: 파일 ID
            current_db_status: 현재 파일 상태
            current_db_hash: 파일 해시값
            time_now: 현재 시간
            detection_source: 변경 감지 유형
        """
        if current_db_status != 'Unchanged': # 상태가 실제로 변경될 때만 로그 기록
            self.create_file_log(cur, file_id, current_db_hash, current_db_status, 'Unchanged', detection_source=detection_source, event_time=time_now)

        cur.execute(# 상태가 Unchanged가 아니었다면 Unchanged로 변경, 시간 업데이트. 이미 Unchanged면 시간만 업데이트.
            "UPDATE Files SET updated_at = %s, status = 'Unchanged' WHERE id = %s",
            (time_now, file_id)
        )
    
    def _update_modified_file_status(self, cur, file_id: int, old_hash: str, new_hash: str,
                                     file_path: str, time_now: datetime, detection_source: Optional[str]) -> None:
        """
        변경된 파일 상태 업데이트
        
        Args:
            cur: 데이터베이스 커서
            file_id: 파일 ID
            old_hash: 이전 해시값
            new_hash: 새 해시값
            file_path: 파일 경로
            time_now: 현재 시간
            detection_source: 변경 감지 유형
        """
        # 파일 상태 업데이트
        cur.execute(
            "UPDATE Files SET file_hash = %s, updated_at = %s, status = 'Modified' WHERE id = %s",
            (new_hash, time_now, file_id)
        )
        
        # 변경 로그 생성
        self.create_file_log(cur, file_id, old_hash, new_hash, 'Modified', detection_source=detection_source, event_time=time_now)
        
        # 알림 발송
        self.send_notifications(cur, file_id, file_path, old_hash, new_hash, time_now, "Modified", detection_source)

    def _register_new_file_entry(self, cur, file_path: str, new_hash: str, user_id: int,
                                 time_now: datetime, detection_source: Optional[str],
                                 check_interval_seconds: int = 86400) -> int:
        """
        새 파일 레코드 생성
        
        Args:
            cur: 데이터베이스 커서
            file_path: 파일 경로
            new_hash: 파일 해시값
            user_id: 사용자 ID
            time_now: 현재 시간
            detection_source: 변경 감지 유형
            check_interval_seconds: 감시 주기

        Returns:
            file_id
        """
        # PostgreSQL INTERVAL 타입으로 변환
        check_interval_for_db = f"{check_interval_seconds} seconds"

        cur.execute(
            "INSERT INTO Files "
            "(user_id, file_name, file_path, file_hash, status, check_interval, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, 'Unchanged', %s::INTERVAL, %s, %s) RETURNING id",
            (user_id, os.path.basename(file_path), file_path, new_hash, check_interval_for_db, time_now, time_now)
        )
        id_row = cur.fetchone()
        file_id = id_row['id']
        self.create_file_log(cur, file_id, None, new_hash, 'UserUpdated', detection_source, event_time=time_now)
        return file_id

    # =============== 공개 API 메서드 ===============

    def handle_file_report(self, user_id: int, file_path: str, new_hash: str,
                           detection_source: Optional[str] = "Unknown",
                           file_content_bytes: Optional[bytes] = None) -> Tuple[Dict[str, Any], int]:
        """
        클라이언트로부터 파일 상태 보고 처리 (신규/수정/변경없음).
        file_path는 FIM 기준 상대 경로

        Args:
            user_id: 사용자 ID
            file_path: 파일 경로
            new_hash: 파일 해시값
            detection_source: 변경 감지 유형
            file_content_bytes: 파일 데이터(바이트)
        """
        time_now = datetime.now()
        response_message = "No action taken."
        file_id_for_response = None
        status_code = 200 # 기본 성공 코드

        # DB 연결 및 트랜잭션 관리
        if self.conn is None or self.conn.closed:
            print("handle_file_report: Database connection is not available.")
            return {"status": "error", "message": "Database connection error.", "file_id": None}, 500

        with self.conn.cursor(row_factory=dict_row) as cur:
            try:
                cur.execute(
                    "SELECT id, file_hash, status FROM Files WHERE user_id = %s AND file_path = %s",
                    (user_id, file_path)
                )
                file_record = cur.fetchone()

                if file_record: #기존 파일 (삭제되지 않음)
                    file_id_for_response = file_record["id"]
                    old_hash = file_record["file_hash"]
                    current_status = file_record["status"]

                    if new_hash == old_hash:
                        self._update_unchanged_file_status(cur, file_id_for_response, current_status, old_hash, time_now, detection_source)
                        response_message = f"File '{file_path}' is unchanged. Timestamp updated."
                    else:
                        self._update_modified_file_status(cur, file_id_for_response, old_hash, new_hash, file_path, time_now, detection_source)
                        response_message = f"File '{file_path}' is modified. Timestamp updated."
                else:
                    # 새 파일이거나, 이전에 삭제된 파일과 동일한 경로로 다시 생성된 경우
                    # 이전에 삭제된 동일 경로 파일이 있는 지 확인
                    cur.execute(
                        "SELECT id, file_hash, status FROM Files WHERE user_id = %s AND file_path = %s AND status = 'Deleted'",
                        (user_id, file_path)
                    )
                    deleted_file_record = cur.fetchone()
                    if deleted_file_record: # 이전에 삭제되었던 파일이면, 해당 레코드 업데이트 (복구 개념)
                        file_id_for_response = deleted_file_record["id"]
                        print(f"[{detection_source or 'RE_REGISTER'}] 이전에 삭제된 파일 재등록: {file_path}")
                        cur.execute(
                            "UPDATE Files SET file_hash = %s, status = 'Unchanged', updated_at = %s, check_interval = %s::INTERVAL WHERE id = %s",
                            (new_hash, time_now, f"{86400} seconds", file_id_for_response)  # 기본 24시간 인터벌로 복구
                        )
                        self.create_file_log(cur, file_id_for_response, None, new_hash, 'Recovered', detection_source=detection_source, event_time=time_now)
                        response_message = f"File '{file_path}' is re-registered. Timestamp updated."
                    else: # 완전한 새 파일
                        file_id_for_response = self._register_new_file_entry(cur, file_path, new_hash, user_id, time_now, detection_source)
                        response_message = f"File '{file_path}' is registered. Timestamp updated."

                    if file_content_bytes:
                        # Google Drive 백업 로직 등 추가
                        print(f"  ㄴ 파일 내용 수신됨 (추가 처리 가능): {file_path}, {len(file_content_bytes)} bytes")

                self.conn.commit()  # 모든 작업 성공 시 커밋
                return {"status": "success", "message": response_message, "file_id": file_id_for_response, "status_code": status_code}, status_code

            except psycopg.Error as db_err:  # DB 관련 에러 명시적 처리
                self.conn.rollback()
                print(f"DB 오류 발생 ({file_path}, user: {user_id}): {db_err}")
                import traceback
                traceback.print_exc()
                return {"status": "error", "message": f"Database error: {str(db_err)}", "status_code": 500}, 500

            except Exception as e:
                self.conn.rollback()
                print(f"파일 보고 처리 중 일반 오류 발생 ({file_path}, user: {user_id}): {e}")
                import traceback
                traceback.print_exc()
                return {"status": "error", "message": f"Error processing file report: {str(e)}", "status_code": 500}, 500

    def handle_file_deletion_report(self, user_id: int, file_path: str, detection_source: Optional[str] = "Unknown") -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
        """
        클라이언트로부터 파일 삭제 보고 처리.
        file_path는 FIM 기준 상대 경로.

        Args:
            user_id: 사용자 ID
            file_path: 파일 경로
            detection_source: 변경 감지 유형
        """
        time_now = datetime.now()

        if self.conn is None or self.conn.closed:
            print("handle_file_deletion_report: Database connection is not available.")
            return {"status": "error", "message": "Database connection error."}, 500

        with self.conn.cursor(row_factory=dict_row) as cur:
            try:
                cur.execute(
                    "SELECT id, file_hash, status FROM Files WHERE user_id = %s AND file_path = %s AND status != 'Deleted'",
                    (user_id, file_path)
                )
                file_record = cur.fetchone()

                if not file_record:
                    print(f"[{detection_source or 'DELETE_REPORT'}] 삭제 보고된 파일이 DB에 없거나 이미 삭제됨: {file_path} (user: {user_id})")
                    return {"status": "not_found", "message": f"File '{file_path}' is not found or already marked as deleted."}, 404

                file_id = file_record["id"]
                old_hash = file_record["file_hash"]

                print(f"[{detection_source or 'MARK_DELETED'}] 파일 삭제 처리: {file_path} (file_id: {file_id})")

                cur.execute(
                    "UPDATE Files SET status = 'Deleted', updated_at = %s WHERE id = %s",
                    (time_now, file_id)
                )
                self.create_file_log(cur, file_id, old_hash, None, 'Deleted', detection_source, time_now)
                self.send_notifications(cur, file_id, file_path, old_hash, None, time_now, "Deleted", detection_source)

                self.conn.commit()
                return {"status": "success", "message": f"File '{file_path}' marked as deleted.", "file_id": file_id, "status_code": 200}

            except psycopg.Error as db_err:
                self.conn.rollback()
                print(f"DB 오류 발생 (삭제 처리 중 {file_path}, user: {user_id}): {db_err}")
                return {"status": "error", "message": f"Database error during deletion: {str(db_err)}", "status_code": 500}

            except Exception as e:
                self.conn.rollback()
                print(f"파일 삭제 처리 중 일반 오류 발생 ({file_path}, user: {user_id}): {e}")
                return {"status": "error", "message": f"Error processing file deletion: {str(e)}", "status_code": 500}



# =============== 독립적인 사용자 관리 함수 ===============

def get_or_create_user(username: str, email: str) -> Optional[Dict[str, Any]]:
    """
    이메일 주소를 기반으로 사용자 조회 또는 생성
    
    Args:
        username: 사용자 이름
        email: 사용자 이메일
        
    Returns:
        사용자 정보 딕셔너리
    """
    time_now = datetime.now()
    conn = None

    try:
        conn = DatabaseManager.connect()
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT user_id, username, email FROM Users WHERE email = %s", (email,))
            user_record = cur.fetchone()

            if user_record:
                return {"user_id": user_record["user_id"], "username": user_record["username"], "email": user_record["email"]}

            cur.execute(
                "INSERT INTO Users (username, email, created_at) VALUES (%s, %s, %s) RETURNING user_id",
                (username, email, time_now)
            )
            user_id_tuple = cur.fetchone()
            if not user_id_tuple:
                raise Exception("User creation failed.")
            user_id = user_id_tuple["user_id"]

            conn.commit()
            return {"user_id": user_id, "username": username, "email": email}

    except psycopg.Error as db_err:
        if conn:
            conn.rollback()
            print(f"DB 오류 (get_or_create_user for {email}): {db_err}")
            raise # 호출부에서 처리하도록 예외 다시 발생

    except Exception as e:
        if conn: conn.rollback()
        print(f"일반 오류 (get_or_create_user for {email}): {e}")
        raise

    finally:
        if conn:
            conn.close()

def save_or_update_google_tokens(user_id: int, access_token: str, refresh_token: Optional[str], expires_at: Optional[datetime]) -> bool:
    """
    특정 사용자의 Google OAuth 토큰 정보를 데이터베이스에 저장하거나 업데이트합니다.

    Args:
        user_id: 사용자 ID
        access_token: access token
        refresh_token: refresh token
        expires_at: 만료 시간
    """
    conn = None

    try:
        conn = DatabaseManager.connect() # 또는 기존의 DB 연결 방식 사용
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users 
                SET google_access_token = %s, 
                    google_refresh_token = %s,
                    google_token_expires_at = %s
                WHERE user_id = %s
                """,
                (access_token, refresh_token, expires_at, user_id)
            )
            conn.commit()
            return cur.rowcount > 0 # 업데이트된 행이 있으면 True

    except psycopg.Error as db_err:
        if conn:
            conn.rollback()
        print(f"DB 오류 (save_or_update_google_tokens for user {user_id}): {db_err}")
        return False

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"일반 오류 (save_or_update_google_tokens for user {user_id}): {e}")
        return False

    finally:
        if conn:
            conn.close()

def get_google_tokens_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    사용자 ID로 데이터베이스에서 Google OAuth 토큰 정보를 조회합니다.

    Args:
        user_id: 사용자 ID
    """
    conn = None
    try:
        conn = DatabaseManager.connect()
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT google_access_token, google_refresh_token, google_token_expires_at
                FROM users
                WHERE user_id = %s
                """,
                (user_id,)
            )
            tokens = cur.fetchone()
            return tokens

    except psycopg.Error as db_err:
        print(f"DB 오류 (get_google_tokens_by_user_id for user {user_id}): {db_err}")
        return None

    except Exception as e:
        print(f"일반 오류 (get_google_tokens_by_user_id for user {user_id}): {e}")
        return None

    finally:
        if conn:
            conn.close()