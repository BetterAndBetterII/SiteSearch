import { useState } from 'react';
import { Button } from './ui/button';
import { siteApi } from '../api';

// 站点添加模态框组件接口
interface SiteDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  siteId: string;
}

export function SiteDeleteModal({ isOpen, onClose, onSuccess, siteId }: SiteDeleteModalProps) {
  // 如果模态框不是打开状态，不渲染任何内容
  if (!isOpen) return null;

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  
  const deleteSite = async (siteId: string) => {
    try {
      setLoading(true);
      await siteApi.deleteSite(siteId);
      onSuccess();
    } catch (err) {
      console.error(`删除站点 ${siteId} 失败`, err);
      setError('删除站点失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">删除站点</h2>
          <button 
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-md mb-4">
            {error}
          </div>
        )}
        <div className="text-sm mb-4">
            确定要删除站点吗？删除后站点将无法恢复。
        </div>
        <div className="flex justify-end gap-2">
          <Button 
            variant="destructive" 
            onClick={() => deleteSite(siteId)}
            disabled={loading}
          >
            {loading ? '删除中...' : '删除'}
          </Button>
          <Button 
            variant="outline" 
            onClick={onClose}
            disabled={loading}
          >取消</Button>
        </div>
      </div>
    </div>
  );
} 