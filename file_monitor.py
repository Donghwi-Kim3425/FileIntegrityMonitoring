#file_monitor.py
import time
import schedule
import os
from integrity_checker import IntegrityChecker
from database import DatabaseManager

class FileMonitor:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.integrity_checker = IntegrityChecker()

    def get_files_to_check(self):
        """검사가 필요한 파일 목록을 가져옴"""
        return self.db_manager.get_files_due_for_check()

    def check_files(self):
        """검사가 필요한 모든 파일의 무결성을 검사"""
        files_to_check = self.get_files_to_check()
        for file_id, file_path, check_interval, last_check in files_to_check:
            print(f"파일 검사 중: {file_path}")
            self.integrity_checker.check_file_integrity(file_path)

    def run(self):
        """모니터링을 시작"""
        print("파일 모니터링을 시작합니다...")

        # 1분마다 검사 실행
        schedule.every(1).minutes.do(self.check_files)

        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    monitor = FileMonitor()
    monitor.run()