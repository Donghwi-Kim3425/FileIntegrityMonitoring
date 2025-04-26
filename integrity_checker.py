#integrity_checker.py
from hash_calculator import calculate_file_hash
from database import DatabaseManager
import os

class IntegrityChecker:
    def __init__(self):
        self.db_manager = DatabaseManager()

    def check_file_integrity(self, file_path):
        """파일 무결성 검사 및 DB 업데이트"""
        # 파일이 존재하지 않으면 'Deleted' 처리
        if not os.path.exists(file_path):
            self.db_manager.mark_file_as_deleted(file_path)
            return

        # 파일이 존재하는 경우 'Recovered' 상태 여부 확인
        current_status = self.db_manager.get_file_status(file_path)
        if current_status == 'Deleted':
            self.db_manager.mark_file_as_recovered(file_path)

        # 해시 계산
        new_hash = calculate_file_hash(file_path)
        if not new_hash:
            return

        # DB 업데이트
        self.db_manager.update_file_record(file_path, new_hash)