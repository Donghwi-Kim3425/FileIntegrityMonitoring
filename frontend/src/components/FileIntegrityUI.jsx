import { useState, useEffect } from "react";
import apiClient from "@/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Undo, Trash, RefreshCw, Clock } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

// 임시 모달 컴포넌트
function ConfirmationModal({ message, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-xl space-y-4">
        <p className="font-semibold">{message}</p>
        <div className="flex justify-end space-x-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm}>Confirm</Button>
        </div>
      </div>
    </div>
  );
}

export default function FileIntegrityUI() {
  const [logs, setLogs] = useState([])
  const [selectedLog, setSelectedLog] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('fim_api_token');
    if (token) {
      setIsLoggedIn(true);
      fetchLogs(token);
    } else {
      setIsLoggedIn(false);
    }
  }, []);

  // API에서 로그 데이터를 가져오는 함수
  const fetchLogs = async (token) => {
    try {
      const response = await apiClient.get('/api/files/logs', {
          headers: { Authorization: `Bearer ${token} ` }
      });
      setLogs(response.data);
      return response.data;
    } catch (error) {
      console.error("로그 데이터를 불러오는 데 실패했습니다:", error);
      if (error.response && (error.response.status === 401 || error.response.status === 403)) {
        handleLogout();
      }
      return [];
    }
  };

  const handleLogout = () => {
      localStorage.removeItem('fim_api_token');
      setIsLoggedIn(false);
      setLogs([]);

  }

  // 차트 데이터 가공
  const data = logs.reduce((acc, log) => {
    const found = acc.find((item) => item.status === log.status);
    if (found) {
      found.count++;
    } else {
      acc.push({ status: log.status, count: 1 });
    }
    return acc;
  }, []);

  // 서버에 삭제 요청
  const handleDelete = async () => {
    if (!selectedLog) return;
    try {
        const token = localStorage.getItem('fim_api_token');
        // TODO: 백엔드에 DELETE /api/files/logs/:log_id 와 같은 API 엔드포인트가 필요합니다.
        await apiClient.delete(`/api/files/logs/${selectedLog.id}`, { // log.id가 필요합니다.
            headers: { Authorization: `Bearer ${token}` }
        });

        console.log(`${selectedLog.file} 로그가 성공적으로 삭제되었습니다.`);
        setSelectedLog(null);
        setShowDeleteConfirm(false);
        fetchLogs(); // 삭제 후 목록을 다시 불러옵니다.
    } catch (error) {
        console.error("로그 삭제에 실패했습니다:", error);
    }
  };

