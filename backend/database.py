import collections.abc
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional, Any, Union
import os
import psycopg
from psycopg.rows import dict_row
from alerts import send_notification_email
from config import DB_PARAMS

KST = timezone(timedelta(hours=9))

class DatabaseError(Exception):
    pass

class NotFoundError(Exception):
    pass

# =============== 기본 연결 및 쿼리 실행 ===============

class DatabaseManager:
    def __init__(self, conn):
        """
        DatabaseManager 초기화

        :param conn: 데이터베이스 연결 객체
        """

        self.conn = conn
    
    @staticmethod
    def connect():
        """
        데이터베이스 연결 생성

        :return: psycopg.Connection: 데이터베이스 연결 객체
        """

        return psycopg.connect(**DB_PARAMS)
    
    def execute_query(self, query: str, params: Optional[Tuple] = None, 
                      fetch_all: bool = True, use_dict_row: bool = False) -> Union[List, Tuple, None]:
        """
        SQL 쿼리 실행 및 결과 반환

        :param query: 실행할 SQL 쿼리문
        :param params: 쿼리 파라미터
        :param fetch_all: 모든 결과를 가져올지 여부 (False -> 첫 번째 결과만 반환)
        :param use_dict_row: 결과를 딕셔너리 형태로 반환할지 여부

        :return:쿼리 실행 결과

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
    
    # =============== 파일 정보 / 데이터 조회 메서드 ===============
    
    def get_file_id(self, file_path: str, user_id: int) -> Optional[int]:
        """
        파일 경로로 파일 ID 조회

        :param file_path: 조회할 파일 경로
        :param user_id: 사용자 ID

        :return: 파일 ID 또는 None(없을 경우)
        """

        query = """
            SELECT
                id 
            FROM Files 
            WHERE file_path = %s AND user_id = %s AND status != 'Deleted'
        """

        result = self.execute_query(query, (file_path, user_id), fetch_all=False)
        return result[0] if result else None
    
    def get_file_hash(self, file_path: str, user_id: int) -> Optional[str]:
        """
        파일 경로로 해시값 조회

        :param file_path: 조회할 파일 경로
        :param user_id: 사용자 ID

        :return: 파일 해시값 또는 None(없을 경우)
        """

        query = """
            SELECT 
                file_hash 
            FROM Files 
            WHERE file_path = %s AND user_id = %s AND status != 'Deleted'
        """

        result = self.execute_query(query, (file_path, user_id), fetch_all=False)
        return result[0] if result else None
    
    def get_file_status(self, file_path: str, user_id: int) -> Optional[str]:
        """
        파일 결로로 상태 조회

        :param file_path: 조회할 파일 경로
        :param user_id: 사용자 ID

        :return: 파일 상태 또는 None(없을 경우)
        """

        query = """
            SELECT 
                status 
            FROM Files 
            WHERE file_path = %s AND user_id = %s
        """

        result = self.execute_query(query, (file_path, user_id), fetch_all=False)
        return result[0] if result else None
    
    def get_files_for_user(self, user_id: int) -> List[Dict]:
        """
        특정 사용자의 파일 목록 조회

        :param user_id: 사용자 ID

        :return: 사용자의 파일 목록 (딕셔너리 리스트)
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
            return [] # 결과가 없으면 빈 리스트

        processed_files = [] # 최종 반환할 파일 목록
        for f_dict in raw_files:
            check_interval_val = f_dict.get('check_interval') # 검사주기 값
            check_interval_seconds = None # 초 단위로 변환된 체크 주기
            # 숫자형이면 float형태로 변환
            if isinstance(check_interval_val, timedelta):
                check_interval_seconds = check_interval_val.total_seconds()
            elif isinstance(check_interval_val, (int, float)):
                check_interval_seconds = float(check_interval_val)

            processed_files.append({
                "id": f_dict.get('id'),
                "file_path": f_dict.get('file_path'),
                "current_hash": f_dict.get('current_hash'),
                "check_interval": check_interval_seconds,
                "updated_at": f_dict.get('updated_at').isoformat() if f_dict.get('updated_at') else None
            })

        return processed_files

    def get_user_email_by_file_id(self, file_id: int) -> Optional[str]:
        """
        파일 ID로 사용자 이메일 조회

        :param file_id: 파일 ID

        :return: 사용자 이메일 또는 None(없을 경우)

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

        :param user_id: 사용자 ID

        :return: 파일 정보 리스트 (로그)
        """

        query = """
            SELECT DISTINCT ON (f.id)
                l.id,
                f.id AS file_id,
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

    @staticmethod
    def create_file_log(cur, file_id: int, old_hash: Optional[str], new_hash: Optional[str],
                        change_type: str, detection_source: Optional[str] = "Unknown",
                        event_time: Optional[datetime] = None) -> None:
        """
        파일 변경 로그 생성

        :param cur: 데이터베이스 커서
        :param file_id: 파일 ID
        :param old_hash: 이전 해시값
        :param new_hash: 새 해시값
        :param change_type: 파일 상태 변경 유형
        :param detection_source: 변경 감지 유형
        :param event_time: 이벤트 발생 시간

        """

        log_time = event_time if event_time else datetime.now()
        cur.execute(
            "INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at, detection_source) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (file_id, old_hash, new_hash, change_type, log_time, detection_source)
        )

    @staticmethod
    def create_alert(cur, file_id: int, message: str, event_time: Optional[datetime] = None) -> None:
        """
        파일 변경 알림 생성

        :param cur: 데이터베이스 커서
        :param file_id: 파일 ID
        :param message: 알림 메시지
        :param event_time: 알림 발생 시간

        """

        alert_time = event_time if event_time else datetime.now()
        cur.execute(
            "INSERT INTO alerts (file_id, message, created_at) "
            "VALUES (%s, %s, %s)",
            (file_id, message, alert_time)
        )
    
    def send_notifications(self, cur, file_id: int, file_path: str, old_hash: Optional[str],
                            new_hash: Optional[str], time_now: datetime,
                            change_type: str = "Modified") -> None:
        """
        파일 변경에 대한 알림 발송 (이메일 / 웹소켓 Toast)flak

        :param cur: 데이터베이스 커서
        :param file_id: 파일 ID
        :param file_path: 파일 경로
        :param old_hash: 이전 해시값
        :param new_hash: 새 해시값
        :param time_now: 현재 시간
        :param change_type: 파일 상태 변경 유형

        :returns : None
        """
        # 알림 메시지 생성
        file_basename = os.path.basename(file_path) # 파일 이름
        alert_message_base = f"파일 '{file_basename}' ({file_path}) 상태 변경: {change_type}"

        alert_message_detail = ""
        if change_type == "Modified" and old_hash and new_hash: # Modified시 이전 해시값과 새 해시값
            alert_message_detail = f"\n- 이전 해시: {old_hash}\n- 현재 해시: {new_hash}"

        elif change_type == "Deleted": # Deleted시 이전 해시값
            alert_message_detail = f"\n- 이전 해시: {old_hash or 'N/A'}"

        elif change_type in ["Created", "UserUpdated", "Registered"]:
            alert_message_detail = f"\n- 현재 해시: {new_hash or 'N/A'}"

        full_alert_message = alert_message_base + alert_message_detail
        self.create_alert(cur, file_id, full_alert_message, time_now)

        user_email = self.get_user_email_by_file_id(file_id)

        if user_email:
            print(f"알림을 발송할 사용자 이메일: {user_email}")
            subject = f"파일 {change_type} 알림: {file_basename}"
            body = full_alert_message + f"\n- 변경/감지 시각: {time_now.strftime('%Y-%m-%d %H:%M:%S')}"
            # body += "\n\n웹사이트에서 확인: [여기에 웹사이트 링크]" # TODO: 사이트 주소 추가
            send_notification_email(user_email, subject, body)
            print(f"이메일 알림 발송 시도 완료: {user_email}")

        else:
            print(f"file_id {file_id}의 사용자 이메일 찾지 못해 이메일 알림을 보낼 수 없습니다.")


    # =============== 백업 관련 ===============

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
            if created_at.tzinfo is None:
                aware_created_at = created_at.replace(tzinfo=KST)
            else:
                aware_created_at = created_at.astimezone()

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

    def get_backup_details_by_id(self, user_id: int, backup_id: int) -> Optional[Dict]:
        """
        백업 ID로 백업 상세 정보를 조회

        :param user_id: 사용자 ID
        :param backup_id: 백업 ID

        :return: 백업 상세 정보 딕셔너리 (None, if no details)
        """

        query = """
                SELECT b.id, \
                       b.file_id, \
                       b.backup_path, \
                       b.backup_hash, \
                       f.file_path AS original_file_path, \
                       f.user_id
                FROM Backups AS b
                         JOIN Files AS f ON b.file_id = f.id
                WHERE b.id = %s \
                  AND f.user_id = %s \
                """

        return self.execute_query(query, (backup_id, user_id), fetch_all=False, use_dict_row=True)

    def get_backups_for_file(self, user_id: int, file_id: int) -> List[Dict]:
        """
        특정 파일의 모든 백업 기록을 조회

        :param user_id: 사용자 ID
        :param file_id: 파일 ID

        :return: 파일 백업 기록 리스트
        """

        query = """
                SELECT b.id, b.backup_path, b.backup_hash, b.created_at
                FROM Backups b
                         JOIN Files f ON b.file_id = f.id
                WHERE b.file_id = %s
                  AND f.user_id = %s
                ORDER BY b.created_at DESC \
                """

        return self.execute_query(query, (file_id, user_id), fetch_all=True, use_dict_row=True)

    def rollback_file_to_backup(self, user_id: int, file_id: int, backup_id: int) -> Optional[str]:
        """
        파일을 지정된 백업 버전으로 롤백
            - 백업 테이블에서 해시값을 가져와 파일 테이블에 적용
            - 롤백 로그를 남기고 DB에 커밋

        :param user_id: 사용자 ID
        :param file_id: 파일 ID
        :param backup_id: 백업 ID

        :return: 롤백 후 적용된 해시값 (None, if no backup found)

        :raises: NotFoundError: 파일이 존재하지 않을 때
        :raises: DatabaseError: DB 작업 중 오류 발생
        """

        try:
            with self.conn.cursor(row_factory=dict_row) as cur:
                # 1. 롤백할 백업 정보 가져오기
                cur.execute(
                    """
                    SELECT f.file_hash   AS old_hash,
                           b.backup_hash AS new_hash
                    FROM Files f
                             JOIN Backups b ON f.id = b.file_id
                    WHERE f.id = %s
                      AND f.user_id = %s
                      AND b.id = %s
                    """,
                    (file_id, user_id, backup_id)
                )
                hashes = cur.fetchone()
                if not hashes:
                    raise NotFoundError(
                        f"File or backup not found, or permission denied. file_id: {file_id}, backup_id: {backup_id}")

                old_hash = hashes['old_hash']
                new_hash = hashes['new_hash']
                time_now = datetime.now(timezone.utc)

                # 2. files 테이블의 해시를 백업 해시로 업데이트
                cur.execute(
                    """
                    UPDATE files
                    SET file_hash  = %s,
                        updated_at = %s,
                        status     = 'User Verified'
                    WHERE id = %s
                      AND user_id = %s
                    """,
                    (new_hash, time_now, file_id, user_id)
                )

                # 3. 롤백 이베트 로그 기록
                self.create_file_log(cur, file_id, old_hash, new_hash, 'Rollback', "User_UI_Rollback", time_now)

                self.conn.commit()
                return new_hash

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error during file rollback for file_id {file_id}: {e}")
            raise DatabaseError(f"Database error during rollback: {str(e)}")

    # =============== 내부 파일 상태 관리 메서드 (handle_file_report 등에서 사용) ===============
    
    def _update_unchanged_file_status(self, cur, file_id: int, current_db_status: str, current_db_hash: str, 
                                      time_now: datetime, detection_source: Optional[str]) -> None:
        """
        파일이 변경되지 않을시 상태 업데에트

        :param cur: 데이터베이스 커서
        :param file_id: 파일 ID
        :param current_db_status: 현재 파일 상태
        :param current_db_hash: 현재 파일 해시값
        :param time_now: 현재 시간
        :param detection_source: 변경 감지 유형
        """

        if current_db_status != 'Unchanged': # 상태가 실제로 변경될 때만 로그 기록
            self.create_file_log(cur, file_id, current_db_hash, current_db_hash, 'Unchanged', detection_source=detection_source, event_time=time_now)

        cur.execute( # 상태가 Unchanged가 아니었다면 Unchanged로 변경, 시간 업데이트. 이미 Unchanged면 시간만 업데이트.
            "UPDATE Files SET updated_at = %s, status = 'Unchanged' WHERE id = %s",
            (time_now, file_id)
        )
    
    def _update_modified_file_status(self, cur, file_id: int, old_hash: str, new_hash: str,
                                     file_path: str, time_now: datetime, detection_source: Optional[str]) -> None:
        """
        파일이 변경됐을 때 상태 업데이트

        :param cur: 데이터베이스 커서
        :param file_id: 파일 ID
        :param old_hash: 이전 해시값
        :param new_hash: 새 해식값
        :param file_path: 파일 경로
        :param time_now: 현재 시간
        :param detection_source: 파일 감지 유형
        """

        # 파일 상태 업데이트
        cur.execute(
            "UPDATE Files SET file_hash = %s, updated_at = %s, status = 'Modified' WHERE id = %s",
            (new_hash, time_now, file_id)
        )
        
        # 변경 로그 생성
        self.create_file_log(cur, file_id, old_hash, new_hash, 'Modified', detection_source=detection_source, event_time=time_now)
        
        # 알림 발송
        self.send_notifications(cur, file_id, file_path, old_hash, new_hash, time_now, "Modified")

    def _register_new_file_entry(self, cur, file_path: str, new_hash: str, user_id: int,
                                 time_now: datetime, detection_source: Optional[str],
                                 check_interval_seconds: int = 86400) -> int:
        """
        새 파일 레코드 생성

        :param cur: 데이터베이스 커서
        :param file_path: 파일 경로
        :param new_hash: 새 해시값
        :param user_id: 사용자 ID
        :param time_now: 현재 시간
        :param detection_source: 변경 감지 유형
        :param check_interval_seconds: 검사 주기 (기본 24H)

        :return: 파일 ID
        """

        check_interval_for_db = f"{check_interval_seconds} seconds"

        cur.execute(
            "INSERT INTO Files "
            "(user_id, file_path, file_hash, status, check_interval, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'Unchanged', %s::INTERVAL, %s, %s) RETURNING id",
            (user_id, file_path, new_hash, check_interval_for_db, time_now, time_now)
        )
        id_row = cur.fetchone()
        file_id = id_row['id']
        self.create_file_log(cur, file_id, None, new_hash, 'UserUpdated', detection_source, event_time=time_now)
        return file_id

    # =============== 공개 API 메서드 ===============

    def handle_file_report(self, user_id: int, file_path: str, new_hash: str,
                           detection_source: Optional[str] = "Unknown",
                           file_content_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        """
        클라이언트로부터 파일 상태 보고 처리(신규/수정/변경없음)

        :param user_id: 사용자 ID
        :param file_path: 파일 경로
        :param new_hash: 새 해시값
        :param detection_source: 변경 감지 유형
        :param file_content_bytes: 파일 데이터(바이트)

        :return: 성공 시 처리 결과 딕셔너리

        :raises: DatabaseError: DB 작업 오류 시
        """

        time_now = datetime.now()

        # DB 연결 및 트랜잭션 관리
        if self.conn is None or self.conn.closed:
            raise DatabaseError("Database connection is not available.")

        with self.conn.cursor(row_factory=dict_row) as cur:
            try:
                cur.execute(
                    "SELECT id, file_hash, status FROM Files WHERE user_id = %s AND file_path = %s",
                    (user_id, file_path)
                )
                file_record = cur.fetchone()

                if file_record: # 기존 파일 (삭제되지 않음)
                    file_id_for_response = file_record["id"]
                    old_hash = file_record["file_hash"]
                    current_status = file_record["status"]

                    if new_hash == old_hash: # 해시값 동일 변경 없음
                        self._update_unchanged_file_status(cur, file_id_for_response, current_status, old_hash, time_now, detection_source)
                        response_message = f"File '{file_path}' is unchanged. Timestamp updated."
                    else: # 해시값이 다름 -> 수정된 파일
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
                        print(f"  ㄴ 파일 내용 수신됨: {file_path}, {len(file_content_bytes)} bytes")

                self.conn.commit()  # 모든 작업 성공 시 커밋
                return {
                    "status": "success",
                    "message": response_message,
                    "file_id": file_id_for_response,
                }

            except psycopg.Error as db_err:
                self.conn.rollback()
                print(f"DB 오류 발생 ({file_path}, user: {user_id}): {db_err}")
                raise DatabaseError(f"Database error: {str(db_err)}")

            except Exception as e:
                self.conn.rollback()
                print(f"파일 보고 처리 중 일반 오류 발생 ({file_path}, user: {user_id}): {e}")
                raise DatabaseError(f"Error processing file report: {str(e)}")

    def handle_file_deletion_report(self, user_id: int, file_path: str, detection_source: Optional[str] = "Unknown") -> Dict[str, Any]:
        """
        클라이어트로부터 파일 삭제 보고 처리

        :param user_id: 사용자 ID
        :param file_path: 파일 경로
        :param detection_source: 변경 감지 유형

        :return: 성공 시 처리 결과 딕셔너리

        :raises NotFoundError: 파일이 존재하지 않을 경우
        :raises DatabaseError: DB 작업 중 오류 발생 시
        """

        time_now = datetime.now() # 현재 시간

        if self.conn is None or self.conn.closed:
            raise DatabaseError("Database connection is not available.")

        with self.conn.cursor(row_factory=dict_row) as cur:
            try:
                cur.execute(
                    "SELECT id, file_hash, status FROM Files WHERE user_id = %s AND file_path = %s AND status != 'Deleted'",
                    (user_id, file_path)
                )
                file_record = cur.fetchone()

                if not file_record: # 파일이 없거나 이미 삭제된 경우
                    raise NotFoundError(f"File '{file_path}' was not found.")

                file_id = file_record["id"]
                old_hash = file_record["file_hash"]

                print(f"[{detection_source or 'MARK_DELETED'}] 파일 삭제 처리: {file_path} (file_id: {file_id})")

                # 파일 상태를 Deleted로 업데이트
                cur.execute(
                    "UPDATE Files SET status = 'Deleted', updated_at = %s WHERE id = %s",
                    (time_now, file_id)
                )
                # 로그 기록 및 알림 전송
                self.create_file_log(cur, file_id, old_hash, None, 'Deleted', detection_source, time_now)
                self.send_notifications(cur, file_id, file_path, old_hash, None, time_now, "Deleted")

                self.conn.commit()
                return {"status": "success", "message": f"File '{file_path}' marked as deleted.", "file_id": file_id, "status_code": 200}

            except psycopg.Error as db_err:
                self.conn.rollback()
                raise DatabaseError(f"Database error: {str(db_err)}")

            except Exception as e:
                self.conn.rollback()
                raise DatabaseError(f"Error processing file report: {str(e)}")

    # =============== 사용자 요청 기반 상태 관리 ===============

    def update_file_status(self, user_id: int, file_id: int, new_status: str) -> bool:
        """
        특정 파일의 상태를 직접 업데이트

        :param user_id: 사용장 ID
        :param file_id: 파일 ID
        :param new_status: 파일의 새 상태

        :return: 업데이트 성공 여부 (True, False)

        :raises: NotFoundError: 파일이 존재하지 않을 경우
        :raises: DatabaseError: DB 작업 중 요류 발생
        """
        query = """
                UPDATE Files
                SET status = %s, updated_at = %s
                WHERE id = %s AND user_id = %s AND status != 'Deleted'
                RETURNING id, file_hash
            """
        try:
            with self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (new_status, datetime.now(timezone.utc), file_id, user_id))
                updated_file = cur.fetchone()

                if not updated_file: # 해당 파일이 없거나 삭제된 상태
                    raise NotFoundError(f"File not found for update: {file_id} (user {user_id})")

                # 업데이트된 파일 정보 추출
                file_id = updated_file["id"]
                old_hash = updated_file["file_hash"]

                # 변경 로그 기록 (해시값은 그대로 상태만 변경)
                self.create_file_log(
                    cur,
                    file_id=file_id,
                    old_hash=old_hash,
                    new_hash=old_hash,
                    change_type=new_status,
                    detection_source="UserUpdated"
                )
                self.conn.commit()
                return True

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error updating file status for {file_id} (user {user_id}): {e}")
            raise DatabaseError(f"Database error while updating status: {str(e)}")

    def update_check_interval(self, user_id: int, file_id: int, interval_hours: int) -> bool:
        """
        파일의 검사 주기를 업데이트

        :param user_id: 사용자 ID
        :param file_id: 파일 ID
        :param interval_hours: 검사 주기

        :return: 변경 성공 여부 (True, False)
        """

        # 시간 단위를 timedelta 객체로 변환
        interval_delta = timedelta(hours=interval_hours)

        query = """
            UPDATE Files
            SET check_interval = %s
            WHERE id = %s AND user_id = %s AND status != 'Deleted'
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (interval_delta, file_id, user_id))
                self.conn.commit()
                return cur.rowcount > 0 # 실제로 변경된 행이 있는지 여부 반환

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error updating check interval for {file_id} (user {user_id}): {e}")
            return False

    def soft_delete_file_by_id(self, user_id: int, file_id: int) -> bool:
        """
        사용자 UI 요청에 의해 특정 파일의 모니터링을 중단 (soft delete)

        :param user_id: 사용자 ID
        :param file_id: 파일 ID

        :return: 모니터링 중단 성공 여부 (True, False)
        
        :raises: NotFoundError: 파일이 존재하지 않을 때
        :raises: DatabaseError: DB 작업 중 오류 발생
        """

        # 먼저 파일이 해당 유저의 소유인지 확인
        query_select = "SELECT file_path, file_hash FROM files WHERE id = %s AND user_id = %s AND status != 'Deleted'"
        file_info = self.execute_query(query_select, (file_id, user_id), fetch_all=False, use_dict_row=True)

        if not file_info:
            # 파일이 없거나 이미 삭제되었거나 다른 유저의 파일인 경우
            raise NotFoundError(f"File not found for soft delete: {file_id} (user {user_id})")

        assert isinstance(file_info, collections.abc.Mapping)

        try:
            with self.conn.cursor() as cur:
                time_now = datetime.now()
                # 1. 파일 상태를 Deleted로 업데이트
                cur.execute(
                    "UPDATE files SET status = 'Deleted', updated_at = %s WHERE id = %s",
                    (time_now, file_id)
                )

                # 2. 'Deleted' 로그 기록
                detection_source = "Deleted_by_User_UI"
                self.create_file_log(cur, file_id, file_info['file_hash'], None, 'Deleted', detection_source, time_now)

                # 3. 알림 생성 및 발송
                self.send_notifications(cur, file_id, file_info['file_path'], file_info['file_hash'], None, time_now, "Deleted")

                self.conn.commit()
                print(f"✅ File monitoring stopped for file_id {file_id} by user {user_id}.")
                return True

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error during soft delete for file_id {file_id}: {e}")
            raise DatabaseError(f"Database error during soft delete: {str(e)}")


