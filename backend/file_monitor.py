import os, time, schedule
import api_client
import sys
import traceback
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from hash_calculator import calculate_file_hash
from config import USE_WATCHDOG


def resource_path(relative_path):
    """ PyInstaller로 빌드된 .exe 내부의 리소스 경로를 반환 """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

IS_WINDOWS = sys.platform == 'win32'

if IS_WINDOWS:
    import winreg
    from win10toast_click import ToastNotifier
else:
    winreg = None
    ToastNotifier = None

# --- 자동 시작 프로그램으로 설정 ---
APP_NAME = "FileIntegrityMonitor"
exe_path = sys.executable
KEY_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

def set_startup():
    """
    현재 실행 중인 exe 파이을 자동 시작 레지스트리에 등록
    이미 등록되어 있으면 아무 작업도 하지 않음
    """

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)

    except FileNotFoundError:

        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY_PATH)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)

        except Exception as e:
            print(f"⚠️ Run 키 생성 실패: {e}")

    except Exception as e:
        print(f"⚠️ 자동 실행 등록 중 오류 발생: {e}")


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
        self.api_client = api_client_instance
        self.last_event_time = {}
        self.MODIFIED_IGNORE_THRESHOLD_AFTER_CREATE = 10.0
        self.EVENT_DEBOUNCING_TIME = 2.0
        self.last_sent_hash = {}

        if IS_WINDOWS and ToastNotifier:
            self.toaster = ToastNotifier()
        else:
            self.toaster = None

    def _get_relative_path(self, src_path):
        """ 기본 경로로부터 상대 경로 계산, OS 독립적인 구분자 사용 """
        return os.path.relpath(src_path, self.base_path_str).replace('\\', '/')

    def _should_process(self, event_path):
        """ 이벤트를 처리해야 하는지 확인 (디바운싱 포함) """
        norm_event_path = os.path.normpath(event_path)
        current_time = time.time()

        last_time = self.last_event_time.get(norm_event_path, 0)

        if (current_time - last_time) < self.EVENT_DEBOUNCING_TIME:
            return False

        self.last_event_time[norm_event_path] = current_time
        return True

    def _is_temporary_file(self, filepath):
        """
        파일 경로가 임시파일인지 확인

        :param filepath: 파일 경로

        :return: True/False
        """

        filename = os.path.basename(filepath).lower()

        temp_patterns = [
            filename.startswith('~'),  # MS Office 임시파일 (~$filename.docx)
            filename.endswith('.tmp'),  # 일반 tmp
            filename.endswith('.temp'),  # 일부 프로그램이 생성하는 temp
            filename.endswith('.swp'),  # Vim swap 파일
            filename.endswith('.swo'),  # Vim backup
            filename.endswith('.bak'),  # 일반 백업 파일
            filename.endswith('.part'),  # 브라우저 다운로드 중간 파일
            filename.endswith('.crdownload'),  # Chrome 다운로드 중간 파일
            filename.endswith('.download'),  # Safari 다운로드 중간 파일
            filename.endswith('.wbk'),  # Word 자동 백업
            filename.endswith('.xlk'),  # Excel 백업
            filename.endswith('.~lock'),  # LibreOffice lock 파일
        ]

        return any(temp_patterns)

    def on_created(self, event):
        """ 파일 생성 이벤트 처리 """

        if event.is_directory or self._is_temporary_file(event.src_path):
            return

        if not self._should_process(event.src_path):
            return

        relative_path = self._get_relative_path(event.src_path)
        absolute_path = str(FIM_BASE_DIR / relative_path)
        change_time = datetime.now()

        print(f"[{datetime.now()}] [WATCHDOG] 파일 생성됨: {relative_path}")

        try:
            time.sleep(1.0) # 파일 쓰기 완료 대기
            new_hash = calculate_file_hash(absolute_path)
            if new_hash:
                with open(absolute_path, 'rb') as f:
                    file_content_bytes = f.read()

                print(f"  ㄴ Google Drive 백업 시도 (생성됨): {relative_path}")
                backup_success = self.api_client.request_gdrive_backup(
                    relative_path,
                    file_content_bytes,
                    new_hash,
                    is_modified=False,
                    change_time=change_time,
                )
                if backup_success:
                    self.last_sent_hash[relative_path] = new_hash
                    if self.toaster:
                        try:
                            self.toaster.show_toast(
                                "FIM: 파일 생성됨",
                                f"파일이 백업되었습니다: {relative_path}",
                                icon_path=resource_path("app_icon.ico"),
                                duration=10,
                                threaded=True
                            )
                        except Exception as e:
                            print(f" ㄴ[알림 오류] OS 알림 표시에 실패했습니다: {e}")

                if not backup_success:
                    print(f"    ㄴ Google Drive 백업 요청 실패.")
            else:
                print(f"  ㄴ 오류: 해시 계산 실패 ({relative_path})")

        except Exception as e:
            print(f"  ㄴ 오류 (on_created 처리 중 {relative_path}): {e}")

    def on_modified(self, event):
        """ 파일 수정 이벤트 처리 """
        if event.is_directory or self._is_temporary_file(event.src_path):
            return

        if not self._should_process(event.src_path):
            return

        relative_path = self._get_relative_path(event.src_path)
        absolute_path = str(FIM_BASE_DIR / relative_path)
        change_time = datetime.now()
        print(f"[{datetime.now()}] [WATCHDOG] 파일 수정됨: {relative_path}")

        try:
            time.sleep(0.5) # 파일 쓰기 완료 대기
            new_hash = calculate_file_hash(absolute_path)
            if new_hash:
                last_hash = self.last_sent_hash.get(relative_path)
                if last_hash == new_hash:
                    return

                with open(absolute_path, 'rb') as f:
                    file_content_bytes = f.read()

                print(f"  ㄴ Google Drive 백업 시도 (수정됨): {relative_path}")
                backup_success = self.api_client.request_gdrive_backup(
                    relative_path,
                    file_content_bytes,
                    new_hash,
                    is_modified=True,
                    change_time=change_time,
                )
                if backup_success:
                    self.last_sent_hash[relative_path] = new_hash
                    if self.toaster:
                        try:
                            self.toaster.show_toast(
                                "FIM: 파일 수정됨",
                                f"새 버전이 백업되었습니다: {relative_path}",
                                icon_path=resource_path("app_icon.ico"),
                                duration=10,
                                threaded=True
                            )
                        except Exception as e:
                            print(f"  ㄴ [알림 오류] OS 알림 표시에 실패했습니다: {e}")

                if not backup_success:
                    print(f"    ㄴ Google Drive 백업 요청 실패 (수정됨).")
            else:
                print(f"  ㄴ 오류: 해시 계산 실패 ({relative_path})")

        except Exception as e:
            print(f"  ㄴ 오류 (on_modified 처리 중 {relative_path}): {e}")

    def on_deleted(self, event):
        """ 파일 삭제 이벤트 처리 """
        if event.is_directory or self._is_temporary_file(event.src_path):
            return

        relative_path = self._get_relative_path(event.src_path)
        print(f"[{datetime.now()}] [WATCHDOG] 파일 삭제됨: {relative_path}")

        success = self.api_client.report_file_deleted_on_server(
            relative_path, detection_source="watchdog"
        )
        if success:
            print(f"  ㄴ 서버에 삭제 보고 성공: {relative_path}")
            if self.toaster:
                try:
                    self.toaster.show_toast(
                        "FIM: 파일 삭제됨",
                        f"파일 삭제가 서버에 보고되었습니다: {relative_path}",
                        icon_path=resource_path("app_icon.ico"),
                        duration=10,
                        threaded=True
                    )
                except Exception as e:
                    print(f"  ㄴ [알림 오류] OS 알림 표시에 실패했습니다: {e}")
        else:
            print(f"  ㄴ 서버에 삭제 보고 실패: {relative_path}")

        if relative_path in self.last_sent_hash:
            try:
                del self.last_sent_hash[relative_path]
            except KeyError:
                pass

    def on_moved(self, event):
        """
        파일 이동/이름 변경 이벤트 처리.
        '안전한 저장' 패턴(임시 파일 -> 원본 파일)을 '수정'으로 간주하여 처리
        """
        backup_performed_or_skipped = False
        if event.is_directory or self._is_temporary_file(event.src_path) or self._is_temporary_file(event.dest_path):
            print(f"[{datetime.now()}] [WATCHDOG] 디렉토리 이동 감지 (현재 미처리): {event.src_path} -> {event.dest_path}")
            return

        if not self._should_process(event.dest_path):
            return

        # 이동 이벤트의 최종 목적지 파일을 기준으로 '수정'된 것으로 간주
        relative_path = self._get_relative_path(event.dest_path)
        absolute_path = str(FIM_BASE_DIR / relative_path)
        change_time = datetime.now()
        print(f"[{datetime.now()}] [WATCHDOG] 파일 이동 감지 -> '수정'으로 처리: {relative_path}")

        try:
            # 파일 쓰기가 완전히 끝날 때까지 잠시 대기
            time.sleep(1.0)
            new_hash = calculate_file_hash(absolute_path)

            if new_hash:
                last_hash = self.last_sent_hash.get(relative_path)
                if last_hash == new_hash:
                    backup_performed_or_skipped = True
                else:
                    with open(absolute_path, 'rb') as f:
                        file_content_bytes = f.read()

                    print(f"  ㄴ Google Drive 백업 시도 (이동으로 인한 수정): {relative_path}")
                    # is_modified=True로 설정하여 수정된 파일과 동일하게 백업을 요청합니다.
                    backup_success = self.api_client.request_gdrive_backup(
                        relative_path,
                        file_content_bytes,
                        new_hash,
                        is_modified=True,
                        change_time=change_time,
                    )
                    if backup_success:
                        self.last_sent_hash[relative_path] = new_hash
                        backup_performed_or_skipped = True
            else:
                print(f"  ㄴ 오류: 해시 계산 실패 ({relative_path})")

        except Exception as e:
            print(f"  ㄴ 오류 (on_moved 처리 중 {relative_path}): {e}")

        # 만약 원본 파일이 임시 파일이 아니었다면 (단순 이름 변경의 경우)
        # 이전 이름의 파일을 삭제된 것으로 보고
        if not self._is_temporary_file(event.src_path):
            relative_old_path = self._get_relative_path(event.src_path)

            if backup_performed_or_skipped:
                print(f"  ㄴ 원본 경로 삭제 보고 (이름 변경 감지): {relative_old_path}")
                self.api_client.report_file_deleted_on_server(
                    relative_old_path, detection_source="watchdog_rename"
                )
                if relative_old_path in self.last_sent_hash:
                    try:
                        del self.last_sent_hash[relative_old_path]
                    except KeyError:
                        pass
            else:
                print(f"  ㄴ 목적지 파일 백업 실패. 원본 경로 삭제 보고 건너뜀: {relative_old_path}")


