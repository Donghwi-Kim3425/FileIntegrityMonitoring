import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:5000', // Flask 백엔드 서버 주소
  headers: {
    'Content-Type': 'application/json',
  },
});

export default apiClient;
