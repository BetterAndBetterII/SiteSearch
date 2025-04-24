import { useState } from 'react';
import { Button } from './ui/button';
import { siteApi } from '../api';

// 站点添加模态框组件接口
interface SiteAddModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function SiteAddModal({ isOpen, onClose, onSuccess }: SiteAddModalProps) {
  // 如果模态框不是打开状态，不渲染任何内容
  if (!isOpen) return null;
  
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    base_url: '',
    description: ''
  });
  
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    // 验证表单数据
    if (!formData.id.trim()) {
      setError('站点ID不能为空');
      return;
    }
    
    if (!formData.name.trim()) {
      setError('站点名称不能为空');
      return;
    }
    
    if (!formData.base_url.trim()) {
      setError('基础URL不能为空');
      return;
    }
    
    try {
      setLoading(true);
      
      // 使用API创建站点
      await siteApi.createSite(formData);
      
      // 成功后关闭模态框并刷新站点列表
      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('创建站点失败', err);
      setError(err.message || '创建站点失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">添加新站点</h2>
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
        
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">站点ID *</label>
            <input
              type="text"
              name="id"
              value={formData.id}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-md p-2"
              placeholder="例如: company-website"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              唯一标识符，只能包含字母、数字、连字符和下划线
            </p>
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">站点名称 *</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-md p-2"
              placeholder="例如: 公司官网"
              required
            />
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">基础URL *</label>
            <input
              type="url"
              name="base_url"
              value={formData.base_url}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-md p-2"
              placeholder="例如: https://example.com"
              required
            />
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">描述</label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-md p-2"
              placeholder="站点描述（可选）"
              rows={3}
            />
          </div>
          
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
            >
              取消
            </Button>
            <Button
              type="submit"
              disabled={loading}
            >
              {loading ? '创建中...' : '创建站点'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
} 