// 서버에 업데이트 요청
  const handleUpdate = async (fileId) => {
    try {
        const token = localStorage.getItem('fim_api_token');
        await apiClient.put('/api/files/status',
            { id: fileId, status: "User Verified" }, // 업데이트할 정보 전송
            { headers: { Authorization: `Bearer ${token}` } }
        );
        console.log(`${fileId} 상태가 업데이트되었습니다.`);

        const newLogs = await fetchLogs(token)
        const updatedLog = newLogs.find(log => log.file === fileId);
        if (updatedLog) {
            setSelectedLog(updatedLog);
        }
    } catch(error) {
        console.error("파일 상태 업데이트에 실패했습니다:", error);
        const errorMsg = error.response?.data?.error || "파일 상태 업데이트에 실패했습니다.";
    alert(errorMsg);
    }
  };

  // 서버에 주기 변경 요청
  const handleChangeInterval = async (fileId, newInterval) => {
    try {
      const token = localStorage.getItem('fim_api_token');
      await apiClient.put('/api/files/interval',
          { id: fileId, interval: newInterval }, // 변경할 정보 전송
          { headers: { Authorization: `Bearer ${token}` } }
      );
      console.log(`${fileId}의 검사 주기가 ${newInterval}로 변경되었습니다.`);

      const newLogs = await fetchLogs(token);
      const updatedLog = newLogs.find(log => log.file_id === fileId);
      if (updatedLog) {
        setSelectedLog(updatedLog);
      }

    } catch(error) {
      console.error("검사 주기 변경에 실패했습니다:", error);
      alert("검사 주기 변경에 실패했습니다.");
    }
  };

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      {/*  Header - 로그인 및 다운로드 버튼에 링크 연결 */}
      <header className="flex justify-between items-center p-4 bg-white shadow rounded-lg">
        <h1 className="text-xl font-bold text-gray-800">File Integrity Monitor</h1>
        <div className="space-x-2">
          {isLoggedIn ? (
            // 로그인 된 경우
            <>
              <Button asChild variant="default">
                <a href="http://127.0.0.1:5000/download_client">⬇️ 클라이언트 다운로드</a>
              </Button>
              <Button variant="outline" onClick={handleLogout}>
                🔓 로그아웃
              </Button>
            </>
          ) : (
            // 로그아웃 된 경우
            <Button asChild variant="outline">
              <a href="http://127.0.0.1:5000/login/google">🔐 로그인</a>
            </Button>
          )}
        </div>
      </header>

      {/* Logs Screen */}
      <Card className="p-6 space-y-4 shadow-md">
        <h2 className="text-xl font-bold">File Change Logs</h2>
        <div className="overflow-x-auto">
          <table className="w-full border rounded-lg text-sm">
            <thead>
              <tr className="bg-gray-100">
                <th className="p-2 text-left">File Name</th>
                <th className="p-2 text-left">Status</th>
                <th className="p-2 text-left">Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, index) => (
                <tr
                  key={index}
                  className={`border-t cursor-pointer hover:bg-gray-100 ${selectedLog?.file === log.file ? 'bg-blue-50' : ''}`}
                  onClick={() => setSelectedLog(log)}
                >
                  <td className="p-2 text-blue-600 font-medium">{log.file}</td>
                  <td className={`p-2 font-semibold ${log.status === "Modified" ? "text-red-500" : log.status === "Unchanged" ? "text-green-600" : "text-yellow-600"}`}>
                    {log.status}
                  </td>
                  <td className="p-2 text-gray-500">{log.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data}>
            <XAxis dataKey="status" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#8884d8" />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* Detailed Log Screen */}
      {selectedLog && (
        <Card className="p-6 space-y-4 shadow-md">
          <h2 className="text-xl font-bold">File Details: {selectedLog.file}</h2>
          <p className="text-gray-600">Status: <span className={`${selectedLog.status === "Modified" ? "text-red-500" : selectedLog.status === "Unchanged" ? "text-green-600" : "text-yellow-600"} font-semibold`}>{selectedLog.status}</span></p>
          <p className="text-gray-600">Last Modified: {selectedLog.time}</p>
          {selectedLog.status !== "Unchanged" && (
            <>
              <p className="text-gray-600 break-all">Old Hash: {selectedLog.oldHash}</p>
              <p className="text-gray-600 break-all">New Hash: {selectedLog.newHash}</p>
            </>
          )}
          <p className="text-gray-600">Check Interval: {selectedLog.checkInterval}</p>

          <div className="flex justify-between items-center pt-4">
            <div className="flex space-x-2">
              <Button variant="outline" size="sm" className="flex items-center" onClick={() => handleUpdate(selectedLog.id)}>
                <RefreshCw className="w-4 h-4 mr-2" /> Update
              </Button>
              <Button variant="outline" size="sm" className="flex items-center" disabled={selectedLog.status !== "Modified"}>
                <Undo className="w-4 h-4 mr-2" /> Rollback
              </Button>
              <Button asChild variant="outline" size="sm" className="flex items-center">
                 <label className="flex items-center cursor-pointer">
                    <Clock className="w-4 h-4 mr-2" />
                    <select
                      value={selectedLog.checkInterval || ''}
                      onChange={(e) => handleChangeInterval(selectedLog.id, e.target.value)}
                      className="bg-transparent outline-none appearance-none"
                    >
                      <option value="1h">1 hour</option>
                      <option value="6h">6 hours</option>
                      <option value="12h">12 hours</option>
                      <option value="24h">24 hours</option>
                    </select>
                 </label>
              </Button>
            </div>
            <Button variant="destructive" size="sm" onClick={() => setShowDeleteConfirm(true)}>
              <Trash className="w-4 h-4 mr-2" /> Delete
            </Button>
          </div>
        </Card>
      )}

      {/* 삭제 확인 모달 */}
      {showDeleteConfirm && selectedLog && (
        <ConfirmationModal
          message={`Are you sure you want to delete ${selectedLog.file}?`}
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}
    </div>
  );
}
