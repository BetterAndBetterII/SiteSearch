import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { documentApi, siteApi } from '../api';
import { Button } from '../components/ui/button';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '../components/ui/table';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue 
} from '../components/ui/select';
import { Input } from '../components/ui/input';
import { 
  Pagination, 
  PaginationContent, 
  PaginationItem, 
  PaginationLink, 
  PaginationNext, 
  PaginationPrevious 
} from '../components/ui/pagination';
import { 
  ArrowDownIcon, 
  ArrowUpIcon, 
  RefreshCwIcon, 
  SearchIcon, 
  FileIcon, 
  TrashIcon, 
  Clock 
} from 'lucide-react';
import { 
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose
} from '../components/ui/dialog';
import { AlertCircle } from 'lucide-react';

// 简单的Spinner组件
const Spinner = () => (
  <div className="animate-spin h-5 w-5 border-2 border-current border-t-transparent rounded-full" 
       aria-label="正在加载"></div>
);

// 定义文档类型
interface Document {
  id: number;
  url: string;
  title: string;
  description: string;
  mimetype: string;
  status: string;
  last_modified: string;
  content_type: string;
  content_hash: string;
  created_at: string;
  updated_at: string;
  is_indexed: boolean;
  index_operation: string;
  timestamp: string;
  version: number;
}

// 定义站点类型
interface Site {
  id: string;
  name: string;
}

// 定义排序字段类型
type SortField = 'title' | 'url' | 'created_at' | 'updated_at' | 'last_modified';

// 定义MIME类型选项
const MIMETYPE_OPTIONS = [
  { value: 'all', label: '全部类型' },
  { value: 'text/html', label: 'HTML' },
  { value: 'application/json', label: 'JSON' },
  { value: 'text/plain', label: 'Text' },
  { value: 'application/pdf', label: 'PDF' },
  { value: 'image/', label: '图片' }
];

// 定义索引状态选项
const INDEX_STATUS_OPTIONS = [
  { value: 'all', label: '全部状态' },
  { value: 'true', label: '已索引' },
  { value: 'false', label: '未索引' }
];

