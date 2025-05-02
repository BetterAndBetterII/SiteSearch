import { useState } from 'react';
import { Button } from './ui/button';
import { refreshApi } from '../api';

interface RefreshPolicyFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  siteId: string;
  editPolicy?: {
    id: number;
    name: string;
    description: string;
    strategy: string;
    refresh_interval_days: number;
    url_patterns: string[];
    exclude_patterns: string[];
    max_age_days: number;
    priority_patterns: string[];
    enabled: boolean;
    last_refresh?: string | null;
    next_refresh?: string | null;
  };
}

export function RefreshPolicyFormModal({ 
  isOpen, 
  onClose, 
  onSuccess, 
  siteId,
  editPolicy 
}: RefreshPolicyFormModalProps) {
  // 如果模态框不是打开状态，不渲染任何内容
  if (!isOpen) return null;
  
  const isEditing = !!editPolicy;
  
  const [formData, setFormData] = useState({
    name: editPolicy?.name || '默认刷新策略',
    description: editPolicy?.description || '',
    strategy: editPolicy?.strategy || 'incremental',
    refresh_interval_days: editPolicy?.refresh_interval_days || 7,
    url_patterns: editPolicy?.url_patterns ? editPolicy.url_patterns.join('\n') : '',
    exclude_patterns: editPolicy?.exclude_patterns ? editPolicy.exclude_patterns.join('\n') : '',
    max_age_days: editPolicy?.max_age_days || 30,
    priority_patterns: editPolicy?.priority_patterns ? editPolicy.priority_patterns.join('\n') : '',
    enabled: editPolicy?.enabled !== undefined ? editPolicy.enabled : true,
    advanced_config: {}
  });
  
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    // 对于数值类型的字段，转换为数字
    if (name === 'refresh_interval_days' || name === 'max_age_days') {
      setFormData(prev => ({ ...prev, [name]: parseInt(value) || 0 }));
    } else if (name === 'enabled') {
      setFormData(prev => ({ ...prev, [name]: (e.target as HTMLInputElement).checked }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    // 验证表单数据
    if (!formData.name.trim()) {
      setError('策略名称不能为空');
      return;
    }
    
    // 将多行文本字段转换为数组
    const processedData = {
      name: formData.name,
      description: formData.description,
      strategy: formData.strategy,
      refresh_interval_days: formData.refresh_interval_days,
      url_patterns: formData.url_patterns.split('\n').filter(pattern => pattern.trim()),
      exclude_patterns: formData.exclude_patterns.split('\n').filter(pattern => pattern.trim()),
      max_age_days: formData.max_age_days,
      priority_patterns: formData.priority_patterns.split('\n').filter(pattern => pattern.trim()),
      enabled: formData.enabled,
      advanced_config: {}
    };
    
    try {
      setLoading(true);
      
      if (isEditing) {
        // 更新刷新策略，使用PUT方法
        await refreshApi.updateRefreshPolicy(siteId, processedData);
      } else {
        // 创建新刷新策略，使用POST方法
        await refreshApi.createRefreshPolicy(siteId, processedData);
      }
      
      // 成功后关闭模态框并刷新数据
      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('保存刷新策略失败', err);
      setError(err.message || '保存刷新策略失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">{isEditing ? '编辑' : '添加'}刷新策略</h2>
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">策略名称 *</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md p-2"
                placeholder="例如: 每周刷新策略"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">刷新策略类型</label>
              <select
                name="strategy"
                value={formData.strategy}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md p-2"
              >
                <option value="incremental">增量刷新 (默认)</option>
                <option value="all">全量刷新</option>
                <option value="selective">选择性刷新</option>
              </select>
            </div>
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">描述</label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-md p-2"
              placeholder="刷新策略描述（可选）"
              rows={2}
            />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">刷新间隔（天）</label>
              <input
                type="number"
                name="refresh_interval_days"
                value={formData.refresh_interval_days}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md p-2"
                min="1"
                max="365"
              />
              <p className="text-xs text-gray-500 mt-1">内容刷新的间隔天数</p>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">内容最大有效期（天）</label>
              <input
                type="number"
                name="max_age_days"
                value={formData.max_age_days}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md p-2"
                min="1"
                max="365"
              />
              <p className="text-xs text-gray-500 mt-1">超过该天数的内容将被标记为过期</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">URL匹配模式</label>
              <textarea
                name="url_patterns"
                value={formData.url_patterns}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md p-2 font-mono text-sm"
                placeholder="每行一个正则表达式，例如：&#10;https://example\\.com/.*&#10;https://blog\\.example\\.com/.*"
                rows={3}
              />
              <p className="text-xs text-gray-500 mt-1">仅刷新匹配这些模式的URL，每行一个正则表达式</p>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">排除URL模式</label>
              <textarea
                name="exclude_patterns"
                value={formData.exclude_patterns}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md p-2 font-mono text-sm"
                placeholder="每行一个正则表达式，例如：&#10;.*\\.pdf$&#10;.*\\?sort=.*"
                rows={3}
              />
              <p className="text-xs text-gray-500 mt-1">排除匹配这些模式的URL，每行一个正则表达式</p>
            </div>
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">优先刷新URL模式</label>
            <textarea
              name="priority_patterns"
              value={formData.priority_patterns}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-md p-2 font-mono text-sm"
              placeholder="每行一个正则表达式，例如：&#10;https://example\\.com/important/.*&#10;https://example\\.com/news/.*"
              rows={3}
            />
            <p className="text-xs text-gray-500 mt-1">这些URL将被优先刷新，每行一个正则表达式</p>
          </div>
          
          <div className="mb-6">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                name="enabled"
                checked={formData.enabled}
                onChange={handleChange}
                className="rounded"
              />
              <span className="text-sm font-medium">启用此刷新策略</span>
            </label>
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
              {loading ? '保存中...' : isEditing ? '更新策略' : '创建策略'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
} 