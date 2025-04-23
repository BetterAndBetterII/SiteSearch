import { useState } from 'react';
import { Button } from '../ui/button';

type NavItem = {
  label: string;
  path: string;
};

const navItems: NavItem[] = [
  { label: '搜索', path: '/' },
  { label: '站点管理', path: '/sites' },
  { label: '爬取监控', path: '/monitor' }
];

export function Header() {
  const [activeItem, setActiveItem] = useState('/');

  return (
    <header className="bg-card border-b border-border sticky top-0 z-50">
      <div className="container mx-auto px-4 py-3 flex justify-between items-center">
        <div className="flex items-center">
          <h1 className="text-xl font-bold mr-8">SiteSearch</h1>
          <nav className="hidden md:flex space-x-1">
            {navItems.map((item) => (
              <Button
                key={item.path}
                variant={activeItem === item.path ? "default" : "ghost"}
                className="text-sm"
                onClick={() => setActiveItem(item.path)}
              >
                {item.label}
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