import { ReactNode } from 'react';
import { Header } from './Header';

type LayoutProps = {
  children: ReactNode;
};

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-6">
        {children}
      </main>
      <footer className="bg-card py-6 border-t border-border">
        <div className="container mx-auto px-4 text-center text-muted-foreground text-sm">
          <p>SiteSearch © {new Date().getFullYear()} - 高性能网站搜索引擎</p>
        </div>
      </footer>
    </div>
  );
} 