# =============== 독립적인 사용자 관리 함수 ===============

def get_or_create_user(username: str, email: str) -> Optional[Dict[str, Any]]:
    """
    이메일 주소를 기반으로 사용자 조회 또는 생성

    :param username: 사용자 이름
    :param email: 사용자 이메일

    :return: 사요자 정보 딕셔너리 (user_id, username, email) or None (if no user found)
    """

    time_now = datetime.now()
    conn = None

    try:
        conn = DatabaseManager.connect()
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. 이메일 기준으로 사용자 조회
            cur.execute("SELECT user_id, username, email FROM Users WHERE email = %s", (email,))
            user_record = cur.fetchone()

            if user_record: # 이미 존재하는 사욪자일 경우 해당 정보 반환
                return {
                    "user_id": user_record["user_id"],
                    "username": user_record["username"],
                    "email": user_record["email"]
                }

            # 2. 사요자 정보가 없으면 새로 생성
            cur.execute(
                """
                INSERT INTO Users (username, email, created_at)
                VALUES (%s, %s, %s) 
                RETURNING user_id
                """,
                (username, email, time_now)
            )
            user_id_tuple = cur.fetchone()
            if not user_id_tuple:
                raise Exception("User creation failed.")
            user_id = user_id_tuple["user_id"]

            conn.commit()
            # 새 사용자 정보 반환
            return {
                "user_id": user_id,
                "username": username,
                "email": email
            }

    except psycopg.Error as db_err:
        if conn:
            conn.rollback()
            print(f"DB 오류 (get_or_create_user for {email}): {db_err}")
            raise

    except Exception as e:
        if conn: conn.rollback()
        print(f"일반 오류 (get_or_create_user for {email}): {e}")
        raise

    finally:
        if conn:
            conn.close()

