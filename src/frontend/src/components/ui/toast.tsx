import React, { createContext, useContext, useState, useEffect } from 'react';

// Toast变体类型
type ToastVariant = 'default' | 'success' | 'error' | 'warning' | 'info';

// Toast属性接口
interface ToastProps {
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

// Toast事件接口
type ToastEvent = ToastProps & { id: number };

// 创建一个全局事件处理系统
const toastEventHandler = {
  listeners: new Set<(toast: ToastEvent) => void>(),
  addListener(listener: (toast: ToastEvent) => void) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  },
  emit(toast: ToastEvent) {
    this.listeners.forEach(listener => listener(toast));
  }
};

// Toast上下文接口
interface ToastContextType {
  toast: (props: ToastProps) => void;
}

// 创建Toast上下文
const ToastContext = createContext<ToastContextType | undefined>(undefined);

// Toast项组件
export const Toast: React.FC<ToastProps & { onClose: () => void }> = ({ 
  title, 
  description, 
  variant = 'default',
  onClose 
}) => {
  // 根据变体返回适当的样式
  const getVariantClasses = (variant: ToastVariant): string => {
    switch (variant) {
      case 'success':
        return 'bg-green-50 border-green-200 text-green-800';
      case 'error':
        return 'bg-red-50 border-red-200 text-red-800';
      case 'warning':
        return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      case 'info':
        return 'bg-blue-50 border-blue-200 text-blue-800';
      default:
        return 'bg-white border-gray-200 text-gray-800';
    }
  };

  return (
    <div 
      className={`${getVariantClasses(variant)} border rounded-md p-4 shadow-md flex justify-between items-start`}
      role="alert"
    >
      <div>
        <h3 className="font-medium text-sm">{title}</h3>
        {description && <p className="text-xs mt-1">{description}</p>}
      </div>
      <button 
        onClick={onClose}
        className="text-gray-400 hover:text-gray-600"
        aria-label="关闭"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
};

// Toast提供者组件
export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<(ToastProps & { id: number })[]>([]);
  
  // 订阅全局Toast事件
  useEffect(() => {
    const unsubscribe = toastEventHandler.addListener((toast) => {
      setToasts(prev => [...prev, toast]);
      
      // 设置自动关闭
      if (toast.duration !== 0) {
        setTimeout(() => {
          removeToast(toast.id);
        }, toast.duration || 3000);
      }
    });
    
    return () => {
      unsubscribe();
    };
  }, []);
  
  // 添加新的Toast
  const addToast = (props: ToastProps) => {
    const id = Date.now();
    const newToast = { ...props, id };
    toastEventHandler.emit(newToast);
  };
  
  // 移除Toast
  const removeToast = (id: number) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };
  
  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      
      {/* Toast容器 */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-xs">
        {toasts.map(toast => (
          <Toast 
            key={toast.id}
            title={toast.title}
            description={toast.description}
            variant={toast.variant}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

// 自定义Hook，用于使用Toast
export const useToast = () => {
  const context = useContext(ToastContext);
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

// 直接导出toast函数，方便使用
export const toast = (props: ToastProps) => {
  const id = Date.now();
  const newToast = { ...props, id };
  toastEventHandler.emit(newToast);
}; 