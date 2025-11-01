import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Link } from 'react-router-dom';

/*** 개인정보처리방침 페이지 컴포넌트 */
export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-gray-50 p-6 py-12">
      <Card className="max-w-4xl mx-auto shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">
            개인정보처리방침 (Privacy Policy)
          </CardTitle>
          <p className="text-sm text-gray-500">
            시행일: 2025년 11월 1일
          </p>
        </CardHeader>
        <CardContent className="space-y-6 text-gray-700 leading-relaxed">
          <p>
            본 개인정보처리방침은 File Monitor (이하 "서비스")가 filemonitor.me 도메인에서 제공하는 서비스와 관련하여 귀하의 개인정보를 어떻게 수집, 이용, 보호하는지에 대해 설명합니다.
          </p>

          <section className="space-y-2">
            <h2 className="text-xl font-semibold">1. 수집하는 개인정보</h2>
            <p>
              본 서비스는 Google OAuth를 통한 사용자 인증을 위해 다음과 같은 최소한의 개인정보를 Google로부터 제공받습니다:
            </p>
            <ul className="list-disc list-inside pl-4">
              <li><strong>Google 계정 이메일 주소:</strong> 사용자 식별 및 계정 관리를 위해 사용됩니다.</li>
              <li><strong>Google 프로필 이름:</strong> 서비스 내 사용자 표시에 사용될 수 있습니다.</li>
            </ul>
            <p>
              또한, 서비스의 핵심 기능인 Google Drive 백업을 위해 귀하의 명시적인 동의 하에 Google Drive API 접근 토큰(Access Token 및 Refresh Token)을 수집하여 암호화된 상태로 서버에 저장합니다.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-xl font-semibold">2. 개인정보의 이용 목적</h2>
            <p>
              수집된 개인정보는 다음 목적을 위해서만 사용됩니다:
            </p>
            <ul className="list-disc list-inside pl-4">
              <li>서비스 제공 및 사용자 인증 (로그인 처리)</li>
              <li>파일 무결성 모니터링 및 변경 내역 기록</li>
              <li>사용자의 Google Drive 계정으로 지정된 파일 백업 수행</li>
              <li>서비스 관련 중요 공지 및 알림 (예: 파일 변경 알림)</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-xl font-semibold">3. 개인정보의 제3자 제공</h2>
            <p>
              본 서비스는 귀하의 동의 없이 개인정보를 제3자에게 판매하거나 공유하지 않습니다. 단, 다음의 경우는 예외로 합니다:
            </p>
            <ul className="list-disc list-inside pl-4">
              <li>귀하가 Google Drive 백업 기능을 사용하여 명시적으로 Google 서비스에 데이터 전송을 요청하는 경우</li>
              <li>법령의 규정에 의거하거나, 수사 목적으로 법령에 정해진 절차와 방법에 따라 수사기관의 요구가 있는 경우</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-xl font-semibold">4. 개인정보의 보유 및 파기</h2>
            <p>
              귀하의 개인정보는 회원 탈퇴 시 또는 서비스 종료 시까지 보유 및 이용됩니다. 귀하의 Google OAuth 토큰은 언제든지 서비스 내에서 연결을 해제할 수 있으며, 회원 탈퇴 시 즉시 파기됩니다.
            </p>
          </section>

          <div className="pt-6 border-t mt-6">
            <Link to="/" className="text-blue-600 hover:underline font-medium">
              &larr; 메인 화면으로 돌아가기
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}