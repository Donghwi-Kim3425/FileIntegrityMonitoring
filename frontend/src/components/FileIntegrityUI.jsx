import React, { useState, useEffect } from "react";
import apiClient from "@/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Undo, Trash, RefreshCw, Clock } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

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

function RollbackModal({ backups, onConfirm, onCancel }) {
    const [selectedBackup, setSelectedBackup] = useState(null);

    return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-xl space-y-4 w-2/3 max-w-lg">
        <h2 className="text-lg font-bold">Restore to a Backup</h2>
        {backups.length > 0 ? (
          <div className="max-h-60 overflow-y-auto border rounded-md">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="p-2 text-left">Backup Time</th>
                  <th className="p-2 text-left">Backup Hash</th>
                  <th className="p-2 text-center">Select</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {backups.map((backup) => (
                  <tr key={backup.id}>
                    <td className="p-2">
                      {new Date(backup.created_at).toLocaleString()}
                    </td>
                    <td className="p-2 font-mono text-xs break-all">
                      {backup.backup_hash}
                    </td>
                    <td className="p-2 text-center">
                      <input
                        type="radio"
                        name="backupSelect"
                        value={backup.id}
                        onChange={() => setSelectedBackup(backup.id)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No backup history available.</p>
        )}
        <div className="flex justify-end space-x-2">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="default"
            disabled={!selectedBackup}
            onClick={() => onConfirm(selectedBackup)}
          >
            Restore
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function FileIntegrityUI() {
  const [logs, setLogs] = useState([])
  const [selectedLog, setSelectedLog] = useState(null);
  const [backupHistory, setBackupHistory] = useState([]);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showRollbackModal, setShowRollbackModal] = useState(false);
  const getStatusColorClass = (status) => {
      switch (status) {
          case "Modified":
              return "text-red-500";
          case "Unchanged":
              return "text-green-600";
          case "User Verified":
              return "text-blue-500";
          case "Deleted":
              return "text-orange-500";
          case "Rollback":
              return "text-purple-500";
          default:
              return "text-gray-600";
      }
  }
  const getStatusLabel = (status) => {
      switch (status) {
        case "Rollback":
              return "Restore";
        case "UserUpdated":
              return "User Updated";
        default:
              return status;
      }
    };

  useEffect(() => {
    const token = localStorage.getItem('fim_api_token');
    if (token) {
      setIsLoggedIn(true);
        (async () => {
            await fetchLogs(token);
        })();
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
      sessionStorage.removeItem('fim_api_token');

      setIsLoggedIn(false);
      setLogs([]);

  }
  // 선택된 파일이 바뀔 때마다 백업 기록을 가져오는 함수
  useEffect(() => {
      const fetchBackupHistory = async () => {
          if (selectedLog && selectedLog.file_id) {
              try {
                  const token = localStorage.getItem('fim_api_token');
                  const response = await apiClient.get(`/api/files/${selectedLog.file_id}/backups`, {
                      headers: { Authorization: `Bearer ${token}` }
                  });
                  setBackupHistory(response.data);
              } catch (error) {
                  console.error("백업 기록을 불러오는 데 실패했습니다.", error);
                  setBackupHistory([]); // 실패 시 초기화
              }
          } else {
              setBackupHistory([]); // 선택 해제 시 초기화
          }
      };
      fetchBackupHistory();
  }, [selectedLog]);

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
    if (!selectedLog.file_id) {
    console.error("오류: selectedLog 객체에 file_id가 없습니다.");
    return;
  }
    try {
        const token = localStorage.getItem('fim_api_token');
        await apiClient.delete(`/api/files/${selectedLog.file_id}`, {
            headers: { Authorization: `Bearer ${token}` }
        });

        console.log(`${selectedLog.file} 파일에 대한 모니터링이 성공적으로 중단되었습니다.`);
        setSelectedLog(null);
        setShowDeleteConfirm(false);
        fetchLogs(token); // 삭제 후 목록을 다시 불러옵니다.
    } catch (error) {
        console.error("파일 모니터링 중단에 실패했습니다:", error);
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
          { file: fileId, interval: newInterval }, // 변경할 정보 전송
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

  // 롤백
  const handleRollback = async (backupId) => {
      if (!selectedLog || !selectedLog.file_id || !backupId) {
          alert("롤백할 파일과 백업을 선택해주세요.");
          return;
      }
    if (!confirm(`정말로 이 백업으로 롤백하시겠습니까? 데이터베이스 상태가 변경되며, 백업 파일이 다운로드됩니다.`)) {
        return
    }
    try {
        const token = localStorage.getItem('fim_api_token');
        await apiClient.post(`/api/files/${selectedLog.file_id}/rollback`,
            { backup_id: backupId },
            { headers: { Authorization: `Bearer ${token}` } }
        );
        alert("데이터베이스 상태가 성공적으로 롤백되었습니다. 이제 백업 파일을 다운로드합니다.");

        const downloadUrl = `${apiClient.defaults.baseURL}/api/backups/${backupId}/download`;

        const response = await fetch(downloadUrl, {
            headers: {
                Authorization: `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'File download failed');
        }

        const blob = await response.blob();

        const disposition = response.headers.get('Content-Disposition');
        let filename = selectedLog.file;
        if (disposition && disposition.indexOf('attachment') !== -1) {
            const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
            const matches = filenameRegex.exec(disposition);
            if (matches && matches[1]) {
                filename = matches[1].replace(/['"]/g, '');
            }
        }

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        fetchLogs(token)
    } catch (error) {
        console.error("롤백 요청에 실패했습니다:", error);
        alert("롤백 요청에 실패했습니다.");
    }
  }

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
                  <td className={`p-2 font-semibold ${getStatusColorClass(log.status)}`}>
                    {getStatusLabel(log.status)}
                  </td>
                  <td className="p-2 text-gray-500">{log.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data}>
            <XAxis dataKey="status" tickFormatter={(status) => getStatusLabel(status)} />
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
          <p className="text-gray-600">
            Status: <span className={`${getStatusColorClass(selectedLog.status)} font-semibold`}>
              {getStatusLabel(selectedLog.status)}
            </span>
          </p>
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
              <Button variant="outline" size="sm" className="flex items-center" onClick={() => handleUpdate(selectedLog.file_id)}>
                <RefreshCw className="w-4 h-4 mr-2" /> Update
              </Button>
              <Button variant="outline" size="sm" className="flex items-center" onClick={() => setShowRollbackModal(true)} disabled={backupHistory.length === 0}>
                <Undo className="w-4 h-4 mr-2" /> Restore
              </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="flex items-center">
                      <Clock className="w-4 h-4 mr-2" />
                      Change Interval
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem onSelect={() => handleChangeInterval(selectedLog.file_id, '1h')}>
                      1 hour
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => handleChangeInterval(selectedLog.file_id, '6h')}>
                      6 hours
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => handleChangeInterval(selectedLog.file_id, '12h')}>
                      12 hours
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => handleChangeInterval(selectedLog.file_id, '24h')}>
                      24 hours
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
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

       {/* 롤백 모달 */}
       {showRollbackModal && (
         <RollbackModal
           backups={backupHistory}
           onConfirm={(backupId) => {
             handleRollback(backupId);
             setShowRollbackModal(false);
           }}
           onCancel={() => setShowRollbackModal(false)}
         />
      )}
    </div>
  );
}
