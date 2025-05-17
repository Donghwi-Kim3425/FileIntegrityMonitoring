# file_monitor.py
import os
import time
import schedule
import api_client
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from integrity_checker import IntegrityChecker


class FileMonitor:
    def __init__(self):
        self.integrity_checker = IntegrityChecker()

    def get_files_to_check(self):
        """서버로부터 검사 대상 파일 목록을 받아옴"""
        return api_client.fetch_file_list()

    def check_files(self):
        """검사가 필요한 모든 파일의 무결성을 검사"""
        print(f"--- 주기적 파일 검사 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
        files_to_check = self.get_files_to_check()

        if not files_to_check:
            print("검사할 파일 목록이 없습니다.")
            # 검사할 파일이 없더라도 검사 사이클은 완료된 것이므로 로그 출력
            print(f"--- 주기적 파일 검사 완료 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
            return

        now = datetime.now().astimezone()

        for file_info in files_to_check:
            file_path = file_info.get("file_path")
            check_interval_seconds_str = file_info.get("check_interval")
            updated_at_str = file_info.get("updated_at")

            if not file_path or check_interval_seconds_str is None:
                continue

            # check_interval_seconds를 float으로 변환
            try:
                check_interval_seconds = float(check_interval_seconds_str)
            except ValueError:
                print(
                    f"'{file_path}'의 check_interval ('{check_interval_seconds_str}')이 유효한 숫자가 아닙니다. 이 파일은 건너<0xEB><0><0x8F>니다.")
                continue

            # updated_at (마지막 검사 시간) 파싱
            last_checked_time = None
            if updated_at_str:
                try:
                    last_checked_time = date_parser.isoparse(updated_at_str)
                except ValueError:
                    print(f"'{file_path}'의 updated_at ('{updated_at_str}') 파싱 실패. 첫 검사로 간주합니다.")
                    last_checked_time = None

            should_check = False
            if last_checked_time is None:
                print(f"'{file_path}': 첫 검사 대상입니다.")
                should_check = True
            else:
                # 다음 검사 예정 시간 계산
                interval_delta = timedelta(seconds=check_interval_seconds)
                next_check_time = last_checked_time + interval_delta

                if now >= next_check_time:
                    # 타임존 정보가 있으면 %Z로 출력, 없으면 시간만 출력
                    last_checked_display = last_checked_time.strftime(
                        '%Y-%m-%d %H:%M:%S %Z') if last_checked_time.tzinfo else last_checked_time.strftime(
                        '%Y-%m-%d %H:%M:%S')
                    next_check_display = next_check_time.strftime(
                        '%Y-%m-%d %H:%M:%S %Z') if next_check_time.tzinfo else next_check_time.strftime(
                        '%Y-%m-%d %H:%M:%S')
                    print(
                        f"'{file_path}': 검사 주기가 도래했습니다 (마지막 검사: {last_checked_display}, 주기: {interval_delta}, 다음 예정: {next_check_display}).")
                    should_check = True
                else:
                    next_check_display = next_check_time.strftime(
                        '%Y-%m-%d %H:%M:%S %Z') if next_check_time.tzinfo else next_check_time.strftime(
                        '%Y-%m-%d %H:%M:%S')
                    print(f"'{file_path}': 검사 주기가 아직 도래하지 않았습니다. (다음 예정: {next_check_display})")

            # 검사해야 하는 파일인 경우
            if should_check:
                print(f"파일 검사 수행: {file_path}")
                if not os.path.exists(file_path):
                    print(f"[경고] 파일 없음: {file_path}")
                    # TODO: 파일 삭제 상태를 서버에 보고하는 기능 추가 고려
                    continue

                # 해시 계산 후 API로 결과 전송
                self.integrity_checker.check_and_report(file_path)

        # for 루프가 끝난 후 "주기적 파일 검사 완료" 로그 출력
        print(f"--- 주기적 파일 검사 완료 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")

    def run(self):
        """모니터링 시작"""
        print("파일 무결성 모니터링을 시작합니다...")

        # 시작과 동시에 한 번 파일 검사 실행
        self.check_files()

        # 이후 스케줄에 따라 주기적으로 실행
        schedule.every(1).minutes.do(self.check_files)

        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    monitor = FileMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\n파일 무결성 모니터링을 종료합니다.")
    except Exception as e:
        print(f"\n모니터링 중 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()