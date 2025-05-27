# file_monitor.py
import os, time, schedule
import api_client
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileMovedEvent
from hash_calculator import calculate_file_hash
from config import USE_WATCHDOG

# --- FIM 디렉토리 설정 ---
FIM_BASE_DIR = Path.home() / "Desktop" / "FIM"


def ensure_fim_directory():
    """ FIM 디렉토리 없으면 생성 """
    if not FIM_BASE_DIR.exists():
        print(f"FIM 디렉토리를 생성합니다: {FIM_BASE_DIR}")
        FIM_BASE_DIR.mkdir(parents=True, exist_ok=True)


# --- Watchdog 이벤트 핸들러 ---
class FIMEventHandler(FileSystemEventHandler):
    def __init__(self, base_path, api_client_instance):
        self.base_path_str = str(base_path)
        self.last_event_time = {}
        self.api_client = api_client_instance
        self.recently_created = {}
        self.MODIFIED_IGNORE_THRESHOLD_AFTER_CREATE = 10.0

    def _get_relative_path(self, src_path):
        """ 기본 경로로부터 상대 경로 계산, OS 독립적인 구분자 사용 """
        return os.path.relpath(src_path, self.base_path_str).replace('\\', '/')

    def _should_process(self, event_path, event_type, debounce_time_ms=500):
        """ 이벤트를 처리해야 하는지 확인 (디바운싱 포함) """
        norm_event_path = os.path.normpath(event_path)

        if os.path.isdir(event_path) and event_type not in ["moved_src", "moved_dest"]:
            return False

        current_time_ms = time.time() * 1000
        key = (os.path.normpath(event_path), event_type)
        last_time = self.last_event_time.get(key, 0)

        if current_time_ms - last_time < debounce_time_ms:
            return False

        if event_type == "modified":
            created_time = self.recently_created.get(norm_event_path)
            if created_time:
                time_since_creation = time.time() - created_time
                if time_since_creation < self.MODIFIED_IGNORE_THRESHOLD_AFTER_CREATE:
                    return False
                else:
                    self.recently_created.pop(norm_event_path)

        self.last_event_time[key] = current_time_ms
        return True

    def on_created(self, event):
        """ 파일 생성 이벤트 처리 """
        if event.is_directory:
            return

        norm_event_path = os.path.normpath(event.src_path)
        self.recently_created[norm_event_path] = time.time()

        if not self._should_process(norm_event_path, "created"):
            return

        relative_path = self._get_relative_path(event.src_path)
        absolute_path = str(FIM_BASE_DIR / relative_path)
        print(f"[{datetime.now()}] [WATCHDOG] 파일 생성됨: {relative_path}")

        try:
            time.sleep(0.5) # 파일 쓰기 완료 대기
            new_hash = calculate_file_hash(absolute_path)
            if new_hash:
                # 1. 서버에 파일 정보 등록
                reg_success = self.api_client.register_new_file_on_server(
                    relative_path, new_hash, None, detection_source="watchdog"
                )
                if reg_success:
                    print(f"  ㄴ 서버에 파일 등록 성공: {relative_path}")
                    # 2. 구글 드라이브 백업 시도
                    with open(absolute_path, 'rb') as f:
                        file_content_bytes = f.read()
                    print(f"  ㄴ Google Drive 백업 시도 (생성됨): {relative_path}")
                    backup_success = self.api_client.request_gdrive_backup(
                        relative_path, file_content_bytes, is_modified=False,
                    )
                    if backup_success:
                        print(f"    ㄴ Google Drive 백업 요청 성공.")
                    else:
                        print(f"    ㄴ Google Drive 백업 요청 실패.")
                else:
                    print(f"  ㄴ 서버에 파일 등록 실패: {relative_path}")
            else:
                print(f"  ㄴ 오류: 해시 계산 실패 ({relative_path})")
        except Exception as e:
            print(f"  ㄴ 오류 (on_created 처리 중 {relative_path}): {e}")

    def on_modified(self, event):
        """ 파일 수정 이벤트 처리 """
        if event.is_directory:
            return

        norm_event_path = os.path.normpath(event.src_path)

        if not self._should_process(norm_event_path, "modified"):
            return

        relative_path = self._get_relative_path(event.src_path)
        absolute_path = str(FIM_BASE_DIR / relative_path)
        print(f"[{datetime.now()}] [WATCHDOG] 파일 수정됨: {relative_path}")

        try:
            time.sleep(0.2) # 파일 쓰기 완료 대기
            new_hash = calculate_file_hash(absolute_path)
            if new_hash:
                # 1. 서버에 해시 보고
                report_success = self.api_client.report_hash(
                    relative_path, new_hash, detection_source="watchdog"
                )
                if report_success:
                    print(f"  ㄴ 서버에 해시 보고 성공: {relative_path}")
                    # 2. 구글 드라이브 백업 시도 (수정된 파일)
                    with open(absolute_path, 'rb') as f:
                        file_content_bytes = f.read()
                    print(f"  ㄴ Google Drive 백업 시도 (수정됨): {relative_path}")
                    backup_success = self.api_client.request_gdrive_backup(
                        relative_path, file_content_bytes, is_modified=True,
                    )
                    if backup_success:
                        print(f"    ㄴ Google Drive 백업 요청 성공 (수정됨).")
                    else:
                        print(f"    ㄴ Google Drive 백업 요청 실패 (수정됨).")

                else:
                    print(f"  ㄴ 서버에 해시 보고 실패: {relative_path}")
            else:
                print(f"  ㄴ 오류: 해시 계산 실패 ({relative_path})")
        except Exception as e:
            print(f"  ㄴ 오류 (on_modified 처리 중 {relative_path}): {e}")

    def on_deleted(self, event):
        """ 파일 삭제 이벤트 처리 """
        if event.is_directory:
            return
        if not self._should_process(event.src_path, "deleted"):
            return

        relative_path = self._get_relative_path(event.src_path)
        print(f"[{datetime.now()}] [WATCHDOG] 파일 삭제됨: {relative_path}")

        success = self.api_client.report_file_deleted_on_server(
            relative_path, detection_source="watchdog"
        )
        if success:
            print(f"  ㄴ 서버에 삭제 보고 성공: {relative_path}")
        else:
            print(f"  ㄴ 서버에 삭제 보고 실패: {relative_path}")

    def on_moved(self, event):
        """ 파일 이동 이벤트 처리 (디렉토리 이동은 현재 미처리) """
        if event.is_directory:
            print(f"[{datetime.now()}] [WATCHDOG] 디렉토리 이동 감지 (현재 미처리): {event.src_path} -> {event.dest_path}")
            return

        move_event_key = (os.path.normpath(event.src_path), os.path.normpath(event.dest_path), "moved")
        current_time = time.time() * 1000
        last_event_time_for_move = self.last_event_time.get(move_event_key, 0)

        if current_time - last_event_time_for_move < 500:
            return
        self.last_event_time[move_event_key] = current_time

        relative_old_path = self._get_relative_path(event.src_path)
        print(f"[{datetime.now()}] [WATCHDOG] 파일 이동 (원본 경로 처리): {relative_old_path}")
        self.api_client.report_file_deleted_on_server(
            relative_old_path,
            detection_source="watchdog"
        )

        relative_new_path = self._get_relative_path(event.dest_path)
        absolute_new_path = str(FIM_BASE_DIR / relative_new_path)
        print(f"[{datetime.now()}] [WATCHDOG] 파일 이동 (대상 경로 처리): {relative_new_path}")
        try:
            new_hash = calculate_file_hash(absolute_new_path)  #
            if new_hash:
                self.api_client.register_new_file_on_server(
                    relative_new_path, new_hash, None, detection_source="watchdog"
                )
            else:
                print(f"  ㄴ 오류: 해시 계산 실패 ({relative_new_path})")
        except Exception as e:
            print(f"  ㄴ 오류 (on_moved 대상 경로 처리 중 {relative_new_path}): {e}")


