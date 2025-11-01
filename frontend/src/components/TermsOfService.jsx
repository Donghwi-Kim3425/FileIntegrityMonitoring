import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Link } from 'react-router-dom';

/*** 서비스 이용약관 페이지 컴포넌트 */

export default function TermsOfService() {
  return (
    <div className="min-h-screen bg-gray-50 p-6 py-12">
      <Card className="max-w-4xl mx-auto shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">
            서비스 이용약관 (Terms of Service)
          </CardTitle>
          <p className="text-sm text-gray-500">
            시행일: 2025년 11월 1일
          </p>
        </CardHeader>
        <CardContent className="space-y-6 text-gray-700 leading-relaxed">
          <p>
            filemonitor.me (이하 "서비스")에 오신 것을 환영합니다. 본 약관은 귀하가 본 서비스를 이용함에 있어 필요한 권리, 의무 및 책임사항을 규정함을 목적으로 합니다.
          </p>

          <section className="space-y-2">
            <h2 className="text-xl font-semibold">1. 서비스의 정의</h2>
            <p>
              본 서비스는 사용자가 지정한 로컬 파일의 무결성을 모니터링하고, 파일 변경 시 이를 감지하여 사용자에게 알리며, 사용자의 Google Drive 계정으로 해당 파일의 버전을 백업할 수 있도록 지원하는 웹 기반 소프트웨어입니다.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-xl font-semibold">2. 사용자 계정 및 의무</h2>
            <p>
              본 서비스는 Google OAuth를 통한 로그인을 필요로 합니다. 귀하는 귀하의 계정 정보 및 Google Drive 접근 권한을 안전하게 관리할 책임이 있습니다. 귀하는 본 서비스를 합법적인 목적으로만 사용해야 합니다.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-xl font-semibold">3. 책임의 한계</h2>
            <p>
              본 서비스는 "있는 그대로(as-is)" 제공됩니다. 서비스는 파일 모니터링 및 백업의 정확성이나 안정성을 보장하기 위해 노력하나, 데이터 유실, 백업 실패, 모니터링 누락 등으로 발생하는 어떠한 손해에 대해서도 책임을 지지 않습니다. 데이터의 중요성에 따라 사용자는 항상 별도의 추가 백업 수단을 마련해야 합니다.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="text-xl font-semibold">4. 서비스의 변경 및 중단</h2>
            <p>
              서비스는 운영상의 필요에 따라 사전 고지 없이 서비스의 일부 또는 전부를 변경하거나 중단할 수 있습니다.
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