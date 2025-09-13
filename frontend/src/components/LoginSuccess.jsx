// frontend/src/components/LoginSuccess.jsx
import { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function LoginSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    // 1. URL의 'token' 파라미터를 가져옴
    const token = searchParams.get('token');

    if (token) {
      // 2. 토큰이 있다면 localStorage에 저장
      console.log("로그인 성공! API 토큰을 저장합니다.");
      localStorage.setItem('fim_api_token', token);

      // 3. 메인 페이지('/')로 사용자를 이동
      navigate('/');
    } else {
      // 토큰 없이 이 페이지에 접근한 경우
      console.error("토큰 없이 /login-success 페이지에 접근했습니다.");
      navigate('/');
    }
  }, [searchParams, navigate]);

  return (
    <div className="flex justify-center items-center h-screen">
      <p>로그인 처리 중입니다...</p>
    </div>
  );
}