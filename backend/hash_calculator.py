import ctypes
from config import DLL_PATH

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