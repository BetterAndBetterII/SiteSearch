import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { crawlPolicyApi } from '../api';

interface CrawlPolicyFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  siteId: string;
  editPolicy?: {
    id: number;
    name: string;
    description: string;
    start_urls: string[];
    url_patterns: string[];
    exclude_patterns: string[];
    max_depth: number;
    max_urls: number;
    crawler_type: string;
  };
}

export function CrawlPolicyFormModal({ 
  isOpen, 
  onClose, 
  onSuccess, 
  siteId,
  editPolicy 
}: CrawlPolicyFormModalProps) {
  // 如果模态框不是打开状态，不渲染任何内容
  if (!isOpen) return null;
  
  const isEditing = !!editPolicy;
  
  const [formData, setFormData] = useState({
    name: editPolicy?.name || '',
    description: editPolicy?.description || '',
    start_urls: editPolicy?.start_urls ? editPolicy.start_urls.join('\n') : '',
    url_patterns: editPolicy?.url_patterns ? editPolicy.url_patterns.join('\n') : '',
    exclude_patterns: editPolicy?.exclude_patterns ? editPolicy.exclude_patterns.join('\n') : '',
    max_depth: editPolicy?.max_depth || 3,
    max_urls: editPolicy?.max_urls || 1000,
    crawler_type: editPolicy?.crawler_type || 'httpx'
  });
  
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    // 对于数值类型的字段，转换为数字
    if (name === 'max_depth' || name === 'max_urls') {
      setFormData(prev => ({ ...prev, [name]: parseInt(value) || 0 }));
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
    
    if (!formData.start_urls.trim()) {
      setError('起始URL不能为空');
      return;
    }
    
    // 将多行文本字段转换为数组
    const processedData = {
      name: formData.name,
      description: formData.description,
      start_urls: formData.start_urls.split('\n').filter(url => url.trim()),
      url_patterns: formData.url_patterns.split('\n').filter(pattern => pattern.trim()),
      exclude_patterns: formData.exclude_patterns.split('\n').filter(pattern => pattern.trim()),
      max_depth: formData.max_depth,
      max_urls: formData.max_urls,
      crawler_type: formData.crawler_type,
    };
    
    try {
      setLoading(true);
      
      if (isEditing && editPolicy) {
        // 更新爬取策略
        await crawlPolicyApi.updateCrawlPolicy(siteId, editPolicy.id, processedData);
      } else {
        // 创建新爬取策略
        await crawlPolicyApi.createCrawlPolicy(siteId, processedData);
      }
      
      // 成功后关闭模态框并刷新列表
      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('保存爬取策略失败', err);
      setError(err.message || '保存爬取策略失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">{isEditing ? '编辑' : '添加'}爬取策略</h2>
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
                placeholder="例如: 主站爬取策略"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">爬虫类型</label>
              <select
                name="crawler_type"
                value={formData.crawler_type}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md p-2"
              >
                <option value="httpx">httpx (默认)</option>
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
              placeholder="爬取策略描述（可选）"
              rows={2}
            />
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">起始URL *</label>
            <textarea
              name="start_urls"
              value={formData.start_urls}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-md p-2 font-mono text-sm"
              placeholder="每行一个URL，例如：&#10;https://example.com&#10;https://example.com/about"
              rows={3}
              required
            />
            <p className="text-xs text-gray-500 mt-1">每行一个URL</p>
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
              <p className="text-xs text-gray-500 mt-1">仅爬取匹配这些模式的URL，每行一个正则表达式</p>
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
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium mb-1">最大爬取深度</label>
              <input
                type="number"
                name="max_depth"
                value={formData.max_depth}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md p-2"
                min="1"
                max="10"
              />
              <p className="text-xs text-gray-500 mt-1">从起始URL计算的最大链接深度</p>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">最大URL数量</label>
              <input
                type="number"
                name="max_urls"
                value={formData.max_urls}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md p-2"
                min="1"
                max="10000"
              />
              <p className="text-xs text-gray-500 mt-1">爬取的最大URL数量</p>
            </div>
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
              {loading ? '保存中...' : isEditing ? '保存更改' : '创建策略'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
} 