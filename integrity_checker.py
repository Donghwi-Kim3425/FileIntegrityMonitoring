# integrity_checker.py
import os
from hash_calculator import calculate_file_hash
from plyer import notification
import api_client

class IntegrityChecker:
    def check_and_report(self, file_path):
        """해시 계산 후 서버에 결과 보고"""
        new_hash = calculate_file_hash(file_path)
        if not new_hash:
            print(f"[오류] 해시 계산 실패: {file_path}")
            return

        success = api_client.report_hash(file_path, new_hash)
        if success:
            print(f"[전송 완료] {file_path} 해시 보고됨")
        else:
            print(f"[오류] {file_path} 해시 전송 실패")

