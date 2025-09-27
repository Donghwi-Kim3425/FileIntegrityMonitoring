import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL, // Flask 백엔드 서버 주소
  headers: {
    'Content-Type': 'application/json',
  },
});

export default apiClient;
