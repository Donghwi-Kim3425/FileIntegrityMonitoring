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
            print("검사할 팔일 목록이 없습니다.")
            return


        now = datetime.now().astimezone()

        for file_info in files_to_check:
            file_path = file_info.get("file_path")
            check_interval_seconds = file_info.get("check_interval") # 초 단위 float
            updated_at_str = file_info.get("updated_at")

            if not file_path or check_interval_seconds is None:
                continue

            # updated_at (마지막 검사 시간) 파싱
            last_checked_time = None
            if updated_at_str:
                last_checked_time = date_parser.isoparse(updated_at_str)
            else:
                continue

            # 검사 주기 확인
            # last_checked_time이 없으면(첫 검사) 무조건 검사
            should_check = False
            if last_checked_time is None:
                print(f"'{file_path}': 첫 검사 대상입니다.")
                should_check = True
            else:
                # 다음 검사 예정 시간 계산
                # check_interval_seconds가 float일 수 있으므로 timedelta로 변환
                interval_delta = timedelta(seconds=check_interval_seconds)
                next_check_time = last_checked_time + interval_delta


                if now >= next_check_time:
                    print(f"'{file_path}': 검사 주기가 도래했습니다 (마지막 검사: {last_checked_time.strftime('%H:%M:%S')}, 주기: {interval_delta}, 다음 예정: {next_check_time.strftime('%H:%M:%S')}).")
                    should_check = True
                else:
                    # 주기가 아직 안 됐으면 건너뜀
                    pass # 검사 안 함

            # 검사해야 하는 파일인 경우
            if should_check:
                print(f"파일 검사 수행: {file_path}")
                if not os.path.exists(file_path):
                    print(f"[경고] 파일 없음: {file_path}")
                    # TODO: 파일 삭제 상태를 서버에 보고하는 기능 추가 고려
                    continue

                # 해시 계산 후 API로 결과 전송
                self.integrity_checker.check_and_report(file_path)

            print("--- 주기적 파일 검사 완료 ---")

            if not os.path.exists(file_path):
                print(f"[경고] 파일 없음: {file_path}")
                # 향후: 삭제 상태도 서버에 보고할 수 있음
                continue

            # 해시 계산 후 API로 결과 전송
            self.integrity_checker.check_and_report(file_path)

    def run(self):
        """모니터링 시작"""
        print("파일 무결성 모니터링을 시작합니다...")

        schedule.every(1).minutes.do(self.check_files)

        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    monitor = FileMonitor()
    monitor.run()