class FileMonitor:
    def __init__(self):
        self.api_client_module = api_client
        # Keyring 사용 시점에 self.api_client_module.initialize_api_credentials() 호출 필요

        self.event_handler = FIMEventHandler(
            FIM_BASE_DIR,
            self.api_client_module
        )
        self.observer = Observer()

    def get_files_to_check_from_server(self):
        """서버로부터 각 파일별 검사 설정을 포함한 파일 목록을 받아옴"""
        print(f"[{datetime.now()}] [SCHEDULER] 서버로부터 파일 목록 요청...")
        files = self.api_client_module.fetch_file_list()
        if files is None:
            print(f"  [SCHEDULER] 서버로부터 파일 목록을 가져오는데 실패했거나 API 클라이언트가 준비되지 않았습니다.")
            return []

        print(f"  [SCHEDULER] 서버로부터 {len(files)}개의 파일 정보 수신 완료.")
        return files

    def check_files_periodically(self):
        """(스케줄러에 의해 주기적 실행) 서버에 등록된 각 파일의 검사 주기에 따라 무결성을 검사합니다."""
        print(f"--- 각 파일별 주기적 검사 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
        files_to_check = self.get_files_to_check_from_server()

        if not files_to_check:
            print("  [SCHEDULER] 주기적 검사 대상 파일 목록이 없습니다 (서버 기준).")
            print(f"--- 각 파일별 주기적 검사 완료 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
            return

        now = datetime.now().astimezone()

        for file_info in files_to_check:
            relative_file_path = file_info.get("file_path")
            check_interval_seconds_val = file_info.get("check_interval")
            updated_at_str = file_info.get("updated_at")

            if not relative_file_path or check_interval_seconds_val is None:
                print(f"  [SCHEDULER] 정보 부족: 건너뜀 ({file_info.get('file_path', '경로 알 수 없음')})")
                continue

            absolute_file_path = FIM_BASE_DIR / relative_file_path

            try:
                check_interval_seconds = float(check_interval_seconds_val)
                if check_interval_seconds <= 0:
                    print(
                        f"  [SCHEDULER] 경고: '{relative_file_path}'의 check_interval ({check_interval_seconds}초)이 유효하지 않음. 건너뜀.")
                    continue
            except ValueError:
                print(
                    f"  [SCHEDULER] 오류: '{relative_file_path}'의 check_interval ('{check_interval_seconds_val}')이 숫자가 아님. 건너뜀.")
                continue

            last_checked_time = None
            if updated_at_str:
                try:
                    last_checked_time = date_parser.isoparse(updated_at_str)
                except ValueError:
                    print(f"  [SCHEDULER] 경고: '{relative_file_path}'의 updated_at ('{updated_at_str}') 파싱 실패. 첫 검사로 간주.")

            should_check = False
            if last_checked_time is None:
                print(f"  [SCHEDULER] 파일: {relative_file_path}, 상태: 첫 검사 대상.")
                should_check = True
            else:
                interval_delta = timedelta(seconds=check_interval_seconds)
                next_check_time = last_checked_time + interval_delta
                if now >= next_check_time:
                    lc_display = last_checked_time.strftime(
                        '%Y-%m-%d %H:%M:%S %Z') if last_checked_time.tzinfo else last_checked_time.strftime(
                        '%Y-%m-%d %H:%M:%S')
                    nc_display = next_check_time.strftime(
                        '%Y-%m-%d %H:%M:%S %Z') if next_check_time.tzinfo else next_check_time.strftime(
                        '%Y-%m-%d %H:%M:%S')
                    print(
                        f"  [SCHEDULER] 파일: {relative_file_path}, 상태: 검사 주기 도래 (마지막: {lc_display}, 다음: {nc_display}).")
                    should_check = True

            if should_check:
                print(f"    [SCHEDULER] 검사 수행: {absolute_file_path}")
                if not absolute_file_path.exists():
                    print(f"    [SCHEDULER] [경고] 파일 없음: {absolute_file_path}")
                    self.api_client_module.report_file_deleted_on_server(
                        relative_file_path, detection_source="scheduled_per_file"
                    )
                    continue
                try:
                    new_hash = calculate_file_hash(str(absolute_file_path))  # 수정: 직접 호출
                    if new_hash:
                        self.api_client_module.report_hash(
                            relative_file_path, new_hash, detection_source="scheduled_per_file"
                        )
                    else:
                        print(f"      ㄴ 오류: 해시 계산 실패 ({relative_file_path})")
                except Exception as e:
                    print(f"      ㄴ 오류 (주기적 검사 중 해시 계산/보고 {relative_file_path}): {e}")
        print(f"--- 각 파일별 주기적 검사 완료 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")

    def run(self):
        """ 모니터링 시작 """
        print("파일 무결성 모니터링을 시작합니다")
        self.api_client_module.initialize_api_credentials()
        if not self.api_client_module.API_TOKEN:
            return

        ensure_fim_directory()

        if USE_WATCHDOG:
            self.observer.schedule(self.event_handler, str(FIM_BASE_DIR), recursive=True)
            self.observer.start()
            print(f"[{datetime.now()}] 실시간 파일 변경 감지(Watchdog) 활성화됨 ({FIM_BASE_DIR})")
        else:
            print(f"[{datetime.now()}] 실시간 파일 변경 감지(Watchdog) 비활성화됨")

        print(f"[{datetime.now()}] 프로그램 시작 초기 파일 검사를 실행합니다...")
        self.check_files_periodically()

        print(f"[{datetime.now()}] 매 1분마다 각 파일별 검사 대상 여부를 확인하는 스케줄러를 시작합니다.")
        schedule.every(1).minutes.do(self.check_files_periodically)

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n사용자에 의해 파일 무결성 모니터링이 중단됩니다...")
        except Exception as e:
            print(f"\n모니터링 중 예상치 못한 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if USE_WATCHDOG and self.observer.is_alive():
                self.observer.stop()
                self.observer.join()
                print("Watchdog 모니터링이 정지되었습니다.")
            schedule.clear()
            print("모든 스케줄된 작업이 정지되었습니다.")
            print("프로그램을 종료합니다.")


if __name__ == "__main__":

    use_watchdog_config = USE_WATCHDOG

    monitor = FileMonitor()
    monitor.run()