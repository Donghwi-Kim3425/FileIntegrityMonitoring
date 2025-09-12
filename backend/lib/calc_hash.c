#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <openssl/evp.h>

#define CHUNK_SIZE 4096  // 읽기 단위 크기

// DLL 내보내기 매크로 (Windows용)
#ifdef _WIN32
    #define EXPORT __declspec(dllexport)
#else
    #define EXPORT
#endif

// SHA-256 계산 함수
void calculate_sha256(FILE *file, unsigned char *final_hash) {
    EVP_MD_CTX *mdctx = EVP_MD_CTX_new();
    if (!mdctx) {
        printf("EVP_MD_CTX_new failed\n");
        return;
    }
    // SHA-256 초기화
    if (EVP_DigestInit_ex(mdctx, EVP_sha256(), NULL) != 1) {
        printf("EVP_DigestInit_ex failed\n");
        EVP_MD_CTX_free(mdctx);
        return;
    }
    // 파일 데이터를 읽으며 해시 업데이트
    unsigned char buffer[CHUNK_SIZE];
    size_t bytes_read;
    while ((bytes_read = fread(buffer, 1, CHUNK_SIZE, file)) > 0) {
        if (EVP_DigestUpdate(mdctx, buffer, bytes_read) != 1) {
            printf("EVP_DigestUpdate failed\n");
            EVP_MD_CTX_free(mdctx);
            return;
        }
    }
    // 최종 해시 계산
    if (EVP_DigestFinal_ex(mdctx, final_hash, NULL) != 1) {
        printf("EVP_DigestFinal_ex failed\n");
        EVP_MD_CTX_free(mdctx);
        return;
    }
    EVP_MD_CTX_free(mdctx);
}

// Python에서 호출할 함수
EXPORT int calculate_file_hash(const char *filename, unsigned char *hash_output) {
    FILE *file = fopen(filename, "rb"); // 바이너리 모드로 파일 열기
    if (!file) {
        printf("Fail to open file: %s\n", filename);
        return 0; // 실패
    }
    
    // SHA-256 계산
    calculate_sha256(file, hash_output);
    fclose(file);
    
    return 1; // 성공
}

// 테스트용 main 함수 (필요시)
int main() {
    char filename[1024]; // 파일 경로 저장
    printf("Enter file path: ");
    if (fgets(filename, sizeof(filename), stdin) == NULL) {
        printf("Fail to find path.\n");
        return 1;
    }
    
    // 줄바꿈 문자 제거
    filename[strcspn(filename, "\n")] = '\0';
    
    // SHA-256 해시값 저장 공간
    unsigned char final_hash[32];
    
    // 함수 호출
    if (calculate_file_hash(filename, final_hash)) {
        // 해시 값 출력
        printf("SHA-256 hash: ");
        for (int i = 0; i < 32; i++) {
            printf("%02x", final_hash[i]);
        }
        printf("\n");
    }
    
    return 0;
}