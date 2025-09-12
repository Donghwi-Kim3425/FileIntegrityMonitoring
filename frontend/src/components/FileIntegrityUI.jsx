import { useState } from "react";
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
  const [logs, setLogs] = useState([
    { file: "report.pdf", status: "Modified", time: "2025-03-08 14:32", oldHash: "abc123def456abc123def456abc123def456", newHash: "def456abc123def456abc123def456abc123", checkInterval: "24h" },
    { file: "data.xlsx", status: "Unchanged", time: "2025-03-08 12:20", oldHash: "xyz789", newHash: "xyz789", checkInterval: "24h" },
    { file: "image.png", status: "User Updated", time: "2025-03-09 10:05", oldHash: "ghi123", newHash: "jkl456", checkInterval: "12h" },
  ]);
  const [selectedLog, setSelectedLog] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

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

  const handleDelete = () => {
    if (selectedLog) {
      setLogs((prevLogs) => prevLogs.filter((log) => log.file !== selectedLog.file));
      setSelectedLog(null); // 상세 정보 창 닫기
      setShowDeleteConfirm(false); // 모달 닫기
    }
  };

  const handleUpdate = (file) => {
    setLogs((prevLogs) =>
      prevLogs.map((log) =>
        log.file === file ? { ...log, status: "User Updated", time: new Date().toLocaleString() } : log
      )
    );
  };

  const handleChangeInterval = (file, newInterval) => {
    setLogs((prevLogs) =>
      prevLogs.map((log) =>
        log.file === file ? { ...log, checkInterval: newInterval } : log
      )
    );
     // 선택된 로그 정보도 즉시 업데이트
    if (selectedLog && selectedLog.file === file) {
        setSelectedLog(prev => ({...prev, checkInterval: newInterval}));
    }
  };

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      {/* Header - 로그인 및 클라이언트 다운로드 */}
      <header className="flex justify-between items-center p-4 bg-white shadow rounded-lg">
        <h1 className="text-xl font-bold text-gray-800">File Integrity Monitor</h1>
        <div className="space-x-2">
            <Button variant="outline">
              🔐 로그인
            </Button>
            <Button variant="default">
              ⬇️ 클라이언트 다운로드
            </Button>
        </div>
      </header>

      {/* File Integrity Monitor 박스는 여기에서 제거되었습니다. */}

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
              <Button variant="outline" size="sm" className="flex items-center" onClick={() => handleUpdate(selectedLog.file)}>
                <RefreshCw className="w-4 h-4 mr-2" /> Update
              </Button>
              <Button variant="outline" size="sm" className="flex items-center" disabled={selectedLog.status !== "Modified"}>
                <Undo className="w-4 h-4 mr-2" /> Rollback
              </Button>
              <Button asChild variant="outline" size="sm" className="flex items-center">
                 <label className="flex items-center cursor-pointer">
                    <Clock className="w-4 h-4 mr-2" />
                    <select
                      value={selectedLog.checkInterval}
                      onChange={(e) => handleChangeInterval(selectedLog.file, e.target.value)}
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