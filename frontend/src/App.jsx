// frontend/src/App.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import FileIntegrityUI from './components/FileIntegrityUI';
import LoginSuccess from './components/LoginSuccess';
import PrivacyPolicy from './components/PrivacyPolicy';
import TermsOfService from './components/TermsOfService';
import './index.css';

function App() {
  console.log("VITE_API_BASE_URL:", import.meta.env.VITE_API_BASE_URL);
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<FileIntegrityUI />} />
        <Route path="/login-success" element={<LoginSuccess />} />
        <Route path="/privacy-policy" element={<PrivacyPolicy />} />
        <Route path="/terms-of-service" element={<TermsOfService />} />
      </Routes>
    </BrowserRouter>
  );
}


export default App;