export function DocumentsPage() {
  const { siteId } = useParams<{ siteId: string }>();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [site, setSite] = useState<Site | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalItems, setTotalItems] = useState(0);
  
  // 排序和筛选状态
  const [sortField, setSortField] = useState<SortField>('updated_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [mimetypeFilter, setMimetypeFilter] = useState('all');
  const [isIndexedFilter, setIsIndexedFilter] = useState('all');
  const [activeFilters, setActiveFilters] = useState<string[]>([]);
  
  // 批量操作状态
  const [selectedDocIds, setSelectedDocIds] = useState<number[]>([]);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [refreshLoading, setRefreshLoading] = useState(false);
  
  // 单个文档操作状态
  const [showDocumentDialog, setShowDocumentDialog] = useState(false);
  const [currentDocument, setCurrentDocument] = useState<Document | null>(null);
  const [documentContent, setDocumentContent] = useState<string>('');
  const [documentContentLoading, setDocumentContentLoading] = useState(false);
  
  // 获取站点信息
  const fetchSiteInfo = async () => {
    if (!siteId) return;
    
    try {
      const response = await siteApi.getSiteDetail(siteId);
      setSite({
        id: response.id,
        name: response.name
      });
    } catch (err) {
      console.error('获取站点信息失败', err);
      setError('无法加载站点信息');
    }
  };
  
  // 获取文档列表
  const fetchDocuments = async () => {
    if (!siteId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      // 构建查询参数
      const params: any = {
        page: currentPage,
        page_size: pageSize,
        sort_by: sortField,
        sort_order: sortOrder
      };
      
      // 添加过滤参数
      if (searchQuery.trim()) {
        params.search = searchQuery.trim();
      }
      
      if (mimetypeFilter && mimetypeFilter !== 'all') {
        params.mimetype = mimetypeFilter;
      }
      
      if (isIndexedFilter && isIndexedFilter !== 'all') {
        params.is_indexed = isIndexedFilter;
      }
      
      const response = await documentApi.getDocuments(siteId, params);
      
      setDocuments(response.results || []);
      setTotalPages(Math.ceil((response.count || 0) / pageSize));
      setTotalItems(response.count || 0);
      
      // 更新激活的过滤条件
      const activeFilters: string[] = [];
      if (searchQuery.trim()) activeFilters.push(`搜索: ${searchQuery.trim()}`);
      if (mimetypeFilter && mimetypeFilter !== 'all') {
        const mimeTypeLabel = MIMETYPE_OPTIONS.find(opt => opt.value === mimetypeFilter)?.label || mimetypeFilter;
        activeFilters.push(`类型: ${mimeTypeLabel}`);
      }
      if (isIndexedFilter && isIndexedFilter !== 'all') {
        const indexLabel = INDEX_STATUS_OPTIONS.find(opt => opt.value === isIndexedFilter)?.label || isIndexedFilter;
        activeFilters.push(`索引状态: ${indexLabel}`);
      }
      setActiveFilters(activeFilters);
      
    } catch (err) {
      console.error('获取文档列表失败', err);
      setError('获取文档数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };
  
  // 获取文档详情
  const fetchDocumentDetail = async (docId: number) => {
    if (!siteId) return;
    
    setDocumentContentLoading(true);
    
    try {
      const response = await documentApi.getDocumentDetail(siteId, docId);
      setCurrentDocument(response);
      setDocumentContent(response.clean_content || response.content || '无内容');
    } catch (err) {
      console.error(`获取文档详情失败: ${docId}`, err);
      setDocumentContent('加载文档内容失败');
    } finally {
      setDocumentContentLoading(false);
    }
  };
  
  // 处理排序变更
  const handleSortChange = (field: SortField) => {
    if (sortField === field) {
      // 如果点击当前排序字段，则切换顺序
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      // 如果点击新字段，设置为该字段降序
      setSortField(field);
      setSortOrder('desc');
    }
  };
  
  // 处理搜索
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1); // 重置到第一页
    fetchDocuments();
  };
  
  // 处理复选框选择
  const handleSelectDocument = (docId: number, checked: boolean) => {
    if (checked) {
      setSelectedDocIds(prev => [...prev, docId]);
    } else {
      setSelectedDocIds(prev => prev.filter(id => id !== docId));
    }
  };
  
  // 处理全选复选框
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedDocIds(documents.map(doc => doc.id));
    } else {
      setSelectedDocIds([]);
    }
  };
  
  // 刷新选中文档
  const refreshSelectedDocuments = async () => {
    if (selectedDocIds.length === 0) return;
    
    setRefreshLoading(true);
    
    try {
      // 使用Promise.all并行处理多个刷新请求
      await Promise.all(
        selectedDocIds.map(docId => documentApi.refreshDocument(siteId!, docId))
      );
      
      // 刷新文档列表
      fetchDocuments();
      // 清除选择
      setSelectedDocIds([]);
    } catch (err) {
      console.error('刷新文档失败', err);
      setError('刷新文档失败，请稍后重试');
    } finally {
      setRefreshLoading(false);
    }
  };
  
  // 删除选中文档
  const deleteSelectedDocuments = async () => {
    if (selectedDocIds.length === 0) return;
    
    setDeleteLoading(true);
    
    try {
      await documentApi.deleteDocuments(siteId!, {
        document_ids: selectedDocIds
      });
      
      // 刷新文档列表
      fetchDocuments();
      // 关闭对话框
      setShowDeleteDialog(false);
      // 清除选择
      setSelectedDocIds([]);
    } catch (err) {
      console.error('删除文档失败', err);
      setError('删除文档失败，请稍后重试');
    } finally {
      setDeleteLoading(false);
    }
  };
  
  // 查看文档详情
  const viewDocumentDetail = (doc: Document) => {
    setCurrentDocument(doc);
    fetchDocumentDetail(doc.id);
    setShowDocumentDialog(true);
  };
  
  // 处理页面切换
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };
  
  // 处理页面大小变更
  const handlePageSizeChange = (value: string) => {
    setPageSize(Number(value));
    setCurrentPage(1); // 重置到第一页
  };
  
  // 处理MIME类型过滤变更
  const handleMimetypeFilterChange = (value: string) => {
    setMimetypeFilter(value);
    setCurrentPage(1); // 重置到第一页
  };
  
  // 处理索引状态过滤变更
  const handleIndexStatusFilterChange = (value: string) => {
    setIsIndexedFilter(value);
    setCurrentPage(1); // 重置到第一页
  };
  
  // 清除所有过滤条件
  const clearAllFilters = () => {
    setSearchQuery('');
    setMimetypeFilter('all');
    setIsIndexedFilter('all');
    setCurrentPage(1); // 重置到第一页
  };
  
  // 首次加载和依赖项变更时获取数据
  useEffect(() => {
    if (siteId) {
      fetchSiteInfo();
    }
  }, [siteId]);
  
  useEffect(() => {
    if (siteId) {
      fetchDocuments();
    }
  }, [siteId, currentPage, pageSize, sortField, sortOrder, mimetypeFilter, isIndexedFilter]);
  
  // 格式化日期时间显示
  const formatDateTime = (dateTimeStr: string | null) => {
    if (!dateTimeStr) return '未知';
    
    try {
      return new Date(dateTimeStr).toLocaleString();
    } catch (e) {
      return dateTimeStr;
    }
  };
  
  // 截断URL显示
  const truncateUrl = (url: string, maxLength: number = 50) => {
    if (url.length <= maxLength) return url;
    
    const start = url.substring(0, maxLength / 2);
    const end = url.substring(url.length - maxLength / 2);
    
    return `${start}...${end}`;
  };
  
  // 获取文档类型显示
  const getContentTypeDisplay = (contentType: string) => {
    if (!contentType) return '未知';
    
    if (contentType.includes('html')) return 'HTML';
    if (contentType.includes('text/plain')) return '文本';
    if (contentType.includes('json')) return 'JSON';
    if (contentType.includes('pdf')) return 'PDF';
    if (contentType.includes('image/')) return '图片';
    if (contentType.includes('application/')) return '应用';
    
    return contentType.split('/')[1] || contentType;
  };
  
  if (loading && documents.length === 0) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner />
        <span className="ml-2">加载文档数据...</span>
      </div>
    );
  }
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">文档管理</h1>
          {site && (
            <p className="text-muted-foreground">站点: {site.name}</p>
          )}
        </div>
        <div className="flex space-x-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => fetchDocuments()}
            disabled={loading}
          >
            {loading ? <Spinner /> : <RefreshCwIcon className="h-4 w-4 mr-1" />}
            刷新
          </Button>
          <Link to={`/sites/${siteId}/policy`}>
            <Button variant="outline" size="sm">
              爬取策略
            </Button>
          </Link>
          <Link to="/sites">
            <Button variant="ghost" size="sm">
              返回站点
            </Button>
          </Link>
        </div>
      </div>
      
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md mb-4">
          <div className="flex items-center">
            <AlertCircle className="h-4 w-4 mr-2" />
            <p>{error}</p>
          </div>
        </div>
      )}
      
      {/* 搜索和批量操作工具栏 */}
      <div className="flex flex-col gap-4 mb-4">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <form onSubmit={handleSearch} className="flex w-full md:w-auto">
            <Input
              type="text"
              placeholder="搜索文档..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="rounded-r-none"
            />
            <Button 
              type="submit" 
              variant="default" 
              className="rounded-l-none"
              disabled={loading}
            >
              <SearchIcon className="h-4 w-4" />
            </Button>
          </form>
          
          <div className="flex space-x-2 w-full md:w-auto justify-end">
            <Button 
              variant="outline" 
              size="sm"
              onClick={refreshSelectedDocuments}
              disabled={selectedDocIds.length === 0 || refreshLoading}
            >
              {refreshLoading ? <Spinner /> : <RefreshCwIcon className="h-4 w-4 mr-1" />}
              刷新 {selectedDocIds.length > 0 ? `(${selectedDocIds.length})` : ''}
            </Button>
            <Button 
              variant="outline" 
              size="sm"
              className="text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600"
              onClick={() => setShowDeleteDialog(true)}
              disabled={selectedDocIds.length === 0}
            >
              <TrashIcon className="h-4 w-4 mr-1" />
              删除 {selectedDocIds.length > 0 ? `(${selectedDocIds.length})` : ''}
            </Button>
          </div>
        </div>
        
        {/* 过滤器行 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-sm font-medium mb-1 block">文档类型</label>
            <Select
              value={mimetypeFilter}
              onValueChange={handleMimetypeFilterChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="全部类型" />
              </SelectTrigger>
              <SelectContent>
                {MIMETYPE_OPTIONS.map(option => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <div>
            <label className="text-sm font-medium mb-1 block">索引状态</label>
            <Select
              value={isIndexedFilter}
              onValueChange={handleIndexStatusFilterChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                {INDEX_STATUS_OPTIONS.map(option => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <div className="flex items-end">
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto"
              onClick={clearAllFilters}
              disabled={!searchQuery && mimetypeFilter === 'all' && isIndexedFilter === 'all'}
            >
              清除所有过滤器
            </Button>
          </div>
        </div>
        
        {/* 活跃过滤器和结果计数 */}
        <div className="flex justify-between items-center pt-2">
          <div className="text-sm text-muted-foreground">
            共找到 <span className="font-medium">{totalItems}</span> 个文档
            {totalItems > 0 && <span> (显示第 {(currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, totalItems)} 个)</span>}
          </div>
          
          {activeFilters.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {activeFilters.map((filter, index) => (
                <div key={index} className="bg-muted text-xs px-2 py-1 rounded-md">
                  {filter}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      
      {/* 文档表格 */}
      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">
                <input
                  type="checkbox"
                  checked={selectedDocIds.length === documents.length && documents.length > 0}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
              </TableHead>
              <TableHead 
                className="cursor-pointer"
                onClick={() => handleSortChange('title')}
              >
                标题
                {sortField === 'title' && (
                  sortOrder === 'asc' ? 
                  <ArrowUpIcon className="inline-block h-4 w-4 ml-1" /> : 
                  <ArrowDownIcon className="inline-block h-4 w-4 ml-1" />
                )}
              </TableHead>
              <TableHead 
                className="cursor-pointer"
                onClick={() => handleSortChange('url')}
              >
                URL
                {sortField === 'url' && (
                  sortOrder === 'asc' ? 
                  <ArrowUpIcon className="inline-block h-4 w-4 ml-1" /> : 
                  <ArrowDownIcon className="inline-block h-4 w-4 ml-1" />
                )}
              </TableHead>
              <TableHead>类型</TableHead>
              <TableHead>索引状态</TableHead>
              <TableHead 
                className="cursor-pointer"
                onClick={() => handleSortChange('updated_at')}
              >
                更新时间
                {sortField === 'updated_at' && (
                  sortOrder === 'asc' ? 
                  <ArrowUpIcon className="inline-block h-4 w-4 ml-1" /> : 
                  <ArrowDownIcon className="inline-block h-4 w-4 ml-1" />
                )}
              </TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  {loading ? (
                    <div className="flex justify-center items-center">
                      <Spinner />
                      <span className="ml-2">加载文档数据...</span>
                    </div>
                  ) : (
                    <div className="text-muted-foreground">
                      <FileIcon className="w-12 h-12 mx-auto mb-2 text-muted-foreground/50" />
                      <p>没有找到文档</p>
                      {activeFilters.length > 0 && (
                        <p className="text-sm mt-1">
                          请尝试清除或修改过滤条件
                        </p>
                      )}
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              documents.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selectedDocIds.includes(doc.id)}
                      onChange={(e) => handleSelectDocument(doc.id, e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    <button
                      onClick={() => viewDocumentDetail(doc)}
                      className="text-left text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {doc.title || '无标题'}
                    </button>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    <a 
                      href={doc.url} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {truncateUrl(doc.url)}
                    </a>
                  </TableCell>
                  <TableCell>
                    {getContentTypeDisplay(doc.mimetype)}
                  </TableCell>
                  <TableCell>
                    {doc.is_indexed ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        已索引
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                        未索引
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    {formatDateTime(doc.updated_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex space-x-1">
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => viewDocumentDetail(doc)}
                        title="查看"
                      >
                        <FileIcon className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => {
                          documentApi.refreshDocument(siteId!, doc.id)
                            .then(() => fetchDocuments())
                            .catch(err => {
                              console.error(`刷新文档失败: ${doc.id}`, err);
                              setError('刷新文档失败');
                            });
                        }}
                        title="刷新"
                      >
                        <RefreshCwIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      
      {/* 分页控制 */}
      <div className="flex justify-between items-center mt-4">
        <div className="flex items-center space-x-2">
          <span className="text-sm text-muted-foreground">每页显示:</span>
          <Select
            value={pageSize.toString()}
            onValueChange={handlePageSizeChange}
          >
            <SelectTrigger className="w-16 h-8">
              <SelectValue placeholder="10" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="20">20</SelectItem>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-sm text-muted-foreground ml-4">
            总计 {totalItems} 项
          </span>
        </div>
        
        {totalPages > 1 && (
          <Pagination>
            <PaginationContent>
              {currentPage > 1 && (
                <PaginationItem>
                  <PaginationPrevious 
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={loading} 
                  />
                </PaginationItem>
              )}
              
              {[...Array(totalPages)].map((_, i) => {
                const page = i + 1;
                
                // 只显示当前页码附近的页码链接
                if (
                  page === 1 || 
                  page === totalPages || 
                  (page >= currentPage - 1 && page <= currentPage + 1)
                ) {
                  return (
                    <PaginationItem key={page}>
                      <PaginationLink
                        onClick={() => handlePageChange(page)}
                        isActive={page === currentPage}
                        disabled={loading}
                      >
                        {page}
                      </PaginationLink>
                    </PaginationItem>
                  );
                }
                
                // 显示省略号
                if (
                  (page === 2 && currentPage > 3) || 
                  (page === totalPages - 1 && currentPage < totalPages - 2)
                ) {
                  return (
                    <PaginationItem key={page}>
                      <span className="px-4">...</span>
                    </PaginationItem>
                  );
                }
                
                return null;
              })}
              
              {currentPage < totalPages && (
                <PaginationItem>
                  <PaginationNext 
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={loading}
                  />
                </PaginationItem>
              )}
            </PaginationContent>
          </Pagination>
        )}
      </div>
      
      {/* 删除确认对话框 */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              您确定要删除选中的 {selectedDocIds.length} 个文档吗？此操作无法撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:justify-end">
            <DialogClose asChild>
              <Button 
                type="button" 
                variant="secondary"
                disabled={deleteLoading}
              >
                取消
              </Button>
            </DialogClose>
            <Button 
              type="button" 
              variant="destructive"
              onClick={deleteSelectedDocuments}
              disabled={deleteLoading}
            >
              {deleteLoading ? <Spinner /> : '确认删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* 文档详情对话框 */}
      <Dialog open={showDocumentDialog} onOpenChange={setShowDocumentDialog}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle>{currentDocument?.title || '文档详情'}</DialogTitle>
            <DialogDescription>
              <a 
                href={currentDocument?.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {currentDocument?.url}
              </a>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2 text-sm text-muted-foreground">
                <div className="flex items-center">
                  <Clock className="h-4 w-4 mr-1" />
                  更新于: {formatDateTime(currentDocument?.updated_at || null)}
                </div>
                <div>
                  类型: {getContentTypeDisplay(currentDocument?.mimetype || '')}
                </div>
                <div>
                  索引状态: {
                    currentDocument?.is_indexed 
                      ? <span className="text-green-600">已索引</span> 
                      : <span className="text-amber-600">未索引</span>
                  }
                </div>
                <div>
                  版本: {currentDocument?.version || 1} 
                  {currentDocument?.index_operation && (
                    <span className="ml-2">
                      ({
                        currentDocument.index_operation === 'new' ? '新增' : 
                        currentDocument.index_operation === 'edit' ? '更新' : 
                        currentDocument.index_operation === 'delete' ? '删除' : 
                        currentDocument.index_operation
                      })
                    </span>
                  )}
                </div>
              </div>
              {currentDocument?.description && (
                <div className="mt-2 p-2 bg-muted/30 rounded text-sm">
                  <p className="font-medium mb-1">描述:</p>
                  {currentDocument.description}
                </div>
              )}
            </DialogDescription>
          </DialogHeader>
          
          <div className="mt-4 border rounded-md p-4 bg-muted/50">
            {documentContentLoading ? (
              <div className="flex justify-center items-center py-8">
                <Spinner />
                <span className="ml-2">加载文档内容...</span>
              </div>
            ) : (
              <pre className="whitespace-pre-wrap text-sm">
                {documentContent}
              </pre>
            )}
          </div>
          
          <DialogFooter>
            <Button 
              type="button" 
              variant="secondary"
              onClick={() => setShowDocumentDialog(false)}
            >
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
} 