def save_or_update_google_tokens(user_id: int, access_token: str, refresh_token: Optional[str], expires_at: Optional[datetime]) -> bool:
    """
    특정 사용자의 Google OAuth 토큰 정보블 데이터베이스 저장 또는 업데이트

    :param user_id: 사요자 ID
    :param access_token: Google API access token
    :param refresh_token: Google API refresh token
    :param expires_at: 엑세스 토큰 만료 시간

    :return: 저장 또는 업데이트 성공 여부 (True, False)
    """

    conn = None

    try:
        conn = DatabaseManager.connect()
        with conn.cursor() as cur:
            if refresh_token: # 리프레시 토큰이 있는 경우 -> 전체 토큰 정보 업데이트
                cur.execute(
                    """
                    UPDATE users
                    SET google_access_token     = %s,
                        google_refresh_token    = %s,
                        google_token_expires_at = %s
                    WHERE user_id = %s
                    """,
                    (access_token, refresh_token, expires_at, user_id)
                )
            else: # 리프레시 토큰이 없는 경우 -> 엑세스 토큰과 만료 시간만 업데이트
                cur.execute(
                    """
                    UPDATE users
                    SET google_access_token     = %s,
                        google_token_expires_at = %s
                    WHERE user_id = %s
                    """,
                    (access_token, expires_at, user_id)
                )
            conn.commit()
            return cur.rowcount > 0

    except Exception as e:
        if conn: conn.rollback()
        print(f"❌ save_or_update_google_tokens error for user {user_id}: {e}")
        return False

    finally:
        if conn: conn.close()

def get_google_tokens_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    사용자 ID로 데이터베이스에서 Google OAuth 토큰 정보를 조회

    :param user_id: 사용자 ID

    :return: 토큰 정보 딕셔너리 또는 None (if no user found)
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

            return tokens # 조회된 토큰 정보 반환 (None, if no tokens found)

    except psycopg.Error as db_err:
        print(f"DB 오류 (get_google_tokens_by_user_id for user {user_id}): {db_err}")
        return None

    except Exception as e:
        print(f"일반 오류 (get_google_tokens_by_user_id for user {user_id}): {e}")
        return None

    finally:
        if conn:
            conn.close()