class FileMonitor:
    def __init__(self):
        self.api_client_module = api_client

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
                    success = self.api_client_module.report_file_deleted_on_server(
                        relative_file_path, detection_source="scheduled_per_file"
                    )
                    if success:
                        if relative_file_path in self.event_handler.last_sent_hash:
                            try:
                                del self.event_handler.last_sent_hash[relative_file_path]
                            except KeyError:
                                pass
                    continue

                try:
                    new_hash = calculate_file_hash(str(absolute_file_path))  # 수정: 직접 호출
                    if new_hash:
                        last_hash = self.event_handler.last_sent_hash.get(relative_file_path)
                        if last_hash == new_hash:
                            print(f"    [SCHEDULER] 해시 변경 없음. 서버 보고 생략.")
                            continue

                        success = self.api_client_module.report_hash(
                            relative_file_path, new_hash, detection_source="scheduled_per_file"
                        )
                        if success:
                            self.event_handler.last_sent_hash[relative_file_path] = new_hash
                    else:
                        print(f"      ㄴ 오류: 해시 계산 실패 ({relative_file_path})")
                except Exception as e:
                    print(f"      ㄴ 오류 (주기적 검사 중 해시 계산/보고 {relative_file_path}): {e}")
        print(f"--- 각 파일별 주기적 검사 완료 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")

    def run(self):
        """ 모니터링 시작 """
        print("파일 무결성 모니터링을 시작합니다")

        api_token_set = False
        try:
            self.api_client_module.initialize_api_credentials()
            if not self.api_client_module.API_TOKEN:
                print("⚠️ 오류: API_TOKEN이 설정되지 않았습니다. API 초기화에 실패했습니다.")
                print("api_client.py의 로그를 확인해야 합니다. (client_startup.log)")
            else:
                api_token_set = True  # 성공 플래그 설정
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

                while True:
                    schedule.run_pending()
                    time.sleep(1)

        except KeyboardInterrupt:
            print("\n사용자에 의해 파일 무결성 모니터링이 중단됩니다...")

        except Exception as e:
            # --- 추가: 예기치 못한 충돌 기록 ---
            print(f"\n모니터링 실행 중 예상치 못한 오류 발생: {e}")
            traceback.print_exc()  # 전체 오류 스택 출력

        finally:
            # --- 추가: 토큰 설정 실패 시(api_token_set == False) 창 닫힘 방지 ---
            if not api_token_set:
                print("\n[자동 종료 방지] 15초 동안 오류 메시지를 표시합니다...")
                time.sleep(15)
            # --- 기존 finally 내용 ... ---
            if USE_WATCHDOG and self.observer.is_alive():
                self.observer.stop()
                self.observer.join()
                print("Watchdog 모니터링이 정지되었습니다.")
            schedule.clear()
            print("모든 스케줄된 작업이 정지되었습니다.")
            print("프로그램을 종료합니다.")


if __name__ == "__main__":

    use_watchdog_config = USE_WATCHDOG
    if IS_WINDOWS:
        set_startup()

    monitor = FileMonitor()
    monitor.run()