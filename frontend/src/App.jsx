// frontend/src/App.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import FileIntegrityUI from './components/FileIntegrityUI';
import LoginSuccess from './components/LoginSuccess';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<FileIntegrityUI />} />
        <Route path="/login-success" element={<LoginSuccess />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;