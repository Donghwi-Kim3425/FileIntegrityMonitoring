import ctypes, os, psycopg
from datetime import datetime
from config import DB_PARAMS

# DLL 경로 설정
DLL_PATH = "lib/calc_hash.dll"

# SHA-256 해시 계산 함수
def calculate_file_hash(file_path):
    try:
        hash_lib = ctypes.CDLL(DLL_PATH)
    except OSError as e:
        print(f"DLL 로드 실패: {e}")
        return None

    hash_lib.calculate_file_hash.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
    hash_lib.calculate_file_hash.restype = ctypes.c_int

    hash_buffer = (ctypes.c_ubyte * 32)()
    result = hash_lib.calculate_file_hash(file_path.encode('cp949'), hash_buffer)

    if result == 0:
        print(f"파일 '{file_path}' 처리 중 오류 발생")
        return None

    return ''.join(f'{b:02x}' for b in hash_buffer)


# DB 연결 함수
def connect_db():
    return psycopg.connect(**DB_PARAMS)


# 파일 무결성 검사 및 DB 업데이트
def check_file_integrity(file_path, user_id):
    new_hash = calculate_file_hash(file_path)
    if not new_hash:
        return

    with connect_db() as conn:
        with conn.cursor() as cur:
            # 파일 정보 조회
            cur.execute("SELECT id, file_hash, status FROM Files WHERE file_path = %s", (file_path,))
            file_record = cur.fetchone()

            if file_record:
                file_id, old_hash, status = file_record

                if new_hash == old_hash:
                    print(f"[UNCHANGED] {file_path}")
                    cur.execute("UPDATE Files SET updated_at = %s, status = 'Unchanged' WHERE id = %s",
                                (datetime.now(), file_id))
                else:
                    print(f"[MODIFIED] {file_path}")
                    cur.execute("UPDATE Files SET file_hash = %s, updated_at = %s, status = 'Modified' WHERE id = %s",
                                (new_hash, datetime.now(), file_id))

                    cur.execute("SELECT id FROM File_logs WHERE file_id = %s", (file_id,))
                    log_record = cur.fetchone()

                    if log_record:
                        cur.execute(
                            "UPDATE File_logs SET old_hash = %s, new_hash = %s, change_type = 'Modified', logged_at = %s "
                            "WHERE file_id = %s",
                            (old_hash, new_hash, datetime.now(), file_id))
                    else:
                        cur.execute("INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at) "
                                    "VALUES (%s, %s, %s, 'Modified', %s)",
                                    (file_id, old_hash, new_hash, datetime.now()))
            else:
                # 새로운 파일 등록 시 user_id 포함
                print(f"[NEW FILE] {file_path}")
                cur.execute(
                    "INSERT INTO Files (user_id, file_name, file_path, file_hash, status, check_interval, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, 'Unchanged', INTERVAL '60 minutes', %s, %s) RETURNING id",
                    (user_id, os.path.basename(file_path), file_path, new_hash, datetime.now(), datetime.now()))
                file_id = cur.fetchone()[0]
                cur.execute("INSERT INTO File_logs (file_id, old_hash, new_hash, change_type, logged_at) "
                            "VALUES (%s, NULL, %s, 'UserUpdated', %s)",
                            (file_id, new_hash, datetime.now()))

        conn.commit()
        print("DB 업데이트 완료.")