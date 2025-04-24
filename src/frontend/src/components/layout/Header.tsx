import { Link } from 'react-router-dom';
import { Button } from '../ui/button';

type NavItem = {
  label: string;
  path: string;
};

interface HeaderProps {
  currentPath: string;
}

const navItems: NavItem[] = [
  { label: '搜索', path: '/' },
  { label: '站点管理', path: '/sites' },
  { label: '爬取监控', path: '/monitor' }
];

export function Header({ currentPath }: HeaderProps) {
  // 确定当前活动的导航项
  const getActiveItem = (path: string) => {
    // 处理子路由，例如 /sites/xxx/policy 应该激活"站点管理"
    if (currentPath.startsWith('/sites/') && path === '/sites') {
      return true;
    }
    return currentPath === path;
  };

  return (
    <header className="bg-card border-b border-border sticky top-0 z-50">
      <div className="container mx-auto px-4 py-3 flex justify-between items-center">
        <div className="flex items-center">
          <Link to="/" className="text-xl font-bold mr-8">SiteSearch</Link>
          <nav className="hidden md:flex space-x-1">
            {navItems.map((item) => (
              <Button
                key={item.path}
                variant={getActiveItem(item.path) ? "default" : "ghost"}
                className="text-sm"
                asChild
              >
                <Link to={item.path}>{item.label}</Link>
              </Button>
            ))}
          </nav>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm">
            登录
          </Button>
        </div>
      </div>
    </header>
  );
} 