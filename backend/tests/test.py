import time
from datetime import datetime

TEST_FILE_PATH = "testfile.txt"

def modify_file_every_minute():
    for i in range(3):  # 3분 동안 테스트
        with open(TEST_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n변경 내용 {i+1} - {datetime.now()}")
        print(f"[{i+1}/3] 파일 수정 완료: {datetime.now()}")

        time.sleep(60)  # 1분 대기

if __name__ == "__main__":
    print("테스트 파일 변경 시작...")
    modify_file_every_minute()

